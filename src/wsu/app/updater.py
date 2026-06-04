"""Entry point for the Windows Software Updater GUI."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from wsu.core.logging_config import configure_logging
from wsu.ui.main_window import MainWindow
from wsu.ui.theme import apply_dark_theme


def main() -> None:
    """Create the application, apply the theme, and run the event loop."""
    configure_logging()
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
