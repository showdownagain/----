"""
系统路由 — 健康检查 / 配置 / 紧急停止。
"""
import sys
import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TickDatum
from app.config import get_settings
from app.mt5_client import mt5_client
from app.services.tick_sync import tick_sync_service
from app.services.websocket_manager import ws_manager

router = APIRouter(tags=["系统"])
settings = get_settings()
START_TIME = time.time()


@router.get("/api/health")
def health():
    """系统健康检查"""
    return {
        "status": "ok",
        "data": {
            "mt5_connected": mt5_client.is_connected,
            "mt5_account": str(mt5_client._account.get("login", "")) if mt5_client._account else "",
            "mt5_server": mt5_client._account.get("server", "") if mt5_client._account else "",
            "uptime_seconds": int(time.time() - START_TIME),
            "python_version": sys.version.split()[0],
            "active_strategies": 0,
            "open_positions": len(mt5_client.positions_get()) if mt5_client.is_connected else 0,
            "tick_sync_running": tick_sync_service.is_running,
            "tick_count_today": tick_sync_service.tick_count_today,
            "last_tick_time": tick_sync_service.last_tick_time,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }


@router.get("/api/config")
def get_config():
    """获取当前系统配置"""
    return {
        "status": "ok",
        "data": {
            "default_symbol": settings.DEFAULT_SYMBOL,
            "default_lot": settings.DEFAULT_LOT,
            "max_lot": settings.MAX_LOT,
            "max_positions": settings.MAX_POSITIONS,
            "max_daily_loss": settings.MAX_DAILY_LOSS,
            "enable_real_trading": settings.ENABLE_REAL_TRADING,
            "allowed_symbols": settings.allowed_symbols_list,
            "tick_sync_interval_ms": settings.TICK_SYNC_INTERVAL_MS,
            "tick_storage_days": settings.TICK_STORAGE_DAYS,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }


@router.post("/api/system/emergency-stop")
async def emergency_stop():
    """一键紧急停止：停止策略 + 禁止交易 + 关闭 WebSocket"""
    import logging
    logger = logging.getLogger(__name__)

    # 停止 Tick 同步
    await tick_sync_service.stop()

    # 关闭所有 WebSocket
    closed = await ws_manager.close_all()

    # 禁用交易
    settings.ENABLE_REAL_TRADING = False

    logger.critical("EMERGENCY STOP activated")

    return {
        "status": "ok",
        "data": {
            "strategies_stopped": 0,
            "real_trading_disabled": True,
            "websocket_connections_closed": closed,
            "tick_sync_stopped": True,
            "mode": "SAFE_MODE",
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }


@router.get("/api/tick-count")
def tick_count(db: Session = Depends(get_db)):
    """获取今日 Tick 采集统计"""
    today = time.strftime("%Y-%m-%d")
    count = db.query(TickDatum).filter(TickDatum.created_at >= today).count()
    return {
        "status": "ok",
        "data": {
            "today": today,
            "count": count,
            "sync_running": tick_sync_service.is_running,
            "last_tick_time": tick_sync_service.last_tick_time,
        },
    }
