"""会员订单"""
from datetime import datetime, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.member import MemberOrder, MemberPackage
from app.api.deps import get_current_user
from app.models.user import SysUser
from app.utils.response import ApiResponse

router = APIRouter(prefix="/member-orders")


@router.get("", response_model=ApiResponse, summary="我的订单列表")
def my_orders(
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    items = db.query(MemberOrder).filter(MemberOrder.user_id == user.id).order_by(MemberOrder.id.desc()).all()
    return ApiResponse.ok(items)


@router.post("", response_model=ApiResponse, summary="创建订单（待支付）")
def create_order(
    package_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    pkg = db.query(MemberPackage).filter(MemberPackage.id == package_id, MemberPackage.status == 1).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="套餐不存在")

    order = MemberOrder(
        order_no=f"BID{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
        user_id=user.id,
        package_id=pkg.id,
        amount=pkg.sale_price,
        status=0,
    )
    db.add(order)
    db.commit()
    return ApiResponse.ok({"order_no": order.order_no, "amount": order.amount}, msg="订单创建成功")


@router.post("/{order_no}/pay", response_model=ApiResponse, summary="模拟支付成功回调")
def pay_order(
    order_no: str,
    pay_type: str = "manual",
    db: Session = Depends(get_db),
):
    order = db.query(MemberOrder).filter(MemberOrder.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
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
