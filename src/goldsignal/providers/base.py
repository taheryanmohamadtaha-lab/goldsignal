"""اینترفیس مشترک منابع داده. هر منبع فقط یک دیکشنری {کلید: قیمت به تومان/دلار} برمی‌گرداند."""
from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import urlparse


class ProviderError(Exception):
    pass


def require_https(url: str) -> str:
    u = urlparse(url.strip())
    if u.scheme != "https" or not u.netloc:
        raise ProviderError("فقط آدرس‌های HTTPS مجاز هستند: " + url)
    return url.strip()


class Provider(ABC):
    name: str = "provider"

    @abstractmethod
    def fetch(self) -> dict[str, float]:
        """قیمت‌های موجود را برمی‌گرداند؛ کلیدهای ناموجود را نباید بیاورد. در خطا ProviderError می‌اندازد."""


def validate_prices(raw: dict) -> dict[str, float]:
    """اعتبارسنجی ورودی: فقط عدد مثبت و متناهی."""
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f and f not in (float("inf"), float("-inf")) and f > 0:
            out[k] = f
    return out
