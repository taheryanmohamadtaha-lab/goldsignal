from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    """اجرای کار سنگین (شبکه/محاسبه) در رشتهٔ پس‌زمینه؛ نتیجه با سیگنال به UI برمی‌گردد."""
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn, self.sig = fn, _Sig()

    def run(self) -> None:
        try:
            self.sig.done.emit(self.fn())
        except Exception:
            self.sig.failed.emit(traceback.format_exc())
