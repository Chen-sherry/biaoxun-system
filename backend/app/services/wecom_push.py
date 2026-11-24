# -*- coding: utf-8 -*-
"""
推送通道：企业微信群聊机器人
Webhook 从 .env WECOM_WEBHOOK 读取，**不硬编码**。
发送前务必确认环境变量已配好；未配置时所有函数返回 False 静默跳过。

⚠️  生产推送前请手动测试单条消息、确认消息格式正确，**不要批量无差别发**。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _get_webhook() -> str:
    """从 settings 读取 webhook，未配置返回空串"""
    return (settings.wecom_webhook or "").strip()


def _webhook_available() -> bool:
    return bool(_get_webhook())


async def send_markdown(
    title: str,
    content: str,
    mentioned_mobiles: Optional[list] = None,
) -> Optional[dict]:
    """发送 Markdown 消息。未配置 webhook 时静默跳过，返回 None。"""
    if not _webhook_available():
        logger.warning("[wecom] WECOM_WEBHOOK 未配置，跳过 markdown 推送")
        return None

    msg = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"## {title}\n{content}",
            "mentioned_mobile_list": mentioned_mobiles or [],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(_get_webhook(), json=msg)
            data = r.json()
            if data.get("errcode") != 0:
                logger.error(f"[wecom] 推送失败 errcode={data.get('errcode')} errmsg={data.get('errmsg')}")
            return data
    except Exception as e:
        logger.exception(f"[wecom] 推送异常: {e}")
        return None


async def send_text(
    text: str,
    mentioned_mobiles: Optional[list] = None,
) -> Optional[dict]:
    """发送纯文本消息。"""
    if not _webhook_available():
        logger.warning("[wecom] WECOM_WEBHOOK 未配置，跳过 text 推送")
        return None

    msg = {
        "msgtype": "text",
        "text": {
            "content": text,
            "mentioned_mobile_list": mentioned_mobiles or [],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(_get_webhook(), json=msg)
            data = r.json()
            if data.get("errcode") != 0:
                logger.error(f"[wecom] 推送失败 {data}")
            return data
    except Exception as e:
        logger.exception(f"[wecom] 推送异常: {e}")
        return None


def send_text_sync(text: str) -> bool:
    """同步发一条纯文本（供 Celery worker 调用）。"""
    if not _webhook_available():
        logger.warning("[wecom] WECOM_WEBHOOK 未配置，跳过同步 text 推送")
        return False
    try:
        import requests
        r = requests.post(
            _get_webhook(),
            json={
                "msgtype": "text",
                "text": {
                    "content": text,
                    "mentioned_mobile_list": [],
                },
            },
            timeout=10,
        )
        data = r.json()
        if data.get("errcode") != 0:
            logger.error(f"[wecom] 同步推送失败 {data}")
            return False
        return True
    except Exception as e:
        logger.exception(f"[wecom] 同步推送异常: {e}")
        return False


# === 业务场景封装 ===

async def send_bid_daily_summary(
    date_str: str,
    new_bids_count: int,
    top_keywords: list,
    top_regions: list = None,
) -> Optional[dict]:
    """每日标讯汇总推送（企业微信群机器人）"""
    kw_lines = "\n".join(f"> - {kw}" for kw in top_keywords[:10]) or "> （无）"
    region_lines = ""
    if top_regions:
        region_lines = "\n\n**热门地区**：\n" + "\n".join(f"> - {rg}" for rg in top_regions[:6])

    content = (
        f"### 📢 {date_str} 新增标讯汇总\n"
        f"**新增数量**：{new_bids_count} 条\n\n"
        f"**Top 关键词**：\n{kw_lines}\n"
        f"{region_lines}\n"
    )
    return await send_markdown("📢 标讯每日汇总", content)


async def send_expiring_soon_bids(
    date_str: str,
    count: int,
    sample_links: list,
) -> Optional[dict]:
    """
    到期预警推送（每天 09:00 Celery Beat 调用）。
    sample_links: [{"title": str, "link": str, "deadline": str}]
    """
    if count == 0:
        content = f"### ⏰ {date_str} 截止预警\n**24 小时内截止的标讯：0 条** ✅"
        return await send_markdown("⏰ 截止时间临近预警", content)

    link_lines = []
    for t in sample_links[:15]:
        link_lines.append(f"- [{t['title'][:40]}]({t['link']}) · {t['deadline']}")
    links_text = "\n".join(link_lines)

    content = (
        f"### ⏰ {date_str} 截止时间临近预警\n"
        f"**{count} 条标讯在 24 小时内截止报名**\n\n"
        f"**样例**：\n{links_text}\n"
    )
    return await send_markdown("⏰ 截止时间临近预警", content)
