import numpy as np
import pandas as pd
import pytest

from goldsignal.analysis import indicators as ind
from goldsignal.analysis import patterns as pat


def frame(close):
    idx = pd.date_range("2025-01-01", periods=len(close), freq="D", tz="UTC")
    c = pd.Series(close, index=idx, dtype=float)
    return pd.DataFrame({"open": c.shift().fillna(c), "high": c + 1, "low": c - 1, "close": c})


def test_sma_ema():
    s = pd.Series([1, 2, 3, 4, 5.0])
    assert ind.sma(s, 3).iloc[-1] == pytest.approx(4)
    assert ind.ema(s, 3).iloc[-1] == pytest.approx(4.0625)


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert ind.rsi(up).iloc[-1] == pytest.approx(100)
    down = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert ind.rsi(down).iloc[-1] < 1
    r = ind.rsi(pd.Series(np.random.default_rng(0).normal(0, 1, 200).cumsum() + 100)).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_macd_columns():
    m = ind.macd(pd.Series(np.arange(100, dtype=float)))
    assert list(m.columns) == ["macd", "signal", "hist"] and m["macd"].iloc[-1] > 0


def test_bollinger_order():
    b = ind.bollinger(pd.Series(np.random.default_rng(1).normal(100, 2, 100))).dropna()
    assert (b["upper"] >= b["mid"]).all() and (b["mid"] >= b["lower"]).all()


def test_atr_positive():
    assert ind.atr(frame(np.arange(50) + 100)).iloc[-1] > 0


def test_make_candles_timeframes():
    h = [(1_700_000_000 + i * 600, 100 + i) for i in range(300)]
    assert len(ind.make_candles(h, "1h")) > len(ind.make_candles(h, "4h")) >= 1
    assert ind.make_candles([], "1d").empty


def test_patterns():
    df = pd.DataFrame({"open": [10, 10.0], "high": [10.1, 10.1], "low": [9.9, 9.9], "close": [10.0, 10.005]})
    assert pat.doji(df).all()
    pin = pd.DataFrame({"open": [10.0], "high": [10.05], "low": [9.0], "close": [10.02]})
    assert pat.pin_bar(pin).iloc[0] == 1
    eng = pd.DataFrame({"open": [10.0, 9.0], "high": [10.1, 10.5], "low": [8.9, 8.9], "close": [9.2, 10.4]})
    assert pat.engulfing(eng).iloc[1] == 1


def test_support_resistance():
    t = np.linspace(0, 6 * np.pi, 120)
    sup, res = pat.support_resistance(frame(100 + 5 * np.sin(t)))
    assert sup and res and max(sup) < min(res)
    assert pat.support_resistance(frame([1, 2, 3])) == ([], [])
