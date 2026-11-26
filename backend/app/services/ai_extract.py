# -*- coding: utf-8 -*-
"""AI 兜底提取（双线策略第二道）

双线并行入库流程（2026-11-26）：
  第一道：data_clean.extract_fields_from_text 规则提取（免费、快）
  第二道：本模块——规则提取后关键字段仍缺失才调 DeepSeek 补提取；
          AI 返回 null 视为「确认没有」，按现状放行入库。

开销控制：
  - 只在 missing_fields() 判定为「不满」时才调用（不是每条都跑）
  - 正文截断 4000 字、只问缺失字段、max_tokens=400、temperature=0
  - 30s 超时、最多重试 1 次；任何失败返回 {} 降级放行，绝不阻塞入库
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 单条 AI 提取等待上限：入库路径不能等太久（deepseek 无专属 timeout 配置，用固定值）
AI_TIMEOUT = 30.0
_AI_MAX_RETRIES = 1
_TEXT_TRUNCATE = 4000

_FIELD_DESC = {
    "tenderee": "采购人/招标人/项目单位的全称（公告中负责采购的主体）",
    "winner_unit": "中标人/中标供应商/成交供应商的全称",
    "win_amount": "中标价/成交金额，换算成元的纯数字；费率、百分比、"
                  "代理服务费都不是成交金额，公告没有总价就填 null",
}

# 结果类标签：正文里出现这些才认为有结果字段可提
_RESULT_LABEL_RE = re.compile(
    r"(中标|成交|中选)(人|供应商|单位)[：:]|中标结果|成交结果")

# winner_unit 脏值（提取到这些视为无效）
_WINNER_BAD = {"未开标", "详见", "/", "-", "—", "无", "待定", "废标"}


def missing_fields(mapped: Dict) -> List[str]:
    """判定规则提取结果是否「不满」→ 返回仍缺失的关键字段名；[] = 满足，无需 AI。

    关键字段定义（宁缺勿滥，避免为真没有的字段白花钱）：
      - tenderee（采购人）：任何公告都关键
      - winner_unit / win_amount：仅当正文确实含结果类标签时才关键
    正文为空时不调 AI（没料可喂）。
    """
    ct = mapped.get("content_text") or ""
    if not ct:
        return []
    miss: List[str] = []
    t = (mapped.get("tenderee") or "").strip()
    # 过短的采购人是规则误抓的通用词（如「要求」——正文「采购人要求」被当值），转 AI 纠正
    if not t or len(t) < 4:
        miss.append("tenderee")
    if _RESULT_LABEL_RE.search(ct[:1500]):
        wu = (mapped.get("winner_unit") or "").strip()
        if not wu or wu in _WINNER_BAD:
            miss.append("winner_unit")
        if not mapped.get("win_amount"):
            miss.append("win_amount")
    return miss


def _build_user_prompt(title: str, text: str, missing: List[str]) -> str:
    desc = "；".join(f"{k}（{_FIELD_DESC.get(k, k)}）" for k in missing)
    example = ", ".join(f'"{k}": null' for k in missing)
    return (
        f"从下面的招标/采购公告正文中提取这些字段：{desc}。\n"
        f"规则：正文中确实没有就填 null，不要编造；金额换算成元（数字）；"
        f"单位名称用全称。\n\n"
        f"标题：{title}\n\n"
        f"正文：\n{text}\n\n"
        f'只输出一个 JSON 对象，例如：{{{example}}}'
    )


def _parse_json(content: str) -> Optional[Dict]:
    """容错解析模型返回：剥离 ```json 代码块、截取首个多余文本外的花括号"""
    if not content:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
    if m:
        content = m.group(1)
    else:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            content = m.group(0)
    try:
        obj = json.loads(content)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _clean_value(field: str, value):
    """按字段类型清洗 AI 返回值；无效 → None（视为确认没有）"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if field == "win_amount":
            v = float(value)
            return v if v > 0 else None
        return value
    s = str(value).strip()
    if not s or s in _WINNER_BAD:
        return None
    if field == "win_amount":
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s.replace(",", ""))
        if not m:
            return None
        v = float(m.group(1))
        if "万" in s:
            v *= 10000
        return v if v > 0 else None
    if field == "tenderee" and len(s) > 120:
        return None
    if field == "winner_unit" and len(s) > 120:
        return None
    return s


def ai_extract_missing(title: str, content_text: str,
                       missing: List[str]) -> Dict:
    """调 DeepSeek 提取缺失字段。返回 {字段: 新值}，只含确实提取到的；
    任何失败返回 {}（降级放行）。AI 返回 null = 确认没有，不写入。"""
    if not missing:
        return {}
    key = settings.deepseek_api_key
    if not key:
        logger.debug("[ai_extract] deepseek_api_key 未配置，跳过 AI 提取")
        return {}

    text = (content_text or "")[:_TEXT_TRUNCATE]
    if not text:
        return {}

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system",
             "content": "你是招投标公告信息提取引擎，只输出 JSON，不要任何解释。"},
            {"role": "user",
             "content": _build_user_prompt(title or "", text, missing)},
        ],
        "max_tokens": 400,
        "temperature": 0,
    }
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {key}"}

    raw_json: Optional[Dict] = None
    for attempt in range(_AI_MAX_RETRIES + 1):
        try:
            r = httpx.post(url, json=payload, headers=headers,
                           timeout=AI_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            content = (data.get("choices") or [{}])[0] \
                .get("message", {}).get("content")
            raw_json = _parse_json(content)
            break
        except Exception as e:
            logger.warning(
                "[ai_extract] 调用失败 attempt=%d fields=%s err=%s",
                attempt + 1, missing, str(e)[:200])
    if raw_json is None:
        return {}

    out: Dict = {}
    for f in missing:
        v = _clean_value(f, raw_json.get(f))
        if v is not None:
            out[f] = v
    logger.info("[ai_extract] fields=%s -> got=%s missing_left=%s",
                missing, list(out.keys()),
                [f for f in missing if f not in out])
    return out
