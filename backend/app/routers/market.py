"""
行情路由 — Tick / K线 / 品种信息 / 历史 Tick 查询。
"""
import json
import time
from typing import Optional
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import TickDatum
from app.mt5_client import mt5_client, TIMEFRAME_MAP

router = APIRouter(tags=["行情"])


@router.get("/api/tick/{symbol}")
def get_tick(symbol: str):
    """获取单个品种实时 Tick"""
    try:
        data = mt5_client.symbol_tick(symbol)
        return {
            "status": "ok",
            "data": {
                "symbol": symbol,
                "bid": data.get("bid"),
                "ask": data.get("ask"),
                "spread": round(data.get("ask", 0) - data.get("bid", 0), 6),
                "last": data.get("last"),
                "volume": data.get("volume", 0),
                "time": str(data.get("time", "")),
                "digits": data.get("digits", 2),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }
    except RuntimeError as e:
        return {"status": "error", "detail": str(e), "error_code": "MT5_TICK_FAILED"}


@router.get("/api/ticks")
def get_ticks_batch(symbols: str = Query(..., description="逗号分隔的品种列表")):
    """批量获取多品种 Tick"""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    results = []
    errors = []
    for sym in sym_list:
        try:
            tick = mt5_client.symbol_tick(sym)
            results.append({
                "symbol": sym,
                "bid": tick.get("bid"),
                "ask": tick.get("ask"),
                "spread": round(tick.get("ask", 0) - tick.get("bid", 0), 6),
                "time": str(tick.get("time", "")),
            })
        except RuntimeError as e:
            errors.append({"symbol": sym, "error": str(e)})
    return {
        "status": "ok",
        "data": results,
        "errors": errors,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }


@router.get("/api/rates/{symbol}")
def get_rates(
    symbol: str,
    timeframe: str = Query(default="M5", description="K线周期: M1/M5/M15/M30/H1/H4/D1/W1"),
    count: int = Query(default=200, ge=1, le=5000),
):
    """获取历史 K 线"""
    if timeframe not in TIMEFRAME_MAP:
        return {
            "status": "error",
            "detail": f"Invalid timeframe '{timeframe}'. Valid: {list(TIMEFRAME_MAP.keys())}",
        }
    try:
        df = mt5_client.get_rates(symbol, timeframe, count)
        rates = df.to_dict(orient="records")
        # 转换时间字段为字符串
        for r in rates:
            if hasattr(r.get("time"), "isoformat"):
                r["time"] = r["time"].isoformat()
        return {
            "status": "ok",
            "data": {
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(rates),
                "rates": rates,
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }
    except RuntimeError as e:
        return {"status": "error", "detail": str(e), "error_code": "MT5_RATES_FAILED"}


@router.get("/api/symbol/{symbol}")
def get_symbol_info(symbol: str):
    """获取品种合约信息"""
    try:
        info = mt5_client.symbol_info(symbol)
        return {
            "status": "ok",
            "data": {
                "symbol": symbol,
                "description": info.get("description", ""),
                "digits": info.get("digits"),
                "point": info.get("point"),
                "trade_contract_size": info.get("trade_contract_size"),
                "volume_min": info.get("volume_min"),
                "volume_max": info.get("volume_max"),
                "volume_step": info.get("volume_step"),
                "swap_long": info.get("swap_long"),
                "swap_short": info.get("swap_short"),
                "spread": info.get("spread"),
                "trade_mode": info.get("trade_mode"),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }
    except RuntimeError as e:
        return {"status": "error", "detail": str(e), "error_code": "SYMBOL_NOT_FOUND"}


@router.get("/api/symbols")
def get_all_symbols():
    """获取 Market Watch 品种列表"""
    try:
        symbols = mt5_client.get_symbols()
        return {
            "status": "ok",
            "data": {
                "count": len(symbols),
                "symbols": [{"name": s.get("name"), "description": s.get("description", "")}
                           for s in symbols[:50]],  # 限制返回前50个
            },
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ═══════════════════════════════════════════════════════════════
# 历史 Tick 查询（从 SQLite 读取同步数据）
# ═══════════════════════════════════════════════════════════════

@router.get("/api/tick-history/{symbol}")
def get_tick_history(
    symbol: str,
    limit: int = Query(default=1000, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    from_time: str = Query(default=None, description="起始时间 (YYYY-MM-DD HH:MM:SS)"),
    to_time: str = Query(default=None, description="结束时间 (YYYY-MM-DD HH:MM:SS)"),
    db: Session = Depends(get_db),
):
    """查询数据库中历史 Tick 记录（支持分页和时间筛选）。
    性能优化: 使用 id 范围估算替代 COUNT(*)，避免全表扫描。
    自动解析品种名：同时查询原始名和已解析名。
    """
    resolved = mt5_client.resolve_symbol(symbol)
    search_symbols = {symbol, resolved}  # 用集合去重

    q = db.query(TickDatum).filter(TickDatum.symbol.in_(search_symbols))

    if from_time:
        q = q.filter(TickDatum.time >= from_time)
    if to_time:
        q = q.filter(TickDatum.time <= to_time)

    # 避免 COUNT(*) 全表扫描：多取 1 条判断是否有更多数据
    records = (
        q.order_by(desc(TickDatum.id))
        .offset(offset)
        .limit(limit + 1)  # +1 to detect has_more
        .all()
    )

    has_more = len(records) > limit
    if has_more:
        records = records[:limit]

    return {
        "status": "ok",
        "data": {
            "symbol": symbol,
            "count": len(records),
            "offset": offset,
            "has_more": has_more,
            "ticks": [r.to_dict() for r in reversed(records)],
        },
    }
