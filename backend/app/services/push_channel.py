# -*- coding: utf-8 -*-
"""
推送通道基类 + 邮件 / 企业微信 / 预留 SMS 实现。
Crawl 服务、Push 定时任务统一走这里。
"""
import logging
import smtplib
from abc import ABC, abstractmethod
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from app.services import wecom_push

logger = logging.getLogger(__name__)


class PushChannel(ABC):
    """推送通道抽象基类"""

    @abstractmethod
    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        """返回 True 表示成功"""


class EmailChannel(PushChannel):
    """SMTP 邮件推送。未配置 SMTP 账号时直接返回 False（不抛异常）。"""

    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        from app.config import settings

        if not recipient:
            logger.warning("[email] 收件人为空，跳过")
            return False
        if not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
            logger.warning("[email] SMTP 未配置（SMTP_HOST/SMTP_USER/SMTP_PASSWORD），无法发送")
            return False

        is_html = bool(kwargs.get("html", False))
        msg = MIMEText(body or "", "html" if is_html else "plain", "utf-8")
        msg["Subject"] = Header(subject or "", "utf-8")
        msg["From"] = formataddr((str(Header(settings.app_name, "utf-8")), settings.smtp_user))
        msg["To"] = recipient

        try:
            if settings.smtp_use_ssl:
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
                server.starttls()
            try:
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.smtp_user, [recipient], msg.as_string())
            finally:
                server.quit()
            logger.info(f"[email] 发送成功 → {recipient}")
            return True
        except Exception as e:
            logger.error(f"[email] 发送失败 → {recipient}: {e}")
            return False


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


# 默认通道：邮件 + 企业微信群
default_channel = CombinedChannel([EmailChannel(), WecomGroupChannel()])

# 单通道实例（订阅个人推送只用邮件）
email_channel = EmailChannel()
