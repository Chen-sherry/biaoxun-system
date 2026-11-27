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
        # 以下三个每日任务改为每 5 分钟自检：执行时间存 push_template.schedule_time，
        # 后台改时间/启停即时生效，无需重启 beat（任务内部 due_window 判定 + 防重）
        "push-daily-check": {
            "task": "app.tasks.push_tasks.push_daily_subscriptions",
            "schedule": crontab(minute="*/5"),
        },
        # 每日问好（08:00，模板 daily_greeting）
        "daily-greeting-check": {
            "task": "app.tasks.push_tasks.send_daily_greeting",
            "schedule": crontab(minute="*/5"),
        },
        "expiry-summary-check": {
            "task": "app.tasks.push_tasks.send_expiring_bid_daily",
            "schedule": crontab(minute="*/5"),
        },
        "archive-expired-bids-check": {
            "task": "app.tasks.bid_tasks.archive_expired_bids",
            "schedule": crontab(minute="*/5"),
        },
        # 自定义定时推送（后台「新增定时推送」创建的 kind=custom 模板）
        "push-custom-templates-check": {
            "task": "app.tasks.push_tasks.push_custom_templates",
            "schedule": crontab(minute="*/5"),
        },
        # 个人订阅推送：每 5 分钟自检，按每条订阅的 frequency 到点才发邮件
        "subscribe-push-check": {
            "task": "app.tasks.push_tasks.push_hourly_subscriptions",
            "schedule": crontab(minute="*/5"),
        },
    },
)
