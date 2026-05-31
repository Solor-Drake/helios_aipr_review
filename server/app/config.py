"""
应用配置管理模块。

负责从环境变量和 .env 文件加载配置，提供统一的配置访问入口。
所有配置项通过 Settings 数据类集中管理，避免散落各处的 os.getenv() 调用。
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class AIConfig(BaseSettings):
    """AI 服务配置，支持阿里云百炼和 DeepSeek 双平台。"""

    daskscope_api_key: str = "sk-xxxxxxxxxxxxxxxxxxxx"
    daskscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    deepseek_api_key: str = "sk-xxxxxxxxxxxxxxxxxxxx"
    deepseek_base_url: str = "https://api.deepseek.com"

    default_model: str = "qwen-turbo"

    # LLM 调用参数
    temperature: float = 0.0  # temperature=0 确保评审结果确定性
    max_tokens: int = 4096
    request_timeout: int = 120  # 单次 API 调用超时（秒）

    model_config = {"env_prefix": "", "extra": "ignore"}


class GitHubConfig(BaseSettings):
    """GitHub / GitLab API 配置。"""

    github_token: str | None = None
    gitlab_token: str | None = None

    model_config = {"env_prefix": "", "extra": "ignore"}


class ServerConfig(BaseSettings):
    """FastAPI 服务配置。"""

    port: int = 8000
    host: str = "0.0.0.0"
    database_path: str = "./server/data/reviews.db"
    log_level: str = "INFO"

    model_config = {"env_prefix": "", "extra": "ignore"}


class Settings(BaseSettings):
    """聚合配置入口。"""

    ai: AIConfig = AIConfig()
    github: GitHubConfig = GitHubConfig()
    server: ServerConfig = ServerConfig()

    model_config = {"env_prefix": "", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """获取全局唯一配置实例（带缓存）。

    使用 lru_cache 确保整个进程内只创建一次 Settings 对象，
    后续调用直接返回缓存实例，避免重复解析环境变量。
    """
    return Settings()
