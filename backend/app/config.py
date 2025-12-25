"""
LeekSaver 配置管理模块

使用 pydantic-settings 进行类型安全的配置管理
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
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

    # 数据同步配置
    akshare_rate_limit: int = Field(default=5, description="AkShare 每秒最大请求数")
    akshare_rate_limit_window: int = Field(default=1, description="限频时间窗口(秒)")
    sync_batch_size: int = Field(default=100, description="数据同步批量大小")

    # 新闻同步配置
    news_sync_market_limit: int = Field(default=50, description="全市场新闻每次同步数量")
    news_sync_watchlist_limit_per_stock: int = Field(
        default=5, description="自选股新闻：每只股票获取的新闻数量"
    )
    news_sync_batch_interval: float = Field(
        default=0.5, description="批量获取新闻时的批次间隔（秒）"
    )

    # 向量生成配置
    embedding_batch_size: int = Field(default=100, description="向量生成的批次大小")

    # 数据清理配置
    news_retention_days: int = Field(default=90, description="新闻保留天数")
    news_cleanup_protect_watchlist: bool = Field(
        default=True, description="是否保护自选股相关的新闻"
    )

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

    # 日志配置
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

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
