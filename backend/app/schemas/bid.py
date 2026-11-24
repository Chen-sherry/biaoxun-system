"""标讯相关 Schema"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class BidListItem(BaseModel):
    id: int
    title: str
    notice_type: Optional[str] = None
    region_name: Optional[str] = None
    publish_time: Optional[datetime] = None
    winner_publish_time: Optional[datetime] = None
    deadline: Optional[datetime] = None
    tenderee: Optional[str] = None
    winner_unit: Optional[str] = None
    win_amount: Optional[Decimal] = None
    procure_type: Optional[str] = None
    customer_group: Optional[str] = None
    budget: Optional[str] = None
    status: int


class BidDetail(BidListItem):
    content: Optional[str] = None
    source_url: Optional[str] = None
    view_count: int = 0
    attachments: List[dict] = []


class BidQuery(BaseModel):
    keyword: Optional[str] = None
    region_code: Optional[str] = None
    industry_id: Optional[int] = None
    notice_type_id: Optional[int] = None
    procure_type: Optional[str] = None
    winner_unit: Optional[str] = None
    customer_group: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    winner_date_from: Optional[datetime] = None
    winner_date_to: Optional[datetime] = None
    status: Optional[int] = 1
    page: int = 1
    page_size: int = 20


class BidCreateIn(BaseModel):
    title: str = Field(..., max_length=512)
    project_code: Optional[str] = None
    tenderee: Optional[str] = None
    agency: Optional[str] = None
    notice_type_id: Optional[int] = None
    industry_id: Optional[int] = None
    region_code: Optional[str] = None
    publish_time: Optional[datetime] = None
    deadline: Optional[datetime] = None
    budget: Optional[str] = None
    content: Optional[str] = None
    source_url: Optional[str] = None
    source_id: Optional[int] = None
    # v0.2 新增字段
    winner_unit: Optional[str] = None
    win_amount: Optional[Decimal] = None
    procure_type: Optional[str] = None
    winner_publish_time: Optional[datetime] = None
    customer_group: Optional[str] = None
    winner_unit_type: Optional[str] = None


class BidUpdateIn(BidCreateIn):
    id: int


# === AI 匹配相关 Schema ===

class AIMatchRequest(BaseModel):
    """企业语义匹配请求"""
    user_id: Optional[int] = None
    company_name: Optional[str] = None
    keywords: Optional[List[str]] = Field(default=None, description="企业订阅关键词；不传则从数据库取该用户的订阅关键词")
    days: int = Field(default=30, description="取最近 N 天的标讯参与匹配", ge=1, le=3650)
    limit: int = Field(default=10, description="返回 Top-N", ge=1, le=50)


class MatchedBid(BaseModel):
    bid_id: int
    title: str
    score: float
    reason: Optional[str] = None
    source_url: Optional[str] = None
    publish_time: Optional[datetime] = None
