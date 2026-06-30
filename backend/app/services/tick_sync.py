"""
Tick 行情同步服务 — 后台异步采集 Tick 数据 → 写入 SQLite → WebSocket 广播。
"""
import asyncio
import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.database import SessionLocal
from app.models import TickDatum, SystemLog
from app.mt5_client import mt5_client

logger = logging.getLogger(__name__)
settings = get_settings()


class TickSyncService:
    """后台 Tick 同步服务"""

    def __init__(self, ws_manager=None):
        self.ws_manager = ws_manager          # WebSocket 管理器引用（可选）
        self._running = False
        self._task: asyncio.Task | None = None
        self._tick_count_today: int = 0
        self._last_tick_time: str = ""
        self._symbols: list[str] = []

    @property
    def tick_count_today(self) -> int:
        return self._tick_count_today

    @property
    def last_tick_time(self) -> str:
        return self._last_tick_time

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, symbols: list[str] = None) -> None:
        """启动后台 Tick 同步"""
        if self._running:
            return

        self._symbols = symbols or settings.allowed_symbols_list
        self._running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info(f"Tick sync started — symbols={self._symbols}, interval={settings.TICK_SYNC_INTERVAL_MS}ms")

        # 记录系统日志
        self._log_system("INFO", "tick_sync", f"Tick sync started for {len(self._symbols)} symbols")

    async def stop(self) -> None:
        """停止后台 Tick 同步"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Tick sync stopped")
        self._log_system("INFO", "tick_sync", "Tick sync stopped")

    async def add_symbol(self, symbol: str) -> None:
        """动态添加品种"""
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            logger.info(f"Tick sync: added symbol {symbol}")

    async def remove_symbol(self, symbol: str) -> None:
        """动态移除品种"""
        if symbol in self._symbols:
            self._symbols.remove(symbol)

    async def _sync_loop(self) -> None:
        """主循环：每隔 TICK_SYNC_INTERVAL_MS 采集一次所有品种的 Tick"""
        interval = settings.TICK_SYNC_INTERVAL_MS / 1000.0

        # 启动时先做一次清理：删除过期数据
        await self._cleanup_old_data()

        while self._running:
            try:
                if not mt5_client.is_connected:
                    logger.warning("MT5 disconnected, attempting reconnect...")
                    mt5_client.reconnect()
                    await asyncio.sleep(2)
                    continue

                for symbol in self._symbols:
                    try:
                        tick = mt5_client.symbol_tick(symbol)
                        resolved_symbol = tick.get("symbol", symbol)
                        self._store_tick(resolved_symbol, tick)
                        self._tick_count_today += 1
                        self._last_tick_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                        # WebSocket 广播 — 同时推送到原始名和已解析名两个频道
                        if self.ws_manager:
                            tick_time_str = datetime.utcfromtimestamp(tick.get("time", 0)).strftime("%Y-%m-%d %H:%M:%S")
                            tick_data = {
                                "symbol": resolved_symbol,
                                "bid": tick.get("bid"),
                                "ask": tick.get("ask"),
                                "spread": round(tick.get("ask", 0) - tick.get("bid", 0), 6),
                                "last": tick.get("last"),
                                "volume": tick.get("volume", 0),
                                "time": tick_time_str,
                            }
                            await self.ws_manager.broadcast_tick(resolved_symbol, tick_data)
                            if resolved_symbol != symbol:
                                await self.ws_manager.broadcast_tick(symbol, tick_data)
                    except Exception as e:
                        logger.debug(f"Tick sync error for {symbol}: {e}")

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Tick sync loop error: {e}", exc_info=True)
                self._log_system("ERROR", "tick_sync", f"Loop error: {e}")
                await asyncio.sleep(2)

    def _store_tick(self, symbol: str, tick: dict) -> None:
        """将 Tick 写入数据库"""
        db = SessionLocal()
        try:
            tick_time_str = datetime.utcfromtimestamp(tick.get("time", 0)).strftime("%Y-%m-%d %H:%M:%S")
            record = TickDatum(
                symbol=symbol,
                bid=tick.get("bid", 0),
                ask=tick.get("ask", 0),
                spread=round(tick.get("ask", 0) - tick.get("bid", 0), 6),
                last=tick.get("last"),
                volume=tick.get("volume", 0),
                time=tick_time_str,
            )
            db.add(record)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store tick for {symbol}: {e}")
        finally:
            db.close()

    async def _cleanup_old_data(self) -> None:
        """清理超过保留期限的 Tick 数据"""
        db = SessionLocal()
        try:
            cutoff = (datetime.now() - timedelta(days=settings.TICK_STORAGE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            deleted = db.query(TickDatum).filter(TickDatum.created_at < cutoff).delete()
            db.commit()
            if deleted:
                logger.info(f"Cleaned up {deleted} old tick records (cutoff: {cutoff})")
        except Exception as e:
            db.rollback()
            logger.warning(f"Tick cleanup failed: {e}")
        finally:
            db.close()

    def _log_system(self, level: str, module: str, message: str) -> None:
        """写入 system_logs 表"""
        db = SessionLocal()
        try:
            db.add(SystemLog(level=level, module=module, message=message))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


# 全局单例
tick_sync_service = TickSyncService()
