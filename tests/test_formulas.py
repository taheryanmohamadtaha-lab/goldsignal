import pytest

from goldsignal.analysis import formulas as f


def test_gram24():
    assert f.gram24(3110.35, 100_000) == pytest.approx(10_000_000)


def test_emami_intrinsic_and_bubble():
    intr = f.coin_intrinsic(3110.35, 100_000, 7.322)
    assert intr == pytest.approx(73_220_000)
    b = f.bubble(80_542_000, intr)
    assert b.amount == pytest.approx(7_322_000)
    assert b.percent == pytest.approx(10.0)


def test_negative_bubble():
    assert f.bubble(70_000_000, 73_220_000).percent < 0


def test_mesghal():
    assert f.mesghal_price(1_000_000) == pytest.approx(4_608_000)


def test_spread():
    d, p = f.spread(100, 102)
    assert d == 2 and p == pytest.approx(2.0)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        f.gram24(0, 100)
    with pytest.raises(ValueError):
        f.bubble(1, 0)


def test_incomplete_data_gives_no_bubbles():
    assert f.compute_bubbles({"emami": 1e8}) == {}
    assert f.compute_bubbles({"ounce": 2000, "usd": 0, "emami": 1e8}) == {}


def test_compute_bubbles_half_and_quarter_weights():
    out = f.compute_bubbles({"ounce": 3110.35, "usd": 100_000, "half": 40_000_000, "quarter": 20_000_000})
    assert out["half"].intrinsic == pytest.approx(36_610_000)
    assert out["quarter"].intrinsic == pytest.approx(18_305_000)


def test_display_unit():
    assert f.to_display(5, "rial") == 50 and f.to_display(5, "toman") == 5
