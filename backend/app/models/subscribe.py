"""订阅表"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index

from app.database import Base
from app.models.base import TimestampMixin


class BidSubscribe(TimestampMixin, Base):
    """用户订阅：关键词 + 地区 + 推送方式"""
    __tablename__ = "bid_subscribe"
    __table_args__ = (
        Index("idx_sub_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False)
    keyword = Column(String(255), nullable=False, comment="关键词（空格/逗号分隔多词）")
    region_code = Column(String(16), nullable=True, comment="限定地区代码")
    industry_id = Column(Integer, ForeignKey("dict_industry.id"), nullable=True)
    notice_type_id = Column(Integer, ForeignKey("dict_notice_type.id"), nullable=True)
    push_email = Column(Boolean, nullable=False, default=True)
    push_wechat = Column(Boolean, nullable=False, default=False, comment="预留企业微信推送")
    frequency = Column(String(16), nullable=False, default="daily", comment="daily / hourly / realtime")
    last_push_at = Column(DateTime, nullable=True)
    status = Column(Integer, nullable=False, default=1, comment="1 启用 0 禁用")
