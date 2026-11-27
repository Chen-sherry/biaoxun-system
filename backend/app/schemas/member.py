"""会员套餐 & 订单 Schema"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class PackageCreateIn(BaseModel):
    name: str = Field(..., max_length=64, description="套餐名称")
    code: str = Field(..., max_length=32, description="套餐编码")
    price: float = Field(..., ge=0, description="原价")
    sale_price: float = Field(..., ge=0, description="售价")
    duration_days: int = Field(..., ge=1, description="有效天数")
    level: int = Field(default=1, ge=1, description="等级")
    max_subscribe: int = Field(default=20, ge=0, description="最大订阅数")
    allow_export: int = Field(default=1, description="1 允许 0 不允许")
    allow_contact: int = Field(default=1, description="是否可见联系方式")
    description: Optional[str] = Field(None, max_length=500)
    sort: int = Field(default=0)
    status: int = Field(default=1)


class PackageUpdateIn(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    price: Optional[float] = Field(None, ge=0)
    sale_price: Optional[float] = Field(None, ge=0)
    duration_days: Optional[int] = Field(None, ge=1)
    level: Optional[int] = Field(None, ge=1)
    max_subscribe: Optional[int] = Field(None, ge=0)
    allow_export: Optional[int] = None
    allow_contact: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    sort: Optional[int] = None
    status: Optional[int] = None


class OrderCreateIn(BaseModel):
    package_id: int = Field(..., description="套餐 ID")
