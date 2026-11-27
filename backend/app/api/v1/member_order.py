"""会员订单（前台用户侧）"""
from datetime import datetime, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.member import MemberOrder, MemberPackage
from app.api.deps import get_current_user
from app.models.user import SysUser
from app.utils.response import ApiResponse, PageData
from app.schemas.member import OrderCreateIn

router = APIRouter(prefix="/member-orders")


@router.get("/my-status", response_model=ApiResponse, summary="我的会员状态")
def my_member_status(
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """返回当前用户的会员状态：是否有效会员、等级、套餐名、到期时间、剩余天数。"""
    now = datetime.now()
    active_order = (
        db.query(MemberOrder)
        .join(MemberPackage)
        .filter(
            MemberOrder.user_id == user.id,
            MemberOrder.status == 1,
            MemberOrder.start_date <= now,
            MemberOrder.end_date >= now,
        )
        .order_by(MemberOrder.end_date.desc())
        .first()
    )
    if not active_order:
        return ApiResponse.ok({
            "is_member": False,
            "level": 0,
            "package_name": None,
            "end_date": None,
            "remaining_days": 0,
        })
    pkg = db.query(MemberPackage).filter(MemberPackage.id == active_order.package_id).first()
    remaining = (active_order.end_date - now).days
    return ApiResponse.ok({
        "is_member": True,
        "level": pkg.level if pkg else 0,
        "package_name": pkg.name if pkg else None,
        "end_date": active_order.end_date.isoformat(),
        "remaining_days": max(remaining, 0),
    })


@router.get("", response_model=ApiResponse, summary="我的订单列表（分页）")
def my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    q = db.query(MemberOrder).filter(MemberOrder.user_id == user.id)
    total = q.count()
    items = q.order_by(MemberOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 补充套餐名称
    result = []
    for o in items:
        pkg = db.query(MemberPackage).filter(MemberPackage.id == o.package_id).first()
        result.append({
            "id": o.id,
            "order_no": o.order_no,
            "package_name": pkg.name if pkg else None,
            "amount": float(o.amount),
            "pay_type": o.pay_type,
            "pay_time": o.pay_time.isoformat() if o.pay_time else None,
            "start_date": o.start_date.isoformat() if o.start_date else None,
            "end_date": o.end_date.isoformat() if o.end_date else None,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return ApiResponse.ok(PageData(total=total, page=page, page_size=page_size, items=result).model_dump())


@router.post("", response_model=ApiResponse, summary="创建订单（待支付）")
def create_order(
    payload: OrderCreateIn,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    pkg = db.query(MemberPackage).filter(MemberPackage.id == payload.package_id, MemberPackage.status == 1).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="套餐不存在或已下架")

    # 检查是否有同套餐未支付订单
    pending = (
        db.query(MemberOrder)
        .filter(MemberOrder.user_id == user.id, MemberOrder.package_id == pkg.id, MemberOrder.status == 0)
        .first()
    )
    if pending:
        return ApiResponse.ok({"order_no": pending.order_no, "amount": float(pending.amount)}, msg="已有待支付订单")

    order = MemberOrder(
        order_no=f"BID{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
        user_id=user.id,
        package_id=pkg.id,
        amount=pkg.sale_price,
        status=0,
    )
    db.add(order)
    db.commit()
    return ApiResponse.ok({"order_no": order.order_no, "amount": float(order.amount)}, msg="订单创建成功")


@router.post("/{order_no}/pay", response_model=ApiResponse, summary="模拟支付成功回调")
def pay_order(
    order_no: str,
    pay_type: str = Query("manual", description="wechat / alipay / manual"),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    order = db.query(MemberOrder).filter(MemberOrder.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能支付自己的订单")
    if order.status != 0:
        return ApiResponse.fail(msg="订单状态不可支付")

    pkg = db.query(MemberPackage).filter(MemberPackage.id == order.package_id).first()
    start = datetime.now()
    order.status = 1
    order.pay_time = start
    order.pay_type = pay_type
    order.start_date = start
    order.end_date = start + timedelta(days=pkg.duration_days)
    order.trade_no = f"FAKE_{uuid.uuid4().hex.upper()}"
    db.commit()
    return ApiResponse.ok(msg="支付成功")
