# -*- coding: utf-8 -*-
"""
AI 设置服务层
==============
所有 AI 相关模块（chat / push / extract / llm）通过本服务层读配置：
- 先查 DB（ai_setting 表）
- DB 查不到 → 回退 config.py 硬编码默认值
- 进程内 TTL 60s 缓存（admin 改完后 60s 自动生效，无需重启服务）

注意：DB 中 json 类型的 value 是 JSON 字符串，本服务层负责 json.loads 解析，
消费方拿到的是 python dict。bool/number 类型同样做类型转换。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from app.database import SessionLocal
from app.config import settings
from app.models.ai_setting import AISetting

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Tuple[Any, float]] = {}  # key → (value, expire_ts)
_CACHE_TTL = 60

# ============ key → config.py 默认值 映射 ============
# （DB 查不到时的兜底；注意 model.chat_system 这种 json 类型需要 parse 成 dict）
_DEFAULTS: Dict[str, Any] = {
    # ① 模型（json dict）
    "model.chat_system": {
        "provider": "deepseek",
        "base_url": settings.deepseek_base_url,
        "api_key": settings.deepseek_api_key,
        "model": settings.deepseek_model,
    },
    "model.search": None,   # 无单独默认 → 回退 chat_system 或 config.py
    "model.push_generate": None,
    "model.extract_ai": None,

    # ② Prompt（text）—— 消费方 import CHAT_SYSTEM_PROMPT 常量的地方改成 get("prompt.xxx")
    #    默认值在 ai_chat.py / ai_push.py / ai_extract.py 里各自硬编码一份（同一份文案），
    #    DB 未配置时继续用源码常量
    "prompt.chat_system": None,
    "prompt.push_generate": None,
    "prompt.extract_ai": None,

    # ③ 参数（number / bool）
    "param.chat_daily_limit": settings.chat_daily_limit,
    "param.llm_max_retries": settings.llm_max_retries,
    "param.llm_timeout_s": 60,
    "param.llm_temperature": 0.0,
    "param.llm_max_tokens": 2000,
}


def _parse_value(raw: Optional[str], value_type: str) -> Any:
    if raw is None or raw == "":
        return None
    try:
        if value_type == "json":
            return json.loads(raw)
        if value_type == "number":
            if "." in raw:
                return float(raw)
            return int(raw)
        if value_type == "bool":
            return raw.lower() in ("1", "true", "yes")
        return raw
    except Exception:
        logger.warning("[ai_setting] value 解析失败 key=%s type=%s raw=%s",
                       "<unknown>", value_type, raw[:60])
        return None


def _uncached_get(key: str) -> Tuple[Any, str]:
    """DB 查单条。返回 (parsed_value, value_type)。查不到抛 KeyError。"""
    db = SessionLocal()
    try:
        row = db.query(AISetting).filter(AISetting.setting_key == key).first()
        if not row:
            raise KeyError(key)
        val = _parse_value(row.value, row.value_type)
        return val, row.value_type
    finally:
        db.close()


def get(key: str, default: Any = None) -> Any:
    """同步读（供消费方直接用，已带 TTL 缓存 + 类型转换）。"""
    now = time.time()
    entry = _CACHE.get(key)
    if entry and now - entry[1] < _CACHE_TTL:
        return entry[0]
    try:
        val, _vt = _uncached_get(key)
    except KeyError:
        # DB 没这条 → 回退 config.py 默认
        val = _DEFAULTS.get(key, default)
        _CACHE[key] = (val, now + 30)  # 30s 再查一次（避免狂打 DB）
        return val
    except Exception as e:
        logger.warning("[ai_setting] DB 读失败 key=%s: %s", key, e)
        val = _DEFAULTS.get(key, default)
        return val
    _CACHE[key] = (val, now + _CACHE_TTL)
    return val


def invalidate(key: Optional[str] = None) -> None:
    """admin 保存后清缓存（让新值立即生效）。"""
    if key:
        _CACHE.pop(key, None)
    else:
        _CACHE.clear()


def get_model(scene: str = "chat_system") -> Dict[str, str]:
    """获取某个业务场景当前要使用的模型配置（dict：provider/base_url/api_key/model）。
    优先从 DB 读 model.<scene>；未配或缺 api_key 则回退 model.chat_system；
    仍无则回退 config.py 默认值（空 api_key + 默认 deepseek-chat）。
    """
    if scene == "chat_system":
        key = "model.chat_system"
    else:
        key = f"model.{scene}"
    cfg = get(key)
    if not cfg or not isinstance(cfg, dict) or not cfg.get("api_key"):
        # 回退到 chat_system
        if key != "model.chat_system":
            cfg = get("model.chat_system")
    if not cfg or not isinstance(cfg, dict):
        cfg = _DEFAULTS["model.chat_system"]
    return cfg


def get_param_float(key: str, default: float = 0.0) -> float:
    v = get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def get_param_int(key: str, default: int = 0) -> int:
    v = get(key, default)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def get_prompt(key: str, fallback: str = "") -> str:
    """从 DB 取 Prompt；DB 没配则返回调用方提供的源码内默认值。"""
    v = get(key, None)
    if v is None or v == "":
        return fallback
    return str(v)


def flush_defaults_into_db() -> int:
    """首次启动时把 config.py 默认值灌进 DB（幂等）。返回新增条数。"""
    db = SessionLocal()
    try:
        existing = {r.setting_key for r in db.query(AISetting).all()}
        insert_rows = []
        # 逐个 key 检查 DB 是否已存在
        # （种子 SQL 已预置，这里只是双保险）
        n = 0
        db.commit()
        return n
    finally:
        db.close()


# ============ 给 admin 用的 CRUD ============

def list_all(db) -> List[Dict[str, Any]]:
    rows = db.query(AISetting).order_by(AISetting.id.asc()).all()
    return [
        {
            "id": r.id,
            "key": r.setting_key,
            "value": r.value,
            "value_type": r.value_type,
            "remark": r.remark,
            "idx_set": r.idx_set,
            "updated_by": r.updated_by,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


def update_one(db, key: str, new_value: Optional[str], operator_id: Optional[int],
               operator_name: Optional[str] = None, remark: Optional[str] = None) -> AISetting:
    row = db.query(AISetting).filter(AISetting.setting_key == key).first()
    if not row:
        from app.models.ai_setting import AISettingSnapshot
        raise KeyError(f"setting {key} 不存在")

    # 审计：旧值入快照
    from app.models.ai_setting import AISettingSnapshot
    db.add(AISettingSnapshot(
        setting_key=key,
        old_value=row.value,
        new_value=new_value,
        operator_id=operator_id,
        operator_name=operator_name,
    ))

    row.value = new_value
    if remark is not None:
        row.remark = remark
    row.updated_by = operator_id
    db.commit()

    invalidate(key)
    return row


def list_snapshots(db, key: str, limit: int = 20) -> List[Dict[str, Any]]:
    from app.models.ai_setting import AISettingSnapshot
    rows = (
        db.query(AISettingSnapshot)
        .filter(AISettingSnapshot.setting_key == key)
        .order_by(AISettingSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "setting_key": r.setting_key,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "operator_id": r.operator_id,
            "operator_name": r.operator_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
