"""ذخیرهٔ امن کلید API کاربر با keyring (Windows Credential Manager). بدون keyring: فقط در حافظهٔ همین اجرا."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)
_SERVICE = "GoldSignalIran"
_mem: dict[str, str] = {}


def set_secret(name: str, value: str) -> bool:
    """True یعنی روی مخزن امن سیستم ذخیره شد."""
    try:
        import keyring
        keyring.set_password(_SERVICE, name, value)
        return True
    except Exception as e:
        log.warning("keyring unavailable (%s); key kept in memory only", e)
        _mem[name] = value
        return False


def get_secret(name: str) -> str | None:
    try:
        import keyring
        v = keyring.get_password(_SERVICE, name)
        if v:
            return v
    except Exception:
        pass
    return _mem.get(name)
