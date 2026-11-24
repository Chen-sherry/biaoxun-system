"""标讯归档 / 清理类定时任务"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.bid_tasks.archive_expired_bids")
def archive_expired_bids():
    """将截止时间已过 30 天的标讯置为已归档"""
    return {"status": "placeholder"}


@celery_app.task(name="app.tasks.bid_tasks.refresh_dedup")
def refresh_dedup():
    """重新计算所有标讯 dedup_key（数据修复）"""
    return {"status": "placeholder"}
