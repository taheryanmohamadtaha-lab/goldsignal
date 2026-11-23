"""ارزیابی هشدارها. هر هشدار فقط یک‌بار هنگام عبور از شرط فعال می‌شود و با برگشتن شرط دوباره مسلح می‌شود."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ..analysis.formulas import Bubble
from ..constants import PRICE_KEYS
from ..models import Signal
from ..storage.db import Database

KINDS = {
    "price_above": "قیمت بالاتر از",
    "price_below": "قیمت پایین‌تر از",
    "bubble_above": "حباب (٪) بالاتر از",
    "bubble_below": "حباب (٪) پایین‌تر از",
    "new_signal": "سیگنال جدید خرید/فروش",
}


@dataclass
class Fired:
    alert_id: int
    title: str
    text: str


def evaluate(db: Database, prices: Mapping[str, float], bubbles: Mapping[str, Bubble],
             new_signals: Optional[list[Signal]] = None) -> list[Fired]:
    fired: list[Fired] = []
    for a in db.alerts():
        if not a["enabled"]:
            continue
        kind, asset, th = a["kind"], a["asset"], a["threshold"]
        name = PRICE_KEYS.get(asset, asset)
        cond, text = False, ""
        if kind == "price_above" and prices.get(asset) is not None:
            cond = prices[asset] > th; text = f"{name}: {prices[asset]:,.0f} (بالاتر از {th:,.0f})"
        elif kind == "price_below" and prices.get(asset) is not None:
            cond = prices[asset] < th; text = f"{name}: {prices[asset]:,.0f} (پایین‌تر از {th:,.0f})"
        elif kind == "bubble_above" and asset in bubbles:
            cond = bubbles[asset].percent > th; text = f"حباب {name}: {bubbles[asset].percent:.1f}٪ (بالاتر از {th:g}٪)"
        elif kind == "bubble_below" and asset in bubbles:
            cond = bubbles[asset].percent < th; text = f"حباب {name}: {bubbles[asset].percent:.1f}٪ (پایین‌تر از {th:g}٪)"
        elif kind == "new_signal":
            hits = [s for s in (new_signals or []) if s.action in ("buy", "sell") and (asset in ("", "*", s.asset))]
            if hits:
                cond = True; text = "؛ ".join(f"{PRICE_KEYS.get(s.asset, s.asset)}: {'خرید' if s.action == 'buy' else 'فروش'}" for s in hits)
            fired_now = cond
            if fired_now:
                fired.append(Fired(a["id"], "سیگنال جدید", text))
            continue   # سیگنال‌ها هر بار که تازه باشند اعلام می‌شوند
        else:
            continue
        if cond and not a["triggered"]:
            fired.append(Fired(a["id"], "هشدار طلاسنج", text)); db.set_alert_state(a["id"], True)
        elif not cond and a["triggered"]:
            db.set_alert_state(a["id"], False)
    return fired
