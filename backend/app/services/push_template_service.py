# -*- coding: utf-8 -*-
"""
推送模板服务：读模板 / 渲染变量 / 长度校验 / 落推送记录
对应设计文档 docs/06-推送模块设计-关系书与功能书.md

关键设计：定时任务执行时**从数据库读模板**，后台改完模板次日到点生效，无需重启服务。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
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
        "name": t.name or "",
        "kind": t.kind or "fixed",
        "schedule_time": t.schedule_time or DEFAULT_SCHEDULE.get(t.code, ""),
        "schedule_is_default": not (t.schedule_time or "").strip(),
        "frequency": t.frequency or "daily",
        "weekday": t.weekday,
        "title": t.title,
        "content": t.content,
        "default_title": t.default_title,
        "default_content": t.default_content,
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


# ============================================================
# 执行时间（M5）：任务每 5 分钟自检，到点才真正发
# ============================================================

# 内置任务的默认执行时间（表里 schedule_time 为空时兜底）
DEFAULT_SCHEDULE = {
    "daily_summary": "08:00",
    "expiring_alert": "09:00",
    "archive_notice": "02:00",
}
# 到点判定窗口（分钟）：beat 每 5 分钟触发一次，窗口内任一次命中即执行一次
DUE_WINDOW_MINUTES = 15

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def is_valid_time(v: str) -> bool:
    return bool(_TIME_RE.match(v or ""))


def due_window(db, tpl: PushTemplate, now: Optional[datetime] = None) -> Optional[datetime]:
    """判断模板是否处于「应执行窗口」，是则返回窗口起点 target，否则 None。
    - schedule_time 为空 → 用内置默认（custom 无默认 → None 不执行）
    - weekly 模板仅在匹配 weekday 的那天执行
    - 窗口 = [target, target + DUE_WINDOW_MINUTES)
    """
    now = now or datetime.now()
    hhmm = (tpl.schedule_time or "").strip() or DEFAULT_SCHEDULE.get(tpl.code)
    if not hhmm or not is_valid_time(hhmm):
        return None
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if tpl.kind == "custom" and tpl.frequency == "weekly":
        if tpl.weekday is None or now.weekday() != int(tpl.weekday):
            return None
    if target <= now < target + timedelta(minutes=DUE_WINDOW_MINUTES):
        return target
    return None


def already_pushed(db, template_id: int, since: datetime) -> bool:
    """防重复：窗口起点之后该模板已有真实发送记录（成功或失败都算）→ 跳过。
    也顺带实现「失败不重试轰炸」——失败记录落库即止，人工用测试发送补救。"""
    return db.query(PushRecord.id).filter(
        PushRecord.template_id == template_id,
        PushRecord.preview == 0,
        PushRecord.push_time >= since,
    ).first() is not None


# ============================================================
# 每日推送「最新标讯」结构化列表（2026-11-26 用户指定格式）
# 标题 / 单位 / 金额 / 截止时间 / 分类 / 查看详情（蓝字链接）
# ============================================================

def format_bids_rows(rows) -> str:
    """把 (BidInfo, 公告类型名) 行集合格式化为企微 markdown 情报简报卡片（方案A）。
    字段有什么显示什么；每条用引用块做卡片骨架（企微渲染为左侧蓝竖线）。
    每日推送 / 到期预警 / 归档通知 / 自定义模板共用同一格式。
    """
    blocks = []
    for idx, (b, nt) in enumerate(rows, start=1):
        title = (b.title or '').strip()[:60]
        lines = [f"> **{idx:02d}｜** {title}"]
        fields = []
        if b.tenderee:
            fields.append(f"单位 · {b.tenderee}")
        if b.budget:
            fields.append(f"金额 · <font color=\"warning\">{b.budget}</font>")
        if b.deadline:
            fields.append(f"截止 · <font color=\"warning\">{b.deadline.strftime('%Y-%m-%d %H:%M')}</font>")
        if nt:
            fields.append(f"分类 · <font color=\"info\">{nt}</font>")
        if fields:
            lines.append("> " + "　".join(fields))
        if b.source_url:
            lines.append(f"> [查看详情 →]({b.source_url})")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) or "> （无标讯）"


def query_bids_with_type(db, *filters, order_by=None, limit: int = 5):
    """带公告类型 join 的标讯查询（归档/到期等任务用，与每日推送同格式）。
    status 过滤由调用方传（每日/到期=1 已发布，归档=3 已归档）。
    """
    from app.models.bid import BidInfo
    from app.models.dict import DictNoticeType
    q = (db.query(BidInfo, DictNoticeType.name.label("nt_name"))
         .join(DictNoticeType, DictNoticeType.id == BidInfo.notice_type_id, isouter=True)
         .filter(*filters))
    if order_by is not None:
        q = q.order_by(order_by)
    return q.limit(limit).all()


def count_recent(hours: int = 24) -> int:
    """近 N 小时新增标讯数（每日推送的 {count}）——只统计已清洗提取的"""
    from app.models.bid import BidInfo
    db = SessionLocal()
    try:
        since = datetime.now() - timedelta(hours=hours)
        return db.query(BidInfo.id).filter(
            BidInfo.status == 1, BidInfo.created_at >= since,
            BidInfo.notice_type_id.isnot(None)).count()  # 未提取的不发
    finally:
        db.close()


def build_latest_bids_list(db, limit: int = 3) -> str:
    """最新 N 条标讯的结构化 markdown（任务与预览共用同一实现）。
    过滤未清洗/未提取的条目（notice_type_id 为空 = 提取流程未跑过）。
    """
    from app.models.bid import BidInfo
    since = datetime.now() - timedelta(hours=24)
    rows = query_bids_with_type(
        db, BidInfo.status == 1, BidInfo.created_at >= since,
        BidInfo.notice_type_id.isnot(None),   # 未提取的不发
        order_by=BidInfo.publish_time.desc(), limit=limit)
    return format_bids_rows(rows)
