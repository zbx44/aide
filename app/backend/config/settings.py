from __future__ import annotations
"""全局配置 - 支持多平台LLM + 多层配置优先级 + 数据/代码分离

目录结构：
  aide/
    ├── app/backend/     ← 代码（升级时覆盖）
    ├── config/          ← 预置配置（升级时覆盖）
    ├── data/            ← 用户数据（升级不碰）
    ├── user/            ← 用户自定义（升级不碰）
    ├── output/          ← 生成文档（升级不碰）
    └── logs/            ← 日志（升级不碰）

配置加载优先级：
  1. user/user.env       ← 用户自己改的（最高优先级）
  2. config/default.env  ← 开发者预置的默认配置
  3. 代码中硬编码的默认值   ← 最低优先级
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _find_root_dir() -> Path:
    """自动检测项目根目录

    检测逻辑：
    1. 环境变量 AIDE_ROOT（最高优先级，启动脚本可指定）
    2. 从当前文件向上查找包含 app/ 和 config/ 的目录
    3. 兜底：当前文件往上3级
    """
    # 环境变量指定
    env_root = os.environ.get("AIDE_ROOT")
    if env_root:
        root = Path(env_root)
        if root.exists():
            return root

    # 从当前文件位置向上查找
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "app").exists() and (parent / "config").exists():
            return parent

    # 兜底：旧版兼容，backend/的上级
    return Path(__file__).parent.parent.parent


def _load_env_file(env_path: Path) -> dict:
    """手动解析.env文件，不依赖pydantic的env_file（需要支持多文件合并）"""
    env_vars = {}
    if not env_path.exists():
        return env_vars
    # 兼容Windows记事本保存的GBK编码文件
    for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            with open(env_path, "r", encoding=enc) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # 去掉引号
            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            env_vars[key] = value
    return env_vars


def _merge_env_files(config_env: Path, user_env: Path) -> str:
    """合并配置文件：config/default.env + user/user.env

    优先级：user.env > default.env
    合并后生成临时.env供pydantic读取
    """
    merged = {}

    # 先加载默认配置
    default_vars = _load_env_file(config_env)
    merged.update(default_vars)

    # 再加载用户配置（覆盖默认）
    user_vars = _load_env_file(user_env)
    merged.update(user_vars)

    return merged


# ===== 项目根目录 =====
ROOT_DIR = _find_root_dir()

# ===== 合并配置文件 =====
_config_env = ROOT_DIR / "config" / "default.env"
_user_env = ROOT_DIR / "user" / "user.env"
_merged_env = _merge_env_files(_config_env, _user_env)

# 将合并后的配置写入环境变量（pydantic会从环境变量读取）
# 只设置还没在环境中存在的变量，不覆盖已有的
for key, value in _merged_env.items():
    if key not in os.environ:
        os.environ[key] = value

# 标记哪些配置项被用户覆盖过（用于升级提示）
_user_overridden_keys = set(_load_env_file(_user_env).keys()) if _user_env.exists() else set()


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "AI Assistant"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8900

    # ===== 目录配置 =====
    # 新版目录结构
    ROOT_DIR: Path = ROOT_DIR
    APP_DIR: Path = ROOT_DIR / "app" / "backend"
    CONFIG_DIR: Path = ROOT_DIR / "config"
    DATA_DIR: Path = ROOT_DIR / "data"
    USER_DIR: Path = ROOT_DIR / "user"
    OUTPUT_DIR: Path = ROOT_DIR / "output"
    LOGS_DIR: Path = ROOT_DIR / "logs"

    # 兼容旧版的目录别名
    TASKS_DIR: Path = ROOT_DIR / "user" / "tasks"
    TEMPLATES_DIR: Path = ROOT_DIR / "user" / "templates"
    SYSTEM_TEMPLATES_DIR: Path = ROOT_DIR / "config" / "templates"

    # SQLite
    DATABASE_URL: str = ""

    # ===== LLM多平台配置 =====
    LLM_PROVIDER: str = "vllm"

    # vLLM (本地部署)
    LLM_BASE_URL: str = "http://localhost:8000/v1"
    LLM_API_KEY: str = "not-needed"
    LLM_MODEL: str = "qwen3.6-27B"

    # 腾讯TokenHub
    LLM_TENCENT_BASE_URL: str = "https://api.lkeap.cloud.tencent.com/plan/v3"
    LLM_TENCENT_API_KEY: str = ""
    LLM_TENCENT_MODEL: str = "glm-5.1"

    # 通用OpenAI兼容 (DeepSeek, 通义千问, Moonshot等)
    LLM_OPENAI_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_OPENAI_API_KEY: str = ""
    LLM_OPENAI_MODEL: str = "deepseek-chat"

    # 自定义端点
    LLM_CUSTOM_BASE_URL: str = ""
    LLM_CUSTOM_API_KEY: str = ""
    LLM_CUSTOM_MODEL: str = ""

    # 通用LLM参数
    LLM_MAX_TOKENS: int = 4096          # 生成最大token数
    LLM_TEMPERATURE: float = 0.7        # 温度
    LLM_CONTEXT_WINDOW: int = 32768    # 模型上下文窗口大小（token数），Qwen3.6-27B=32K, DeepSeek=64K等
    LLM_MAX_CONTEXT_MESSAGES: int = 20 # 上下文最大消息条数（按条数截断的兜底）
    LLM_THINKING_MODEL: bool = True    # 是否启用思考模式（Qwen3等带<think>标签的模型设为True）

    # 达梦数据库
    DM_HOST: str = "127.0.0.1"
    DM_STANDBY_HOST: str = "127.0.0.2"
    DM_PORT: int = 5236
    DM_USERNAME: str = "dmdb"
    DM_PASSWORD: str = ""
    DM_DATABASE: str = "lczx"

    # 致远OA
    SEELYON_BASE_URL: str = ""
    SEELYON_USERNAME: str = ""
    SEELYON_PASSWORD: str = ""

    # 邮件通知
    EMAIL_SMTP: str = "smtp.qq.com"
    EMAIL_SMTP_PORT: int = 465
    EMAIL_SENDER: str = "your-email@example.com"
    EMAIL_PASSWORD: str = ""

    def model_post_init(self, __context):
        """初始化后自动设置派生字段和创建目录"""
        # 确保用户数据目录存在
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.USER_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.TASKS_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

        # SQLite数据库路径
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite+aiosqlite:///{self.DATA_DIR / 'assistant.db'}"

    def get_user_overridden_keys(self) -> set:
        """获取被用户自定义覆盖的配置项（升级时需要提示）"""
        return _user_overridden_keys

    def get_merged_config_summary(self) -> dict:
        """获取配置来源摘要（用于诊断）"""
        return {
            "root_dir": str(self.ROOT_DIR),
            "config_env": str(_config_env),
            "config_env_exists": _config_env.exists(),
            "user_env": str(_user_env),
            "user_env_exists": _user_env.exists(),
            "user_overridden_keys": list(_user_overridden_keys),
        }

    class Config:
        # 不再直接读.env文件，配置已通过环境变量注入
        env_file = None
        env_file_encoding = "utf-8"


settings = Settings()
