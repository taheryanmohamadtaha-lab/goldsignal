"""صفحات برنامه. منطق در services/ است؛ اینجا فقط نمایش و دریافت ورودی."""
from __future__ import annotations

import json
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import __version__
from ..analysis import formulas
from ..constants import COIN_KEYS, DISCLAIMER, PRICE_KEYS
from ..providers.csv_import import import_csv
from ..services import export as export_svc
from ..services.alerts import KINDS
from ..services.autostart import set_autostart
from ..services.controller import Controller
from ..services.secrets import set_secret
from ..signals.backtest import run_backtest
from .chart import ChartWidget
from .theme import fmt_date, fmt_num

ACTION_FA = {"buy": "خرید", "sell": "فروش", "hold": "نگه‌داری"}


def card() -> QFrame:
    f = QFrame(); f.setObjectName("card"); return f


def disclaimer_label() -> QLabel:
    l = QLabel("⚠ " + DISCLAIMER); l.setObjectName("warn"); l.setWordWrap(True); return l


def make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QTableWidget.NoEditTriggers); t.setSelectionBehavior(QTableWidget.SelectRows)
    t.horizontalHeader().setStretchLastSection(True); t.verticalHeader().setVisible(False)
    return t


def fill(t: QTableWidget, rows: list[list[str]]) -> None:
    t.setRowCount(len(rows))
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            it = QTableWidgetItem(str(v)); it.setTextAlignment(Qt.AlignCenter); t.setItem(i, j, it)
    t.resizeColumnsToContents()


class DashboardPage(QWidget):
    def __init__(self, ctl: Controller) -> None:
        super().__init__(); self.ctl = ctl
        lay = QVBoxLayout(self)
        self.status = QLabel("—"); self.status.setObjectName("muted")
        lay.addWidget(self.status)
        self.grid = QGridLayout(); self.cards: dict[str, tuple[QLabel, QLabel]] = {}
        for i, (k, name) in enumerate(PRICE_KEYS.items()):
            c = card(); v = QVBoxLayout(c)
            t = QLabel(name); t.setObjectName("muted"); val = QLabel("—"); val.setObjectName("big")
            v.addWidget(t); v.addWidget(val); self.cards[k] = (t, val); self.grid.addWidget(c, i // 4, i % 4)
        lay.addLayout(self.grid)
        lay.addWidget(QLabel("جدول حباب و ارزش ذاتی"))
        self.table = make_table(["سکه", "قیمت بازار", "ارزش ذاتی", "حباب (مبلغ)", "حباب (٪)"]); lay.addWidget(self.table)
        lay.addWidget(QLabel("اختلاف قیمت داخلی/جهانی و خلاصهٔ سیگنال‌ها"))
        self.info = QLabel("—"); self.info.setWordWrap(True); lay.addWidget(self.info)
        lay.addWidget(disclaimer_label())

    def update_view(self, prices: dict[str, float], ts: int, stale: bool, errors: dict[str, str], sigs) -> None:
        unit, dg = self.ctl.setting("unit"), self.ctl.setting("digits")
        u = "ریال" if unit == "rial" else "تومان"
        derived = {**prices, **formulas.derived_prices(prices)}
        for k, (_, val) in self.cards.items():
            v = derived.get(k)
            if v is None:
                val.setText("—")
            elif k == "ounce":
                val.setText(fmt_num(v, dg, 2) + " $")
            else:
                val.setText(fmt_num(formulas.to_display(v, unit), dg) + (" " + u if k != "usd" or True else ""))
        msg = f"آخرین به‌روزرسانی: {fmt_date(ts, dg)}"
        if stale:
            msg += "  —  ⚠ اینترنت/منبع در دسترس نیست؛ آخرین دادهٔ ذخیره‌شده نمایش داده می‌شود"
        if errors:
            msg += "\nخطای منابع: " + " | ".join(f"{k}: {v}" for k, v in errors.items())
        self.status.setText(msg)
        bubbles = formulas.compute_bubbles(prices, self.ctl.pure_gold())
        rows = [[PRICE_KEYS[k], fmt_num(formulas.to_display(b.market, unit), dg), fmt_num(formulas.to_display(b.intrinsic, unit), dg),
                 fmt_num(formulas.to_display(b.amount, unit), dg), fmt_num(b.percent, dg, 1) + "٪"] for k, b in bubbles.items()]
        fill(self.table, rows)
        parts = []
        if "gold18" in prices and "gold18_intrinsic" in derived:
            d, pc = formulas.spread(derived["gold18_intrinsic"], prices["gold18"])
            parts.append(f"طلای ۱۸ بازار نسبت به ذاتی: {fmt_num(pc, dg, 1)}٪")
        if sigs:
            parts.append("سیگنال‌ها (۱ روزه): " + "، ".join(f"{PRICE_KEYS.get(s.asset, s.asset)}: {ACTION_FA[s.action]}" for s in sigs))
        self.info.setText("\n".join(parts) or "داده کافی برای مقایسه/سیگنال نیست. در تنظیمات منبع یا قیمت دستی وارد کنید.")


class ChartPage(QWidget):
    def __init__(self, ctl: Controller) -> None:
        super().__init__(); self.ctl = ctl
        lay = QVBoxLayout(self); bar = QHBoxLayout()
        self.asset = QComboBox(); [self.asset.addItem(PRICE_KEYS[k], k) for k in (*COIN_KEYS, "gold18", "usd", "ounce")]
        self.tf = QComboBox(); [self.tf.addItem(n, k) for n, k in (("۱ ساعته", "1h"), ("۴ ساعته", "4h"), ("روزانه", "1d"), ("هفتگی", "1w"))]
        self.tf.setCurrentIndex(2)
        self.opts = {k: QCheckBox(n) for k, n in (("ema", "EMA 9/21"), ("sma", "SMA 50"), ("bb", "بولینگر"), ("sr", "حمایت/مقاومت"))}
        self.opts["ema"].setChecked(True)
        for w in (self.asset, self.tf, *self.opts.values()):
            bar.addWidget(w)
        bar.addStretch(); lay.addLayout(bar)
        self.chart = ChartWidget(); lay.addWidget(self.chart, 1)
        self.note = QLabel(""); self.note.setObjectName("muted"); lay.addWidget(self.note)
        lay.addWidget(disclaimer_label())
        for w in (self.asset, self.tf):
            w.currentIndexChanged.connect(self.reload)
        for w in self.opts.values():
            w.toggled.connect(self.reload)

    def reload(self) -> None:
        df = self.ctl.candles(self.asset.currentData(), self.tf.currentData())
        self.chart.plot(df, {k: w.isChecked() for k, w in self.opts.items()})
        self.note.setText(f"{len(df)} کندل از تاریخچهٔ ذخیره‌شده. با هر به‌روزرسانی داده بیشتر می‌شود؛ برای تاریخچهٔ طولانی‌تر از CSV وارد کنید."
                          if len(df) else "تاریخچه‌ای نیست؛ از تنظیمات CSV وارد کنید یا چند بار به‌روزرسانی کنید.")


class SignalsPage(QWidget):
    def __init__(self, ctl: Controller) -> None:
        super().__init__(); self.ctl = ctl
        lay = QVBoxLayout(self); lay.addWidget(disclaimer_label())
        self.rate = QLabel("—"); lay.addWidget(self.rate)
        self.table = make_table(["زمان", "دارایی", "تایم‌فریم", "اقدام", "ورود", "حد ضرر", "هدف", "R/R", "اطمینان", "نتیجه", "دلیل"])
        lay.addWidget(self.table)
        bar = QHBoxLayout()
        for name, fn in (("CSV", self.exp_csv), ("Excel", self.exp_xlsx), ("PDF", self.exp_pdf)):
            b = QPushButton("خروجی " + name); b.clicked.connect(fn); bar.addWidget(b)
        bar.addStretch(); lay.addLayout(bar)

    def reload(self) -> None:
        dg = self.ctl.setting("digits"); rows = []
        for r in self.ctl.db.signals():
            rows.append([fmt_date(r["ts"], dg), PRICE_KEYS.get(r["asset"], r["asset"]), r["timeframe"], ACTION_FA.get(r["action"], r["action"]),
                         fmt_num(r["entry"], dg), fmt_num(r["stop"], dg), fmt_num(r["target"], dg), fmt_num(r["rr"], dg, 1),
                         fmt_num(r["confidence"], dg), {"win": "موفق", "loss": "ناموفق", "open": "باز"}.get(r["outcome"], ""), r["reasons"]])
        fill(self.table, rows)
        w, l, pct = self.ctl.db.success_rate()
        self.rate.setText(f"نرخ موفقیت واقعی (سیگنال‌های بسته‌شده): {fmt_num(pct, dg, 1)}٪ — {fmt_num(w, dg)} موفق، {fmt_num(l, dg)} ناموفق"
                          if pct is not None else "هنوز سیگنال بسته‌شده‌ای برای محاسبهٔ نرخ موفقیت وجود ندارد.")

    def _export(self, filt: str, ext: str, fn: Callable) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره", f"signals.{ext}", filt)
        if path:
            try:
                fn(export_svc.signals_frame(self.ctl.db.signals(5000)), path)
                QMessageBox.information(self, "خروجی", "ذخیره شد.")
            except Exception as e:
                QMessageBox.warning(self, "خطا", str(e))

    def exp_csv(self): self._export("CSV (*.csv)", "csv", export_svc.export_csv)
    def exp_xlsx(self): self._export("Excel (*.xlsx)", "xlsx", export_svc.export_excel)
    def exp_pdf(self): self._export("PDF (*.pdf)", "pdf", export_svc.export_pdf)


class AlertsPage(QWidget):
    def __init__(self, ctl: Controller) -> None:
        super().__init__(); self.ctl = ctl
        lay = QVBoxLayout(self); form = QHBoxLayout()
        self.kind = QComboBox(); [self.kind.addItem(n, k) for k, n in KINDS.items()]
        self.asset = QComboBox(); [self.asset.addItem(n, k) for k, n in PRICE_KEYS.items()]; self.asset.addItem("همه", "*")
        self.th = QDoubleSpinBox(); self.th.setRange(-1e12, 1e12); self.th.setDecimals(2); self.th.setGroupSeparatorShown(True)
        add = QPushButton("افزودن"); add.clicked.connect(self.add)
        rm = QPushButton("حذف انتخاب‌شده"); rm.clicked.connect(self.remove)
        for w in (self.kind, self.asset, self.th, add, rm):
            form.addWidget(w)
        lay.addLayout(form)
        self.table = make_table(["#", "نوع", "دارایی", "آستانه", "وضعیت"]); lay.addWidget(self.table)
        lay.addWidget(QLabel("قیمت‌ها به «تومان» وارد شوند (حباب به درصد). اعلان‌ها به‌صورت Toast ویندوز و صدا نمایش داده می‌شوند."))

    def add(self) -> None:
        self.ctl.db.add_alert(self.kind.currentData(), self.asset.currentData(), self.th.value()); self.reload()

    def remove(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.ctl.db.delete_alert(int(self.table.item(r, 0).text())); self.reload()

    def reload(self) -> None:
        fill(self.table, [[a["id"], KINDS.get(a["kind"], a["kind"]), PRICE_KEYS.get(a["asset"], a["asset"]), f"{a['threshold']:g}",
                           "فعال‌شده" if a["triggered"] else "در انتظار"] for a in self.ctl.db.alerts()])


class BacktestPage(QWidget):
    def __init__(self, ctl: Controller) -> None:
        super().__init__(); self.ctl = ctl
        lay = QVBoxLayout(self); bar = QHBoxLayout()
        self.asset = QComboBox(); [self.asset.addItem(PRICE_KEYS[k], k) for k in (*COIN_KEYS, "gold18")]
        self.tf = QComboBox(); [self.tf.addItem(n, k) for n, k in (("۱ ساعته", "1h"), ("۴ ساعته", "4h"), ("روزانه", "1d"), ("هفتگی", "1w"))]
        self.tf.setCurrentIndex(2)
        self.fee = QDoubleSpinBox(); self.fee.setRange(0, 5); self.fee.setValue(0.3); self.fee.setSuffix(" ٪ کارمزد/اسپرد هر طرف")
        run = QPushButton("اجرای بک‌تست"); run.clicked.connect(self.run)
        for w in (self.asset, self.tf, self.fee, run):
            bar.addWidget(w)
        lay.addLayout(bar); self.summary = QLabel("—"); self.summary.setWordWrap(True); lay.addWidget(self.summary)
        self.table = make_table(["ورود", "خروج", "قیمت ورود", "قیمت خروج", "سود/زیان ٪", "دلیل خروج"]); lay.addWidget(self.table)
        lay.addWidget(disclaimer_label())

    def run(self) -> None:
        a, tf = self.asset.currentData(), self.tf.currentData(); dg = self.ctl.setting("digits")
        df = self.ctl.candles(a, tf)
        rep = run_backtest(df, self.ctl.rule_config(), self.ctl.bubble_series(a, tf), self.fee.value())
        if rep.note:
            self.summary.setText(rep.note); fill(self.table, []); return
        pf = fmt_num(rep.profit_factor, dg, 2) if rep.profit_factor is not None else "—"
        self.summary.setText(f"تعداد معاملات: {fmt_num(rep.n_trades, dg)} | Win Rate: {fmt_num(rep.win_rate, dg, 1)}٪ | "
                             f"سود/زیان کل: {fmt_num(rep.total_return_pct, dg, 1)}٪ | بیشینه Drawdown: {fmt_num(rep.max_drawdown_pct, dg, 1)}٪ | Profit Factor: {pf}\n"
                             "نتیجهٔ گذشته تضمینی برای آینده نیست.")
        fill(self.table, [[fmt_date(int(t.entry_ts.timestamp()), dg), fmt_date(int(t.exit_ts.timestamp()), dg), fmt_num(t.entry, dg),
                           fmt_num(t.exit, dg), fmt_num(t.pnl_pct, dg, 2), t.reason] for t in rep.trades])


class SettingsPage(QWidget):
    changed = Signal()

    def __init__(self, ctl: Controller) -> None:
        super().__init__(); self.ctl = ctl; db = ctl.db
        lay = QVBoxLayout(self); form = QFormLayout()
        self.unit = QComboBox(); self.unit.addItem("تومان", "toman"); self.unit.addItem("ریال", "rial")
        self.digits = QComboBox(); self.digits.addItem("فارسی (۱۲۳)", "fa"); self.digits.addItem("انگلیسی (123)", "en")
        self.theme = QComboBox(); self.theme.addItem("شب", "dark"); self.theme.addItem("روز", "light")
        self.interval = QSpinBox(); self.interval.setRange(1, 240); self.interval.setSuffix(" دقیقه")
        self.stooq = QCheckBox("اونس جهانی از Stooq (تأییدنشده؛ در صورت خطا خاموش کنید)")
        self.sound = QCheckBox("صدای هشدار"); self.auto = QCheckBox("اجرای خودکار با ویندوز")
        for lbl, w in (("واحد نمایش", self.unit), ("ارقام", self.digits), ("تم", self.theme), ("بازهٔ به‌روزرسانی", self.interval),
                       ("", self.stooq), ("", self.sound), ("", self.auto)):
            form.addRow(lbl, w)
        lay.addLayout(form)
        lay.addWidget(QLabel("منابع JSON شخصی (فهرست JSON؛ فقط HTTPS؛ بدون آدرس پیش‌فرض—راهنما در docs/data-sources.md):"))
        self.json_src = QPlainTextEdit(); self.json_src.setFixedHeight(110); lay.addWidget(self.json_src)
        kr = QHBoxLayout(); self.key_name = QLineEdit(); self.key_name.setPlaceholderText("نام منبع")
        self.key_val = QLineEdit(); self.key_val.setPlaceholderText("کلید API"); self.key_val.setEchoMode(QLineEdit.Password)
        kb = QPushButton("ذخیرهٔ امن کلید"); kb.clicked.connect(self.save_key)
        for w in (self.key_name, self.key_val, kb):
            kr.addWidget(w)
        lay.addLayout(kr)
        lay.addWidget(QLabel("ورود دستی قیمت (تومان؛ اونس به دلار):"))
        mg = QGridLayout(); self.man: dict[str, QDoubleSpinBox] = {}
        for i, (k, n) in enumerate((x for x in PRICE_KEYS.items() if x[0] != "mesghal18")):
            s = QDoubleSpinBox(); s.setRange(0, 1e13); s.setDecimals(2); s.setGroupSeparatorShown(True); self.man[k] = s
            mg.addWidget(QLabel(n), i // 4 * 2, i % 4); mg.addWidget(s, i // 4 * 2 + 1, i % 4)
        lay.addLayout(mg)
        row = QHBoxLayout()
        b1 = QPushButton("ذخیرهٔ تنظیمات"); b1.clicked.connect(self.save)
        b2 = QPushButton("ثبت قیمت دستی"); b2.clicked.connect(self.save_manual)
        b3 = QPushButton("ایمپورت CSV تاریخچه"); b3.clicked.connect(self.import_csv)
        for b in (b1, b2, b3):
            row.addWidget(b)
        lay.addLayout(row)
        lay.addWidget(QLabel("پیشرفته (JSON): قوانین سیگنال و وزن طلای خالص سکه‌ها"))
        self.adv = QPlainTextEdit(); self.adv.setFixedHeight(90); lay.addWidget(self.adv); lay.addStretch()
        self.load()

    def load(self) -> None:
        c = self.ctl
        self.unit.setCurrentIndex(self.unit.findData(c.setting("unit"))); self.digits.setCurrentIndex(self.digits.findData(c.setting("digits")))
        self.theme.setCurrentIndex(self.theme.findData(c.setting("theme"))); self.interval.setValue(int(c.setting("interval_min")))
        self.stooq.setChecked(bool(c.setting("use_stooq"))); self.sound.setChecked(bool(c.setting("sound"))); self.auto.setChecked(bool(c.setting("autostart")))
        self.json_src.setPlainText(json.dumps(c.setting("json_sources") or [], ensure_ascii=False, indent=2))
        self.adv.setPlainText(json.dumps({"rules": c.rule_config().to_dict(), "pure_gold": c.pure_gold()}, ensure_ascii=False, indent=2))

    def save(self) -> None:
        db = self.ctl.db
        try:
            srcs = json.loads(self.json_src.toPlainText() or "[]"); adv = json.loads(self.adv.toPlainText() or "{}")
            if not isinstance(srcs, list):
                raise ValueError("منابع باید فهرست باشند")
            from ..providers.base import require_https
            for s in srcs:
                require_https(s["url"])
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"JSON نامعتبر: {e}"); return
        for k, w in (("unit", self.unit), ("digits", self.digits), ("theme", self.theme)):
            db.set_setting(k, w.currentData())
        db.set_setting("interval_min", self.interval.value()); db.set_setting("use_stooq", self.stooq.isChecked())
        db.set_setting("sound", self.sound.isChecked()); db.set_setting("autostart", self.auto.isChecked())
        db.set_setting("json_sources", srcs)
        db.set_setting("rules", adv.get("rules", {})); db.set_setting("pure_gold", adv.get("pure_gold", {}))
        set_autostart(self.auto.isChecked())
        self.changed.emit()

    def save_key(self) -> None:
        if self.key_name.text() and self.key_val.text():
            ok = set_secret(self.key_name.text(), self.key_val.text()); self.key_val.clear()
            QMessageBox.information(self, "کلید", "در Credential Manager ذخیره شد." if ok else "keyring در دسترس نیست؛ کلید فقط تا بستن برنامه نگه‌داری می‌شود.")

    def save_manual(self) -> None:
        self.ctl.manual.set_prices({k: w.value() for k, w in self.man.items() if w.value() > 0})
        self.ctl.db.add_prices({k: w.value() for k, w in self.man.items() if w.value() > 0}, "manual")
        self.changed.emit()

    def import_csv(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "CSV", "", "CSV (*.csv)")
        if p:
            try:
                ok, bad = import_csv(self.ctl.db, p)
                QMessageBox.information(self, "ایمپورت", f"{ok} ردیف وارد شد، {bad} ردیف نامعتبر رد شد.")
                self.changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "خطا", str(e))


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__(); lay = QVBoxLayout(self)
        t = QLabel(f"طلاسنج (GoldSignal Iran) — نسخه {__version__}\n\nتحلیل و سیگنال‌دهی بازار طلا و سکهٔ ایران.\n"
                   "داده‌ها از منابعی است که خودتان تنظیم می‌کنید؛ دقت و به‌روز بودن آن‌ها تضمین نمی‌شود.\n"
                   "فونت وزیرمتن با مجوز OFL. مجوز برنامه: MIT.")
        t.setWordWrap(True); lay.addWidget(t); lay.addWidget(disclaimer_label()); lay.addStretch()
