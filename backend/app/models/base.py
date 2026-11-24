"""模型基类：统一创建时间 / 更新时间"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, func

from app.database import Base


class TimestampMixin:
    """时间戳混入"""
    created_at = Column(
        DateTime, nullable=False, server_default=func.current_timestamp(),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime, nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="更新时间",
    )


class SoftDeleteMixin:
    """软删除混入"""
    deleted = Column(Integer, nullable=False, default=0, comment="0 正常 1 删除")
