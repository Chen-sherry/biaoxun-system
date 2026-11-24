"""推送日志"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index

from app.database import Base
from app.models.base import TimestampMixin


class PushRecord(Base):
    """推送日志"""
    __tablename__ = "push_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    subscribe_id = Column(Integer, ForeignKey("bid_subscribe.id"), nullable=True)
    bid_ids = Column(String(2000), nullable=True, comment="本次推送的标讯 ID 列表（逗号分隔）")
    channel = Column(String(16), nullable=False, comment="email / wechat / sms")
    recipient = Column(String(255), nullable=False, comment="接收人地址")
    subject = Column(String(255), nullable=True)
    status = Column(Integer, nullable=False, default=0, comment="0 成功 1 失败")
    error_msg = Column(String(500), nullable=True)
    push_time = Column(DateTime, nullable=False, comment="推送时间")
