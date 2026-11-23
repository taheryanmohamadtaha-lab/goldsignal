"""موتور سیگنال مبتنی بر قوانین شفاف: تقاطع EMA + تأیید RSI + MACD + الگوی کندلی + شرایط حباب.
هیچ خروجی‌ای تضمینی نیست؛ «درجه اطمینان» فقط تعداد قوانین هم‌جهت را نشان می‌دهد، نه احتمال سود."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np
import pandas as pd

from ..analysis import indicators as ind
from ..analysis import patterns as pat
from ..models import Signal


@dataclass
class RuleConfig:
    ema_fast: int = 9
    ema_slow: int = 21
    rsi_period: int = 14
    rsi_buy_low: float = 40.0      # تأیید خرید: RSI بین این دو
    rsi_buy_high: float = 70.0
    rsi_sell_min: float = 30.0     # تأیید فروش: RSI بالاتر از این (کف اشباع فروش نباشد)
    atr_period: int = 14
    atr_stop_mult: float = 2.0
    reward_risk: float = 2.0
    use_bubble: bool = True
    min_confidence: int = 55

    def to_dict(self) -> dict:
        return asdict(self)


def compute_frame(df: pd.DataFrame, cfg: RuleConfig, bubble_pct: Optional[pd.Series] = None) -> pd.DataFrame:
    """تمام ستون‌های لازم و سیگنال هر کندل را برداری حساب می‌کند."""
    out = df.copy()
    c = out["close"]
    out["ema_f"], out["ema_s"] = ind.ema(c, cfg.ema_fast), ind.ema(c, cfg.ema_slow)
    out["rsi"] = ind.rsi(c, cfg.rsi_period)
    m = ind.macd(c)
    out["hist"] = m["hist"]
    out["atr"] = ind.atr(out, cfg.atr_period)
    out["pin"], out["eng"] = pat.pin_bar(out), pat.engulfing(out)
    up = (out["ema_f"] > out["ema_s"]) & (out["ema_f"].shift() <= out["ema_s"].shift())
    dn = (out["ema_f"] < out["ema_s"]) & (out["ema_f"].shift() >= out["ema_s"].shift())
    # وضعیت حباب نسبت به میانگین متحرک خودش (z-score ساده روی ۶۰ کندل)
    if cfg.use_bubble and bubble_pct is not None:
        b = bubble_pct.reindex(out.index).ffill()
        mu, sd = b.rolling(60, min_periods=10).mean(), b.rolling(60, min_periods=10).std(ddof=0)
        z = (b - mu) / sd.replace(0, np.nan)
        out["bubble_z"] = z
    else:
        out["bubble_z"] = np.nan

    conf = np.zeros(len(out)); action = np.array(["hold"] * len(out), dtype=object)
    rsi_ok_buy = out["rsi"].between(cfg.rsi_buy_low, cfg.rsi_buy_high)
    rsi_ok_sell = out["rsi"] > cfg.rsi_sell_min
    for side, cross, rsi_ok, sgn in (("buy", up, rsi_ok_buy, 1), ("sell", dn, rsi_ok_sell, -1)):
        c0 = 40 + 20 * rsi_ok.astype(int)
        c0 = c0 + 15 * (np.sign(out["hist"]) == sgn).astype(int)
        c0 = c0 + 10 * ((out["pin"] == sgn) | (out["eng"] == sgn)).astype(int)
        bz = out["bubble_z"]
        if side == "buy":
            c0 = c0 + 15 * (bz < 0.5).astype(int) - 20 * (bz > 1).astype(int)
        else:
            c0 = c0 + 15 * (bz > 0.5).astype(int)
        mask = cross.to_numpy()
        action[mask] = side
        conf[mask] = np.clip(c0.to_numpy()[mask], 0, 100)
    out["action"], out["confidence"] = action, conf.astype(int)
    out["entry"] = np.where(out["action"] == "buy", c, np.nan)
    out["stop"] = np.where(out["action"] == "buy", c - cfg.atr_stop_mult * out["atr"], np.nan)
    out["target"] = np.where(out["action"] == "buy", c + cfg.reward_risk * cfg.atr_stop_mult * out["atr"], np.nan)
    return out


def _reasons(row: pd.Series, cfg: RuleConfig) -> list[str]:
    r: list[str] = []
    if row["action"] == "buy":
        r.append(f"EMA{cfg.ema_fast} از بالا EMA{cfg.ema_slow} را قطع کرد")
    elif row["action"] == "sell":
        r.append(f"EMA{cfg.ema_fast} از پایین EMA{cfg.ema_slow} را قطع کرد")
    else:
        return ["شرط تقاطع EMA برقرار نیست؛ نگه‌داری/بدون سیگنال"]
    if pd.notna(row["rsi"]):
        r.append(f"RSI = {row['rsi']:.0f}")
    if pd.notna(row["hist"]):
        r.append("MACD هم‌جهت" if (row["hist"] > 0) == (row["action"] == "buy") else "MACD ناهم‌جهت")
    if row["pin"] or row["eng"]:
        r.append("الگوی کندلی هم‌جهت یا مخالف دیده شد")
    z = row.get("bubble_z", np.nan)
    if pd.notna(z):
        r.append("حباب بالاتر از میانگین تاریخی" if z > 1 else "حباب پایین‌تر از میانگین تاریخی" if z < -1 else "حباب نزدیک میانگین")
    return r


def latest_signal(df: pd.DataFrame, asset: str, timeframe: str, cfg: Optional[RuleConfig] = None,
                  bubble_pct: Optional[pd.Series] = None) -> Signal:
    """سیگنال آخرین کندل. داده کم → hold با دلیل."""
    cfg = cfg or RuleConfig()
    need = max(cfg.ema_slow, cfg.rsi_period, 26) + 2
    if len(df) < need:
        return Signal(int(pd.Timestamp.now(tz="UTC").timestamp()), asset, timeframe, "hold", None, None, None, None, 0,
                      [f"داده کافی نیست (حداقل {need} کندل لازم است، {len(df)} موجود)"])
    f = compute_frame(df, cfg, bubble_pct)
    row = f.iloc[-1]
    ts = int(f.index[-1].timestamp())
    if row["action"] == "hold" or (row["action"] == "buy" and row["confidence"] < cfg.min_confidence):
        reasons = _reasons(row, cfg)
        if row["action"] == "buy":
            reasons.append(f"اطمینان {row['confidence']} کمتر از حداقل {cfg.min_confidence}")
        return Signal(ts, asset, timeframe, "hold", None, None, None, None, int(row["confidence"]), reasons)
    if row["action"] == "sell":
        return Signal(ts, asset, timeframe, "sell", float(row["close"]), None, None, None, int(row["confidence"]), _reasons(row, cfg))
    risk = row["entry"] - row["stop"]
    rr = float((row["target"] - row["entry"]) / risk) if risk > 0 else None
    return Signal(ts, asset, timeframe, "buy", float(row["entry"]), float(row["stop"]), float(row["target"]), rr,
                  int(row["confidence"]), _reasons(row, cfg))
