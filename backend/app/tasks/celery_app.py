"""Celery 应用初始化（爬虫 & 推送定时任务）"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "bid_celery",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # worker 启动时必须加载任务模块，否则收到 beat 消息会报 unregistered task 并丢弃
    include=[
        "app.tasks.crawl_tasks",
        "app.tasks.push_tasks",
        "app.tasks.bid_tasks",
    ],
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
            "schedule": crontab(minute=0, hour=8),  # 每天 8:00
        },
        "expiry-summary-9am": {
            "task": "app.tasks.push_tasks.send_expiring_bid_daily",
            "schedule": crontab(minute=0, hour=9),  # 每天 9:00
        },
        "archive-expired-bids": {
            "task": "app.tasks.bid_tasks.archive_expired_bids",
            "schedule": crontab(minute=0, hour=2),  # 每天 2:00
        },
    },
)
