"""推送日志 + 推送模板"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey

from app.database import Base
from app.models.base import TimestampMixin


class PushRecord(Base):
    """推送日志"""
    __tablename__ = "push_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True)
    subscribe_id = Column(Integer, ForeignKey("bid_subscribe.id"), nullable=True)
    push_type = Column(String(16), nullable=False, default="scheduled",
                       comment="scheduled定时/manual临时/test测试/subscribe订阅/ai生成")
    template_id = Column(Integer, ForeignKey("push_template.id"), nullable=True,
                         comment="关联 push_template.id")
    operator_id = Column(Integer, nullable=True, comment="操作人（定时任务为 NULL）")
    preview = Column(Integer, nullable=False, default=0, comment="1=预览记录")
    bid_ids = Column(String(2000), nullable=True, comment="本次推送的标讯 ID 列表（逗号分隔）")
    channel = Column(String(16), nullable=False, comment="email / wechat / sms")
    recipient = Column(String(255), nullable=False, comment="接收人地址")
    subject = Column(String(255), nullable=True)
    status = Column(Integer, nullable=False, default=0, comment="0 成功 1 失败")
    error_msg = Column(String(500), nullable=True)
    push_time = Column(DateTime, nullable=False, comment="推送时间")


class PushTemplate(Base):
    """推送模板：定时推送文案存库，后台可改、执行时读库渲染"""
    __tablename__ = "push_template"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), nullable=False, unique=True, index=True,
                  comment="daily_summary/expiring_alert/archive_notice/自定义")
    name = Column(String(64), nullable=False, default="", comment="显示名")
    kind = Column(String(16), nullable=False, default="fixed",
                  comment="fixed 内置任务 / custom 自定义定时推送")
    schedule_time = Column(String(5), nullable=False, default="",
                           comment="执行时间 HH:MM，空=内置默认")
    frequency = Column(String(8), nullable=False, default="daily",
                       comment="daily 每天 / weekly 每周（custom 用）")
    weekday = Column(Integer, nullable=True, comment="weekly 时 0=周一..6=周日")
    title = Column(String(255), nullable=False, comment="消息标题（## 前缀由发送层加）")
    content = Column(Text, nullable=False, comment="模板正文，{var} 占位符")
    variables = Column(String(500), nullable=False, default="",
                       comment="可用变量清单（逗号分隔）")
    enabled = Column(Integer, nullable=False, default=1, comment="1 启用 0 停用（到点跳过）")
    updated_by = Column(Integer, nullable=True, comment="最后修改后台用户 id")
    updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=True)
