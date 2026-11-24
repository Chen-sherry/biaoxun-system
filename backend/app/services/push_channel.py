# -*- coding: utf-8 -*-
"""
推送通道基类 + 邮件 / 企业微信 / 预留 SMS 实现。
Crawl 服务、Push 定时任务统一走这里。
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.services import wecom_push


class PushChannel(ABC):
    """推送通道抽象基类"""

    @abstractmethod
    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        """返回 True 表示成功"""


class EmailChannel(PushChannel):
    """SMTP 邮件推送（骨架，等 SMTP 账号后补全）"""

    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        # TODO: import smtplib + 实际发送
        print(f"[email] → {recipient} | {subject}")
        return True


class WecomGroupChannel(PushChannel):
    """企业微信群机器人推送"""

    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        # recipient 这里可以是 @all 或指定手机号
        return wecom_push.send_text_sync(f"【{subject}】{body}")


class CombinedChannel(PushChannel):
    """组合推送：同时推多个通道"""

    def __init__(self, channels: list[PushChannel]):
        self.channels = channels

    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        return all(c.send(recipient, subject, body, **kwargs) for c in self.channels)


# 默认通道：邮件（骨架）+ 企业微信群
default_channel = CombinedChannel([EmailChannel(), WecomGroupChannel()])
