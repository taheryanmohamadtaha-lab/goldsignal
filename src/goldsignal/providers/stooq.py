"""اونس جهانی طلا (XAUUSD) از CSV عمومی Stooq. توجه: در محیط توسعه این آدرس تأیید نشده؛
در صورت تغییر یا بلاک شدن، از منبع JSON یا ورود دستی استفاده کنید. تنظیمات → خاموش‌کردن."""
from __future__ import annotations

import csv
import io
from typing import Optional

import requests

from .base import Provider, ProviderError, require_https, validate_prices

URL = "https://stooq.com/q/l/?s=xauusd&f=sd2t2ohlcv&h&e=csv"


class StooqOunceProvider(Provider):
    name = "stooq-xauusd"

    def __init__(self, session: Optional[requests.Session] = None, url: str = URL, timeout: float = 10.0) -> None:
        self.url, self.timeout = require_https(url), timeout
        self.session = session or requests.Session()

    def fetch(self) -> dict[str, float]:
        try:
            r = self.session.get(self.url, timeout=self.timeout)
            r.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(r.text)))
            close = float(rows[0]["Close"])
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            raise ProviderError(f"{self.name}: {e}") from e
        out = validate_prices({"ounce": close})
        if not out:
            raise ProviderError(f"{self.name}: مقدار نامعتبر")
        return out
