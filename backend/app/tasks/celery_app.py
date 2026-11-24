"""Celery 应用初始化（爬虫 & 推送定时任务）"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "bid_celery",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    timezone="Asia/Shanghai",
    enable_utc=False,
    worker_concurrency=4,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    beat_schedule={
        "crawl-every-hour": {
            "task": "app.tasks.crawl_tasks.crawl_all_sources",
            "schedule": 3600,  # 1 小时
        },
        "push-daily-8am": {
            "task": "app.tasks.push_tasks.push_daily_subscriptions",
            "schedule": "0 8 * * *",
        },
        "expiry-summary-9am": {
            "task": "app.tasks.push_tasks.send_expiring_bid_daily",
            "schedule": "0 9 * * *",
        },
        "archive-expired-bids": {
            "task": "app.tasks.bid_tasks.archive_expired_bids",
            "schedule": "0 2 * * *",
        },
    },
)
