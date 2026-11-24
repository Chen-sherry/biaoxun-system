"""会员套餐、订单"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index

from app.database import Base
from app.models.base import TimestampMixin


class MemberPackage(TimestampMixin, Base):
    """会员套餐"""
    __tablename__ = "member_package"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, comment="套餐名称，如「年度会员」")
    code = Column(String(32), nullable=False, unique=True)
    price = Column(Float, nullable=False, default=0, comment="原价")
    sale_price = Column(Float, nullable=False, default=0, comment="售价")
    duration_days = Column(Integer, nullable=False, default=365, comment="有效天数")
    level = Column(Integer, nullable=False, default=1, comment="1 基础会员 2 高级会员 ...")
    max_subscribe = Column(Integer, nullable=False, default=20, comment="最大订阅数")
    allow_export = Column(Integer, nullable=False, default=1, comment="1 允许 0 不允许")
    allow_contact = Column(Integer, nullable=False, default=1, comment="是否可见联系方式")
    description = Column(String(500), nullable=True)
    sort = Column(Integer, nullable=False, default=0)
    status = Column(Integer, nullable=False, default=1)


class MemberOrder(TimestampMixin, Base):
    """会员订单"""
    __tablename__ = "member_order"
    __table_args__ = (Index("idx_order_user", "user_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(64), nullable=False, unique=True, comment="订单号")
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("member_package.id"), nullable=False)
    amount = Column(Float, nullable=False, comment="实付金额")
    pay_type = Column(String(16), nullable=True, comment="wechat / alipay / manual")
    pay_time = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True, comment="会员生效起始")
    end_date = Column(DateTime, nullable=True, comment="会员到期时间")
    status = Column(Integer, nullable=False, default=0, comment="0 待支付 1 已支付 2 已取消 3 已退款")
    trade_no = Column(String(128), nullable=True, comment="第三方支付流水号")
    remark = Column(String(255), nullable=True)
