"""اجرای خودکار با ویندوز (HKCU\\...\\Run). روی سیستم‌های غیر ویندوز بی‌اثر است."""
from __future__ import annotations

import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "GoldSignalIran"


def set_autostart(enabled: bool, command: str | None = None) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    if command is None:
        command = (f'"{sys.executable}" --minimized' if getattr(sys, "frozen", False)
                   else f'"{sys.executable}" -m goldsignal --minimized')
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass
    return True
