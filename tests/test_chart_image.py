import numpy as np
import pandas as pd
import pytest

from goldsignal.analysis.chart_image import Calibration, ChartImageError, extract_candles
from goldsignal.signals.image_signal import analyze_candles

GREEN, RED = (8, 153, 129), (242, 54, 69)
BG = (19, 23, 34)


def render(ohlc, H=500, W=900, pmin=None, pmax=None, step=10, bw=6, line=False, labelbox=False):
    pmin = pmin if pmin is not None else min(r[2] for r in ohlc) - 1
    pmax = pmax if pmax is not None else max(r[1] for r in ohlc) + 1
    y = lambda p: int(round((pmax - p) / (pmax - pmin) * (H - 1)))
    img = np.zeros((H, W, 3), np.uint8); img[:] = BG
    for i, (o, h, l, c) in enumerate(ohlc):
        x = 10 + i * step; col = GREEN if c >= o else RED
        img[y(h):y(l) + 1, x + bw // 2] = col
        img[y(max(o, c)):y(min(o, c)) + 2, x:x + bw] = col
    if line:
        img[y(ohlc[-1][3]), ::2] = RED          # خط چین قیمت فعلی
        img[y(ohlc[-1][3]), 1::2] = RED
    if labelbox:
        img[200:220, W - 60:] = RED
    return img, Calibration(y(pmax), pmax, y(pmin), pmin), y


def series(n=60, seed=1, drift=0.4):
    rng = np.random.default_rng(seed); c = 100 + np.cumsum(rng.normal(drift, 1.2, n)); out = []
    prev = 100.0
    for ci in c:
        o = prev; h = max(o, ci) + rng.random() * 1.5; l = min(o, ci) - rng.random() * 1.5
        out.append((o, h, l, ci)); prev = ci
    return out


def test_round_trip_accuracy():
    ohlc = series(); img, cal, _ = render(ohlc)
    ex = extract_candles(img, cal)
    assert len(ex.candles) == len(ohlc)
    exp = np.array(ohlc)
    got = ex.candles[["open", "high", "low", "close"]].to_numpy()
    tol = (max(r[1] for r in ohlc) - min(r[2] for r in ohlc)) * 0.03   # ۳٪ دامنه ≈ چند پیکسل
    assert np.abs(got - exp).max() < tol


def test_direction_and_invert():
    ohlc = series(); img, cal, _ = render(ohlc)
    ex = extract_candles(img, cal)
    assert ((ex.candles["close"] >= ex.candles["open"]).to_numpy() == np.array([c >= o for o, h, l, c in ohlc])).mean() > 0.95
    inv = extract_candles(img, cal, invert=True)     # رنگ‌ها وارونه: جهت‌ها برعکس
    assert ((inv.candles["close"] >= inv.candles["open"]).to_numpy() != np.array([c >= o for o, h, l, c in ohlc])).mean() > 0.9


def test_ignores_price_line_and_label_box():
    ohlc = series(); img, cal, _ = render(ohlc, line=True, labelbox=True)
    ex = extract_candles(img, cal)
    assert len(ex.candles) == len(ohlc)


def test_errors():
    ohlc = series(); img, cal, _ = render(ohlc)
    with pytest.raises(ChartImageError):
        extract_candles(img, Calibration(100, 5, 105, 4))          # فاصلهٔ کم
    with pytest.raises(ChartImageError):
        extract_candles(img, Calibration(10, 5, 400, 5))           # قیمت برابر
    with pytest.raises(ChartImageError):
        extract_candles(np.zeros((300, 300, 3), np.uint8), Calibration(10, 10, 280, 5))   # بدون کندل
    with pytest.raises(ChartImageError):
        extract_candles(np.zeros((300, 300), np.uint8), cal)


def test_few_candles_warns_and_holds():
    ohlc = series(12); img, cal, _ = render(ohlc)
    ex = extract_candles(img, cal)
    assert any("حداقل ۳۰" in w for w in ex.warnings)
    a = analyze_candles(ex.candles)
    assert a.signal.action == "hold" and a.signal.confidence == 0


def test_uptrend_gives_buy_or_hold_never_sell_and_capped():
    ohlc = series(80, drift=0.6); img, cal, _ = render(ohlc, W=1000)
    a = analyze_candles(extract_candles(img, cal).candles)
    assert a.trend == "صعودی" and a.signal.action in ("buy", "hold") and a.signal.confidence <= 70
    if a.signal.action == "buy":
        s = a.signal
        assert s.stop < s.entry < s.target and s.rr > 1


def test_downtrend_gives_sell():
    ohlc = series(80, drift=-0.6, seed=4); img, cal, _ = render(ohlc, W=1000)
    a = analyze_candles(extract_candles(img, cal).candles)
    assert a.trend == "نزولی" and a.signal.action == "sell"
