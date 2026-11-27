"""
应用全局配置
从 .env 文件或环境变量读取
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ===== 应用基础 =====
    app_name: str = "标讯系统"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    secret_key: str = "change_me_in_prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24h

    # ===== MySQL =====
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "123456"
    db_name: str = "bid_info"
    db_charset: str = "utf8mb4"

    # ===== Redis =====
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0

    # ===== Celery =====
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    # ===== OSS =====
    oss_endpoint: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket: str = ""
    oss_domain: str = ""

    # ===== SMTP =====
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = True

    # ===== 日志 =====
    log_level: str = "INFO"
    log_dir: str = "./logs"

    # ===== 企业微信群机器人 =====
    wecom_webhook: str = ""
    wecom_send_zero_summary: bool = False  # 到期预警 count=0 时是否仍推送（默认 False 不打扰群）

    # ===== DeepSeek AI 匹配 =====
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_max_retries: int = 1   # LLM 可重试错误（timeout/429/5xx）的重试次数
    chat_daily_limit: int = 30  # AI 悬浮球：每会员每日对话条数频控（0=不限）

    # ===== 阿里云 DashScope（DeepSeek 兜底 · qwen-plus）=====
    alibaba_api_key: str = ""
    alibaba_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    alibaba_model: str = "qwen-plus"

    # ===== 爬虫出口代理 =====
    ccgp_proxy: str = ""  # ccgp.gov.cn 专用代理（服务器 IP 被封 403 时配置，如 http://user:pass@host:port；留空直连）

    # ===== CORS =====
    cors_origins: str = "*"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset={self.db_charset}"
        )

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
