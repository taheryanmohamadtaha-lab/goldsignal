import pytest
import requests

from goldsignal.providers.base import Provider, ProviderError, require_https
from goldsignal.providers.csv_import import import_csv
from goldsignal.providers.generic_json import GenericJsonProvider, dig, parse_number
from goldsignal.providers.manager import ProviderManager
from goldsignal.providers.manual import ManualProvider
from goldsignal.providers.stooq import StooqOunceProvider
from goldsignal.services import alerts
from goldsignal.analysis.formulas import compute_bubbles
from goldsignal.storage.db import Database


class Fake(Provider):
    def __init__(self, name, data=None, err=None):
        self.name, self.data, self.err = name, data, err

    def fetch(self):
        if self.err:
            raise ProviderError(self.err)
        return self.data


class Resp:
    def __init__(self, payload=None, text="", status=200):
        self.payload, self.text, self.status = payload, text, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError("bad")

    def json(self):
        if self.payload is None:
            raise ValueError("no json")
        return self.payload


class Sess:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc = resp, exc

    def get(self, *a, **k):
        if self.exc:
            raise self.exc
        return self.resp


def test_https_only():
    with pytest.raises(ProviderError):
        require_https("http://x.com")
    assert require_https("https://x.com")


def test_dig_and_numbers():
    assert dig({"a": [{"b": 5}]}, "a.0.b") == 5
    assert parse_number("۱۲۳٬۴۵۶") == 123456


def test_generic_json_mapping_scale_and_partial():
    cfg = {"name": "j", "url": "https://x.com", "mapping": {"emami": "d.e", "usd": "d.missing"}, "scale": {"emami": 0.1}}
    p = GenericJsonProvider(cfg, session=Sess(Resp({"d": {"e": "1,000"}})))
    assert p.fetch() == {"emami": 100.0}


def test_generic_json_failures():
    cfg = {"name": "j", "url": "https://x.com", "mapping": {"emami": "d.e"}}
    for s in (Sess(exc=requests.ConnectionError("down")), Sess(Resp(None)), Sess(Resp({"x": 1})), Sess(Resp({}, status=500))):
        with pytest.raises(ProviderError):
            GenericJsonProvider(cfg, session=s).fetch()


def test_stooq_parse():
    csv = "Symbol,Date,Time,Open,High,Low,Close,Volume\nXAUUSD,2026-01-01,00:00:00,1,2,3,2650.5,0\n"
    assert StooqOunceProvider(session=Sess(Resp(text=csv))).fetch() == {"ounce": 2650.5}
    with pytest.raises(ProviderError):
        StooqOunceProvider(session=Sess(Resp(text="garbage"))).fetch()


def test_manager_fallback_merge_and_cache():
    db = Database()
    m = ProviderManager([Fake("a", err="boom"), Fake("b", {"usd": 100.0, "bad": -5}), Fake("c", {"usd": 1.0, "ounce": 2000.0})], db)
    r = m.refresh()
    assert r.prices["usd"] == 100.0 and r.prices["ounce"] == 2000.0 and "bad" not in r.prices
    assert r.errors == {"a": "boom"} and not r.from_cache
    r2 = ProviderManager([Fake("a", err="offline")], db).refresh()   # قطع اینترنت
    assert r2.from_cache and r2.prices["usd"] == 100.0 and r2.ts > 0


def test_manager_unexpected_exception_does_not_crash():
    class Boom(Provider):
        name = "boom"

        def fetch(self):
            raise RuntimeError("x")
    assert ProviderManager([Boom()], Database()).refresh().prices == {}


def test_manual_provider_roundtrip():
    db = Database(); mp = ManualProvider(db)
    with pytest.raises(ProviderError):
        mp.fetch()
    mp.set_prices({"emami": 5e7, "usd": -1})
    assert mp.fetch() == {"emami": 5e7}


def test_csv_import_wide_long_and_bad_rows(tmp_path):
    db = Database()
    w = tmp_path / "w.csv"; w.write_text("date,emami,usd\n2025-01-01 10:00,50000000,90000\nbad,x,y\n2025-01-02,51000000,\n", encoding="utf-8")
    ok, bad = import_csv(db, w)
    assert ok == 2 and bad == 1 and len(db.history("emami")) == 2 and len(db.history("usd")) == 1
    l = tmp_path / "l.csv"; l.write_text("ts,key,value\n1700000000,ounce,2000\n1700000100,ounce,oops\n", encoding="utf-8")
    assert import_csv(db, l) == (1, 1)
    n = tmp_path / "n.csv"; n.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        import_csv(db, n)


def test_db_settings_signals_outcomes():
    from goldsignal.models import Signal
    db = Database()
    db.set_setting("k", {"a": 1}); assert db.get_setting("k") == {"a": 1} and db.get_setting("zz", 7) == 7
    db.add_signal(Signal(1, "emami", "1d", "buy", 100, 90, 120, 2, 70, ["r"]))
    db.add_signal(Signal(2, "half", "1d", "buy", 100, 90, 120, 2, 70, ["r"]))
    assert db.update_signal_outcomes({"emami": 125, "half": 85}) == 2
    assert db.success_rate() == (1, 1, 50.0)


def test_alerts_fire_once_and_rearm():
    db = Database(); db.add_alert("price_above", "emami", 100); db.add_alert("bubble_above", "emami", 5)
    pr = {"emami": 150.0, "ounce": 3110.35, "usd": 0.1}   # ارزش ذاتی ≈ ۷۳٫۲
    f1 = alerts.evaluate(db, pr, compute_bubbles(pr))
    assert len(f1) == 2 and alerts.evaluate(db, pr, compute_bubbles(pr)) == []
    pr2 = {**pr, "emami": 50.0}; alerts.evaluate(db, pr2, compute_bubbles(pr2))
    assert len(alerts.evaluate(db, pr, compute_bubbles(pr))) == 2


def test_new_signal_alert():
    from goldsignal.models import Signal
    db = Database(); db.add_alert("new_signal", "*", 0)
    s = Signal(1, "emami", "1d", "buy", 1, 0.5, 2, 2, 80, [])
    assert alerts.evaluate(db, {}, {}, [s]) and not alerts.evaluate(db, {}, {}, [])
