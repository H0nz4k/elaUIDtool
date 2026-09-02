"""Cesty aplikace – fungují ve vývoji i ve frozen .exe (PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Adresář vedle .exe (writable) nebo kořen repozitáře."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    """Read-only data z PyInstaller (_MEIPASS) nebo kořen repo."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent
