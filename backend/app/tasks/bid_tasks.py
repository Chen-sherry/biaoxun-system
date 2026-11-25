"""标讯归档 / 清理类定时任务"""
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.bid_tasks.archive_expired_bids")
def archive_expired_bids():
    """将截止时间已过 30 天且状态为已发布的标讯置为已归档，
    归档完成后按 archive_notice 模板发归档汇总到企微群（已定 Q3=发）。"""
    from app.database import SessionLocal
    from app.models.bid import BidInfo
    from app.tasks.push_tasks import _send

    db = SessionLocal()
    try:
        from app.tasks.push_tasks import _due_gate
        tpl, target = _due_gate(db, "archive_notice")
        if not tpl:
            # 未到点/停用/已发过 → 整个跳过（归档动作也只在到点窗口内做，幂等且每日一次）
            return {"archived": 0, "notified": False, "reason": "not_due_or_disabled"}

        cutoff = datetime.now() - timedelta(days=30)
        rows = (
            db.query(BidInfo)
            .filter(BidInfo.status == 1, BidInfo.deadline.isnot(None),
                    BidInfo.deadline < cutoff)
            .all()
        )
        count = len(rows)
        for r in rows:
            r.status = 3  # 已归档
        db.commit()

        logger.info(f"[archive] archived {count} bids (deadline < {cutoff.date()})")
        if count == 0:
            return {"archived": 0, "notified": False, "reason": "nothing_to_archive"}

        # 归档通知：结构化卡片格式（与每日推送一致，2026-11-26），取被归档的前 5 条
        from app.services.push_template_service import query_bids_with_type, format_bids_rows
        sample_rows = query_bids_with_type(
            db, BidInfo.status == 3, BidInfo.deadline.isnot(None),
            BidInfo.deadline < cutoff,
            order_by=BidInfo.deadline.desc(), limit=5)
        bid_list = format_bids_rows(sample_rows)
        result = _send(db, code="archive_notice", variables={
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": str(count),
            "bid_list": bid_list,
        })
        return {"archived": count, "notified": result.get("pushed", False)}
    except Exception as e:
        logger.exception(f"[archive] archive_expired_bids failed: {e}")
        return {"archived": 0, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.bid_tasks.refresh_dedup")
def refresh_dedup():
    """重新计算所有标讯 dedup_key（数据修复）"""
    return {"status": "placeholder"}
