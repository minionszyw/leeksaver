"""
LeekSaver 配置管理模块

使用 pydantic-settings 进行类型安全的配置管理
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "LeekSaver"
    app_env: Literal["development", "production", "testing"] = "development"
    debug: bool = True

    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # PostgreSQL 配置
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "leeksaver"
    postgres_password: str = "leeksaver_password"
    postgres_db: str = "leeksaver"

    @property
    def database_url(self) -> str:
        """构建数据库连接 URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """构建同步数据库连接 URL (用于 Alembic)"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        """构建 Redis 连接 URL"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Celery 配置
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # LLM 配置
    llm_provider: Literal["deepseek", "openai", "ollama"] = "deepseek"

    # DeepSeek 配置
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # OpenAI 配置
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"

    # Ollama 配置
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # 数据清理配置
    news_retention_days: int = Field(default=90, description="新闻保留天数")
    news_cleanup_protect_watchlist: bool = Field(
        default=True, description="是否保护自选股相关的新闻"
    )

    # 数据同步限制配置
    news_sync_market_limit: int = Field(
        default=100, description="全市场新闻同步单次最大数量"
    )
    news_sync_watchlist_limit_per_stock: int = Field(
        default=20, description="自选股新闻同步单次每只股票最大数量"
    )

    # ==================== 分层调度策略配置 ====================

    # L1 - 日更组：收盘后统一同步时间（HH:MM 格式）
    sync_l1_daily_time: str = Field(
        default="17:30",
        description="L1 日更任务统一执行时间（24小时制，格式：HH:MM）",
    )

    # L2 - 日内组：高频更新间隔（秒）
    sync_l2_interval_seconds: int = Field(
        default=300,
        description="L2 日内任务更新间隔（秒，推荐 300=5分钟）",
        ge=60,  # 最小 1 分钟
        le=3600,  # 最大 1 小时
    )

    # L2 任务错开间隔（秒）
    sync_l2_task_offset_seconds: int = Field(
        default=120,
        description="L2 任务错开执行的时间间隔（秒，推荐 120=2分钟）",
        ge=0,
        le=300,
    )

    # L3 - 按需组：实时缓存时间（秒）
    realtime_cache_ttl: int = Field(
        default=10,
        description="L3 按需查询的缓存时间（秒）",
        ge=1,
        le=300,
    )

    # ==================== 特殊任务配置 ====================

    # 财务报表同步（每周六 20:00）
    sync_financial_day_of_week: int = Field(
        default=6, description="财报同步星期几（0=周一，6=周日）"
    )
    sync_financial_hour: int = Field(default=20, description="财报同步小时")
    sync_financial_minute: int = Field(default=0, description="财报同步分钟")

    # 新闻清理（每周一 02:00）
    cleanup_news_day_of_week: int = Field(default=0, description="新闻清理星期几（0=周一）")
    cleanup_news_hour: int = Field(default=2, description="新闻清理小时")
    cleanup_news_minute: int = Field(default=0, description="新闻清理分钟")

    # 数据健康巡检（每天 09:00）
    health_check_hour: int = Field(default=9, description="数据健康巡检小时")
    health_check_minute: int = Field(default=0, description="数据健康巡检分钟")

    # 向量服务配置
    embedding_provider: Literal["openai", "siliconflow", "ollama"] = Field(
        default="openai", description="向量服务提供商"
    )

    # OpenAI 向量配置
    embedding_openai_api_key: str = Field(default="", description="OpenAI API Key（向量服务专用）")
    embedding_openai_model: str = Field(
        default="text-embedding-3-small", description="OpenAI 向量模型"
    )
    embedding_openai_dimension: int = Field(default=1536, description="OpenAI 向量维度")

    # SiliconFlow 向量配置
    embedding_siliconflow_api_key: str = Field(default="", description="SiliconFlow API Key")
    embedding_siliconflow_base_url: str = Field(
        default="https://api.siliconflow.cn/v1", description="SiliconFlow API 地址"
    )
    embedding_siliconflow_model: str = Field(
        default="BAAI/bge-large-zh-v1.5", description="SiliconFlow 向量模型"
    )
    embedding_siliconflow_dimension: int = Field(
        default=1024, description="SiliconFlow 向量维度"
    )

    # Ollama 向量配置
    embedding_ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama API 地址"
    )
    embedding_ollama_model: str = Field(default="nomic-embed-text", description="Ollama 向量模型")
    embedding_ollama_dimension: int = Field(default=768, description="Ollama 向量维度")

    embedding_batch_size: int = Field(
        default=50, description="向量处理批次大小"
    )

    # 日志配置
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ==================== 配置验证器 ====================

    @field_validator("sync_l1_daily_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """验证时间格式 HH:MM"""
        try:
            hour, minute = v.split(":")
            h, m = int(hour), int(minute)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError("时间超出有效范围")
            return v
        except ValueError as e:
            raise ValueError(f"时间格式必须为 HH:MM (24小时制): {e}")
        except Exception:
            raise ValueError("时间格式必须为 HH:MM (24小时制)")

    # ==================== 属性方法 ====================

    @property
    def l1_schedule_hour(self) -> int:
        """解析 L1 执行时间的小时部分"""
        return int(self.sync_l1_daily_time.split(":")[0])

    @property
    def l1_schedule_minute(self) -> int:
        """解析 L1 执行时间的分钟部分"""
        return int(self.sync_l1_daily_time.split(":")[1])

    @property
    def embedding_api_key(self) -> str:
        """根据当前提供商返回对应的 API Key"""
        provider_key_map = {
            "openai": self.embedding_openai_api_key,
            "siliconflow": self.embedding_siliconflow_api_key,
            "ollama": "",
        }
        return provider_key_map.get(self.embedding_provider, "")

    @property
    def embedding_model(self) -> str:
        """根据当前提供商返回对应的模型名称"""
        provider_model_map = {
            "openai": self.embedding_openai_model,
            "siliconflow": self.embedding_siliconflow_model,
            "ollama": self.embedding_ollama_model,
        }
        return provider_model_map.get(self.embedding_provider, "")

    @property
    def embedding_dimension(self) -> int:
        """根据当前提供商返回对应的向量维度"""
        provider_dim_map = {
            "openai": self.embedding_openai_dimension,
            "siliconflow": self.embedding_siliconflow_dimension,
            "ollama": self.embedding_ollama_dimension,
        }
        return provider_dim_map.get(self.embedding_provider, 1536)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 导出配置实例
settings = get_settings()
