"""مدیریت چند منبع با fallback خودکار، ادغام کلید به کلید و کش محلی (SQLite)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from ..storage.db import Database
from .base import Provider, ProviderError, validate_prices

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    prices: dict[str, float]
    sources: dict[str, str] = field(default_factory=dict)   # key -> provider name
    errors: dict[str, str] = field(default_factory=dict)    # provider -> error
    from_cache: bool = False
    ts: int = 0


class ProviderManager:
    def __init__(self, providers: list[Provider], db: Database) -> None:
        self.providers, self.db = providers, db

    def refresh(self, wanted: tuple[str, ...] = ("usd", "ounce", "emami", "half", "quarter", "gerami", "gold18")) -> FetchResult:
        merged: dict[str, float] = {}
        sources: dict[str, str] = {}
        errors: dict[str, str] = {}
        for p in self.providers:
            if all(k in merged for k in wanted):
                break
            try:
                got = validate_prices(p.fetch())
            except ProviderError as e:
                errors[p.name] = str(e); log.warning("provider failed: %s", e); continue
            except Exception as e:  # شبکه/پارس غیرمنتظره نباید برنامه را بیندازد
                errors[p.name] = f"خطای غیرمنتظره: {e}"; log.exception("provider crashed"); continue
            for k, v in got.items():
                if k not in merged:
                    merged[k], sources[k] = v, p.name
        now = int(time.time())
        if merged:
            for k, v in merged.items():
                self.db.add_prices({k: v}, sources[k], now)
            cached, ts = self.db.latest()
            full = {**cached, **merged}          # کلیدهای ناموجود از کش تکمیل می‌شوند
            return FetchResult(full, sources, errors, False, now)
        cached, ts = self.db.latest()            # قطع اینترنت: آخرین داده کش‌شده
        return FetchResult(cached, {}, errors, True, ts)
