from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Signal:
    ts: int
    asset: str
    timeframe: str
    action: str                 # buy / sell / hold
    entry: Optional[float]
    stop: Optional[float]
    target: Optional[float]
    rr: Optional[float]
    confidence: int             # 0..100
    reasons: list[str] = field(default_factory=list)

    @property
    def reason_text(self) -> str:
        return " | ".join(self.reasons)
