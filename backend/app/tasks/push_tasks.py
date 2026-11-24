"""推送定时任务：每日订阅推送 + 到期预警汇总"""
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.push_tasks.push_daily_subscriptions")
def push_daily_subscriptions():
    """
    每日 08:00：扫描 frequency=daily 的订阅，匹配最新标讯并推送。
    —— 实现时结合 subscribe 表 + bid_info 表做关键词匹配后调推送通道。
    这里先占位，具体匹配逻辑后续补充。
    """
    logger.info("[push] daily subscriptions triggered")
    return {"status": "ok", "message": "placeholder: need business rule"}


@celery_app.task(name="app.tasks.push_tasks.send_expiring_bid_daily")
def send_expiring_bid_daily():
    """
    每日 09:00：查询 bid_info 中 deadline 在 24 小时内的标讯，
    汇总后推送到企业微信群机器人。

    ⚠️  安全措施：
    - count == 0 时默认**不推送**（防止打扰群），可通过 WECOM_SEND_ZERO_SUMMARY=true 开启
    - WECOM_WEBHOOK 必须在 .env 中配置，未配置时静默跳过
    """
    from app.config import settings
    from app.database import SessionLocal
    from app.models.bid import BidInfo
    from app.services.wecom_push import send_text_sync

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
        date_str = now.strftime("%Y-%m-%d")
        send_zero = getattr(settings, "wecom_send_zero_summary", False)

        # ⚠️ 没有到期标讯时默认**不推送**
        if count == 0:
            if send_zero:
                summary = f"⏰ {date_str} 截止预警：24h 内截止的标讯 0 条 ✅"
                ok = send_text_sync(summary)
                logger.info(f"[push] expiring summary ZERO count but send enabled, pushed={ok}")
                return {"count": 0, "pushed": ok}
            logger.info(
                "[push] expiring summary: 0 due bids, SKIP send "
                "(set WECOM_SEND_ZERO_SUMMARY=true in .env to send zero-count messages)"
            )
            return {"count": 0, "pushed": False, "skipped_reason": "no_expiring_bids"}

        # count > 0：推送汇总
        summary_lines = [f"### ⏰ {date_str} 截止预警"]
        summary_lines.append(f"**{count} 条标讯 24h 内截止**")
        for r in rows[:15]:
            dl = r.deadline.strftime("%m-%d %H:%M") if r.deadline else "?"
            link = r.source_url or f"http://localhost:8000/api/v1/bids/{r.id}"
            summary_lines.append(f"- [{r.title[:40]}]({link}) · {dl}")
        summary = "\n".join(summary_lines)

        ok = send_text_sync(summary)
        logger.info(f"[push] expiring summary count={count} pushed={ok}")
        return {"count": count, "pushed": ok}

    except Exception as e:
        logger.exception(f"[push] send_expiring_bid_daily failed: {e}")
        return {"count": 0, "pushed": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.push_tasks.push_hourly_subscriptions")
def push_hourly_subscriptions():
    """每小时推送（可选加速版）"""
    return {"status": "placeholder"}


@celery_app.task(name="app.tasks.push_tasks.send_email")
def send_email(to_addr: str, subject: str, html_body: str):
    """发送单封邮件（底层 SMTP，占位）"""
    return {"to": to_addr, "status": "placeholder"}
