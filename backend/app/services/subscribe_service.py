# -*- coding: utf-8 -*-
"""
订阅匹配与个人推送（公共封装）。

三条链路共用同一实现，避免逻辑漂移：
- 用户前台「立即推送」（API）
- Celery 定时任务（push_hourly_subscriptions）
- 后台预览/立即推送（admin 接口）

推送通道：邮件（SMTP）。未配置 SMTP 时返回失败并落记录，便于先跑通流程。
"""
import html as _html
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import or_

from app.models.bid import BidInfo
from app.models.member import MemberOrder, MemberPackage
from app.models.subscribe import BidSubscribe
from app.models.user import SysUser

logger = logging.getLogger(__name__)

# 无有效会员时回退免费套餐；再兜底一个常量
FREE_FALLBACK_MAX = 3
# 订阅频率 → 推送间隔（小时）；realtime 视作随时可推
FREQ_HOURS = {"realtime": 0, "hourly": 1, "daily": 24}


# ============================================================
# 会员上限
# ============================================================

def get_active_package(db, user_id: int) -> Optional[MemberPackage]:
    """返回用户当前生效的最高等级套餐（无则 None）。"""
    now = datetime.now()
    return (
        db.query(MemberPackage)
        .join(MemberOrder, MemberOrder.package_id == MemberPackage.id)
        .filter(
            MemberOrder.user_id == user_id,
            MemberOrder.status == 1,
            MemberOrder.start_date <= now,
            MemberOrder.end_date >= now,
        )
        .order_by(MemberPackage.level.desc())
        .first()
    )


def get_user_max_subscribe(db, user_id: int) -> int:
    """用户当前可创建的最大订阅数：有效套餐 → 免费套餐 → 常量兜底。"""
    pkg = get_active_package(db, user_id)
    if pkg and pkg.max_subscribe is not None:
        return pkg.max_subscribe
    free = db.query(MemberPackage).filter(MemberPackage.code == "free").first()
    if free and free.max_subscribe is not None:
        return free.max_subscribe
    return FREE_FALLBACK_MAX


def count_active_subscribes(db, user_id: int) -> int:
    return (
        db.query(BidSubscribe)
        .filter(BidSubscribe.user_id == user_id, BidSubscribe.status == 1)
        .count()
    )


# ============================================================
# 匹配
# ============================================================

def match_bids(db, s: BidSubscribe, days: int = 7, limit: int = 50,
               ignore_last_push: bool = False) -> List[BidInfo]:
    """按订阅条件匹配标讯：
    keyword 拆词 OR LIKE title；region/industry/notice_type 等值；NULL/空 = 不约束。
    仅取 status=1；ignore_last_push=False 时只取 last_push_at 之后的新标讯。"""
    q = db.query(BidInfo).filter(BidInfo.status == 1)

    words = [w for w in (s.keyword or "").replace("，", " ").replace(",", " ").split() if w]
    if words:
        q = q.filter(or_(*[BidInfo.title.like(f"%{w}%") for w in words]))
    if s.region_code:
        q = q.filter(BidInfo.region_code == s.region_code)
    if s.industry_id:
        q = q.filter(BidInfo.industry_id == s.industry_id)
    if s.notice_type_id:
        q = q.filter(BidInfo.notice_type_id == s.notice_type_id)

    if ignore_last_push:
        pass  # 预览/立即推送：不限时间
    elif s.last_push_at:
        q = q.filter(BidInfo.created_at > s.last_push_at)
    else:
        since = datetime.now() - timedelta(days=days)
        q = q.filter(BidInfo.created_at >= since)

    return q.order_by(BidInfo.publish_time.desc()).limit(limit).all()


def bid_brief(b) -> dict:
    return {
        "id": b.id,
        "title": b.title,
        "notice_type_id": b.notice_type_id,
        "region_code": b.region_code,
        "publish_time": b.publish_time.isoformat() if b.publish_time else None,
        "deadline": b.deadline.isoformat() if b.deadline else None,
        "source_url": b.source_url,
    }


# ============================================================
# 邮件正文
# ============================================================

def build_email_html(sub: BidSubscribe, rows: List[BidInfo]) -> str:
    """把命中的标讯渲染成简洁 HTML 邮件列表。"""
    from app.config import settings

    parts = [
        f"<h3>「{_html.escape(sub.keyword or '订阅')}」有 {len(rows)} 条新标讯</h3>",
        "<ol>",
    ]
    for b in rows:
        title = _html.escape(b.title or "")
        line = f"<li><strong>{title}</strong>"
        meta = []
        if b.tenderee:
            meta.append(f"单位：{_html.escape(b.tenderee)}")
        if b.budget:
            meta.append(f"金额：{_html.escape(str(b.budget))}")
        if b.deadline:
            meta.append(f"截止：{b.deadline.strftime('%Y-%m-%d %H:%M')}")
        if meta:
            line += "<br><span style='color:#666;font-size:13px'>" + " · ".join(meta) + "</span>"
        if b.source_url:
            line += f"<br><a href='{_html.escape(b.source_url)}'>查看详情 →</a>"
        line += "</li>"
        parts.append(line)
    parts.append("</ol>")
    parts.append(f"<p style='color:#999;font-size:12px'>本邮件由{settings.app_name}自动推送，请勿直接回复。</p>")
    return "".join(parts)


# ============================================================
# 个人推送
# ============================================================

def is_sub_due(sub: BidSubscribe, now: Optional[datetime] = None) -> bool:
    """按订阅频率判断是否到推送时间。无推送记录 → 立即到期。"""
    if sub.status != 1:
        return False
    now = now or datetime.now()
    if not sub.last_push_at:
        return True
    hours = FREQ_HOURS.get((sub.frequency or "daily"), 24)
    return (now - sub.last_push_at) >= timedelta(hours=hours)


def push_subscribe(db, sub: BidSubscribe, *, ignore_last_push: bool = False,
                   trigger: str = "scheduled") -> dict:
    """匹配并推送单条订阅给其所有者。返回结果摘要；调用方负责最终 commit 语义（本函数内部会 commit）。"""
    from app.services.push_channel import email_channel
    from app.services.push_template_service import save_record

    rows = match_bids(db, sub, ignore_last_push=ignore_last_push)
    if not rows:
        return {"matched": 0, "sent": False, "reason": "no_bids"}

    subject = f"「{sub.keyword or '订阅'}」{len(rows)} 条新标讯"

    # 仅支持邮件通道；订阅未开启邮件则跳过
    if not sub.push_email:
        return {"matched": len(rows), "sent": False, "reason": "email_disabled"}

    user = db.query(SysUser).filter(SysUser.id == sub.user_id).first()
    if not user or not user.email:
        save_record(
            db, push_type="subscribe", channel="email", recipient=user.email if user else "",
            subscribe_id=sub.id, user_id=sub.user_id, status=1,
            subject=subject, bid_ids=[b.id for b in rows],
            error_msg="用户未绑定邮箱",
        )
        db.commit()
        return {"matched": len(rows), "sent": False, "reason": "no_email"}

    ok = email_channel.send(
        user.email, subject, build_email_html(sub, rows), html=True
    )
    save_record(
        db, push_type="subscribe", channel="email", recipient=user.email,
        subscribe_id=sub.id, user_id=sub.user_id,
        status=0 if ok else 1, subject=subject, bid_ids=[b.id for b in rows],
        error_msg=None if ok else "邮件发送失败（SMTP 未配置或发送异常）",
    )
    if ok:
        sub.last_push_at = datetime.now()
    db.commit()
    logger.info(f"[subscribe] sub={sub.id} trigger={trigger} matched={len(rows)} sent={ok}")
    return {"matched": len(rows), "sent": ok, "reason": None if ok else "send_failed"}


def run_all_subscribe_pushes(db) -> dict:
    """定时任务入口：遍历所有启用订阅，按频率到期的逐个推送。"""
    subs = db.query(BidSubscribe).filter(BidSubscribe.status == 1).all()
    now = datetime.now()
    stats = {"checked": len(subs), "pushed_subs": 0, "sent": 0, "skipped": 0, "matched": 0}
    for sub in subs:
        if not is_sub_due(sub, now):
            stats["skipped"] += 1
            continue
        try:
            r = push_subscribe(db, sub, trigger="scheduled")
            stats["pushed_subs"] += 1
            stats["matched"] += r.get("matched", 0)
            if r.get("sent"):
                stats["sent"] += 1
        except Exception as e:
            db.rollback()
            logger.exception(f"[subscribe] sub={sub.id} 推送异常: {e}")
    return stats
