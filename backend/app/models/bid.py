"""标讯主表、附件表、采集源表"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, UniqueConstraint,
    Numeric,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class BidInfo(TimestampMixin, Base):
    """标讯主表"""
    __tablename__ = "bid_info"
    __table_args__ = (
        Index("idx_bid_region_pub", "region_code", "publish_time"),
        Index("idx_bid_deadline", "deadline"),
        Index("idx_bid_notice_type", "notice_type_id"),
        Index("idx_bid_industry", "industry_id"),
        Index("idx_bid_status", "status"),
        Index("idx_bid_winner_publish", "winner_publish_time"),
        Index("idx_bid_customer_group", "customer_group"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False, comment="公告标题")
    project_code = Column(String(128), nullable=True, index=True, comment="项目编号")
    tenderee = Column(String(255), nullable=True, comment="招标人/采购人")
    agency = Column(String(255), nullable=True, comment="招标代理机构")
    notice_type_id = Column(Integer, ForeignKey("dict_notice_type.id"), nullable=True, comment="公告类型")
    industry_id = Column(Integer, ForeignKey("dict_industry.id"), nullable=True, comment="行业分类")
    region_code = Column(String(16), nullable=True, index=True, comment="地区代码")
    publish_time = Column(DateTime, nullable=True, comment="公告发布时间（原文）")
    deadline = Column(DateTime, nullable=True, comment="报名/投标截止时间")
    budget = Column(String(64), nullable=True, comment="预算金额（原字符串，保留币种）")
    content = Column(Text, nullable=True, comment="公告正文 HTML")
    content_text = Column(Text, nullable=True, comment="公告正文纯文本（用于检索）")

    # === v0.2 新增业务字段 ===
    winner_unit = Column(String(255), nullable=True, comment="中标单位")
    win_amount = Column(Numeric(18, 2), nullable=True, comment="中标金额")
    procure_type = Column(String(32), nullable=True, comment="招采类型（中标/招采/询价等）")
    winner_publish_time = Column(DateTime, nullable=True, comment="中标/成交时间（与 publish_time 双保留）")
    customer_group = Column(String(64), nullable=True, comment="客群（政务/国企/民企）")
    winner_unit_type = Column(String(64), nullable=True, comment="中标单位类型")

    source_id = Column(Integer, ForeignKey("bid_source.id"), nullable=True, comment="采集源")
    source_url = Column(String(512), nullable=True, comment="原文地址")
    dedup_key = Column(String(128), nullable=True, index=True, comment="去重指纹（sha1(source_keyword+news_id+title)）")
    view_count = Column(Integer, nullable=False, default=0, comment="浏览量")
    status = Column(Integer, nullable=False, default=1, comment="0 待审核 1 已发布 2 已下架 3 已归档")
    is_top = Column(Boolean, nullable=False, default=False, comment="是否置顶")
    remark = Column(Text, nullable=True, comment="内部备注")

    attachments = relationship("BidAttachment", back_populates="bid")


class BidAttachment(TimestampMixin, Base):
    """标讯附件（招标文件 PDF 等）"""
    __tablename__ = "bid_attachment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bid_id = Column(Integer, ForeignKey("bid_info.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    oss_key = Column(String(512), nullable=False, comment="OSS 对象 key")
    file_size = Column(Integer, nullable=True, comment="字节")
    mime_type = Column(String(128), nullable=True)
    is_require_member = Column(Boolean, nullable=False, default=True, comment="会员才能下载")
    download_count = Column(Integer, nullable=False, default=0)

    bid = relationship("BidInfo", back_populates="attachments")


class BidSource(TimestampMixin, Base):
    """采集源配置：爬虫源 / 接口源 / 手动录入"""
    __tablename__ = "bid_source"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="采集源名称")
    code = Column(String(64), nullable=False, unique=True, comment="唯一编码")
    source_type = Column(Integer, nullable=False, default=1, comment="1 爬虫 2 开放接口 3 手动 4 Excel")
    base_url = Column(String(512), nullable=True, comment="根地址")
    list_url_rule = Column(Text, nullable=True, comment="列表页 URL 模板")
    detail_url_rule = Column(Text, nullable=True, comment="详情页 URL 模板")
    list_selector = Column(String(255), nullable=True, comment="列表项 CSS/XPath")
    field_rules = Column(Text, nullable=True, comment="字段提取规则（JSON）")
    request_headers = Column(Text, nullable=True, comment="自定义 Header（JSON）")
    request_params = Column(Text, nullable=True, comment="请求参数（JSON）")
    http_method = Column(String(16), nullable=False, default="GET")
    interval_minutes = Column(Integer, nullable=False, default=60, comment="采集间隔（分钟）")
    last_crawl_at = Column(DateTime, nullable=True, comment="上次采集时间")
    status = Column(Integer, nullable=False, default=1, comment="1 启用 0 禁用")
    description = Column(String(255), nullable=True)
