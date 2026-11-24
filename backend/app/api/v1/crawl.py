"""爬虫任务控制接口（手动触发）"""
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bid import BidSource
from app.utils.response import ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crawl")


@router.post("/run/{source_id}", response_model=ApiResponse, summary="手动触发一次采集")
def run_once(source_id: int, db: Session = Depends(get_db)):
    source = db.query(BidSource).filter(BidSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="采集源不存在")

    if source.code in ("ggzy", "ccgp"):
        from app.services.crawl import crawl_and_save
        try:
            result = crawl_and_save(source.code, pages=1)
            # 更新上次采集时间
            source.last_crawl_at = __import__("datetime").datetime.now()
            db.commit()
            return ApiResponse.ok(result, msg=f"{source.name} 采集完成")
        except Exception as e:
            logger.exception(f"crawl {source.code} failed: {e}")
            return ApiResponse(
                code=-1, msg=f"采集异常: {str(e)}",
                data={"source": source.code, "error": str(e)},
            )
    else:
        return ApiResponse.ok(
            msg=f"采集源 [{source.name}] (code={source.code}) 暂无内置爬虫，"
                f"请在 app/services/crawl.py 中实现",
        )


@router.post("/run-all", response_model=ApiResponse, summary="触发所有启用的采集源")
def run_all(db: Session = Depends(get_db)):
    sources = db.query(BidSource).filter(BidSource.status == 1).all()
    results = []
    for src in sources:
        if src.code in ("ggzy", "ccgp"):
            try:
                from app.services.crawl import crawl_and_save
                r = crawl_and_save(src.code, pages=1)
                src.last_crawl_at = __import__("datetime").datetime.now()
                results.append({"source": src.code, "name": src.name, **r})
            except Exception as e:
                logger.exception(f"crawl {src.code} failed: {e}")
                results.append({"source": src.code, "name": src.name, "status": "error", "message": str(e)})
        else:
            results.append({"source": src.code, "name": src.name, "status": "skipped", "message": "no built-in crawler"})
    db.commit()
    return ApiResponse.ok({"sources": results}, msg=f"已触发 {len(sources)} 个采集源")
