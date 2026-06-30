"""
WebSocket 路由 — Tick 实时推送 / 事件推送。
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.services.websocket_manager import ws_manager
from app.services.tick_sync import tick_sync_service
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/ticks/{symbol}")
async def ws_ticks_single(websocket: WebSocket, symbol: str):
    """单品种 Tick 实时推送"""
    await ws_manager.connect_tick(websocket, symbol)
    try:
        while True:
            # 保持连接存活（接收客户端 pong/close）
            data = await websocket.receive_text()
            # 支持客户端动态切换品种
            if data.startswith("subscribe:"):
                new_symbol = data.split(":", 1)[1].strip()
                await ws_manager.disconnect_tick(websocket, symbol)
                symbol = new_symbol
                await ws_manager.connect_tick(websocket, symbol)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WS tick error: {e}")
    finally:
        await ws_manager.disconnect_tick(websocket, symbol)


@router.websocket("/ws/ticks")
async def ws_ticks_multi(websocket: WebSocket, symbols: str = Query(default="")):
    """多品种 Tick 推送 (ws://host/ws/ticks?symbols=XAUUSD,EURUSD)"""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else [settings.DEFAULT_SYMBOL]

    # 注册到所有品种
    for sym in sym_list:
        await ws_manager.connect_tick(websocket, sym)

    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WS multi-tick error: {e}")
    finally:
        for sym in sym_list:
            await ws_manager.disconnect_tick(websocket, sym)


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """系统事件实时推送（策略信号 / 订单状态 / 告警）"""
    await ws_manager.connect_events(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WS events error: {e}")
    finally:
        await ws_manager.disconnect_events(websocket)
