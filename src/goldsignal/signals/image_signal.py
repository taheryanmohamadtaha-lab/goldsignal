"""تحلیل و پیشنهاد روی کندل‌های استخراج‌شده از تصویر. قوانین شفاف و بدون ادعای تضمین."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..analysis import patterns as pat
from ..models import Signal
from .engine import RuleConfig, compute_frame

MIN_CANDLES = 30
CONF_CAP = 70   # دقت تصویر محدود است؛ اطمینان هرگز بالاتر از این نمایش داده نمی‌شود


@dataclass
class ImageAnalysis:
    n: int
    score: int = 0
    trend: str = ""
    lines: list[str] = field(default_factory=list)
    signal: Optional[Signal] = None
    supports: list[float] = field(default_factory=list)
    resistances: list[float] = field(default_factory=list)


def analyze_candles(df: pd.DataFrame, timeframe: str = "1d", cfg: Optional[RuleConfig] = None) -> ImageAnalysis:
    cfg = cfg or RuleConfig(use_bubble=False)
    n = len(df)
    ts = int(df.index[-1].timestamp()) if n else 0
    if n < MIN_CANDLES:
        s = Signal(ts, "image", timeframe, "hold", None, None, None, None, 0, [f"کندل کافی نیست ({n} از حداقل {MIN_CANDLES})"])
        return ImageAnalysis(n, 0, "نامشخص", [s.reasons[0]], s)
    f = compute_frame(df, cfg)
    r = f.iloc[-1]
    close, atr = float(r["close"]), float(r["atr"])
    sup, res = pat.support_resistance(df)
    score, reasons = 0, []
    up_trend = r["ema_f"] > r["ema_s"]
    score += 1 if up_trend else -1
    reasons.append(f"EMA{cfg.ema_fast} {'بالاتر' if up_trend else 'پایین‌تر'} از EMA{cfg.ema_slow}")
    above = close > r["ema_s"]
    score += 1 if above else -1
    reasons.append(f"قیمت {'بالای' if above else 'زیر'} EMA{cfg.ema_slow}")
    macd_up = r["hist"] > 0
    score += 1 if macd_up else -1
    reasons.append("هیستوگرام MACD " + ("مثبت" if macd_up else "منفی"))
    rsi_v = float(r["rsi"])
    if 50 <= rsi_v < 70:
        score += 1
    elif 30 < rsi_v < 50:
        score -= 1
    zone = "اشباع خرید (احتیاط)" if rsi_v >= 70 else "اشباع فروش" if rsi_v <= 30 else "خنثی"
    reasons.append(f"RSI = {rsi_v:.0f} ({zone})")
    last3 = f.iloc[-3:]
    if (last3["pin"] == 1).any() or (last3["eng"] == 1).any():
        reasons.append("الگوی کندلی صعودی در ۳ کندل اخیر")
    if (last3["pin"] == -1).any() or (last3["eng"] == -1).any():
        reasons.append("الگوی کندلی نزولی در ۳ کندل اخیر")
    trend = "صعودی" if score >= 2 else "نزولی" if score <= -2 else "خنثی/رنج"
    near_sup = max(sup) if sup else None
    near_res = min(res) if res else None

    if score >= 3 and rsi_v < 70:
        risk = cfg.atr_stop_mult * atr
        stop = close - risk
        if near_sup is not None and 0 < close - near_sup <= 3 * atr:
            stop = min(stop, near_sup - 0.25 * atr)
        risk = close - stop
        target = close + cfg.reward_risk * risk
        conf = 40 + 10 * score
        if near_res is not None and near_res - close < risk:
            conf -= 15; reasons.append("مقاومت خیلی نزدیک است؛ نسبت ریسک به ریوارد ضعیف می‌شود")
        sig = Signal(ts, "image", timeframe, "buy", close, stop, target, (target - close) / risk, int(min(max(conf, 0), CONF_CAP)), reasons)
    elif score <= -3:
        sig = Signal(ts, "image", timeframe, "sell", close, None, None, None, int(min(40 + 10 * abs(score), CONF_CAP)), reasons)
    else:
        if score >= 3:
            reasons.append("RSI اشباع خرید است؛ ورود جدید توصیه نمی‌شود")
        sig = Signal(ts, "image", timeframe, "hold", None, None, None, None, int(min(30 + 5 * abs(score), CONF_CAP)), reasons)

    lines = [f"روند کلی: {trend} (امتیاز {score:+d} از ۴)"] + reasons
    if near_sup is not None:
        lines.append(f"نزدیک‌ترین حمایت: {near_sup:,.2f}")
    if near_res is not None:
        lines.append(f"نزدیک‌ترین مقاومت: {near_res:,.2f}")
    if sig.action == "buy":
        lines.append(f"پیشنهاد: ورود پله‌ای نزدیک {sig.entry:,.2f}؛ حد ضرر {sig.stop:,.2f}؛ هدف {sig.target:,.2f} (R/R≈{sig.rr:.1f})")
    elif sig.action == "sell":
        lines.append("پیشنهاد: شرایط نزولی است؛ خرید جدید نکنید یا در صورت داشتن پوزیشن، مدیریت ریسک/خروج را بررسی کنید.")
    else:
        lines.append("پیشنهاد: فعلاً سیگنال روشن نیست؛ منتظر تأیید (شکست حمایت/مقاومت یا تقاطع EMA) بمانید.")
    return ImageAnalysis(n, score, trend, lines, sig, sup, res)
