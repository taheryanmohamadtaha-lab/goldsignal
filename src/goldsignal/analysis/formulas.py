"""فرمول‌های بازار طلا. همهٔ قیمت‌ها به تومان‌اند؛ تبدیل ریال فقط در نمایش انجام می‌شود."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ..constants import COIN_PURE_GOLD, MESGHAL_GRAMS, OUNCE_GRAMS, PURITY_18K


def gram24(ounce_usd: float, usd_rate: float) -> float:
    """قیمت هر گرم طلای ۲۴ عیار = (اونس ÷ ۳۱٫۱۰۳۵) × نرخ دلار."""
    if ounce_usd <= 0 or usd_rate <= 0:
        raise ValueError("اونس و نرخ دلار باید مثبت باشند")
    return ounce_usd / OUNCE_GRAMS * usd_rate


def gram18_intrinsic(ounce_usd: float, usd_rate: float) -> float:
    return gram24(ounce_usd, usd_rate) * PURITY_18K


def mesghal_price(gram_price: float) -> float:
    """قیمت مثقال = قیمت گرم × ۴٫۶۰۸."""
    return gram_price * MESGHAL_GRAMS


def coin_intrinsic(ounce_usd: float, usd_rate: float, pure_grams: float) -> float:
    """ارزش ذاتی سکه = (اونس ÷ ۳۱٫۱۰۳۵) × گرم طلای خالص × نرخ دلار."""
    return gram24(ounce_usd, usd_rate) * pure_grams


@dataclass(frozen=True)
class Bubble:
    market: float
    intrinsic: float
    amount: float
    percent: float


def bubble(market_price: float, intrinsic: float) -> Bubble:
    """حباب = قیمت بازار − ارزش ذاتی (مبلغ و درصد نسبت به ارزش ذاتی)."""
    if intrinsic <= 0:
        raise ValueError("ارزش ذاتی باید مثبت باشد")
    amount = market_price - intrinsic
    return Bubble(market_price, intrinsic, amount, amount / intrinsic * 100)


def spread(buy: float, sell: float) -> tuple[float, float]:
    """اختلاف خرید/فروش (مبلغ، درصد نسبت به قیمت خرید)."""
    if buy <= 0:
        raise ValueError("قیمت خرید باید مثبت باشد")
    d = sell - buy
    return d, d / buy * 100


def compute_bubbles(prices: Mapping[str, float], pure: Optional[Mapping[str, float]] = None) -> dict[str, Bubble]:
    """حباب سکه‌هایی که قیمت بازار و اونس/دلارشان موجود است. داده ناقص = کلید حذف می‌شود."""
    pure = pure or COIN_PURE_GOLD
    out: dict[str, Bubble] = {}
    ounce, usd = prices.get("ounce"), prices.get("usd")
    if not ounce or not usd or ounce <= 0 or usd <= 0:
        return out
    for key, grams in pure.items():
        mp = prices.get(key)
        if mp and mp > 0:
            out[key] = bubble(mp, coin_intrinsic(ounce, usd, grams))
    return out


def derived_prices(prices: Mapping[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    if prices.get("gold18"):
        out["mesghal18"] = mesghal_price(prices["gold18"])
    if prices.get("ounce") and prices.get("usd"):
        out["gold24_intrinsic"] = gram24(prices["ounce"], prices["usd"])
        out["gold18_intrinsic"] = gram18_intrinsic(prices["ounce"], prices["usd"])
    return out


def to_display(value: float, unit: str) -> float:
    """تومان → ریال (×۱۰) در صورت انتخاب کاربر."""
    return value * 10 if unit == "rial" else value
