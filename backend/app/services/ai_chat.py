# -*- coding: utf-8 -*-
"""
DeepSeek 多轮 AI 助手（P2 新功能）

核心约束：**AI 只有查询权限**，不能改数据、不能改系统设置。
系统提示词硬性限定：只能回答"查询标讯相关"的问题，其他一律拒绝。

依赖：DEEPSEEK_API_KEY 配在 .env（**你自己粘贴，我不写进文件**）
未配置时返回明确提示。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.config import settings
from app.database import SessionLocal
from app.models.bid import BidInfo

logger = logging.getLogger(__name__)


# =====================================================
# 系统提示词：**硬约束 AI 行为边界**
# =====================================================

CHAT_SYSTEM_PROMPT = """你是一个「标讯查询助手」，仅能帮助用户查询和解释标讯相关数据。

⚠️  你的权限严格限定为「只读查询」，禁止任何写入操作。

你能做的：
1. 查询某个地区/关键词/类型的标讯
2. 解释某条标讯的内容、截止时间、中标情况
3. 统计近 N 天新增多少条标讯
4. 回答"XX 类标讯最近有哪些"这类问题
5. 根据用户的订阅习惯推荐相关标讯
6. 解释"采购公告"、"招标公告"、"成交公告"的区别

你绝对**不能**做的：
1. 创建、修改、删除任何标讯、用户、权限
2. 执行爬虫、触发推送、修改系统设置
3. 回答与"标讯/招投标/政府采购"完全无关的问题
4. 索要或处理任何密码、密钥、token 等敏感信息
5. 执行任何代码、命令、SQL

回答风格：
- 简洁直接，先给结论再解释
- 列数据时用列表，数字用粗体
- 涉及具体标讯时，附上简要标题和发布时间
- 如果用户的问题超出了标讯范围，礼貌拒绝并说明你是"标讯查询助手"
"""


# =====================================================
# 把"最新标讯数据"注入上下文（让 AI 参考数据库内容回答）
# =====================================================

def _get_context_snippet(max_bids: int = 30) -> str:
    """取最新一批标讯做上下文注入，避免 AI 幻觉。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(BidInfo)
            .filter(BidInfo.status == 1)
            .order_by(BidInfo.publish_time.desc())
            .limit(max_bids)
            .all()
        )
        lines = []
        for r in rows:
            t = r.publish_time.strftime("%Y-%m-%d") if r.publish_time else "?"
            lines.append(f"- [{r.id}] {t} | {r.title[:80]}")
        return f"【系统最新标讯参考（仅供查询时对照，数据来自数据库）】\n" + "\n".join(lines)
    finally:
        db.close()


# =====================================================
# DeepSeek 多轮对话主入口
# =====================================================

async def ai_chat(
    messages: List[dict],          # 用户/助手交替消息：[{"role":"user","content":"..."}, ...]
    inject_context: bool = True,   # 是否注入最新标讯上下文
) -> str:
    """
    多轮对话：把历史消息 + 系统提示词 + (可选)上下文 → DeepSeek。
    """
    if not settings.deepseek_api_key:
        return (
            "⚠️  **DeepSeek API Key 未配置**，AI 助手暂时无法使用。\n\n"
            "请在 `.env` 文件里填入 `DEEPSEEK_API_KEY=你的key`，重启后端即可。\n\n"
            "（为了安全，建议你自己粘贴，不要在聊天里发送密钥）"
        )

    # 组装最终 messages：[system, (可选 context), ...history]
    final_messages: List[dict] = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

    if inject_context:
        ctx = _get_context_snippet()
        final_messages.append({"role": "system", "content": ctx})

    final_messages.extend(messages)

    try:
        from app.services.llm import achat, LLMError
        result = await achat(final_messages, temperature=0.6, max_tokens=1500,
                             timeout=30.0, tag="chat")
        logger.info(f"[ai-chat] tokens used: {result.usage}")
        return result.content
    except LLMError as e:
        logger.error(f"[ai-chat] LLM error kind={e.kind}: {e}")
        return f"⚠️ AI 服务返回错误：{str(e)[:80]}"
    except Exception as e:
        logger.exception(f"[ai-chat] failed: {e}")
        return f"⚠️ AI 服务暂时不可用：{str(e)[:80]}"
