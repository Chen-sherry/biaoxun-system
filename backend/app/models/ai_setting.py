# -*- coding: utf-8 -*-
"""AI 设置表：后台可改 + 热更（含 Prompt / 模型 / 参数）"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.database import Base


class AISetting(Base):
    __tablename__ = "ai_setting"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(64), unique=True, nullable=False, index=True)
    value       = Column(Text, nullable=True)
    value_type  = Column(String(16), nullable=False, default="text")   # text/json/number/bool
    remark      = Column(String(128), nullable=False, default="")
    idx_set     = Column(String(64), nullable=True)                    # model/prompt/param
    updated_by  = Column(Integer, nullable=True)
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AISettingSnapshot(Base):
    __tablename__ = "ai_setting_snapshot"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    setting_key   = Column(String(64), nullable=False, index=True)
    old_value     = Column(Text, nullable=True)
    new_value     = Column(Text, nullable=True)
    operator_id   = Column(Integer, nullable=True)
    operator_name = Column(String(64), nullable=True)
    created_at    = Column(DateTime, server_default=func.now(), index=True)
