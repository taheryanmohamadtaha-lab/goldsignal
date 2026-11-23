"""ذخیره‌سازی SQLite: تاریخچه قیمت، سیگنال‌ها، هشدارها، تنظیمات و کش آخرین قیمت."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices(ts INTEGER NOT NULL, key TEXT NOT NULL, value REAL NOT NULL,
    source TEXT NOT NULL DEFAULT '', PRIMARY KEY(ts, key));
CREATE INDEX IF NOT EXISTS ix_prices_key_ts ON prices(key, ts);
CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, asset TEXT, timeframe TEXT,
    action TEXT, entry REAL, stop REAL, target REAL, rr REAL, confidence INTEGER, reasons TEXT,
    outcome TEXT DEFAULT 'open', closed_ts INTEGER);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, asset TEXT, threshold REAL,
    enabled INTEGER DEFAULT 1, triggered INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
"""


def default_db_path() -> Path:
    base = Path.home() / ".goldsignal"
    base.mkdir(parents=True, exist_ok=True)
    return base / "goldsignal.db"


class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _exec(self, sql: str, args: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(args))
            self._conn.commit()
            return cur

    def _query(self, sql: str, args: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(args)).fetchall()

    # ---- settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self._query("SELECT v FROM settings WHERE k=?", (key,))
        if not rows:
            return default
        try:
            return json.loads(rows[0]["v"])
        except (ValueError, TypeError):
            return default

    def set_setting(self, key: str, value: Any) -> None:
        self._exec("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                   (key, json.dumps(value, ensure_ascii=False)))

    # ---- prices
    def add_prices(self, prices: dict[str, float], source: str = "", ts: Optional[int] = None) -> int:
        ts = int(ts if ts is not None else time.time())
        rows = [(ts, k, float(v), source) for k, v in prices.items() if v is not None and float(v) > 0]
        with self._lock:
            self._conn.executemany("INSERT OR REPLACE INTO prices(ts,key,value,source) VALUES(?,?,?,?)", rows)
            self._conn.commit()
        return len(rows)

    def add_price_rows(self, rows: Iterable[tuple[int, str, float, str]]) -> int:
        rows = [(int(t), k, float(v), s) for t, k, v, s in rows if float(v) > 0]
        with self._lock:
            self._conn.executemany("INSERT OR REPLACE INTO prices(ts,key,value,source) VALUES(?,?,?,?)", rows)
            self._conn.commit()
        return len(rows)

    def history(self, key: str, since: int = 0) -> list[tuple[int, float]]:
        return [(r["ts"], r["value"]) for r in
                self._query("SELECT ts,value FROM prices WHERE key=? AND ts>=? ORDER BY ts", (key, since))]

    def latest(self) -> tuple[dict[str, float], int]:
        """آخرین مقدار هر کلید و زمان آخرین به‌روزرسانی."""
        rows = self._query("SELECT key, value, MAX(ts) AS ts FROM prices GROUP BY key")
        vals = {r["key"]: r["value"] for r in rows}
        return vals, max((r["ts"] for r in rows), default=0)

    # ---- signals
    def add_signal(self, s) -> int:
        return self._exec(
            "INSERT INTO signals(ts,asset,timeframe,action,entry,stop,target,rr,confidence,reasons) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (s.ts, s.asset, s.timeframe, s.action, s.entry, s.stop, s.target, s.rr, s.confidence, s.reason_text)).lastrowid

    def signals(self, limit: int = 500) -> list[sqlite3.Row]:
        return self._query("SELECT * FROM signals ORDER BY ts DESC, id DESC LIMIT ?", (limit,))

    def update_signal_outcomes(self, current: dict[str, float]) -> int:
        """سیگنال‌های باز خرید را با قیمت فعلی بررسی می‌کند: رسیدن به هدف = موفق، به حد ضرر = ناموفق."""
        n = 0
        for r in self._query("SELECT * FROM signals WHERE outcome='open' AND action='buy'"):
            p = current.get(r["asset"])
            if not p or r["stop"] is None or r["target"] is None:
                continue
            res = "win" if p >= r["target"] else "loss" if p <= r["stop"] else None
            if res:
                self._exec("UPDATE signals SET outcome=?, closed_ts=? WHERE id=?", (res, int(time.time()), r["id"]))
                n += 1
        return n

    def success_rate(self) -> tuple[int, int, Optional[float]]:
        rows = self._query("SELECT outcome, COUNT(*) c FROM signals WHERE outcome IN ('win','loss') GROUP BY outcome")
        d = {r["outcome"]: r["c"] for r in rows}
        w, l = d.get("win", 0), d.get("loss", 0)
        return w, l, (w / (w + l) * 100 if w + l else None)

    # ---- alerts
    def add_alert(self, kind: str, asset: str, threshold: float) -> int:
        return self._exec("INSERT INTO alerts(kind,asset,threshold) VALUES(?,?,?)", (kind, asset, threshold)).lastrowid

    def alerts(self) -> list[sqlite3.Row]:
        return self._query("SELECT * FROM alerts ORDER BY id")

    def delete_alert(self, alert_id: int) -> None:
        self._exec("DELETE FROM alerts WHERE id=?", (alert_id,))

    def set_alert_state(self, alert_id: int, triggered: bool) -> None:
        self._exec("UPDATE alerts SET triggered=? WHERE id=?", (int(triggered), alert_id))

    def close(self) -> None:
        with self._lock:
            self._conn.close()
