"""نمودار کندل‌استیک تعاملی با pyqtgraph + EMA/SMA/Bollinger + RSI + MACD + حمایت/مقاومت."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPicture

from ..analysis import indicators as ind
from ..analysis import patterns as pat


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, df: pd.DataFrame, width: float) -> None:
        super().__init__()
        self.pic = QPicture()
        p = QPainter(self.pic)
        xs = df.index.astype("int64").to_numpy() / 1e9
        for t, (_, r) in zip(xs, df.iterrows()):
            up = r["close"] >= r["open"]
            p.setPen(pg.mkPen("#2ecc71" if up else "#e74c3c"))
            p.setBrush(pg.mkBrush("#2ecc71" if up else "#e74c3c"))
            p.drawLine(QPointF(t, r["low"]), QPointF(t, r["high"]))
            p.drawRect(QRectF(t - width / 2, r["open"], width, r["close"] - r["open"]))
        p.end()
        self._rect = QRectF(self.pic.boundingRect())

    def paint(self, p, *args) -> None:
        p.drawPicture(0, 0, self.pic)

    def boundingRect(self) -> QRectF:
        return self._rect


class ChartWidget(pg.GraphicsLayoutWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setBackground(None)
        self.price = self.addPlot(row=0, col=0, axisItems={"bottom": pg.DateAxisItem(utcOffset=0)})
        self.rsi_p = self.addPlot(row=1, col=0, axisItems={"bottom": pg.DateAxisItem(utcOffset=0)})
        self.macd_p = self.addPlot(row=2, col=0, axisItems={"bottom": pg.DateAxisItem(utcOffset=0)})
        self.ci.layout.setRowStretchFactor(0, 5)
        self.ci.layout.setRowStretchFactor(1, 1)
        self.ci.layout.setRowStretchFactor(2, 1)
        self.rsi_p.setXLink(self.price)
        self.macd_p.setXLink(self.price)
        for p in (self.price, self.rsi_p, self.macd_p):
            p.showGrid(x=True, y=True, alpha=0.2)

    def plot(self, df: pd.DataFrame, opts: dict) -> None:
        for p in (self.price, self.rsi_p, self.macd_p):
            p.clear()
        if df.empty:
            return
        xs = df.index.astype("int64").to_numpy() / 1e9
        step = np.median(np.diff(xs)) if len(xs) > 1 else 3600
        self.price.addItem(CandlestickItem(df, step * 0.7))
        c = df["close"]
        if opts.get("ema"):
            self.price.plot(xs, ind.ema(c, 9).to_numpy(), pen=pg.mkPen("#3498db", width=1.5))
            self.price.plot(xs, ind.ema(c, 21).to_numpy(), pen=pg.mkPen("#e67e22", width=1.5))
        if opts.get("sma"):
            self.price.plot(xs, ind.sma(c, 50).to_numpy(), pen=pg.mkPen("#9b59b6", width=1.5))
        if opts.get("bb"):
            bb = ind.bollinger(c)
            for col in ("upper", "mid", "lower"):
                self.price.plot(xs, bb[col].to_numpy(), pen=pg.mkPen("#95a5a6", style=pg.QtCore.Qt.DashLine))
        if opts.get("sr"):
            sup, res = pat.support_resistance(df)
            for y in sup:
                self.price.addItem(pg.InfiniteLine(pos=y, angle=0, pen=pg.mkPen("#2ecc71", style=pg.QtCore.Qt.DotLine)))
            for y in res:
                self.price.addItem(pg.InfiniteLine(pos=y, angle=0, pen=pg.mkPen("#e74c3c", style=pg.QtCore.Qt.DotLine)))
        self.rsi_p.plot(xs, ind.rsi(c).to_numpy(), pen=pg.mkPen("#f1c40f"))
        for y in (30, 70):
            self.rsi_p.addItem(pg.InfiniteLine(pos=y, angle=0, pen=pg.mkPen("#777", style=pg.QtCore.Qt.DotLine)))
        m = ind.macd(c)
        self.macd_p.addItem(pg.BarGraphItem(x=xs, height=m["hist"].fillna(0).to_numpy(), width=step * 0.6, brush="#7f8c8d"))
        self.macd_p.plot(xs, m["macd"].to_numpy(), pen=pg.mkPen("#3498db"))
        self.macd_p.plot(xs, m["signal"].to_numpy(), pen=pg.mkPen("#e67e22"))
        self.price.autoRange()
