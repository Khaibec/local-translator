"""Entrypoint for running GUI directly via `python -m src.gui`."""

import sys
from src.gui import run_gui

if __name__ == "__main__":
    sys.exit(run_gui())
