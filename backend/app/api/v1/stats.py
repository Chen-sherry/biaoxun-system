"""统计接口：dashboard 概览 + 趋势"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bid import BidInfo, BidSource
from app.models.dict import DictNoticeType, DictRegion
from app.utils.response import ApiResponse

router = APIRouter(prefix="/stats")


@router.get("/overview", summary="Dashboard 概览卡片")
def overview(db: Session = Depends(get_db)):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total_bids = db.query(func.count(BidInfo.id)).scalar() or 0
    published = db.query(func.count(BidInfo.id)).filter(BidInfo.status == 1).scalar() or 0
    pending = db.query(func.count(BidInfo.id)).filter(BidInfo.status == 0).scalar() or 0
    today_new = db.query(func.count(BidInfo.id)).filter(BidInfo.created_at >= today_start).scalar() or 0
    sources_enabled = db.query(func.count(BidSource.id)).filter(BidSource.status == 1).scalar() or 0
    sources_total = db.query(func.count(BidSource.id)).scalar() or 0

    # 待审核里最新 5 条
    latest_pending = (
        db.query(BidInfo)
        .filter(BidInfo.status == 0)
        .order_by(BidInfo.id.desc())
        .limit(5)
        .all()
    )
    pending_preview = [
        {"id": b.id, "title": b.title[:80], "publish_time": b.publish_time, "created_at": b.created_at}
        for b in latest_pending
    ]

    # 近 7 天每日新增
    trend = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day + timedelta(days=1)
        cnt = db.query(func.count(BidInfo.id)).filter(
            BidInfo.created_at >= day_start, BidInfo.created_at < day_end
        ).scalar() or 0
        trend.append({"date": day_start.strftime("%m-%d"), "count": cnt})

    return ApiResponse.ok({
        "cards": {
            "total_bids": total_bids,
            "published": published,
            "pending": pending,
            "today_new": today_new,
            "sources_enabled": sources_enabled,
            "sources_total": sources_total,
        },
        "trend_7d": trend,
        "latest_pending": pending_preview,
    })


@router.get("/today-by-type", summary="当日各公告类型新增数量 Top4")
def today_by_type(db: Session = Depends(get_db)):
    """当日新增标讯按公告类型分组，取数量前4"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(
            DictNoticeType.name,
            func.count(BidInfo.id).label("count")
        )
        .join(DictNoticeType, BidInfo.notice_type_id == DictNoticeType.id)
        .filter(
            BidInfo.status == 1,
            BidInfo.created_at >= today_start
        )
        .group_by(BidInfo.notice_type_id, DictNoticeType.name)
        .order_by(desc("count"))
        .limit(4)
        .all()
    )

    return ApiResponse.ok([{"type": r.name, "count": r.count} for r in rows])


@router.get("/region-top10", summary="当月标讯地区分布 Top5")
def region_top10(db: Session = Depends(get_db)):
    """当月新增标讯按省级地区分组，取数量前5"""
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 取省级地区代码前2位
    region_code_prefix = func.substr(BidInfo.region_code, 1, 2)

    rows = (
        db.query(
            DictRegion.name,
            func.count(BidInfo.id).label("count")
        )
        .join(DictRegion, func.substr(DictRegion.code, 1, 2) == region_code_prefix)
        .filter(
            DictRegion.level == 1,  # 省级
            BidInfo.status == 1,
            BidInfo.created_at >= month_start,
            BidInfo.region_code.isnot(None)
        )
        .group_by(DictRegion.name)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    return ApiResponse.ok([{"region": r.name, "count": r.count} for r in rows])
