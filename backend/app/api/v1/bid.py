"""标讯接口：列表 / 详情 / 新增 / 编辑 / 审核 / 下架"""
from datetime import datetime
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bid import BidInfo
from app.models.dict import DictNoticeType, DictIndustry, DictRegion
from app.schemas.bid import (
    BidListItem, BidDetail, BidCreateIn, BidUpdateIn,
)
from app.utils.response import ApiResponse, PageData
from app.api.deps import get_current_user, require_role
from app.models.user import SysUser

router = APIRouter(prefix="/bids")


def _bid_to_dict(b: BidInfo, db: Session) -> dict:
    """统一 ORM → dict 转换（列表 + 详情复用）"""
    return {
        "id": b.id,
        "title": b.title,
        "project_code": b.project_code,
        "notice_type": db.query(DictNoticeType.name)
            .filter(DictNoticeType.id == b.notice_type_id).scalar() if b.notice_type_id else None,
        "notice_type_id": b.notice_type_id,
        "region_code": b.region_code,
        "region_name": db.query(DictRegion.name)
            .filter(DictRegion.code == b.region_code).scalar() if b.region_code else None,
        "publish_time": b.publish_time,
        "winner_publish_time": b.winner_publish_time,
        "deadline": b.deadline,
        "tenderee": b.tenderee,
        "agency": b.agency,
        "winner_unit": b.winner_unit,
        "win_amount": float(b.win_amount) if b.win_amount is not None else None,
        "procure_type": b.procure_type,
        "customer_group": b.customer_group,
        "winner_unit_type": b.winner_unit_type,
        "budget": b.budget,
        "status": b.status,
        "is_top": b.is_top,
        "source_url": b.source_url,
        "view_count": b.view_count or 0,
    }


@router.get("", response_model=ApiResponse[PageData[dict]], summary="标讯列表")
def list_bids(
    keyword: Optional[str] = Query(None, description="关键词（标题/正文模糊）"),
    region_code: Optional[str] = None,
    industry_id: Optional[int] = None,
    notice_type_id: Optional[int] = None,
    procure_type: Optional[str] = None,
    winner_unit: Optional[str] = None,
    customer_group: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    winner_date_from: Optional[str] = None,
    winner_date_to: Optional[str] = None,
    status: int = 1,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    q = db.query(BidInfo).filter(BidInfo.status == status)

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
    if winner_unit:
        q = q.filter(BidInfo.winner_unit.like(f"%{winner_unit}%"))
    if customer_group:
        q = q.filter(BidInfo.customer_group == customer_group)
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
        items=[_bid_to_dict(b, db) for b in items],
    ))


@router.get("/{bid_id}", summary="标讯详情")
def get_bid(bid_id: int, db: Session = Depends(get_db)):
    b = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="标讯不存在")
    b.view_count = (b.view_count or 0) + 1
    db.commit()
    b = db.query(BidInfo).filter(BidInfo.id == bid_id).first()  # 刷 view_count

    data = _bid_to_dict(b, db)
    data["content"] = b.content
    data["attachments"] = [
        {"id": a.id, "file_name": a.file_name, "is_require_member": a.is_require_member}
        for a in b.attachments
    ]
    return ApiResponse.ok(data)


@router.post("", response_model=ApiResponse, summary="新增标讯（后台）")
def create_bid(
    payload: BidCreateIn,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    kw = payload.model_dump(exclude_unset=True)
    bid = BidInfo(**kw, status=0 if not payload.source_id else 1)
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return ApiResponse.ok({"id": bid.id}, msg="新增成功")


@router.put("", response_model=ApiResponse, summary="编辑标讯")
def update_bid(
    payload: BidUpdateIn,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == payload.id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    for k, v in payload.model_dump(exclude={"id"}, exclude_unset=True).items():
        setattr(bid, k, v)
    db.commit()
    db.refresh(bid)
    return ApiResponse.ok({"id": bid.id}, msg="更新成功")


@router.post("/{bid_id}/audit", response_model=ApiResponse, summary="审核通过")
def audit_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    bid.status = 1
    db.commit()
    return ApiResponse.ok(msg="审核通过")


@router.post("/{bid_id}/offline", response_model=ApiResponse, summary="下架")
def offline_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    bid.status = 2
    db.commit()
    return ApiResponse.ok(msg="已下架")


@router.post("/{bid_id}/top", response_model=ApiResponse, summary="置顶/取消置顶")
def toggle_top(
    bid_id: int,
    top: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    bid.is_top = top if top is not None else not bid.is_top
    db.commit()
    return ApiResponse.ok(msg=f"已{'置顶' if bid.is_top else '取消置顶'}")
