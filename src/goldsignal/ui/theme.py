from __future__ import annotations

import sys
from pathlib import Path

import jdatetime
from PySide6.QtGui import QFont, QFontDatabase

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    return base / rel


def load_fonts() -> str:
    family = "Vazirmatn"
    for f in ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf"):
        p = resource_path(f"assets/fonts/{f}")
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
    return family


def app_font(size: int = 10) -> QFont:
    return QFont(load_fonts(), size)


def fmt_num(v: float | None, digits: str = "fa", decimals: int = 0, thousands: bool = True) -> str:
    if v is None or v != v:
        return "—"
    s = f"{v:,.{decimals}f}" if thousands else f"{v:.{decimals}f}"
    return s.translate(FA_DIGITS).replace(",", "٬") if digits == "fa" else s


def fmt_date(ts: int, digits: str = "fa") -> str:
    if not ts:
        return "—"
    s = jdatetime.datetime.fromtimestamp(ts).strftime("%Y/%m/%d %H:%M")
    return s.translate(FA_DIGITS) if digits == "fa" else s


DARK = dict(bg="#14161c", panel="#1e2230", text="#e8e8ee", muted="#9aa0b4", accent="#d4a017", good="#2ecc71", bad="#e74c3c", border="#2d3347")
LIGHT = dict(bg="#f4f5f8", panel="#ffffff", text="#1b1d26", muted="#667", accent="#b8860b", good="#1e9e57", bad="#d03a2c", border="#d8dbe6")


def stylesheet(theme: str) -> str:
    c = DARK if theme == "dark" else LIGHT
    return f"""
    QWidget {{ background:{c['bg']}; color:{c['text']}; font-family:Vazirmatn; }}
    QFrame#card, QFrame#panel {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:10px; }}
    QLabel#muted {{ color:{c['muted']}; background:transparent; }}
    QLabel#warn {{ color:{c['bad']}; background:transparent; font-weight:bold; }}
    QLabel#big {{ font-size:18pt; font-weight:bold; background:transparent; }}
    QListWidget {{ background:{c['panel']}; border:none; border-radius:10px; padding:6px; }}
    QListWidget::item {{ padding:10px 14px; border-radius:8px; }}
    QListWidget::item:selected {{ background:{c['accent']}; color:#111; }}
    QPushButton {{ background:{c['accent']}; color:#111; border:none; border-radius:8px; padding:8px 16px; font-weight:bold; }}
    QPushButton:disabled {{ background:{c['border']}; color:{c['muted']}; }}
    QTableWidget, QPlainTextEdit, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
        background:{c['panel']}; border:1px solid {c['border']}; border-radius:6px; gridline-color:{c['border']}; }}
    QHeaderView::section {{ background:{c['bg']}; border:none; padding:6px; font-weight:bold; }}
    """
