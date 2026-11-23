"""بک‌تست long-only روی دادهٔ تاریخی (خرید در سیگنال buy؛ خروج با حد ضرر/هدف/سیگنال sell/پایان داده).
فرض محافظه‌کارانه: اگر در یک کندل هم حد ضرر و هم هدف لمس شود، حد ضرر فرض می‌شود.
کارمزد/اسپرد هر طرف قابل تنظیم است. نتایج گذشته تضمینی برای آینده نیستند."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .engine import RuleConfig, compute_frame


@dataclass
class Trade:
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry: float
    exit: float
    pnl_pct: float
    reason: str


@dataclass
class BacktestReport:
    trades: list[Trade] = field(default_factory=list)
    total_return_pct: float = 0.0
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    max_drawdown_pct: float = 0.0
    n_trades: int = 0
    equity: list[float] = field(default_factory=list)
    note: str = ""


def run_backtest(df: pd.DataFrame, cfg: Optional[RuleConfig] = None, bubble_pct: Optional[pd.Series] = None,
                 fee_pct: float = 0.3) -> BacktestReport:
    cfg = cfg or RuleConfig()
    rep = BacktestReport()
    if len(df) < max(cfg.ema_slow, 26) + 5:
        rep.note = "داده برای بک‌تست کافی نیست"
        return rep
    f = compute_frame(df, cfg, bubble_pct)
    eq, equity = 1.0, [1.0]
    pos: Optional[tuple[int, float, float, float]] = None   # idx, entry, stop, target
    idx = f.index
    for i in range(len(f)):
        row = f.iloc[i]
        if pos is not None:
            _, entry, stop, target = pos
            exit_p, reason = None, ""
            if row["low"] <= stop:
                exit_p, reason = stop, "حد ضرر"
            elif row["high"] >= target:
                exit_p, reason = target, "هدف"
            elif row["action"] == "sell":
                exit_p, reason = float(row["close"]), "سیگنال فروش"
            elif i == len(f) - 1:
                exit_p, reason = float(row["close"]), "پایان داده"
            if exit_p is not None:
                gross = (exit_p / entry - 1) * 100
                pnl = gross - 2 * fee_pct
                rep.trades.append(Trade(idx[pos[0]], idx[i], entry, exit_p, pnl, reason))
                eq *= 1 + pnl / 100
                pos = None
        elif row["action"] == "buy" and row["confidence"] >= cfg.min_confidence and pd.notna(row["stop"]) and row["stop"] < row["close"]:
            pos = (i, float(row["close"]), float(row["stop"]), float(row["target"]))
        equity.append(eq)
    rep.equity = equity
    rep.n_trades = len(rep.trades)
    rep.total_return_pct = (eq - 1) * 100
    if rep.trades:
        wins = [t.pnl_pct for t in rep.trades if t.pnl_pct > 0]
        losses = [-t.pnl_pct for t in rep.trades if t.pnl_pct <= 0]
        rep.win_rate = len(wins) / len(rep.trades) * 100
        rep.profit_factor = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else None
    arr = np.array(equity)
    peak = np.maximum.accumulate(arr)
    rep.max_drawdown_pct = float(((arr - peak) / peak).min() * 100)
    return rep
