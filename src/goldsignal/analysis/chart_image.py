"""استخراج کندل از «تصویر چارت» (اسکرین‌شات) بدون API و بدون هوش مصنوعی خارجی.

روش: رنگ سبز/قرمز کندل‌ها با HSV جدا می‌شود، هر کندل از ستون‌های پیوسته پیدا می‌شود،
سایه = بالاترین/پایین‌ترین پیکسل و بدنه = ردیف‌هایی که به پهنای کندل رنگ دارند.
قیمت هر پیکسل با «کالیبراسیون دو نقطه‌ای» (دو ردیف تصویر + قیمت هرکدام) و مقیاس خطی محاسبه می‌شود.
دقت: تقریبی (در حد پیکسل). فقط چارت‌های کندلی سبز/قرمز؛ مقیاس لگاریتمی پشتیبانی نمی‌شود."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FREQ = {"1h": "1h", "4h": "4h", "1d": "1D", "1w": "7D"}


class ChartImageError(Exception):
    pass


@dataclass(frozen=True)
class Calibration:
    y1: float
    p1: float
    y2: float
    p2: float

    def validate(self) -> None:
        if abs(self.y1 - self.y2) < 20:
            raise ChartImageError("دو نقطهٔ کالیبراسیون باید حداقل ۲۰ پیکسل از هم فاصله داشته باشند.")
        if self.p1 <= 0 or self.p2 <= 0 or self.p1 == self.p2:
            raise ChartImageError("قیمت دو نقطه باید مثبت و متفاوت باشد.")

    def price(self, y: float) -> float:
        return self.p1 + (y - self.y1) * (self.p2 - self.p1) / (self.y2 - self.y1)


@dataclass
class Extraction:
    candles: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    median_width: float = 0.0


def _hsv(img: np.ndarray):
    x = img.astype(np.float32) / 255.0
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    mx, mn = x.max(axis=-1), x.min(axis=-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    h = np.zeros_like(mx)
    nz = d > 1e-6
    rc = nz & (mx == r); gc = nz & (mx == g) & ~rc; bc = nz & ~rc & ~gc
    h[rc] = (60 * ((g - b)[rc] / d[rc])) % 360
    h[gc] = 60 * ((b - r)[gc] / d[gc]) + 120
    h[bc] = 60 * ((r - g)[bc] / d[bc]) + 240
    return h, s, mx


def color_masks(img: np.ndarray, invert: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """(ماسک صعودی، ماسک نزولی). invert=True: قرمز صعودی/سبز نزولی (مثل برخی چارت‌های آسیایی)."""
    h, s, v = _hsv(img)
    ok = (s >= 0.35) & (v >= 0.30)
    green = ok & (h >= 85) & (h <= 195)
    red = ok & ((h <= 20) | (h >= 340))
    return (red, green) if invert else (green, red)


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - 1)); start = None
    if start is not None:
        out.append((start, len(flags) - 1))
    return out


def extract_candles(img: np.ndarray, cal: Calibration, invert: bool = False, timeframe: str = "1d") -> Extraction:
    if img.ndim != 3 or img.shape[2] < 3:
        raise ChartImageError("تصویر باید رنگی (RGB) باشد.")
    cal.validate()
    img = img[..., :3]
    H = img.shape[0]
    span = abs(cal.y2 - cal.y1)
    lo = int(max(0, min(cal.y1, cal.y2) - 0.03 * span)); hi = int(min(H, max(cal.y1, cal.y2) + 0.03 * span))
    if hi - lo < 20:
        raise ChartImageError("ناحیهٔ کالیبراسیون خارج از تصویر است.")
    bull, bear = (m[lo:hi] for m in color_masks(img, invert))
    anym = bull | bear
    # حذف خطوط افقی بلند (خط قیمت فعلی / شبکه)
    anym[anym.mean(axis=1) > 0.5] = False
    warnings: list[str] = []
    groups = _runs(anym.any(axis=0))
    if not groups:
        raise ChartImageError("کندل سبز/قرمزی در ناحیهٔ انتخابی پیدا نشد. رنگ‌ها یا نقاط کالیبراسیون را بررسی کنید.")
    widths = np.array([b - a + 1 for a, b in groups])
    med = float(np.median(widths))
    keep = [g for g, w in zip(groups, widths) if not (w > 3 * med and w > 6)]   # برچسب‌های رنگی محور و ...
    if len(keep) < len(groups):
        warnings.append(f"{len(groups) - len(keep)} شیء پهن (احتمالاً برچسب قیمت/حجم) نادیده گرفته شد.")
    rows = []
    merged = thin = 0
    mw = float(np.median([b - a + 1 for a, b in keep]))
    for a, b in keep:
        gw = b - a + 1
        sub = anym[:, a:b + 1]
        cnt = sub.sum(axis=1)
        ys = np.nonzero(cnt)[0]
        top, bot = int(ys.min()), int(ys.max()) + 1   # لبهٔ بالا و لبهٔ پایین (پیکسل)
        if gw >= 3:
            body = np.nonzero(cnt >= max(2, int(np.ceil(0.6 * gw))))[0]
        else:
            body = np.array([], dtype=int)
        if body.size:
            btop, bbot = int(body.min()), int(body.max()) + 1
        else:
            btop, bbot = top, bot; thin += 1
        up = bull[:, a:b + 1].sum() >= bear[:, a:b + 1].sum()
        if gw > 1.8 * mw:
            merged += 1
        pr = lambda y: cal.price(y + lo)
        hi_p, lo_p = pr(top), pr(bot)
        o, c = (pr(bbot), pr(btop)) if up else (pr(btop), pr(bbot))
        hi_p, lo_p = max(hi_p, o, c), min(lo_p, o, c)
        rows.append((o, hi_p, lo_p, c))
    if mw < 3:
        warnings.append("کندل‌ها خیلی باریک‌اند؛ بدنه دقیق خوانده نمی‌شود. روی چارت زوم کنید (کندل‌های کمتر ولی پهن‌تر).")
    if merged:
        warnings.append(f"{merged} کندل ممکن است به هم چسبیده باشند؛ زوم بیشتر یا فاصلهٔ بیشتر بین کندل‌ها لازم است.")
    if len(rows) < 30:
        warnings.append(f"فقط {len(rows)} کندل پیدا شد؛ برای تحلیل مطمئن‌تر حداقل ۳۰ کندل لازم است.")
    n = len(rows)
    idx = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("h"), periods=n, freq=FREQ[timeframe])
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    if (df["low"] <= 0).any():
        raise ChartImageError("قیمت منفی/صفر محاسبه شد؛ کالیبراسیون را دوباره انجام دهید.")
    return Extraction(df, warnings, mw)
