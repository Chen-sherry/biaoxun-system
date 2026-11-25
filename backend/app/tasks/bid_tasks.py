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

        # 归档通知：0 条归档时按设计也跳过（避免每天 2 点空消息打扰）
        bid_list = "\n".join(
            f"- [{(r.title or '')[:40]}]({r.source_url or ''})" for r in rows[:15]
        )
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
