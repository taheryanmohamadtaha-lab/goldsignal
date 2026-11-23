from __future__ import annotations

from ..storage.db import Database
from .base import Provider, ProviderError, validate_prices


class ManualProvider(Provider):
    """قیمت‌های واردشده دستی (ذخیره در تنظیمات). آخرین حلقهٔ fallback."""
    name = "manual"

    def __init__(self, db: Database) -> None:
        self.db = db

    def fetch(self) -> dict[str, float]:
        out = validate_prices(self.db.get_setting("manual_prices", {}) or {})
        if not out:
            raise ProviderError("قیمت دستی ثبت نشده است")
        return out

    def set_prices(self, prices: dict[str, float]) -> None:
        cur = self.db.get_setting("manual_prices", {}) or {}
        cur.update(validate_prices(prices))
        self.db.set_setting("manual_prices", cur)
