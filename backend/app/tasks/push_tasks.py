"""推送定时任务：每日汇总 + 到期预警 + 归档通知 —— 全部从 push_template 读库渲染
（后台改模板，次日到点按新文案发送，无需重启服务）
"""
import logging
from collections import Counter
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _send(db, *, code: str, variables: dict, push_type: str = "scheduled") -> dict:
    """读模板 → 模板停用则跳过 → 渲染 → 长度校验 → 发企微群 → 落记录"""
    from app.services.push_template_service import render_push_message, check_length, save_record
    from app.services.wecom_push import send_markdown_sync

    msg = render_push_message(code, variables, db=db)
    if not msg:
        logger.warning(f"[push] 模板 {code} 不存在，跳过")
        return {"pushed": False, "reason": "template_missing", "code": code}
    if not msg["enabled"]:
        logger.info(f"[push] 模板 {code} 已停用，SKIP")
        return {"pushed": False, "reason": "template_disabled", "code": code}

    length = check_length(msg["full"])
    if not length["ok"]:
        save_record(db, push_type=push_type, status=1, preview=0,
                    template_id=msg["template_id"], subject=msg["title"],
                    error_msg=f"内容超长 {length['bytes']}/{length['limit']} 字节")
        db.commit()
        logger.error(f"[push] 模板 {code} 渲染超长 {length['bytes']} 字节，未发送")
        return {"pushed": False, "reason": "too_long", "bytes": length["bytes"]}

    result = send_markdown_sync(msg["title"], msg["content"])
    ok = bool(result and result.get("errcode") == 0)
    err = None if ok else str(result or "send_failed")[:500]
    save_record(db, push_type=push_type, status=0 if ok else 1, preview=0,
                template_id=msg["template_id"], subject=msg["title"], error_msg=err)
    db.commit()
    logger.info(f"[push] 模板 {code} 发送 pushed={ok}")
    return {"pushed": ok, "code": code, "bytes": length["bytes"]}


# ============================================================
# 每天 08:00 每日汇总（原占位 → 真实实现）
# ============================================================

@celery_app.task(name="app.tasks.push_tasks.push_daily_subscriptions")
def push_daily_subscriptions():
    from app.database import SessionLocal
    from app.models.bid import BidInfo

    db = SessionLocal()
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        since = today_start - timedelta(days=1)
        rows = (
            db.query(BidInfo)
            .filter(BidInfo.status == 1, BidInfo.created_at >= since,
                    BidInfo.created_at < today_start)
            .all()
        )
        # Top 关键词：标讯标题按 2-4 字中文词粗略统计（取高频名词近似）
        titles = " ".join((r.title or "") for r in rows)
        # 用常见招投标关键词表做命中统计，避免分词依赖
        seed_kw = ["招标", "中标", "采购", "询价", "磋商", "竞价", "工程", "服务",
                   "货物", "监理", "设计", "施工", "运维", "物业", "信息化", "设备"]
        cnt = Counter({k: titles.count(k) for k in seed_kw if titles.count(k) > 0})
        top_keywords = [f"{k}（{v}）" for k, v in cnt.most_common(10)] or ["（无）"]
        regions = Counter((r.region_code or "未知") for r in rows)
        top_regions = [f"{k}（{v}）" for k, v in regions.most_common(6)] if regions else []

        bid_list = "\n".join(
            f"- [{(r.title or '')[:40]}]({r.source_url or ''})" for r in rows[:15]
        ) or "（无）"

        return _send(db, code="daily_summary", variables={
            "date": today_start.strftime("%Y-%m-%d"),
            "count": str(len(rows)),
            "top_keywords": "\n".join(f"> - {k}" for k in top_keywords),
            "top_regions": "\n".join(f"> - {r}" for r in top_regions) if top_regions else "",
            "bid_list": bid_list,
        })
    except Exception as e:
        logger.exception(f"[push] daily summary failed: {e}")
        return {"pushed": False, "error": str(e)}
    finally:
        db.close()


# ============================================================
# 每天 09:00 到期预警（改造为读库渲染）
# ============================================================

@celery_app.task(name="app.tasks.push_tasks.send_expiring_bid_daily")
def send_expiring_bid_daily():
    from app.config import settings
    from app.database import SessionLocal
    from app.models.bid import BidInfo

    db = SessionLocal()
    try:
        now = datetime.now()
        cutoff = now + timedelta(hours=24)
        rows = (
            db.query(BidInfo)
            .filter(
                BidInfo.status == 1,
                BidInfo.deadline.isnot(None),
                BidInfo.deadline >= now,
                BidInfo.deadline <= cutoff,
            )
            .order_by(BidInfo.deadline.asc())
            .all()
        )
        count = len(rows)
        send_zero = getattr(settings, "wecom_send_zero_summary", False)

        # 0 条默认不发（防打扰群），WECOM_SEND_ZERO_SUMMARY=true 可开
        if count == 0 and not send_zero:
            logger.info("[push] expiring summary: 0 due bids, SKIP")
            return {"count": 0, "pushed": False, "skipped_reason": "no_expiring_bids"}

        bid_list = "\n".join(
            f"- [{(r.title or '')[:40]}]({r.source_url or ''}) · "
            f"{r.deadline.strftime('%m-%d %H:%M') if r.deadline else '?'}"
            for r in rows[:15]
        ) or "（无）"

        return _send(db, code="expiring_alert", variables={
            "date": now.strftime("%Y-%m-%d"),
            "count": str(count),
            "bid_list": bid_list,
        })
    except Exception as e:
        logger.exception(f"[push] send_expiring_bid_daily failed: {e}")
        return {"count": 0, "pushed": False, "error": str(e)}
    finally:
        db.close()


# ============================================================
# 每天 02:00 归档（原纯数据任务 → 归档后发 archive_notice，已定 Q3=发）
# ============================================================

@celery_app.task(name="app.tasks.push_tasks.push_hourly_subscriptions")
def push_hourly_subscriptions():
    """每小时推送（Q7 已定：本期不启用，保留占位）"""
    return {"status": "placeholder"}


@celery_app.task(name="app.tasks.push_tasks.send_email")
def send_email(to_addr: str, subject: str, html_body: str):
    """发送单封邮件（底层 SMTP，占位）"""
    return {"to": to_addr, "status": "placeholder"}
