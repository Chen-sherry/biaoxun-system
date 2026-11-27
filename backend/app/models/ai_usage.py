# -*- coding: utf-8 -*-
"""AI 调用用量日志：每次 LLM 调用落一条，后台按日/周/月统计成本"""
from sqlalchemy import Column, BigInteger, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class AIUsageLog(Base):
    __tablename__ = "ai_usage_log"

    id                = Column(BigInteger, primary_key=True, autoincrement=True)
    tag               = Column(String(32), nullable=False, default="", index=True)
    model             = Column(String(64), nullable=False, default="")
    prompt_tokens     = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens      = Column(Integer, nullable=False, default=0)
    latency_ms        = Column(Integer, nullable=False, default=0)
    created_at        = Column(DateTime, server_default=func.now(), index=True)
