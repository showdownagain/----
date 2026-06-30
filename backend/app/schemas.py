"""
Pydantic 模型 — API 请求体 / 响应体 / 数据校验。
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# 通用
# ═══════════════════════════════════════════════════════════════

class BaseResponse(BaseModel):
    status: str = "ok"
    data: dict | list | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat() + "Z")


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
    error_code: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat() + "Z")


# ═══════════════════════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════════════════════

class HealthData(BaseModel):
    mt5_connected: bool = False
    mt5_account: str = ""
    mt5_server: str = ""
    uptime_seconds: int = 0
    python_version: str = ""
    active_strategies: int = 0
    open_positions: int = 0
    tick_count_today: int = 0
    last_tick_time: str = ""


# ═══════════════════════════════════════════════════════════════
# 行情
# ═══════════════════════════════════════════════════════════════

class TickData(BaseModel):
    symbol: str
    bid: float
    ask: float
    spread: float = 0
    last: Optional[float] = None
    volume: int = 0
    time: str


class RatesQuery(BaseModel):
    symbol: str
    timeframe: str = "M5"
    count: int = Field(default=200, ge=1, le=5000)
    from_time: Optional[str] = None
    to_time: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# 订单
# ═══════════════════════════════════════════════════════════════

class OrderRequest(BaseModel):
    symbol: str
    action: str = Field(..., pattern="^(BUY|SELL|CLOSE_BUY|CLOSE_SELL)$")
    volume: float = Field(..., gt=0)
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT|STOP)$")
    price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    deviation: int = Field(default=20, ge=0, le=100)
    comment: str = ""


class CloseRequest(BaseModel):
    ticket: int
    volume: Optional[float] = None
    deviation: int = Field(default=20, ge=0, le=100)


# ═══════════════════════════════════════════════════════════════
# 策略
# ═══════════════════════════════════════════════════════════════

class StrategyParams(BaseModel):
    params: dict = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

class ConfigData(BaseModel):
    default_symbol: str
    default_lot: float
    max_lot: float
    max_positions: int
    max_daily_loss: float
    enable_real_trading: bool
    allowed_symbols: list[str]
    tick_sync_interval_ms: int


# ═══════════════════════════════════════════════════════════════
# WebSocket 消息
# ═══════════════════════════════════════════════════════════════

class WSMessage(BaseModel):
    type: str
    data: dict
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat() + "Z")
