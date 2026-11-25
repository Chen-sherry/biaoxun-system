"""
门户公开接口（public API）
- 所有 status=1 的公开标讯都能访问
- 不需要登录（login 可选带 token，带了能看到更多字段）
- AI 搜索可以匿名调用，也可以登录后调用
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, defer

from app.database import get_db
from app.models.bid import BidInfo, BidSource
from app.models.dict import DictNoticeType, DictIndustry, DictRegion
from app.utils.response import ApiResponse, PageData

router = APIRouter(prefix="/public", tags=["门户公开接口"])


def _bid_to_public_dict(b: BidInfo, db: Session) -> dict:
    """公开字段（隐藏内部字段）"""
    return {
        "id": b.id,
        "title": b.title,
        "project_code": b.project_code,
        "notice_type": db.query(DictNoticeType.name)
            .filter(DictNoticeType.id == b.notice_type_id).scalar() if b.notice_type_id else None,
        "region_code": b.region_code,
        "region_name": db.query(DictRegion.name)
            .filter(DictRegion.code == b.region_code).scalar() if b.region_code else None,
        "publish_time": b.publish_time,
        "winner_publish_time": b.winner_publish_time,
        "deadline": b.deadline,
        "tenderee": b.tenderee,
        "winner_unit": b.winner_unit,
        "win_amount": float(b.win_amount) if b.win_amount is not None else None,
        "procure_type": b.procure_type,
        "customer_group": b.customer_group,
        "industry_name": db.query(DictIndustry.name)
            .filter(DictIndustry.id == b.industry_id).scalar() if b.industry_id else None,
        "budget": b.budget,
        "source_url": b.source_url,
        "view_count": b.view_count or 0,
    }


@router.get("/bids", summary="门户：公开标讯列表（无需登录）")
def public_list_bids(
    keyword: Optional[str] = Query(None, description="关键词（标题/正文模糊）"),
    region_code: Optional[str] = None,
    industry_id: Optional[int] = None,
    notice_type_id: Optional[int] = None,
    procure_type: Optional[str] = None,
    customer_group: Optional[str] = None,
    winner_unit: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    winner_date_from: Optional[str] = None,
    winner_date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """门户搜索的核心接口。status 锁定=1（已发布），支持 AI 搜索关键词走 OR 匹配。"""
    q = db.query(BidInfo).filter(BidInfo.status == 1).options(
        defer(BidInfo.content), defer(BidInfo.content_text))

    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(BidInfo.title.like(like), BidInfo.content_text.like(like)))
    if region_code:
        q = q.filter(BidInfo.region_code == region_code)
    if industry_id:
        q = q.filter(BidInfo.industry_id == industry_id)
    if notice_type_id:
        q = q.filter(BidInfo.notice_type_id == notice_type_id)
    if procure_type:
        q = q.filter(BidInfo.procure_type == procure_type)
    if customer_group:
        q = q.filter(BidInfo.customer_group == customer_group)
    if winner_unit:
        q = q.filter(BidInfo.winner_unit.like(f"%{winner_unit}%"))
    if date_from:
        q = q.filter(BidInfo.publish_time >= date_from)
    if date_to:
        q = q.filter(BidInfo.publish_time <= date_to)
    if winner_date_from:
        q = q.filter(BidInfo.winner_publish_time >= winner_date_from)
    if winner_date_to:
        q = q.filter(BidInfo.winner_publish_time <= winner_date_to)

    total = q.count()
    items = (
        q.order_by(BidInfo.is_top.desc(), BidInfo.publish_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ApiResponse.ok(PageData(
        total=total, page=page, page_size=page_size,
        items=[_bid_to_public_dict(b, db) for b in items],
    ))


@router.get("/bids/hot", summary="门户：热门标讯（首页）")
def hot_bids(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """按发布时间倒序 + 置顶优先，返回首页的热门标讯列表。"""
    items = (
        db.query(BidInfo)
        .filter(BidInfo.status == 1)
        .options(defer(BidInfo.content), defer(BidInfo.content_text))
        .order_by(BidInfo.is_top.desc(), BidInfo.publish_time.desc())
        .limit(limit)
        .all()
    )
    return ApiResponse.ok([_bid_to_public_dict(b, db) for b in items])


@router.get("/bids/{bid_id}", summary="门户：标讯详情（无需登录）")
def public_bid_detail(bid_id: int, db: Session = Depends(get_db)):
    b = db.query(BidInfo).filter(BidInfo.id == bid_id, BidInfo.status == 1).first()
    if not b:
        raise HTTPException(status_code=404, detail="标讯不存在或已下架")
    b.view_count = (b.view_count or 0) + 1
    db.commit()

    data = _bid_to_public_dict(b, db)
    data["content"] = b.content  # 门户可看正文
    data["attachments"] = [
        {"id": a.id, "file_name": a.file_name}
        for a in b.attachments
    ]
    return ApiResponse.ok(data)


@router.get("/stats/portal", summary="门户首页统计")
def portal_stats(db: Session = Depends(get_db)):
    """门户首页的统计数字（总标讯数 / 今日新增 / 启用采集源）"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return ApiResponse.ok({
        "total_bids": db.query(func.count(BidInfo.id)).filter(BidInfo.status == 1).scalar() or 0,
        "today_new": db.query(func.count(BidInfo.id)).filter(
            BidInfo.status == 1, BidInfo.created_at >= today_start
        ).scalar() or 0,
        "sources_enabled": db.query(func.count(BidSource.id)).filter(BidSource.status == 1).scalar() or 0,
    })


@router.get("/dicts/notice-types", summary="门户：公告类型字典")
def public_notice_types(db: Session = Depends(get_db)):
    items = db.query(DictNoticeType).filter(DictNoticeType.status == 1).order_by(DictNoticeType.sort).all()
    return ApiResponse.ok([
        {"id": i.id, "name": i.name, "category": i.category} for i in items
    ])


@router.get("/dicts/regions", summary="门户：地区字典")
def public_regions(parent_id: int = 0, db: Session = Depends(get_db)):
    items = db.query(DictRegion).filter(DictRegion.parent_id == parent_id).order_by(DictRegion.code).all()
    return ApiResponse.ok([
        {"code": i.code, "name": i.name, "parent_id": i.parent_id} for i in items
    ])
