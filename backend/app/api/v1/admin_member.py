"""后台：会员套餐 & 订单管理"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.member import MemberPackage, MemberOrder
from app.models.user import SysUser
from app.api.deps import require_role
from app.utils.response import ApiResponse, PageData
from app.schemas.member import PackageCreateIn, PackageUpdateIn

router = APIRouter(prefix="/admin/member")


# ============================================================
# 套餐管理
# ============================================================

def _pkg_to_dict(p: MemberPackage) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "code": p.code,
        "price": float(p.price),
        "sale_price": float(p.sale_price),
        "duration_days": p.duration_days,
        "level": p.level,
        "max_subscribe": p.max_subscribe,
        "allow_export": p.allow_export,
        "allow_contact": p.allow_contact,
        "description": p.description,
        "sort": p.sort,
        "status": p.status,
        "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
        "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
    }


@router.get("/packages", response_model=ApiResponse, summary="全量套餐列表（含下架）")
def list_all_packages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "ops")),
):
    q = db.query(MemberPackage)
    total = q.count()
    items = q.order_by(MemberPackage.sort.asc(), MemberPackage.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return ApiResponse.ok(PageData(total=total, page=page, page_size=page_size, items=[_pkg_to_dict(p) for p in items]).model_dump())


@router.post("/packages", response_model=ApiResponse, summary="新增套餐")
def create_package(
    payload: PackageCreateIn,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin")),
):
    # 检查 code 唯一性
    exists = db.query(MemberPackage).filter(MemberPackage.code == payload.code).first()
    if exists:
        return ApiResponse.fail(msg=f"套餐编码 '{payload.code}' 已存在")
    pkg = MemberPackage(**payload.model_dump())
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return ApiResponse.ok({"id": pkg.id}, msg="新增成功")


@router.put("/packages/{pkg_id}", response_model=ApiResponse, summary="修改套餐")
def update_package(
    pkg_id: int,
    payload: PackageUpdateIn,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin")),
):
    pkg = db.query(MemberPackage).filter(MemberPackage.id == pkg_id).first()
    if not pkg:
        return ApiResponse.fail(msg="套餐不存在")
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(pkg, k, v)
    db.commit()
    return ApiResponse.ok(msg="更新成功")


@router.delete("/packages/{pkg_id}", response_model=ApiResponse, summary="删除套餐")
def delete_package(
    pkg_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin")),
):
    pkg = db.query(MemberPackage).filter(MemberPackage.id == pkg_id).first()
    if not pkg:
        return ApiResponse.fail(msg="套餐不存在")
    # 检查是否有关联的已支付订单
    active_orders = db.query(MemberOrder).filter(
        MemberOrder.package_id == pkg_id, MemberOrder.status == 1
    ).count()
    if active_orders > 0:
        return ApiResponse.fail(msg=f"该套餐下有 {active_orders} 笔已支付订单，建议先下架而非删除")
    db.delete(pkg)
    db.commit()
    return ApiResponse.ok(msg="删除成功")


# ============================================================
# 订单管理
# ============================================================

@router.get("/orders", response_model=ApiResponse, summary="订单列表（筛选+分页）")
def list_orders(
    status: Optional[int] = Query(None, description="0待支付 1已支付 2已取消 3已退款"),
    keyword: Optional[str] = Query(None, description="搜索订单号"),
    user_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="截止日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "ops")),
):
    q = db.query(MemberOrder)
    if status is not None:
        q = q.filter(MemberOrder.status == status)
    if keyword:
        q = q.filter(MemberOrder.order_no.like(f"%{keyword}%"))
    if user_id is not None:
        q = q.filter(MemberOrder.user_id == user_id)
    if date_from:
        q = q.filter(MemberOrder.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        q = q.filter(MemberOrder.created_at <= datetime.strptime(date_to, "%Y-%m-%d") + __import__('datetime').timedelta(days=1))

    total = q.count()
    raw_items = q.order_by(MemberOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for o in raw_items:
        pkg = db.query(MemberPackage).filter(MemberPackage.id == o.package_id).first()
        u = db.query(SysUser).filter(SysUser.id == o.user_id).first()
        items.append({
            "id": o.id,
            "order_no": o.order_no,
            "user_id": o.user_id,
            "username": u.username if u else None,
            "nickname": u.nickname if u else None,
            "package_id": o.package_id,
            "package_name": pkg.name if pkg else None,
            "amount": float(o.amount),
            "pay_type": o.pay_type,
            "pay_time": o.pay_time.isoformat() if o.pay_time else None,
            "start_date": o.start_date.isoformat() if o.start_date else None,
            "end_date": o.end_date.isoformat() if o.end_date else None,
            "status": o.status,
            "trade_no": o.trade_no,
            "remark": o.remark,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return ApiResponse.ok(PageData(total=total, page=page, page_size=page_size, items=items).model_dump())


@router.get("/orders/{order_no}", response_model=ApiResponse, summary="订单详情")
def order_detail(
    order_no: str,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "ops")),
):
    o = db.query(MemberOrder).filter(MemberOrder.order_no == order_no).first()
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    pkg = db.query(MemberPackage).filter(MemberPackage.id == o.package_id).first()
    u = db.query(SysUser).filter(SysUser.id == o.user_id).first()
    return ApiResponse.ok({
        "id": o.id,
        "order_no": o.order_no,
        "user_id": o.user_id,
        "username": u.username if u else None,
        "nickname": u.nickname if u else None,
        "phone": u.phone if u else None,
        "package_id": o.package_id,
        "package_name": pkg.name if pkg else None,
        "amount": float(o.amount),
        "pay_type": o.pay_type,
        "pay_time": o.pay_time.isoformat() if o.pay_time else None,
        "start_date": o.start_date.isoformat() if o.start_date else None,
        "end_date": o.end_date.isoformat() if o.end_date else None,
        "status": o.status,
        "trade_no": o.trade_no,
        "remark": o.remark,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if getattr(o, "updated_at", None) else None,
    })


@router.post("/orders/{order_no}/refund", response_model=ApiResponse, summary="退款")
def refund_order(
    order_no: str,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin")),
):
    o = db.query(MemberOrder).filter(MemberOrder.order_no == order_no).first()
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.status != 1:
        return ApiResponse.fail(msg="只有已支付订单才能退款")
    o.status = 3
    db.commit()
    return ApiResponse.ok(msg="退款成功")
