"""地区 / 行业 / 公告类型等基础字典表"""
from sqlalchemy import Column, Integer, String, Float

from app.database import Base
from app.models.base import TimestampMixin


class DictRegion(TimestampMixin, Base):
    """行政区划（省/市/区）"""
    __tablename__ = "dict_region"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, nullable=False, default=0, comment="父级 ID，0 为省级")
    code = Column(String(16), nullable=False, unique=True, comment="区划代码")
    name = Column(String(64), nullable=False, comment="名称")
    level = Column(Integer, nullable=False, default=1, comment="1 省 2 市 3 区")
    lng = Column(Float, nullable=True, comment="经度")
    lat = Column(Float, nullable=True, comment="纬度")
    sort = Column(Integer, nullable=False, default=0)
    status = Column(Integer, nullable=False, default=1)


class DictIndustry(TimestampMixin, Base):
    """行业分类（住建部标准或自定义）"""
    __tablename__ = "dict_industry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, nullable=False, default=0)
    code = Column(String(32), nullable=False, unique=True)
    name = Column(String(64), nullable=False)
    sort = Column(Integer, nullable=False, default=0)
    status = Column(Integer, nullable=False, default=1)


class DictNoticeType(TimestampMixin, Base):
    """公告类型：招标公告 / 中标公告 / 更正公告 / 流标公告 / 单一来源公示 ..."""
    __tablename__ = "dict_notice_type"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), nullable=False, unique=True, comment="notice_code")
    name = Column(String(64), nullable=False)
    category = Column(String(32), nullable=True, comment="大类：工程/货物/服务/政府采购")
    sort = Column(Integer, nullable=False, default=0)
    status = Column(Integer, nullable=False, default=1)
