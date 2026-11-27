# -*- coding: utf-8 -*-
"""
统一 LLM 服务层（AI 搜索流程重设计 · 阶段1）

把散落在 ai_search / ai_chat / deepseek_match / ai_push 里的 DeepSeek 裸 httpx 调用
合并为统一入口，提供：
- achat / chat            文本补全（chat 供 ThreadPoolExecutor 场景用）
- achat_json / chat_json  结构化 JSON 补全（自动剥围栏、正则兜底、expect 校验）

硬约束：
- 重试仅针对 timeout / 429 / 5xx；其余错误立即抛 LLMError。
- JSON 解析失败按 "只输出 JSON" 追加重试 1 次。
- 每次调用打 usage 日志：[llm] tag=... in=.. out=.. ms=..
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 事件循环复用：chat() 在线程里跑 asyncio.run，避免与已运行循环冲突
_LOOP_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm")


class LLMError(RuntimeError):
    """LLM 调用失败。kind: config | auth | http | timeout | parse"""

    def __init__(self, message: str, kind: str = "http", status: int = 0):
        super().__init__(message)
        self.kind = kind
        self.status = status


@dataclass
class LLMResult:
    content: str = ""
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    latency_ms: int = 0
    model: str = ""


# 可重试的 HTTP 状态码
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
_OBJ_RE = re.compile(r"\{.*\}", re.S)
_ARR_RE = re.compile(r"\[.*\]", re.S)


def _build_payload(messages, *, temperature, max_tokens, tools, json_mode, tag) -> dict:
    payload: dict[str, Any] = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if tools:
        payload["tools"] = tools
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


async def achat(
    messages: list,
    *,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    timeout: float = 60.0,
    tools: Optional[list] = None,
    json_mode: bool = False,
    retries: Optional[int] = None,
    tag: str = "",
) -> LLMResult:
    """异步 chat completion。失败抛 LLMError。"""
    if not settings.deepseek_api_key:
        raise LLMError("DEEPSEEK_API_KEY 未配置", kind="config")

    if retries is None:
        retries = settings.llm_max_retries

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(
        messages, temperature=temperature, max_tokens=max_tokens,
        tools=tools, json_mode=json_mode, tag=tag,
    )

    last_err: Optional[LLMError] = None
    for attempt in range(retries + 1):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(url, headers=headers, json=payload)
            latency_ms = int((time.monotonic() - t0) * 1000)

            if r.status_code in (401, 403):
                raise LLMError(f"DeepSeek 鉴权失败 HTTP {r.status_code}", kind="auth",
                               status=r.status_code)
            if r.status_code in _RETRYABLE_STATUS:
                last_err = LLMError(f"DeepSeek HTTP {r.status_code}: {r.text[:200]}",
                                    kind="http", status=r.status_code)
                if attempt < retries:
                    logger.warning("[llm] tag=%s 可重试状态 %s，第 %d 次重试",
                                   tag, r.status_code, attempt + 1)
                    continue
                raise last_err
            if r.status_code >= 400:
                raise LLMError(f"DeepSeek HTTP {r.status_code}: {r.text[:200]}",
                               kind="http", status=r.status_code)

            data = r.json()
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
            usage = data.get("usage") or {}
            logger.info("[llm] tag=%s in=%s out=%s ms=%d",
                        tag, usage.get("prompt_tokens", "?"),
                        usage.get("completion_tokens", "?"), latency_ms)
            return LLMResult(
                content=content,
                tool_calls=tool_calls,
                usage=usage,
                latency_ms=latency_ms,
                model=data.get("model", settings.deepseek_model),
            )

        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = LLMError(f"DeepSeek 超时/网络错误: {e}", kind="timeout")
            if attempt < retries:
                logger.warning("[llm] tag=%s %s，第 %d 次重试", tag, e, attempt + 1)
                continue
            raise last_err from e

    raise last_err or LLMError("LLM 调用失败", kind="http")


def chat(messages: list, *, timeout: float = 60.0, tag: str = "", **kw) -> LLMResult:
    """同步封装：在独立事件循环中执行 achat，供线程池/同步代码调用。"""

    def _run() -> LLMResult:
        return asyncio.run(achat(messages, timeout=timeout, tag=tag, **kw))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run()
    # 已有运行中的事件循环 → 放到线程里跑
    return _LOOP_POOL.submit(_run).result(timeout=timeout + 30)


def _extract_json(text: str, expect: str) -> Any:
    """剥围栏 → json.loads → 正则兜底，按 expect 校验类型。"""
    if not text or not text.strip():
        raise LLMError("LLM 返回空内容", kind="parse")

    candidates = []
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text.strip())

    # 正则兜底：取最长大括号/方括号片段
    for rx in (_ARR_RE, _OBJ_RE):
        m = rx.search(text)
        if m:
            candidates.append(m.group(0))

    for cand in candidates:
        try:
            val = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if expect == "object" and isinstance(val, dict):
            return val
        if expect == "array":
            # DeepSeek json_object 模式只保证对象：包成 {"results":[...]} 时自动解包
            if isinstance(val, list):
                return val
            if isinstance(val, dict) and isinstance(val.get("results"), list):
                return val["results"]
        if expect == "any":
            return val
    raise LLMError(f"LLM 输出非合法 JSON（expect={expect}）", kind="parse")


async def achat_json(
    messages: list,
    *,
    expect: str = "object",
    json_mode: bool = True,
    retries: Optional[int] = None,
    tag: str = "",
    **kw,
) -> Any:
    """异步 JSON 补全，返回解析后的 dict / list。
    解析失败时追加"只输出 JSON"重试 1 次。"""
    result = await achat(messages, json_mode=json_mode, retries=retries, tag=tag, **kw)
    try:
        return _extract_json(result.content, expect)
    except LLMError:
        logger.warning("[llm] tag=%s JSON 解析失败，追加严格指令重试", tag)
        retry_messages = list(messages) + [
            {"role": "assistant", "content": result.content},
            {"role": "user", "content": "只输出合法 JSON，不要任何解释、markdown 围栏或前后文字。"},
        ]
        result2 = await achat(retry_messages, json_mode=json_mode,
                              retries=0, tag=f"{tag}+jsonretry", **kw)
        return _extract_json(result2.content, expect)


def chat_json(messages: list, *, expect: str = "object",
              tag: str = "", **kw) -> Any:
    """同步 JSON 封装，语义同 achat_json。"""
    timeout = kw.get("timeout", 60.0)

    def _run() -> Any:
        return asyncio.run(achat_json(messages, expect=expect, tag=tag, **kw))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run()
    return _LOOP_POOL.submit(_run).result(timeout=timeout + 30)


async def achat_stream(
    messages: list,
    *,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    timeout: float = 60.0,
    tools: Optional[list] = None,
    retries: Optional[int] = None,
    tag: str = "",
):
    """流式 chat completion（async generator）。

    yield ("content", delta)            —— 文本增量
    yield ("tool_calls", [dict, ...])  —— 完整工具调用列表（一轮结束时，name+arguments 已合并）
    yield ("usage", dict)              —— usage（末尾）
    yield ("error", str)               —— 内部错误（不抛，让上层决定如何处理）

    重试仅在首个 token 到达前执行；已流出则直接 yield error 终止，不重试。
    """
    if not settings.deepseek_api_key:
        yield ("error", "DEEPSEEK_API_KEY 未配置")
        return

    if retries is None:
        retries = settings.llm_max_retries

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = _build_payload(
        messages, temperature=temperature, max_tokens=max_tokens,
        tools=tools, json_mode=False, tag=tag,
    )
    payload["stream"] = True
    payload["stream_options"] = {"include_usage": True}

    first_token = True
    last_err: Optional[Exception] = None

    for attempt in range(retries + 1):
        first_token = True
        last_err = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as r:
                    if r.status_code in (401, 403):
                        raise LLMError(
                            f"DeepSeek 鉴权失败 HTTP {r.status_code}",
                            kind="auth", status=r.status_code,
                        )
                    if r.status_code >= 400:
                        body = await r.aread()
                        raise LLMError(
                            f"DeepSeek HTTP {r.status_code}: {body[:200]}",
                            kind="http", status=r.status_code,
                        )

                    # 流式解析
                    pending: dict = {}   # index -> {id, name, arguments: str}
                    final_tcs: list = []
                    got_final_tcs = False

                    async for raw in r.aiter_lines():
                        if not raw or raw.startswith(":"):
                            continue
                        if not raw.startswith("data:"):
                            continue
                        line = raw[5:].strip()
                        if not line:
                            continue
                        if line == "[DONE]":
                            break
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # usage 独立块
                        if data.get("usage") and not data.get("choices"):
                            yield ("usage", data["usage"])
                            continue

                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        finish = choices[0].get("finish_reason")

                        # 文本增量
                        text = delta.get("content")
                        if text:
                            if first_token:
                                first_token = False
                            yield ("content", text)

                        # tool_calls 增量（可能多个 index 各出一段）
                        for tc_chunk in delta.get("tool_calls") or []:
                            idx = tc_chunk.get("index", 0)
                            slot = pending.setdefault(idx, {
                                "id": tc_chunk.get("id") or "",
                                "function": {"name": "", "arguments": ""},
                            })
                            fn = tc_chunk.get("function") or {}
                            if fn.get("name"):
                                slot["function"]["name"] = fn["name"]
                            if fn.get("arguments"):
                                slot["function"]["arguments"] += fn["arguments"]

                        # finish_reason = "tool_calls" 时组装最终工具调用
                        if finish == "tool_calls" and pending and not got_final_tcs:
                            got_final_tcs = True
                            final_tcs = [pending[k] for k in sorted(pending.keys())]
                            yield ("tool_calls", final_tcs)

                    # 流结束但没收到 finish_reason=tool_calls，把 pending 兜底发出去
                    if pending and not got_final_tcs:
                        final_tcs = [pending[k] for k in sorted(pending.keys())]
                        yield ("tool_calls", final_tcs)

            # 正常结束跳出重试循环
            return

        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = LLMError(f"DeepSeek 流式超时/网络错误: {e}", kind="timeout")
        except LLMError as e:
            last_err = e
            # auth / http 非可重试状态直接跳出
            if e.kind == "auth":
                break
            if e.status and e.status not in _RETRYABLE_STATUS:
                break
        except Exception as e:  # noqa: BLE001
            last_err = LLMError(f"DeepSeek 流式异常: {e}", kind="http")

        if not first_token and attempt > 0:
            # 已经流出过 token，不再重试
            break
        if attempt < retries:
            logger.warning("[llm.stream] tag=%s 第 %d 次重试: %s", tag, attempt + 1, last_err)
            continue
        break

    msg = str(last_err) if last_err else "LLM 流式调用失败"
    kind = getattr(last_err, "kind", "http") if isinstance(last_err, LLMError) else "http"
    logger.warning("[llm.stream] tag=%s 终止 kind=%s: %s", tag, kind, msg)
    yield ("error", msg)
