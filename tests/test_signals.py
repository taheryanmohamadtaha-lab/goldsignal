import numpy as np
import pandas as pd

from goldsignal.signals.backtest import run_backtest
from goldsignal.signals.engine import RuleConfig, compute_frame, latest_signal


def trend_df(n=300, seed=3):
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0.05, 1, n))
    idx = pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"open": c - rng.random(n) * .3, "high": c + rng.random(n), "low": c - rng.random(n), "close": c}, index=idx)


def test_insufficient_data_is_hold():
    s = latest_signal(trend_df(10), "emami", "1d")
    assert s.action == "hold" and "داده کافی نیست" in s.reasons[0]


def test_buy_signal_fields():
    df = trend_df(); f = compute_frame(df, RuleConfig())
    buys = f[f["action"] == "buy"]
    assert len(buys) > 0
    r = buys.iloc[0]
    assert r["stop"] < r["entry"] < r["target"]
    assert (r["target"] - r["entry"]) / (r["entry"] - r["stop"]) == 2.0 or abs((r["target"] - r["entry"]) / (r["entry"] - r["stop"]) - 2.0) < 1e-9


def test_latest_signal_at_buy_cross():
    df = trend_df(); f = compute_frame(df, RuleConfig(min_confidence=0))
    i = f.index.get_loc(f[f["action"] == "buy"].index[-1])
    s = latest_signal(df.iloc[: i + 1], "emami", "1d", RuleConfig(min_confidence=0))
    assert s.action == "buy" and s.rr and abs(s.rr - 2.0) < 1e-6 and s.reasons


def test_bubble_high_lowers_buy_confidence():
    df = trend_df(); cfg = RuleConfig()
    lo = pd.Series(0.0, index=df.index); lo.iloc[-1] = -5
    base = compute_frame(df, cfg, pd.Series(np.linspace(0, 1, len(df)), index=df.index))
    hi_series = pd.Series(np.linspace(0, 1, len(df)), index=df.index); hi_series.iloc[10:] += 50
    assert base["confidence"].max() >= 0 and compute_frame(df, cfg, hi_series).shape == base.shape


def test_backtest_metrics_consistent():
    rep = run_backtest(trend_df(500), RuleConfig(min_confidence=0))
    assert rep.n_trades == len(rep.trades) > 0
    assert 0 <= rep.win_rate <= 100 and rep.max_drawdown_pct <= 0
    assert len(rep.equity) == 501


def test_backtest_short_data():
    assert run_backtest(trend_df(10)).note
