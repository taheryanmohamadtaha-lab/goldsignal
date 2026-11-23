"""حمایت/مقاومت و الگوهای کندلی پایه."""
from __future__ import annotations

import numpy as np
import pandas as pd


def doji(df: pd.DataFrame, ratio: float = 0.1) -> pd.Series:
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return ((df["close"] - df["open"]).abs() / rng <= ratio).fillna(False)


def pin_bar(df: pd.DataFrame) -> pd.Series:
    """+1 پین‌بار صعودی (سایه پایین بلند)، −1 نزولی، 0 هیچ."""
    body = (df["close"] - df["open"]).abs()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    lower = df[["open", "close"]].min(axis=1) - df["low"]
    bull = (lower >= 2 * body) & (lower / rng >= 0.6)
    bear = (upper >= 2 * body) & (upper / rng >= 0.6)
    return pd.Series(np.where(bull, 1, np.where(bear, -1, 0)), index=df.index)


def engulfing(df: pd.DataFrame) -> pd.Series:
    """+1 انگلفینگ صعودی، −1 نزولی."""
    po, pc = df["open"].shift(), df["close"].shift()
    bull = (pc < po) & (df["close"] > df["open"]) & (df["open"] <= pc) & (df["close"] >= po)
    bear = (pc > po) & (df["close"] < df["open"]) & (df["open"] >= pc) & (df["close"] <= po)
    return pd.Series(np.where(bull, 1, np.where(bear, -1, 0)), index=df.index)


def support_resistance(df: pd.DataFrame, window: int = 3, tol: float = 0.005, max_levels: int = 4) -> tuple[list[float], list[float]]:
    """پیوت‌های محلی را خوشه‌بندی می‌کند (فاصلهٔ نسبی tol). برمی‌گرداند (حمایت‌ها، مقاومت‌ها) نسبت به قیمت آخر."""
    if len(df) < 2 * window + 1:
        return [], []
    hi, lo = df["high"].to_numpy(), df["low"].to_numpy()
    piv: list[float] = []
    for i in range(window, len(df) - window):
        if hi[i] == hi[i - window:i + window + 1].max():
            piv.append(float(hi[i]))
        if lo[i] == lo[i - window:i + window + 1].min():
            piv.append(float(lo[i]))
    levels: list[list[float]] = []
    for p in sorted(piv):
        if levels and abs(p - np.mean(levels[-1])) / np.mean(levels[-1]) <= tol:
            levels[-1].append(p)
        else:
            levels.append([p])
    levels.sort(key=len, reverse=True)
    lv = sorted(float(np.mean(x)) for x in levels[:max_levels * 2])
    last = float(df["close"].iloc[-1])
    return [x for x in lv if x < last][-max_levels:], [x for x in lv if x >= last][:max_levels]


def bubble_trend(bubble_pct: pd.Series, lookback: int = 60) -> str:
    """موقعیت حباب فعلی نسبت به میانگین تاریخی: 'high' / 'low' / 'normal' / 'unknown'."""
    s = bubble_pct.dropna()
    if len(s) < 10:
        return "unknown"
    s = s.iloc[-lookback:]
    m, sd = s.mean(), s.std(ddof=0)
    if sd == 0:
        return "normal"
    z = (s.iloc[-1] - m) / sd
    return "high" if z > 1 else "low" if z < -1 else "normal"
