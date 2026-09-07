"""GUI package for Local Japanese -> Vietnamese Translator."""

import sys
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.gui.main_window import MainWindow
from src.gui.dialogs import SettingsDialog, GlossaryDialog, PromptDialog
from src.gui.widgets import (
    DropAreaWidget,
    ChapterTableWidget,
    RecentJobsWidget,
    LogViewerWidget,
)
from src.gui.workers import (
    CrawlWorker,
    NovelTranslationWorker,
    SingleDocTranslationWorker,
)


def run_gui(argv: Optional[list] = None) -> int:
    """Launch the PySide6 Desktop GUI application."""
    # Ensure UTF-8 console output
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = sys.argv if argv is None else argv

    app = QApplication.instance()
    if app is None:
        app = QApplication(args)

    # Use Fusion style for consistent modern appearance across Windows versions
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    return app.exec()


__all__ = [
    "MainWindow",
    "SettingsDialog",
    "GlossaryDialog",
    "PromptDialog",
    "DropAreaWidget",
    "ChapterTableWidget",
    "RecentJobsWidget",
    "LogViewerWidget",
    "CrawlWorker",
    "NovelTranslationWorker",
    "SingleDocTranslationWorker",
    "run_gui",
]
