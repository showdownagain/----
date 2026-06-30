"""
ORM 模型 — 对应数据库 6 张表。
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Index
from app.database import Base


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════════════════════════
# 1. tick_data — 实时 Tick 行情数据（核心表）
# ═══════════════════════════════════════════════════════════════
class TickDatum(Base):
    __tablename__ = "tick_data"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String(16), nullable=False, comment="品种代码")
    bid         = Column(Float, nullable=False, comment="卖价")
    ask         = Column(Float, nullable=False, comment="买价")
    spread      = Column(Float, default=0, comment="点差")
    last        = Column(Float, comment="最新成交价")
    volume      = Column(Integer, default=0, comment="成交量")
    time        = Column(String(24), nullable=False, comment="MT5 行情时间")
    created_at  = Column(String(24), nullable=False, default=_now, comment="入库时间")

    __table_args__ = (
        Index("ix_tick_symbol", "symbol"),
        Index("ix_tick_time", "time"),
        Index("ix_tick_symbol_time", "symbol", "time"),       # 按品种+时间筛选
        Index("ix_tick_symbol_id", "symbol", "id"),           # 按品种分页 (ORDER BY id DESC)
        {"comment": "Tick 行情数据表 — 高频写入，按天清理"},
    )

    def to_dict(self):
        return {
            "symbol": self.symbol, "bid": self.bid, "ask": self.ask,
            "spread": self.spread, "last": self.last, "volume": self.volume,
            "time": self.time,
        }


# ═══════════════════════════════════════════════════════════════
# 2. strategy_signals — 策略信号记录
# ═══════════════════════════════════════════════════════════════
class StrategySignal(Base):
    __tablename__ = "strategy_signals"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    symbol        = Column(String(16), nullable=False)
    timeframe     = Column(String(8), nullable=False)
    strategy_name = Column(String(64), nullable=False)
    signal        = Column(String(16), nullable=False, comment="BUY/SELL/CLOSE_BUY/CLOSE_SELL/HOLD")
    reason        = Column(Text)
    price         = Column(Float)
    confidence    = Column(Float, default=0.5)
    extra_data    = Column(Text, comment="JSON 扩展字段")
    created_at    = Column(String(24), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_signal_symbol", "symbol"),
        Index("ix_signal_strategy", "strategy_name"),
        Index("ix_signal_time", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id, "symbol": self.symbol, "timeframe": self.timeframe,
            "strategy_name": self.strategy_name, "signal": self.signal,
            "reason": self.reason, "price": self.price,
            "confidence": self.confidence, "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 3. orders — 订单记录
# ═══════════════════════════════════════════════════════════════
class Order(Base):
    __tablename__ = "orders"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    symbol          = Column(String(16), nullable=False)
    action          = Column(String(16), nullable=False, comment="BUY/SELL/CLOSE_BUY/CLOSE_SELL")
    order_type      = Column(String(16), nullable=False, comment="MARKET/LIMIT/STOP")
    volume          = Column(Float, nullable=False)
    price           = Column(Float)
    sl              = Column(Float)
    tp              = Column(Float)
    deviation       = Column(Integer, default=20)
    status          = Column(String(24), nullable=False, default="PENDING",
                            comment="PENDING/CHECK_PASSED/CHECK_FAILED/SENT/FILLED/CANCELED/REJECTED")
    mt5_order_id    = Column(Integer)
    mt5_retcode     = Column(Integer)
    comment         = Column(Text)
    risk_check_json = Column(Text, comment="风控检查 JSON")
    request_json    = Column(Text, comment="请求 JSON")
    response_json   = Column(Text, comment="MT5 响应 JSON")
    created_at      = Column(String(24), nullable=False, default=_now)
    updated_at      = Column(String(24))

    __table_args__ = (
        Index("ix_order_symbol", "symbol"),
        Index("ix_order_status", "status"),
        Index("ix_order_time", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id, "symbol": self.symbol, "action": self.action,
            "order_type": self.order_type, "volume": self.volume,
            "price": self.price, "sl": self.sl, "tp": self.tp,
            "status": self.status, "mt5_order_id": self.mt5_order_id,
            "comment": self.comment, "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 4. positions_snapshot — 持仓快照
# ═══════════════════════════════════════════════════════════════
class PositionSnapshot(Base):
    __tablename__ = "positions_snapshot"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    symbol        = Column(String(16), nullable=False)
    ticket        = Column(Integer, nullable=False)
    type          = Column(String(8), nullable=False, comment="BUY/SELL")
    volume        = Column(Float, nullable=False)
    price_open    = Column(Float, nullable=False)
    price_current = Column(Float, nullable=False)
    sl            = Column(Float)
    tp            = Column(Float)
    profit        = Column(Float, default=0)
    swap          = Column(Float, default=0)
    commission    = Column(Float, default=0)
    comment       = Column(Text)
    magic         = Column(Integer)
    snapshot_at   = Column(String(24), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_pos_ticket", "ticket"),
        Index("ix_pos_time", "snapshot_at"),
    )


# ═══════════════════════════════════════════════════════════════
# 5. alerts — 告警记录
# ═══════════════════════════════════════════════════════════════
class Alert(Base):
    __tablename__ = "alerts"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    level        = Column(String(12), nullable=False, comment="info/warn/error/success")
    title        = Column(String(128), nullable=False)
    message      = Column(Text, nullable=False)
    channel      = Column(String(128), default="system", comment="telegram,feishu,dingtalk")
    status       = Column(String(12), default="pending", comment="pending/sent/failed/skipped")
    error_detail = Column(Text)
    created_at   = Column(String(24), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_alert_level", "level"),
        Index("ix_alert_time", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id, "level": self.level, "title": self.title,
            "message": self.message, "channel": self.channel,
            "status": self.status, "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 6. system_logs — 系统运行日志
# ═══════════════════════════════════════════════════════════════
class SystemLog(Base):
    __tablename__ = "system_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    level      = Column(String(12), nullable=False, comment="DEBUG/INFO/WARNING/ERROR/CRITICAL")
    module     = Column(String(64), nullable=False)
    message    = Column(Text, nullable=False)
    traceback  = Column(Text)
    extra_data = Column(Text)
    created_at = Column(String(24), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_log_level", "level"),
        Index("ix_log_module", "module"),
        Index("ix_log_time", "created_at"),
    )
