from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging() -> None:
    d = Path.home() / ".goldsignal"; d.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(d / "goldsignal.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[h], format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> int:
    setup_logging()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from .services.controller import Controller
    from .storage.db import Database, default_db_path
    from .ui.main_window import MainWindow
    from .ui.theme import app_font

    app = QApplication(sys.argv)
    app.setApplicationName("GoldSignal"); app.setQuitOnLastWindowClosed(False)
    app.setLayoutDirection(Qt.RightToLeft); app.setFont(app_font(10))
    sys.excepthook = lambda t, v, tb: logging.getLogger("crash").error("uncaught", exc_info=(t, v, tb))
    ctl = Controller(Database(default_db_path()))
    w = MainWindow(ctl, start_minimized="--minimized" in sys.argv)
    if "--minimized" not in sys.argv:
        w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
