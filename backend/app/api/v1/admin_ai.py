# -*- coding: utf-8 -*-
"""后台 AI 设置管理接口（一期）
功能：
- /admin/ai/settings   列表 + 按 key 分组（model / prompt / param）
- PUT 单条保存（自动存 snapshot）
- /admin/ai/settings/{key}/snapshots 变更历史
- /admin/ai/settings/{key}/rollback   回滚到某版本
- /admin/ai/test-connection          连通性测试（对某个 model 发一条空对话看是否 200）
- /admin/ai/prompt/chat-system/try   试运行 Prompt（喂一条示例输入 → 返回 LLM 回复）
"""
from typing import List, Optional

import json as _json
import logging

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import SysUser
from app.services import ai_setting_service as svc
from app.utils.response import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ai/settings", tags=["后台：AI 设置"])

AdminRole = Depends(require_role("admin", "ops"))


class SettingIn(BaseModel):
    value: Optional[str] = None     # text / json 存原文本，number / bool 也存字符串（解析交给后端）
    remark: Optional[str] = None


# ============= 列表 =============

@router.get("", summary="AI 设置全量列表（按 idx_set 分组）")
def list_settings(db: Session = Depends(get_db), _: SysUser = AdminRole):
    rows = svc.list_all(db)
    # 按 idx_set 分组返回，前端四个 tab 直接渲染
    grouped: dict = {"model": [], "prompt": [], "param": []}
    for r in rows:
        g = r.get("idx_set") or "other"
        grouped.setdefault(g, []).append(r)
    return ApiResponse.ok({"groups": grouped, "flat": rows})


# ============= 保存（单条） =============

@router.put("/{key:path}", summary="保存某条设置（自动入快照 + 清缓存立即生效）")
def save_setting(key: str, payload: SettingIn, db: Session = Depends(get_db),
                 user: SysUser = Depends(get_current_user)):
    from app.models.ai_setting import AISetting
    try:
        row = db.query(AISetting).filter(AISetting.setting_key == key).first()
        if not row:
            raise HTTPException(404, f"setting {key} 不存在")

        new_val = payload.value
        if row.value_type == "json" and new_val is not None and new_val.strip():
            try:
                _json.loads(new_val)
            except _json.JSONDecodeError as e:
                raise HTTPException(400, f"JSON 不合法：{e}")
        svc.update_one(db, key, new_val, user.id, user.username, payload.remark)
        return ApiResponse.ok({"key": key})
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("[admin_ai] save_setting 失败")
        raise HTTPException(500, f"保存失败：{str(e)[:120]}")


# ============= 历史 + 回滚 =============

@router.get("/{key:path}/snapshots", summary="某条设置的变更历史（最近 20 条）")
def list_snapshots(key: str, db: Session = Depends(get_db), _: SysUser = AdminRole):
    return ApiResponse.ok(svc.list_snapshots(db, key, 20))


@router.post("/{key:path}/rollback", summary="回滚到某快照（传 snapshot_id）")
def rollback_setting(key: str, payload: dict = Body(...), db: Session = Depends(get_db),
                     user: SysUser = Depends(get_current_user)):
    """payload 需含 snapshot_id（int）。"""
    snap_id = payload.get('snapshot_id')
    if snap_id is None:
        raise HTTPException(400, '缺少 snapshot_id')
    try: snap_id = int(snap_id)
    except (TypeError, ValueError): raise HTTPException(400, 'snapshot_id 必须是整数')
    from app.models.ai_setting import AISettingSnapshot
    snap = db.query(AISettingSnapshot).filter(AISettingSnapshot.id == snap_id).first()
    if not snap or snap.setting_key != key:
        raise HTTPException(404, "快照不存在或 key 不匹配")
    try:
        svc.update_one(db, key, snap.old_value, user.id, user.username, remark=f"回滚到 #{snap_id}")
    except KeyError:
        raise HTTPException(404, f"setting {key} 不存在")
    return ApiResponse.ok({"key": key, "rolled_back_to": snap_id})


# ============= 连通性测试 =============

class ConnTestIn(BaseModel):
    provider: Optional[str] = None  # 不传则从 DB 当前 model.chat_system 取
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.0
    timeout: float = 15.0


@router.post("/test-connection", summary="连通性测试：打一条 ping 看模型是否可用")
async def test_connection(payload: ConnTestIn, _: SysUser = AdminRole):
    """直接打 /chat/completions，15s 超时。返回 ok+延迟ms / 失败原因。"""
    import asyncio
    import httpx

    url = f"{payload.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {payload.api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": payload.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 4,
        "temperature": payload.temperature,
    }
    import time as _t
    t0 = _t.monotonic()
    try:
        async with httpx.AsyncClient(timeout=payload.timeout) as client:
            r = await client.post(url, headers=headers, json=body)
        latency_ms = int((_t.monotonic() - t0) * 1000)
        if r.status_code == 200:
            try:
                content = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
            except Exception:
                content = r.text[:80]
            return ApiResponse.ok({
                "ok": True,
                "latency_ms": latency_ms,
                "model": payload.model,
                "preview": content[:80],
            })
        if r.status_code in (401, 403):
            return ApiResponse.ok({"ok": False, "reason": "鉴权失败（API Key 不对）",
                                   "latency_ms": latency_ms})
        if r.status_code == 404:
            return ApiResponse.ok({"ok": False, "reason": "模型不存在或 base_url 错（404）",
                                   "latency_ms": latency_ms})
        return ApiResponse.ok({"ok": False, "reason": f"HTTP {r.status_code}: {r.text[:200]}",
                               "latency_ms": latency_ms})
    except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout) as e:
        return ApiResponse.ok({"ok": False, "reason": f"网络/超时：{str(e)[:120]}"})
    except Exception as e:
        return ApiResponse.ok({"ok": False, "reason": f"异常：{str(e)[:120]}"})


# ============= Prompt 试运行 =============

class PromptTryIn(BaseModel):
    setting_key: str   # 哪个 Prompt（prompt.chat_system / prompt.push_generate / prompt.extract_ai）
    input_text: str    # 喂给模型的示例输入


@router.post("/prompt/try", summary="Prompt 试运行（admin 后台直接看 LLM 回复）")
async def prompt_try(payload: PromptTryIn, _: SysUser = AdminRole):
    from app.services.llm import achat, LLMError

    if payload.setting_key not in ("prompt.chat_system", "prompt.push_generate", "prompt.extract_ai"):
        raise HTTPException(400, f"不支持的 setting_key: {payload.setting_key}")

    prompt_text = svc.get(payload.setting_key)
    if not prompt_text:
        raise HTTPException(400, "Prompt 为空，先保存一下再试")

    # 拿 chat_system 的 model 配置（其他 prompt 用通用 chat 测试即可）
    model_cfg = svc.get("model.chat_system") or {}
    base_url = model_cfg.get("base_url") or svc._DEFAULTS["model.chat_system"]["base_url"]
    api_key = model_cfg.get("api_key") or ""
    model = model_cfg.get("model") or svc._DEFAULTS["model.chat_system"]["model"]

    # 把 api_key 临时注入 settings（或直接手拼 httpx）
    # achat 走 settings 全局，这里用更简单的方式：临时 patch settings.deepseek_*
    from app.config import settings as app_settings
    orig_key = app_settings.deepseek_api_key
    orig_url = app_settings.deepseek_base_url
    orig_model = app_settings.deepseek_model
    app_settings.deepseek_api_key = api_key
    app_settings.deepseek_base_url = base_url
    app_settings.deepseek_model = model
    try:
        result = await achat(
            [{"role": "system", "content": prompt_text},
             {"role": "user", "content": payload.input_text}],
            max_tokens=800,
            timeout=30,
            temperature=0.0,
            tag="admin_prompt_try",
        )
        return ApiResponse.ok({
            "content": result.content,
            "latency_ms": result.latency_ms,
            "model": result.model,
            "usage": result.usage,
        })
    except LLMError as e:
        return ApiResponse.ok({"error": True, "kind": e.kind,
                               "message": str(e)[:200]})
    finally:
        app_settings.deepseek_api_key = orig_key
        app_settings.deepseek_base_url = orig_url
        app_settings.deepseek_model = orig_model


# ================================================================ #
#  AI 用量统计（成本评估）：日 / 周 / 月 + 30 天趋势 + 按功能拆分
# ================================================================ #

usage_router = APIRouter(prefix="/admin/ai", tags=["后台：AI 用量"])

# DeepSeek 计费估算（元 / 百万 token）。仅用于后台展示，不影响实际计费。
PRICE_INPUT_PER_M = 2.0
PRICE_OUTPUT_PER_M = 3.0


def _agg(db, start, end=None):
    """聚合 [start, end) 区间的调用次数与 token 数。"""
    from sqlalchemy import func
    from app.models.ai_usage import AIUsageLog
    q = db.query(
        func.count(AIUsageLog.id),
        func.coalesce(func.sum(AIUsageLog.prompt_tokens), 0),
        func.coalesce(func.sum(AIUsageLog.completion_tokens), 0),
    ).filter(AIUsageLog.created_at >= start)
    if end is not None:
        q = q.filter(AIUsageLog.created_at < end)
    calls, pt, ct = q.one()
    pt, ct = int(pt or 0), int(ct or 0)
    return {
        "calls": int(calls or 0),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "est_cost": round(pt / 1e6 * PRICE_INPUT_PER_M + ct / 1e6 * PRICE_OUTPUT_PER_M, 4),
    }


def _period_starts():
    from datetime import date, datetime, timedelta
    now = datetime.now()
    today0 = datetime(now.year, now.month, now.day)
    week0 = today0 - timedelta(days=today0.weekday())      # 周一 00:00
    month0 = datetime(now.year, now.month, 1)              # 本月 1 日 00:00
    return today0, week0, month0, now


@usage_router.get("/usage", summary="AI 用量统计（今日/本周/本月 + 30 天趋势 + 按功能）")
def ai_usage_stats(db: Session = Depends(get_db), _: SysUser = AdminRole):
    from sqlalchemy import func
    from app.models.ai_usage import AIUsageLog

    today0, week0, month0, now = _period_starts()

    summary = {
        "today": _agg(db, today0),
        "week": _agg(db, week0),
        "month": _agg(db, month0),
    }

    # 近 30 天逐日
    from datetime import timedelta
    start30 = (today0 - timedelta(days=29))
    rows = (
        db.query(
            func.date(AIUsageLog.created_at).label("d"),
            func.count(AIUsageLog.id),
            func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
        )
        .filter(AIUsageLog.created_at >= start30)
        .group_by(func.date(AIUsageLog.created_at))
        .all()
    )
    by_day = {str(r[0]): {"calls": int(r[1] or 0), "total_tokens": int(r[2] or 0)}
              for r in rows}
    series = []
    for i in range(30):
        d = (start30 + timedelta(days=i)).date()
        v = by_day.get(str(d), {"calls": 0, "total_tokens": 0})
        series.append({"date": d.strftime("%m-%d"), **v})

    # 本月按功能拆分
    tag_rows = (
        db.query(
            AIUsageLog.tag,
            func.count(AIUsageLog.id),
            func.coalesce(func.sum(AIUsageLog.prompt_tokens), 0),
            func.coalesce(func.sum(AIUsageLog.completion_tokens), 0),
        )
        .filter(AIUsageLog.created_at >= month0)
        .group_by(AIUsageLog.tag)
        .all()
    )
    by_tag = []
    for tag, calls, pt, ct in tag_rows:
        pt, ct = int(pt or 0), int(ct or 0)
        by_tag.append({
            "tag": tag or "unknown",
            "calls": int(calls or 0),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
            "est_cost": round(pt / 1e6 * PRICE_INPUT_PER_M + ct / 1e6 * PRICE_OUTPUT_PER_M, 4),
        })
    by_tag.sort(key=lambda x: x["total_tokens"], reverse=True)

    return ApiResponse.ok({
        "summary": summary,
        "series_30d": series,
        "by_tag": by_tag,
        "by_tag_scope": "month",
        "pricing": {
            "input_per_m": PRICE_INPUT_PER_M,
            "output_per_m": PRICE_OUTPUT_PER_M,
            "currency": "CNY",
        },
        "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
    })
