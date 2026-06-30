"""
MT5 客户端封装 — 连接/行情/账户/持仓/订单。
所有 MT5 API 调用集中在此模块，外部不直接调用 MetaTrader5。
"""
import logging
from typing import Optional
from datetime import datetime

import MetaTrader5 as mt5
import pandas as pd

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# MT5 时间周期映射
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M3": getattr(mt5, "TIMEFRAME_M3", 3),
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H2": getattr(mt5, "TIMEFRAME_H2", 16386),
    "H4": mt5.TIMEFRAME_H4,
    "H8": getattr(mt5, "TIMEFRAME_H8", 16392),
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

# ATR 统计使用的 12 周期（与 MQL5 策略面板一致）
ATR_TIMEFRAMES = ["M1", "M3", "M5", "M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1"]


class MT5Client:
    """MT5 连接单例 — 封装所有 MetaTrader5 官方库调用"""

    # 品种后缀候选项（按优先级排列，空字符串表示无后缀）
    _SYMBOL_SUFFIXES = ["", ".c", ".s", ".m", ".pro", ".v", ".t", ".r"]

    def __init__(self):
        self.connected: bool = False
        self._account: Optional[dict] = None
        self._symbol_cache: dict[str, str] = {}  # requested -> actual symbol

    # ---- 生命周期 ----

    def connect(self) -> bool:
        """初始化 MT5 连接。必须先手动打开 MT5 Terminal 并登录。"""
        if self.connected:
            return True

        try:
            if not mt5.initialize():
                err = mt5.last_error()
                logger.error(f"MT5 initialize failed: {err}")
                return False

            self.connected = True
            account = mt5.account_info()
            if account:
                self._account = account._asdict()
                logger.info(
                    f"MT5 connected — account={self._account.get('login')}, "
                    f"server={self._account.get('server')}"
                )
            else:
                logger.warning("MT5 initialized but account_info returned None (not logged in?)")

            return True
        except Exception as e:
            logger.error(f"MT5 connect exception: {e}")
            return False

    def shutdown(self) -> None:
        """关闭 MT5 连接"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 shutdown")

    def reconnect(self) -> bool:
        """断线重连"""
        logger.info("MT5 reconnecting...")
        self.shutdown()
        import time
        time.sleep(1)
        return self.connect()

    @property
    def is_connected(self) -> bool:
        """检查终端是否仍在运行"""
        if not self.connected:
            return False
        try:
            info = mt5.terminal_info()
            return info is not None and info.connected
        except Exception:
            return False

    # ---- 品种解析 ----

    def resolve_symbol(self, symbol: str) -> str:
        """将请求的品种名解析为 MT5 中实际存在的品种名。

        自动尝试常见后缀（.c / .s / .m 等），解决不同券商品种命名差异。
        结果会被缓存，避免重复查询。
        """
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]

        # 1. 精确匹配
        info = mt5.symbol_info(symbol)
        if info is not None:
            self._symbol_cache[symbol] = symbol
            logger.debug(f"Symbol resolved: {symbol} -> {symbol} (exact)")
            return symbol

        # 2. 尝试常见后缀
        base_symbol = symbol
        for suffix in self._SYMBOL_SUFFIXES:
            if suffix == "":
                continue  # 已经试过
            candidate = base_symbol + suffix
            info = mt5.symbol_info(candidate)
            if info is not None:
                self._symbol_cache[symbol] = candidate
                logger.info(f"Symbol resolved: {symbol} -> {candidate}")
                return candidate

        # 3. 如果 symbol 本身带后缀，尝试去掉后缀
        import re
        stripped = re.sub(r'\.[a-zA-Z]+$', '', symbol)
        if stripped != symbol:
            info = mt5.symbol_info(stripped)
            if info is not None:
                self._symbol_cache[symbol] = stripped
                logger.info(f"Symbol resolved: {symbol} -> {stripped} (suffix removed)")
                return stripped

        # 4. 全部失败，返回原始值（后续调用会报错）
        self._symbol_cache[symbol] = symbol
        logger.warning(f"Symbol '{symbol}' not found in Market Watch, using as-is")
        return symbol

    # ---- 账户 ----

    def account_info(self) -> dict:
        """获取账户信息"""
        account = mt5.account_info()
        if account is None:
            err = mt5.last_error()
            raise RuntimeError(f"account_info failed: {err}")
        return account._asdict()

    # ---- 行情 ----

    def symbol_tick(self, symbol: str) -> dict:
        """获取实时 Tick（自动解析品种名称）"""
        symbol = self.resolve_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            err = mt5.last_error()
            raise RuntimeError(f"symbol_tick({symbol}) failed: {err}")
        d = tick._asdict()
        d["symbol"] = symbol           # 补充已解析的品种名
        d["spread"] = round(d.get("ask", 0) - d.get("bid", 0), 6)
        return d

    def symbol_info(self, symbol: str) -> dict:
        """获取品种合约信息（自动解析品种名称）"""
        symbol = self.resolve_symbol(symbol)
        info = mt5.symbol_info(symbol)
        if info is None:
            err = mt5.last_error()
            raise RuntimeError(f"symbol_info({symbol}) failed: {err}")
        return info._asdict()

    def get_symbols(self) -> list[dict]:
        """获取 Market Watch 中的所有品种"""
        symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return [s._asdict() for s in symbols]

    def get_rates(
        self, symbol: str, timeframe: str, count: int = 200,
        from_time: Optional[datetime] = None, to_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """获取历史 K 线（自动解析品种名称）"""
        symbol = self.resolve_symbol(symbol)
        tf = TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M5)

        if from_time and to_time:
            rates = mt5.copy_rates_range(symbol, tf, from_time, to_time)
        else:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

        if rates is None:
            err = mt5.last_error()
            raise RuntimeError(f"get_rates({symbol}, {timeframe}) failed: {err}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    # ---- 持仓 ----

    def positions_get(self, symbol: Optional[str] = None) -> list[dict]:
        """获取当前持仓（自动解析品种名称）"""
        if symbol:
            symbol = self.resolve_symbol(symbol)
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []
        return [p._asdict() for p in positions]

    # ---- 订单 ----

    def order_check(self, request: dict) -> dict:
        """订单预检"""
        result = mt5.order_check(request)
        if result is None:
            err = mt5.last_error()
            raise RuntimeError(f"order_check failed: {err}")
        return result._asdict()

    def order_send(self, request: dict) -> dict:
        """发送订单"""
        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            raise RuntimeError(f"order_send failed: {err}")
        return result._asdict()

    def positions_close(self, ticket: int, lot: float = None, deviation: int = 20) -> dict:
        """平仓"""
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "deviation": deviation,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if lot:
            request["volume"] = lot
        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            raise RuntimeError(f"positions_close({ticket}) failed: {err}")
        return result._asdict()

    # ---- 工具 ----

    def build_market_request(
        self, symbol: str, action: str, volume: float,
        sl: float = None, tp: float = None, deviation: int = 20, comment: str = ""
    ) -> dict:
        """构建市价单请求（自动解析品种名称）"""
        symbol = self.resolve_symbol(symbol)
        tick = self.symbol_tick(symbol)
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick["ask"] if action == "BUY" else tick["bid"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": deviation,
            "magic": 20260101,
            "comment": comment or f"python {action.lower()}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp
        return request

    def last_error(self) -> tuple:
        """获取最后的错误信息"""
        err = mt5.last_error()
        return (err[0], err[1])


# 全局单例
mt5_client = MT5Client()
