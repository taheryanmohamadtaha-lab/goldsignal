from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QListWidget, QMainWindow, QMenu, QStackedWidget,
                               QSystemTrayIcon, QWidget)

from ..services.controller import Controller
from .pages import (AboutPage, AlertsPage, BacktestPage, ChartPage, DashboardPage, SettingsPage, SignalsPage)
from .theme import stylesheet
from .worker import Task

log = logging.getLogger(__name__)


def make_icon() -> QIcon:
    pm = QPixmap(64, 64); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#d4a017")); p.setPen(QColor("#8a6a00")); p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor("#222")); p.drawText(pm.rect(), Qt.AlignCenter, "ط"); p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self, ctl: Controller, start_minimized: bool = False, enable_tray: bool = True) -> None:
        super().__init__(); self.ctl = ctl; self.pool = QThreadPool.globalInstance(); self._busy = False
        self.setWindowTitle("طلاسنج — GoldSignal Iran"); self.setWindowIcon(make_icon()); self.resize(1200, 780)
        self.nav = QListWidget(); self.nav.setFixedWidth(170)
        self.stack = QStackedWidget()
        self.dash, self.chart, self.sigs = DashboardPage(ctl), ChartPage(ctl), SignalsPage(ctl)
        self.alerts, self.bt, self.settings, self.about = AlertsPage(ctl), BacktestPage(ctl), SettingsPage(ctl), AboutPage()
        for name, w in (("داشبورد", self.dash), ("نمودار", self.chart), ("سیگنال‌ها", self.sigs), ("هشدارها", self.alerts),
                        ("بک‌تست", self.bt), ("تنظیمات", self.settings), ("درباره", self.about)):
            self.nav.addItem(name); self.stack.addWidget(w)
        self.nav.currentRowChanged.connect(self._on_nav); self.nav.setCurrentRow(0)
        root = QWidget(); lay = QHBoxLayout(root); lay.addWidget(self.stack, 1); lay.addWidget(self.nav)   # در RTL نوار کناری سمت راست
        self.setCentralWidget(root)
        self.settings.changed.connect(self._settings_changed)
        self.tray = None
        if enable_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(make_icon(), self)
            menu = QMenu(); menu.addAction("نمایش", self.showNormal); menu.addAction("به‌روزرسانی", self.refresh); menu.addAction("خروج", QApplication.quit)
            self.tray.setContextMenu(menu); self.tray.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.Trigger else None)
            self.tray.show()
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh)
        self._apply_settings(); self._show_cached()
        QTimer.singleShot(500, self.refresh)
        if start_minimized and self.tray:
            self.hide()

    # ---- helpers
    def _apply_settings(self) -> None:
        QApplication.instance().setStyleSheet(stylesheet(self.ctl.setting("theme")))
        self.timer.start(int(self.ctl.setting("interval_min")) * 60_000)

    def _settings_changed(self) -> None:
        self._apply_settings(); self._show_cached(); self.sigs.reload(); self.alerts.reload()

    def _on_nav(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        w = self.stack.currentWidget()
        for page, fn in ((self.chart, "reload"), (self.sigs, "reload"), (self.alerts, "reload")):
            if w is page:
                getattr(page, fn)()

    def _show_cached(self) -> None:
        prices, ts = self.ctl.db.latest()
        self.dash.update_view(prices, ts, stale=False, errors={}, sigs=[])

    # ---- refresh in background
    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        t = Task(self.ctl.refresh)
        t.sig.done.connect(self._refreshed); t.sig.failed.connect(self._refresh_failed)
        self.pool.start(t)

    def _refresh_failed(self, tb: str) -> None:
        self._busy = False; log.error("refresh failed: %s", tb)
        self.dash.status.setText("خطای داخلی در به‌روزرسانی؛ جزئیات در فایل لاگ ثبت شد.")

    def _refreshed(self, result) -> None:
        self._busy = False
        res, fired, sigs = result
        self.dash.update_view(res.prices, res.ts, res.from_cache, res.errors, sigs)
        for f in fired:
            if self.tray:
                self.tray.showMessage(f.title, f.text, QSystemTrayIcon.Information, 10_000)
            if self.ctl.setting("sound"):
                self._beep()
        self._on_nav(self.stack.currentIndex())

    @staticmethod
    def _beep() -> None:
        try:
            if sys.platform == "win32":
                import winsound; winsound.MessageBeep()
            else:
                QApplication.beep()
        except Exception:
            pass

    def closeEvent(self, e) -> None:  # بستن = رفتن به System Tray
        if self.tray and self.tray.isVisible():
            self.hide(); e.ignore()
        else:
            e.accept()
