"""
ATR 统计路由 — 多周期 ATR 指标计算与状态分类。
"""
import time
from fastapi import APIRouter, Query
from app.services.atr_service import collect_atr_stats

router = APIRouter(tags=["ATR统计"])


@router.get("/api/atr-stats/{symbol}")
def get_atr_stats(symbol: str, tf: str = Query(default="M5", description="高亮选中的周期")):
    """获取多周期 ATR 统计数据（12 个周期 × 7 个维度）"""
    data = collect_atr_stats(symbol)
    if data is None:
        return {
            "status": "error",
            "detail": "ATR data not available — MT5 may be disconnected or symbol not found",
            "error_code": "ATR_UNAVAILABLE",
        }

    # 标记选中的周期行
    for row in data["table"]:
        row["selected"] = (row["timeframe"] == tf)

    return {
        "status": "ok",
        "data": data,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }
