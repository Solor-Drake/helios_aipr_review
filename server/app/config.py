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

    model_config = {"env_prefix": "", "extra": "ignore", "case_sensitive": False}

    # ── API Key 有效性校验 ─────────────────────────────────

    def is_api_key_configured(self) -> bool:
        """检测当前激活模型的 API Key 是否已正确配置。

        判断标准：
        - Key 不能为空字符串或 None
        - Key 不能是示例占位符（以 "sk-xxx" 开头）

        Returns:
            True 表示已配置有效 Key，False 表示未配置或为占位符。
        """
        if "deepseek" in self.default_model.lower():
            key = self.deepseek_api_key
        else:
            key = self.daskscope_api_key
        return bool(key) and not key.startswith("sk-xxx")

    def active_provider_name(self) -> str:
        """返回当前激活的 AI 服务商名称，用于日志和错误提示。"""
        if "deepseek" in self.default_model.lower():
            return "DeepSeek (DEEPSEEK_API_KEY)"
        return "阿里云百炼 (DASHSCOPE_API_KEY)"


class GitHubConfig(BaseSettings):
    """GitHub / GitLab API 配置。"""

    github_token: str | None = None
    gitlab_token: str | None = None

    model_config = {"env_prefix": "", "extra": "ignore", "case_sensitive": False}


class ServerConfig(BaseSettings):
    """FastAPI 服务配置。"""

    port: int = 8000
    host: str = "0.0.0.0"
    database_path: str = "./server/data/reviews.db"
    log_level: str = "INFO"

    model_config = {"env_prefix": "", "extra": "ignore", "case_sensitive": False}


class Settings(BaseSettings):
    """聚合配置入口。

    pydantic-settings 默认对嵌套 BaseSettings 使用 __ 分隔符
    （如 AI__DASHSCOPE_API_KEY），但 .env.example 使用扁平命名
    （如 DASHSCOPE_API_KEY）。get_settings() 工厂函数会在创建
    Settings 实例后自动将扁平格式的环境变量注入到嵌套子模型中。
    """

    ai: AIConfig = AIConfig()
    github: GitHubConfig = GitHubConfig()
    server: ServerConfig = ServerConfig()

    model_config = {"env_prefix": "", "extra": "ignore", "case_sensitive": False}


# ── 扁平环境变量 → 嵌套配置字段映射表 ──────────────────────
#
# pydantic-settings 对嵌套 BaseSettings 默认使用 __ 分隔符
# （如 AI__DASHSCOPE_API_KEY），但 .env.example 使用扁平命名.
# 此映射表将扁平变量名桥接到对应的嵌套模型字段，
# 同时处理 DASHSCOPE（正确拼写）→ daskscope 的拼写差异.

_FLAT_ENV_MAP: dict[str, tuple[str, str]] = {
    # AI 服务配置
    "DASHSCOPE_API_KEY":  ("ai", "daskscope_api_key"),
    "DASHSCOPE_BASE_URL": ("ai", "daskscope_base_url"),
    "DEEPSEEK_API_KEY":   ("ai", "deepseek_api_key"),
    "DEEPSEEK_BASE_URL":  ("ai", "deepseek_base_url"),
    "DEFAULT_MODEL":      ("ai", "default_model"),
    "TEMPERATURE":        ("ai", "temperature"),
    "MAX_TOKENS":         ("ai", "max_tokens"),
    "REQUEST_TIMEOUT":    ("ai", "request_timeout"),
    # GitHub 配置
    "GITHUB_TOKEN":       ("github", "github_token"),
    "GITLAB_TOKEN":       ("github", "gitlab_token"),
    # 服务配置
    "PORT":               ("server", "port"),
    "HOST":               ("server", "host"),
    "DATABASE_PATH":      ("server", "database_path"),
    "LOG_LEVEL":          ("server", "log_level"),
}


@lru_cache
def get_settings() -> Settings:
    """获取全局唯一配置实例（带缓存）。

    使用 lru_cache 确保整个进程内只创建一次 Settings 对象，
    后续调用直接返回缓存实例，避免重复解析环境变量。

    通过 _FLAT_ENV_MAP 将 .env 中的扁平环境变量自动桥接到
    嵌套配置子模型，解决 pydantic-settings 的嵌套前缀问题
    以及 DASHSCOPE/DASKSCOPE 的字段名拼写差异。
    """
    settings = Settings()

    for env_name, (child_attr, field_name) in _FLAT_ENV_MAP.items():
        env_val = os.getenv(env_name)
        if env_val is not None:
            child = getattr(settings, child_attr)
            setattr(child, field_name, env_val)

    return settings
