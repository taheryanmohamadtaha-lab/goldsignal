"""منبع JSON قابل‌پیکربندی توسط کاربر (آدرس HTTPS، هدرها/کلید API و مسیر هر قیمت در JSON).

هیچ آدرس پیش‌فرضی وجود ندارد: tgju.org و بسیاری از سایت‌های ایرانی API عمومی رسمی ندارند و
آدرس‌ها بدون تأیید در برنامه گذاشته نشده است. سرویس مورد اعتماد خودتان را در تنظیمات وارد کنید.
مثال پیکربندی: {"name":"my","url":"https://example.com/p","headers":{"Authorization":"Bearer {KEY}"},
 "mapping":{"emami":"data.emami.price","usd":"data.usd"},"scale":{"emami":0.1}}
"""
from __future__ import annotations

from typing import Any, Optional

import requests

from .base import Provider, ProviderError, require_https, validate_prices


def dig(obj: Any, path: str) -> Any:
    """مسیر نقطه‌ای مثل a.b.0.c (اندیس لیست عددی)."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def parse_number(v: Any) -> float:
    if isinstance(v, str):
        v = v.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).replace(",", "").replace("٬", "").strip()
    return float(v)


class GenericJsonProvider(Provider):
    def __init__(self, cfg: dict, api_key: Optional[str] = None, session: Optional[requests.Session] = None,
                 timeout: float = 10.0) -> None:
        self.cfg = cfg
        self.name = cfg.get("name", "json")
        self.url = require_https(cfg["url"])
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch(self) -> dict[str, float]:
        headers = {k: str(v).replace("{KEY}", self.api_key or "") for k, v in (self.cfg.get("headers") or {}).items()}
        try:
            r = self.session.get(self.url, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            raise ProviderError(f"{self.name}: {e}") from e
        raw: dict[str, float] = {}
        scale = self.cfg.get("scale") or {}
        for key, path in (self.cfg.get("mapping") or {}).items():
            try:
                raw[key] = parse_number(dig(data, path)) * float(scale.get(key, 1))
            except (KeyError, IndexError, ValueError, TypeError):
                continue   # داده ناقص: همان کلید نادیده گرفته می‌شود
        out = validate_prices(raw)
        if not out:
            raise ProviderError(f"{self.name}: هیچ قیمت معتبری در پاسخ پیدا نشد")
        return out
