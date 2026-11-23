"""ایمپورت CSV تاریخچه. دو قالب:
۱) بلند: ts,key,value  ۲) عریض: ستون زمان (ts یا date) + ستون‌هایی با نام کلیدها (emami, usd, ounce, ...)
زمان: epoch ثانیه یا ISO مثل 2025-01-31 12:00."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from ..constants import PRICE_KEYS
from ..storage.db import Database


def _ts(s: str) -> int:
    s = s.strip()
    try:
        return int(float(s))
    except ValueError:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())


def import_csv(db: Database, path: str | Path) -> tuple[int, int]:
    """برمی‌گرداند (ردیف واردشده، ردیف ردشده). ردیف‌های خراب نادیده گرفته می‌شوند."""
    ok = bad = 0
    rows_out: list[tuple[int, str, float, str]] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        cols = [c.strip().lower() for c in (rd.fieldnames or [])]
        long_fmt = {"ts", "key", "value"} <= set(cols)
        tcol = next((c for c in (rd.fieldnames or []) if c.strip().lower() in ("ts", "date", "time", "datetime")), None)
        if not long_fmt and tcol is None:
            raise ValueError("ستون زمان (ts/date) پیدا نشد")
        for row in rd:
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            try:
                if long_fmt:
                    rows_out.append((_ts(row["ts"]), row["key"], float(row["value"].replace(",", "")), "csv"))
                    ok += 1
                else:
                    t = _ts(row[tcol.strip().lower()])
                    got = False
                    for k in PRICE_KEYS:
                        if row.get(k):
                            rows_out.append((t, k, float(row[k].replace(",", "")), "csv"))
                            got = True
                    ok, bad = (ok + 1, bad) if got else (ok, bad + 1)
            except (ValueError, KeyError):
                bad += 1
    db.add_price_rows(rows_out)
    return ok, bad
