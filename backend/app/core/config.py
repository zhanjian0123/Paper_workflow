"""
配置管理
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, List, Any
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 加载 .env 文件（从项目根目录）
def _load_env_file():
    """手动加载 .env 文件到环境变量"""
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    os.environ[key.strip()] = value.strip()

# 在模块加载时加载 .env
_load_env_file()


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    app_name: str = "Literature Workflow API"
    debug: bool = False

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS 配置 - 从环境变量读取
    cors_origins: List[str] = [
        origin.strip() for origin in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://localhost:4173"
        ).split(",")
        if origin.strip()
    ]
    cors_origin_regex: Optional[str] = os.environ.get(
        "CORS_ORIGIN_REGEX",
        r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$"
    )

    # 文件配置
    output_dir: str = "output"
    workflows_dir: str = "output/workflows"
    download_dir: str = "output/papers"

    # 数据库配置
    database_url: Optional[str] = None  # 默认使用 SQLite

    # 分页配置
    default_page_size: int = 20
    max_page_size: int = 100

    # WebSocket 配置
    websocket_ping_interval: int = 30  # 秒
    websocket_timeout: int = 1800  # 30 分钟

    # 日志配置
    log_level: str = "INFO"

    # LLM 配置 - 从环境变量读取
    llm_model_name: str = os.environ.get("MODEL_ID", "qwen3.5-plus")
    llm_base_url: Optional[str] = os.environ.get("ANTHROPIC_BASE_URL")
    llm_api_key: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")

    @property
    def project_root_path(self) -> Path:
        return PROJECT_ROOT

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.project_root_path / path

    @property
    def output_dir_path(self) -> Path:
        return self.resolve_path(self.output_dir)

    @property
    def workflows_dir_path(self) -> Path:
        return self.resolve_path(self.workflows_dir)

    @property
    def download_dir_path(self) -> Path:
        return self.resolve_path(self.download_dir)

    @property
    def upload_dir_path(self) -> Path:
        return self.output_dir_path / "uploads"

    @property
    def workflow_store_db_path(self) -> Path:
        return self.output_dir_path / "workflow_store.db"

    @property
    def legacy_output_dir_path(self) -> Path:
        return self.project_root_path / "backend" / "output"

    @property
    def legacy_workflow_store_db_path(self) -> Path:
        return self.legacy_output_dir_path / "workflow_store.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略额外的环境变量

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_value(cls, value: Any) -> bool:
        """兼容 DEBUG=release/development 等字符串配置"""
        if isinstance(value, bool):
            return value
        if value is None:
            return False

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False

        return bool(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> List[str]:
        """支持逗号分隔的 CORS_ORIGINS 环境变量"""
        if isinstance(value, list):
            return value
        if value is None:
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return list(value)


# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
