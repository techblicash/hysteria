from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from proxy_gui_client.gui.main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    if window.should_start_minimized():
        window.hide_to_tray()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
