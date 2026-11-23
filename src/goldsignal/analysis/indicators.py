"""اندیکاتورها روی DataFrame با ستون‌های open/high/low/close (و volume اختیاری)."""
from __future__ import annotations

import numpy as np
import pandas as pd

TF_RULES = {"1h": "1h", "4h": "4h", "1d": "1D", "1w": "W"}


def make_candles(history: list[tuple[int, float]], timeframe: str, volume: list[tuple[int, float]] | None = None) -> pd.DataFrame:
    """ساخت کندل از نقاط قیمتی ذخیره‌شده. اگر حجم نبود، ستون volume ساخته نمی‌شود."""
    if not history:
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    s = pd.Series([v for _, v in history], index=pd.to_datetime([t for t, _ in history], unit="s", utc=True)).sort_index()
    df = s.resample(TF_RULES[timeframe]).ohlc().dropna()
    if volume:
        v = pd.Series([x for _, x in volume], index=pd.to_datetime([t for t, _ in volume], unit="s", utc=True)).sort_index()
        df["volume"] = v.resample(TF_RULES[timeframe]).sum().reindex(df.index).fillna(0)
    return df


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI با میانگین وایلدر."""
    d = close.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(ad != 0, 100.0).where(au.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
