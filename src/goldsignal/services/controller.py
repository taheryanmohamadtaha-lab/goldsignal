"""منطق برنامه بدون وابستگی به UI: ساخت منابع از تنظیمات، به‌روزرسانی، تحلیل و سیگنال."""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from ..analysis import formulas
from ..analysis.indicators import make_candles
from ..constants import COIN_KEYS, COIN_PURE_GOLD
from ..models import Signal
from ..providers.base import Provider
from ..providers.generic_json import GenericJsonProvider
from ..providers.manager import FetchResult, ProviderManager
from ..providers.manual import ManualProvider
from ..providers.stooq import StooqOunceProvider
from ..signals.engine import RuleConfig, latest_signal
from ..storage.db import Database
from . import alerts as alert_svc
from .secrets import get_secret

log = logging.getLogger(__name__)
DEFAULTS = {"unit": "toman", "digits": "fa", "theme": "dark", "interval_min": 5, "use_stooq": True,
            "json_sources": [], "sound": True, "autostart": False}


class Controller:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.manual = ManualProvider(db)
        self.last: Optional[FetchResult] = None

    def setting(self, k: str):
        return self.db.get_setting(k, DEFAULTS.get(k))

    def pure_gold(self) -> dict[str, float]:
        return {**COIN_PURE_GOLD, **(self.db.get_setting("pure_gold", {}) or {})}

    def rule_config(self) -> RuleConfig:
        d = self.db.get_setting("rules", {}) or {}
        return RuleConfig(**{k: v for k, v in d.items() if k in RuleConfig.__dataclass_fields__})

    def build_providers(self) -> list[Provider]:
        provs: list[Provider] = []
        for cfg in self.setting("json_sources") or []:
            try:
                provs.append(GenericJsonProvider(cfg, api_key=get_secret(cfg.get("name", "json"))))
            except Exception as e:
                log.warning("bad json source %s: %s", cfg.get("name"), e)
        if self.setting("use_stooq"):
            provs.append(StooqOunceProvider())
        provs.append(self.manual)
        return provs

    def refresh(self) -> tuple[FetchResult, list[alert_svc.Fired], list[Signal]]:
        res = ProviderManager(self.build_providers(), self.db).refresh()
        self.last = res
        fired: list[alert_svc.Fired] = []
        sigs: list[Signal] = []
        if not res.from_cache:
            self.db.update_signal_outcomes(res.prices)
            sigs = self.compute_signals("1d")
            for s in sigs:
                if s.action in ("buy", "sell"):
                    self.db.add_signal(s)
            fired = alert_svc.evaluate(self.db, res.prices, formulas.compute_bubbles(res.prices, self.pure_gold()), sigs)
        return res, fired, sigs

    def candles(self, asset: str, timeframe: str) -> pd.DataFrame:
        return make_candles(self.db.history(asset), timeframe)

    def bubble_series(self, asset: str, timeframe: str) -> Optional[pd.Series]:
        """سری درصد حباب هر کندل (فقط اگر تاریخچه قیمت اونس و دلار موجود باشد)."""
        if asset not in COIN_KEYS:
            return None
        c, o, u = (make_candles(self.db.history(k), timeframe)["close"] for k in (asset, "ounce", "usd"))
        if c.empty or o.empty or u.empty:
            return None
        d = pd.concat([c, o, u], axis=1, keys=["c", "o", "u"]).ffill().dropna()
        intr = d["o"] / 31.1035 * d["u"] * self.pure_gold()[asset]
        return (d["c"] - intr) / intr * 100

    def compute_signals(self, timeframe: str) -> list[Signal]:
        out = []
        for asset in (*COIN_KEYS, "gold18"):
            df = self.candles(asset, timeframe)
            if df.empty:
                continue
            out.append(latest_signal(df, asset, timeframe, self.rule_config(), self.bubble_series(asset, timeframe)))
        return out
