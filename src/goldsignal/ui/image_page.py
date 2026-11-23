"""صفحهٔ «تحلیل تصویر چارت»: تصویر را بارگذاری/پیست کنید، دو نقطهٔ قیمت را مشخص کنید، تحلیل بگیرید."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..analysis.chart_image import Calibration, ChartImageError, extract_candles
from ..signals.image_signal import analyze_candles
from .chart import ChartWidget
from .pages import ACTION_FA, disclaimer_label


def qimage_to_array(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    buf = np.frombuffer(img.constBits(), dtype=np.uint8, count=bpl * h).reshape(h, bpl)
    return buf[:, : w * 3].reshape(h, w, 3).copy()


class ClickLabel(QLabel):
    clicked = Signal(int, int)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        p: QPoint = e.position().toPoint()
        self.clicked.emit(p.x(), p.y())


class ImageAnalysisPage(QWidget):
    HELP = ("۱) تصویر چارت را باز کنید یا با Ctrl+V اسکرین‌شات را بچسبانید (کندل سبز=صعودی، قرمز=نزولی؛ حداقل ۳۰ کندل، بدون عدد/ابزار روی کندل‌ها).\n"
            "۲) روی تصویر دو نقطه کلیک کنید: یکی نزدیک بالای قاب قیمت و یکی نزدیک پایین آن (مثلاً کنار دو عدد روی محور قیمت) و قیمت هرکدام را وارد کنید. "
            "تحلیل فقط بین همین دو نقطه (به‌علاوهٔ ۳٪ حاشیه) انجام می‌شود؛ پس بخش حجم را داخل قاب نگیرید.\n"
            "۳) تایم‌فریم را انتخاب و «تحلیل» را بزنید. مقیاس قیمت باید خطی باشد (نه لگاریتمی).")

    def __init__(self) -> None:
        super().__init__()
        self.qimg: QImage | None = None
        self.points: list[tuple[int, float]] = []
        lay = QVBoxLayout(self)
        h = QLabel(self.HELP); h.setWordWrap(True); h.setObjectName("muted"); lay.addWidget(h)
        bar = QHBoxLayout()
        b_open = QPushButton("باز کردن تصویر"); b_open.clicked.connect(self.open_file)
        b_paste = QPushButton("چسباندن از کلیپ‌بورد"); b_paste.clicked.connect(self.paste)
        b_clear = QPushButton("پاک‌کردن نقاط"); b_clear.clicked.connect(self.clear_points)
        self.tf = QComboBox(); [self.tf.addItem(n, k) for n, k in (("۱ ساعته", "1h"), ("۴ ساعته", "4h"), ("روزانه", "1d"), ("هفتگی", "1w"))]
        self.tf.setCurrentIndex(2)
        self.scheme = QComboBox(); self.scheme.addItem("سبز صعودی / قرمز نزولی", False); self.scheme.addItem("قرمز صعودی / سبز نزولی", True)
        b_run = QPushButton("تحلیل"); b_run.clicked.connect(self.analyze)
        for w in (b_open, b_paste, b_clear, self.tf, self.scheme, b_run):
            bar.addWidget(w)
        bar.addStretch(); lay.addLayout(bar)
        body = QHBoxLayout()
        self.img_label = ClickLabel("تصویری بارگذاری نشده"); self.img_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.img_label.clicked.connect(self.on_click)
        sc = QScrollArea(); sc.setWidget(self.img_label); sc.setWidgetResizable(False); sc.setMinimumWidth(420)
        body.addWidget(sc, 3)
        right = QVBoxLayout()
        self.chart = ChartWidget(); self.chart.setMinimumHeight(220); right.addWidget(self.chart, 2)
        self.verdict = QLabel("—"); self.verdict.setObjectName("big"); right.addWidget(self.verdict)
        self.report = QPlainTextEdit(); self.report.setReadOnly(True); right.addWidget(self.report, 2)
        body.addLayout(right, 3); lay.addLayout(body, 1)
        lay.addWidget(disclaimer_label())

    # ---- input
    def open_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "تصویر چارت", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if p:
            img = QImage(p)
            if img.isNull():
                QMessageBox.warning(self, "خطا", "تصویر خوانده نشد."); return
            self.set_image(img)

    def paste(self) -> None:
        img = QGuiApplication.clipboard().image()
        if img.isNull():
            QMessageBox.information(self, "کلیپ‌بورد", "تصویری در کلیپ‌بورد نیست. اسکرین‌شات بگیرید و دوباره امتحان کنید."); return
        self.set_image(img)

    def keyPressEvent(self, e) -> None:
        if e.matches(__import__("PySide6.QtGui", fromlist=["QKeySequence"]).QKeySequence.Paste):
            self.paste()
        else:
            super().keyPressEvent(e)

    def set_image(self, img: QImage) -> None:
        self.qimg = img.convertToFormat(QImage.Format_RGB888); self.points = []; self._redraw()
        self.report.setPlainText(""); self.verdict.setText("—")

    def clear_points(self) -> None:
        self.points = []; self._redraw()

    def _redraw(self) -> None:
        if self.qimg is None:
            return
        pm = QPixmap.fromImage(self.qimg); p = QPainter(pm); p.setPen(QPen(QColor("#ffd400"), 2))
        for y, price in self.points:
            p.drawLine(0, y, pm.width(), y); p.drawText(6, y - 4, f"{price:,.2f}")
        p.end(); self.img_label.setPixmap(pm); self.img_label.resize(pm.size())

    def on_click(self, x: int, y: int) -> None:
        if self.qimg is None or len(self.points) >= 2:
            return
        price, ok = QInputDialog.getDouble(self, "قیمت این نقطه", "قیمت روی این ردیف:", 0.0, 0.0, 1e13, 4)
        if ok and price > 0:
            self.points.append((y, price)); self._redraw()

    # ---- analysis
    def analyze(self) -> None:
        if self.qimg is None:
            QMessageBox.information(self, "تصویر", "ابتدا تصویر را بارگذاری کنید."); return
        if len(self.points) != 2:
            QMessageBox.information(self, "کالیبراسیون", "دو نقطه با قیمت لازم است (روی تصویر کلیک کنید)."); return
        (y1, p1), (y2, p2) = self.points
        tf = self.tf.currentData()
        try:
            ex = extract_candles(qimage_to_array(self.qimg), Calibration(y1, p1, y2, p2), self.scheme.currentData(), tf)
        except ChartImageError as e:
            QMessageBox.warning(self, "خطا", str(e)); return
        self.show_result(ex, analyze_candles(ex.candles, tf))

    def show_result(self, ex, a) -> None:
        self.chart.plot(ex.candles, {"ema": True, "sr": True})
        s = a.signal
        self.verdict.setText(f"سیگنال: {ACTION_FA[s.action]} — اطمینان {s.confidence}٪ (حداکثر ۷۰٪ برای تحلیل تصویری)")
        lines = [f"تعداد کندل استخراج‌شده: {a.n}"] + a.lines
        if ex.warnings:
            lines += ["", "هشدارهای کیفیت:"] + ["• " + w for w in ex.warnings]
        lines += ["", "⚠ دقت این روش در حد پیکسل تصویر است و فقط با قوانین ساده (EMA/RSI/MACD/حمایت‌مقاومت) کار می‌کند. توصیه مالی نیست."]
        self.report.setPlainText("\n".join(lines))
