"""
持仓路由 — 当前持仓列表。
"""
import time
from typing import Optional
from fastapi import APIRouter, Query
from app.mt5_client import mt5_client

router = APIRouter(tags=["持仓"])


@router.get("/api/positions")
def get_positions(symbol: Optional[str] = Query(default=None)):
    """获取当前持仓"""
    try:
        positions = mt5_client.positions_get(symbol=symbol)
        total_profit = sum(p.get("profit", 0) for p in positions)

        # 添加可读字段
        result = []
        for p in positions:
            result.append({
                "ticket": p.get("ticket"),
                "symbol": p.get("symbol"),
                "type": "BUY" if p.get("type") == 0 else "SELL",
                "volume": p.get("volume"),
                "price_open": p.get("price_open"),
                "price_current": p.get("price_current"),
                "sl": p.get("sl"),
                "tp": p.get("tp"),
                "profit": p.get("profit"),
                "swap": p.get("swap", 0),
                "commission": p.get("commission", 0),
                "comment": p.get("comment", ""),
                "time_open": str(p.get("time")) if p.get("time") else "",
                "magic": p.get("magic"),
            })

        return {
            "status": "ok",
            "data": {
                "count": len(result),
                "total_profit": round(total_profit, 2),
                "positions": result,
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/api/pending-orders")
def get_pending_orders(symbol: Optional[str] = Query(default=None)):
    """获取当前挂单（Limit / Stop 订单）"""
    import MetaTrader5 as mt5
    try:
        if symbol:
            orders = mt5.orders_get(symbol=symbol)
        else:
            orders = mt5.orders_get()
        if orders is None:
            orders = []

        result = []
        for o in orders:
            d = o._asdict()
            otype = d.get("type", 0)
            type_names = {
                2: "BUY_LIMIT", 3: "SELL_LIMIT",
                4: "BUY_STOP", 5: "SELL_STOP",
                6: "BUY_STOP_LIMIT", 7: "SELL_STOP_LIMIT",
            }
            state_names = {
                0: "STARTED", 1: "PLACED", 2: "CANCELED",
                3: "PARTIAL", 4: "FILLED", 5: "REJECTED", 6: "EXPIRED",
            }
            result.append({
                "ticket": d.get("ticket"),
                "symbol": d.get("symbol"),
                "type": type_names.get(otype, f"TYPE_{otype}"),
                "volume": d.get("volume_initial", d.get("volume", 0)),
                "volume_current": d.get("volume_current", 0),
                "price_open": d.get("price_open"),
                "price_current": d.get("price_current"),
                "sl": d.get("sl"),
                "tp": d.get("tp"),
                "state": state_names.get(d.get("state", 1), str(d.get("state"))),
                "comment": d.get("comment", ""),
                "time_setup": str(d.get("time_setup", "")),
                "magic": d.get("magic"),
            })

        return {
            "status": "ok",
            "data": {
                "count": len(result),
                "orders": result,
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
