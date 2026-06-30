"""
ATR 多周期统计服务 — 与 MQL5 ATR_统计交易辅助面板 逻辑一致。

核心指标:
  - ATR(1)  / ATR(5)  / ATR(50)   — 3 个周期 × 12 个 timeframe
  - r15   = ATR1  / ATR5           — 短期/中期波动比
  - r550  = ATR5  / ATR50          — 中期/长期波动比
  - r150  = ATR1  / ATR50          — 短期/长期波动比
  - state = classify(r15, r550)     — 7 种市场状态分类
"""
import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from app.mt5_client import mt5_client, ATR_TIMEFRAMES, TIMEFRAME_MAP

logger = logging.getLogger(__name__)


# ---- 状态分类（与 MQL5 策略完全一致） ----

def classify_state(r15: float, r550: float) -> tuple[str, str]:
    """
    根据 r15 和 r550 返回 (状态名称, 颜色)。
    阈值与 MQL5 Classify() 函数保持一致。
    """
    if r15 > 2.0 and r550 > 1.5:
        return "极端波动", "#FF6347"       # clrTomato
    if r15 > 1.5 and r550 > 1.0:
        return "趋势启动", "#32CD32"       # clrLimeGreen
    if 0.8 <= r15 <= 1.2 and r550 > 1.0:
        return "趋势延续", "#00BFFF"       # clrDeepSkyBlue
    if r15 < 0.5 and r550 < 0.7:
        return "极度压缩", "#D2691E"       # clrChocolate
    if r15 < 0.7 and r550 <= 1.0:
        return "动能衰竭", "#FFA500"       # clrOrange
    if 0.5 <= r15 <= 1.5 and 0.8 <= r550 <= 1.2:
        return "温和波动", "#FFD700"       # clrGold
    return "混合观察", "#C0C0C0"           # clrSilver


def _ratio_direction(value: float) -> int:
    """比率方向：>1 → 1(上升), <1 → -1(下降), ≈1 → 0(持平)"""
    eps = 0.0001
    if value > 1.0 + eps:
        return 1
    if value < 1.0 - eps:
        return -1
    return 0


def _ratio_arrow(value: float) -> str:
    d = _ratio_direction(value)
    if d > 0:
        return "↗"
    if d < 0:
        return "↘"
    return "→"


def _ratio_arrow_color(value: float) -> str:
    d = _ratio_direction(value)
    if d > 0:
        return "#00FF00"
    if d < 0:
        return "#FF4500"
    return "#FFD700"


# ---- ATR 计算 ----

def _calc_tr(df: pd.DataFrame) -> pd.Series:
    """计算 True Range"""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _calc_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """计算 SMA-based ATR（与 MQL5 iATR 默认一致）"""
    tr = _calc_tr(df)
    return tr.rolling(window=period, min_periods=period).mean()


def _get_atr_values(df: pd.DataFrame, shift: int = 0) -> dict:
    """
    从 DataFrame 取出指定 shift 位置的 ATR1/ATR5/ATR50 及比率。
    shift=0 表示最新一根 K 线（实时），shift=1 表示上一根（收盘确认）。
    """
    if df is None or len(df) < 50:
        return None

    atr1_series = _calc_atr(df, 1)
    atr5_series = _calc_atr(df, 5)
    atr50_series = _calc_atr(df, 50)

    idx = -1 - shift  # -1 = last row, -2 = second-to-last
    if abs(idx) > len(df):
        return None

    atr1 = float(atr1_series.iloc[idx]) if not pd.isna(atr1_series.iloc[idx]) else 0.0
    atr5 = float(atr5_series.iloc[idx]) if not pd.isna(atr5_series.iloc[idx]) else 0.0
    atr50 = float(atr50_series.iloc[idx]) if not pd.isna(atr50_series.iloc[idx]) else 0.0

    if atr1 <= 0 or atr5 <= 0 or atr50 <= 0:
        return None

    r15 = round(atr1 / atr5, 4)
    r550 = round(atr5 / atr50, 4)
    r150 = round(atr1 / atr50, 4)
    state_name, state_color = classify_state(r15, r550)

    return {
        "atr1": round(atr1, 2),
        "atr5": round(atr5, 2),
        "atr50": round(atr50, 2),
        "r15": r15,
        "r550": r550,
        "r150": r150,
        "state": state_name,
        "state_color": state_color,
    }


def collect_atr_stats(symbol: str) -> dict | None:
    """
    为指定品种收集所有 12 个周期的 ATR 统计数据。
    返回格式:
    {
        "symbol": "XAUUSD.c",
        "table": [{timeframe, atr1, atr5, atr50, r15, r550, r150, state, ...}, ...],
        "summary": {atr5, r15, r550, state, ...},
    }
    """
    if not mt5_client.is_connected:
        return None

    resolved = mt5_client.resolve_symbol(symbol)
    table = []

    for tf in ATR_TIMEFRAMES:
        try:
            df = mt5_client.get_rates(resolved, tf, count=100)
            current = _get_atr_values(df, shift=0)
            previous = _get_atr_values(df, shift=1)

            if current is None:
                continue

            r15_prev = previous["r15"] if previous else current["r15"]
            r550_prev = previous["r550"] if previous else current["r550"]
            r150_prev = previous["r150"] if previous else current["r150"]

            table.append({
                "timeframe": tf,
                "atr1": current["atr1"],
                "atr5": current["atr5"],
                "atr50": current["atr50"],
                "r15": current["r15"],
                "r550": current["r550"],
                "r150": current["r150"],
                "state": current["state"],
                "state_color": current["state_color"],
                "r15_arrow": _ratio_arrow(current["r15"]),
                "r550_arrow": _ratio_arrow(current["r550"]),
                "r150_arrow": _ratio_arrow(current["r150"]),
                "r15_color": _ratio_arrow_color(current["r15"]),
                "r550_color": _ratio_arrow_color(current["r550"]),
                "r150_color": _ratio_arrow_color(current["r150"]),
            })
        except Exception as e:
            logger.debug(f"ATR calc failed for {resolved} {tf}: {e}")
            continue

    if not table:
        return None

    # 摘要：取当前图表周期的数据（默认为第一个成功计算的周期）
    summary_row = table[0]
    return {
        "symbol": resolved,
        "table": table,
        "summary": {
            "timeframe": summary_row["timeframe"],
            "atr1": summary_row["atr1"],
            "atr5": summary_row["atr5"],
            "atr50": summary_row["atr50"],
            "r15": summary_row["r15"],
            "r550": summary_row["r550"],
            "r150": summary_row["r150"],
            "state": summary_row["state"],
            "state_color": summary_row["state_color"],
        },
    }


# 全局单例
atr_service = type("AtrService", (), {"collect": staticmethod(collect_atr_stats)})()
