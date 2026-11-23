"""خروجی گزارش: CSV / Excel / PDF (PDF با موتور متن Qt تا RTL و فونت فارسی درست باشد)."""
from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd

from ..constants import DISCLAIMER

COLS = {"ts": "زمان", "asset": "دارایی", "timeframe": "تایم‌فریم", "action": "اقدام", "entry": "ورود",
        "stop": "حد ضرر", "target": "هدف", "rr": "R/R", "confidence": "اطمینان", "outcome": "نتیجه", "reasons": "دلیل"}


def signals_frame(rows) -> pd.DataFrame:
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return pd.DataFrame(columns=list(COLS.values()))
    df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    return df[[c for c in COLS if c in df.columns]].rename(columns=COLS)


def export_csv(df: pd.DataFrame, path: str | Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")   # BOM تا Excel فارسی را درست باز کند


def export_excel(df: pd.DataFrame, path: str | Path) -> None:
    df.to_excel(path, index=False, sheet_name="signals", engine="openpyxl")


def export_pdf(df: pd.DataFrame, path: str | Path, title: str = "گزارش طلاسنج") -> None:
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    head = "".join(f"<th>{escape(str(c))}</th>" for c in df.columns)
    body = "".join("<tr>" + "".join(f"<td>{escape('' if pd.isna(v) else str(v))}</td>" for v in r) + "</tr>"
                   for r in df.itertuples(index=False))
    html = (f"<html dir='rtl'><body style='font-family:Vazirmatn;font-size:8pt'><h2>{escape(title)}</h2>"
            f"<p style='color:#b00'>{escape(DISCLAIMER)}</p>"
            f"<table border='1' cellspacing='0' cellpadding='3' width='100%'><tr>{head}</tr>{body}</table></body></html>")
    w = QPdfWriter(str(path))
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(10, 10, 10, 10)))
    doc = QTextDocument()
    doc.setHtml(html)
    doc.print_(w)
