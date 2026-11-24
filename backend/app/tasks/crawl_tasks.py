"""爬虫定时任务"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.crawl_tasks.crawl_all_sources")
def crawl_all_sources():
    """采集所有已注册的爬虫源（ggzy + ccgp 各抓 1 页，约 30 条/页）"""
    from app.services.crawl import crawl_all_registered_sources
    return crawl_all_registered_sources(pages_per_source=1)


@celery_app.task(name="app.tasks.crawl_tasks.crawl_single_source")
def crawl_single_source(source_code: str, pages: int = 1):
    """采集单个爬虫源；source_code: 'ggzy' 或 'ccgp'"""
    from app.services.crawl import crawl_and_save
    return crawl_and_save(source_code, pages=pages)
