"""
应用配置 — 从 .env 文件加载所有配置项。
"""
import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


# 项目根目录 (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """所有配置项集中管理，自动从 .env 读取"""

    # ---- MT5 连接 ----
    MT5_LOGIN: str = ""
    MT5_PASSWORD: str = ""
    MT5_SERVER: str = ""

    # ---- 交易品种 ----
    DEFAULT_SYMBOL: str = "XAUUSD"
    ALLOWED_SYMBOLS: str = "XAUUSD,EURUSD,GBPUSD,USDJPY"

    @property
    def allowed_symbols_list(self) -> list[str]:
        return [s.strip() for s in self.ALLOWED_SYMBOLS.split(",") if s.strip()]

    # ---- 交易参数 ----
    DEFAULT_LOT: float = 0.01
    MAX_LOT: float = 0.05
    MAX_POSITIONS: int = 3
    MAX_DAILY_LOSS: float = 100.0
    MAX_LOSS_PER_TRADE: float = 20.0

    # ---- 安全开关 ----
    ENABLE_REAL_TRADING: bool = False

    # ---- 风控参数 ----
    MAX_SPREAD_XAUUSD: float = 5.0
    MAX_SPREAD_FOREX: float = 2.0
    TRADING_HOURS_START: str = "00:00"
    TRADING_HOURS_END: str = "23:59"

    # ---- 行情同步 ----
    TICK_SYNC_INTERVAL_MS: int = 500         # Tick 采集间隔（毫秒）
    TICK_STORAGE_DAYS: int = 7               # Tick 数据保留天数

    # ---- 告警 ----
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    FEISHU_WEBHOOK_URL: str = ""
    DINGTALK_WEBHOOK_URL: str = ""

    # ---- 系统 ----
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'trading.db'}"

    model_config = dict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（缓存避免反复读取 .env）"""
    return Settings()
