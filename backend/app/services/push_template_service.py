# -*- coding: utf-8 -*-
"""
推送模板服务：读模板 / 渲染变量 / 长度校验 / 落推送记录
对应设计文档 docs/06-推送模块设计-关系书与功能书.md

关键设计：定时任务执行时**从数据库读模板**，后台改完模板次日到点生效，无需重启服务。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional

from app.database import SessionLocal
from app.models.push import PushRecord, PushTemplate

logger = logging.getLogger(__name__)

# 企微 markdown 消息上限（字节）
WECOM_MD_LIMIT = 4096
# 临时推送单次标讯条数上限（Q14 = 20）
MANUAL_BID_LIMIT = 20

_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


# ============================================================
# 模板 CRUD
# ============================================================

def get_template(db, code: str) -> Optional[PushTemplate]:
    return db.query(PushTemplate).filter(PushTemplate.code == code).first()


def list_templates(db) -> List[PushTemplate]:
    return db.query(PushTemplate).order_by(PushTemplate.id.asc()).all()


def template_to_dict(t: Optional[PushTemplate]) -> dict:
    if not t:
        return {}
    return {
        "id": t.id,
        "code": t.code,
        "title": t.title,
        "content": t.content,
        "variables": [v for v in (t.variables or "").split(",") if v],
        "enabled": bool(t.enabled),
        "updated_by": t.updated_by,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def validate_variables(content: str, allowed: List[str]) -> List[str]:
    """返回模板里用到但不在允许清单中的变量名（空列表 = 合法）"""
    used = set(_VAR_RE.findall(content or ""))
    return sorted(used - set(allowed))


# ============================================================
# 渲染
# ============================================================

def render_template(content: str, variables: dict) -> str:
    """把 {var} 替换为实际值；未提供的变量保持原样（便于排查）"""
    def _sub(m: re.Match) -> str:
        key = m.group(1)
        val = variables.get(key)
        return val if val is not None else m.group(0)
    return _VAR_RE.sub(_sub, content or "")


def render_push_message(code: str, variables: dict, db=None) -> Optional[dict]:
    """读库 + 渲染，返回 {title, content, full, enabled, template_id}；模板不存在返回 None"""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        t = get_template(db, code)
        if not t:
            logger.warning(f"[push-tpl] 模板 {code} 不存在")
            return None
        title = render_template(t.title, variables)
        content = render_template(t.content, variables)
        return {
            "template_id": t.id,
            "enabled": bool(t.enabled),
            "title": title,
            "content": content,
            "full": f"## {title}\n{content}",
        }
    finally:
        if own:
            db.close()


def utf8_len(s: str) -> int:
    """utf-8 字节数（企微限制按字节算）"""
    return len((s or "").encode("utf-8"))


def check_length(text: str) -> dict:
    """长度校验：返回 {ok, bytes, limit}"""
    n = utf8_len(text)
    return {"ok": n <= WECOM_MD_LIMIT, "bytes": n, "limit": WECOM_MD_LIMIT}


# ============================================================
# 落推送记录（统一入口，预览/发送都走这里）
# ============================================================

def save_record(
    db,
    *,
    push_type: str,
    channel: str = "wechat",
    recipient: str = "群机器人",
    subject: Optional[str] = None,
    status: int = 0,
    error_msg: Optional[str] = None,
    bid_ids: Optional[List[int]] = None,
    user_id: Optional[int] = None,
    subscribe_id: Optional[int] = None,
    template_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    preview: int = 0,
) -> int:
    """写一条 push_record，返回 id。调用方负责 commit。"""
    rec = PushRecord(
        user_id=user_id,
        subscribe_id=subscribe_id,
        push_type=push_type,
        template_id=template_id,
        operator_id=operator_id,
        preview=preview,
        bid_ids=",".join(str(i) for i in bid_ids) if bid_ids else None,
        channel=channel,
        recipient=recipient,
        subject=(subject or "")[:255] or None,
        status=status,
        error_msg=(error_msg or "")[:500] or None,
        push_time=datetime.now(),
    )
    db.add(rec)
    db.flush()
    return rec.id


def record_to_dict(r: PushRecord, operator_name: Optional[str] = None,
                   template_code: Optional[str] = None) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "subscribe_id": r.subscribe_id,
        "push_type": r.push_type,
        "template_id": r.template_id,
        "template_code": template_code,
        "operator_id": r.operator_id,
        "operator_name": operator_name,
        "preview": bool(r.preview),
        "bid_ids": [int(x) for x in r.bid_ids.split(",")] if r.bid_ids else [],
        "channel": r.channel,
        "recipient": r.recipient,
        "subject": r.subject,
        "status": r.status,
        "error_msg": r.error_msg,
        "push_time": r.push_time.isoformat() if r.push_time else None,
    }
