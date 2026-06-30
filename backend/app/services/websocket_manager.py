"""
WebSocket 连接管理器 — 管理所有活跃 WS 连接，支持广播和房间。
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """管理 WebSocket 连接：Tick 频道 + 事件频道"""

    def __init__(self):
        # tick 频道: {symbol: set[WebSocket]}
        self._tick_connections: dict[str, set[WebSocket]] = {}
        # 事件频道: set[WebSocket]
        self._event_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    # ---- Tick 频道 ----

    async def connect_tick(self, websocket: WebSocket, symbol: str) -> None:
        """接受 WebSocket 并注册到指定 symbol 的 Tick 频道"""
        await websocket.accept()
        async with self._lock:
            if symbol not in self._tick_connections:
                self._tick_connections[symbol] = set()
            self._tick_connections[symbol].add(websocket)
        logger.info(f"WS tick connected: {symbol} (total: {len(self._tick_connections.get(symbol, set()))})")

        # 发送连接确认
        await self._send(websocket, {
            "type": "connected",
            "data": {"symbol": symbol},
            "timestamp": self._now(),
        })

    async def disconnect_tick(self, websocket: WebSocket, symbol: str) -> None:
        """从 Tick 频道断开"""
        async with self._lock:
            if symbol in self._tick_connections:
                self._tick_connections[symbol].discard(websocket)
                if not self._tick_connections[symbol]:
                    del self._tick_connections[symbol]
        logger.info(f"WS tick disconnected: {symbol}")

    async def broadcast_tick(self, symbol: str, data: dict) -> None:
        """向订阅了指定 symbol 的所有客户端广播 Tick"""
        async with self._lock:
            connections = list(self._tick_connections.get(symbol, set()))

        if not connections:
            return

        message = json.dumps({
            "type": "tick",
            "data": data,
            "timestamp": self._now(),
        })

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._tick_connections.get(symbol, set()).discard(ws)

    # ---- 事件频道 ----

    async def connect_events(self, websocket: WebSocket) -> None:
        """接受 WebSocket 并注册到事件频道"""
        await websocket.accept()
        async with self._lock:
            self._event_connections.add(websocket)
        logger.info(f"WS events connected (total: {len(self._event_connections)})")

        await self._send(websocket, {
            "type": "connected",
            "data": {"channel": "events"},
            "timestamp": self._now(),
        })

    async def disconnect_events(self, websocket: WebSocket) -> None:
        """从事件频道断开"""
        async with self._lock:
            self._event_connections.discard(websocket)
        logger.info(f"WS events disconnected")

    async def broadcast_event(self, event_type: str, data: dict) -> None:
        """向所有事件频道客户端广播"""
        async with self._lock:
            connections = list(self._event_connections)

        if not connections:
            return

        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": self._now(),
        })

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._event_connections.discard(ws)

    # ---- 工具 ----

    async def close_all(self) -> int:
        """关闭所有连接（紧急停止时使用）"""
        count = 0
        async with self._lock:
            for ws_set in self._tick_connections.values():
                for ws in list(ws_set):
                    try:
                        await ws.close()
                        count += 1
                    except Exception:
                        pass
            self._tick_connections.clear()

            for ws in list(self._event_connections):
                try:
                    await ws.close()
                    count += 1
                except Exception:
                    pass
            self._event_connections.clear()

        logger.info(f"Closed {count} WebSocket connections")
        return count

    async def _send(self, ws: WebSocket, data: dict) -> None:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            pass

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat() + "Z"


# 全局单例
ws_manager = WebSocketManager()
