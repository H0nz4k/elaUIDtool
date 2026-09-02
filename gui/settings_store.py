"""Uživatelské nastavení GUI (DevPack cesta atd.)."""

from __future__ import annotations

import json
from pathlib import Path

from app_paths import app_root

ROOT = app_root()
SETTINGS_PATH = ROOT / "user_settings.json"

DEFAULT_DEVPACK_CANDIDATES = (
    ROOT / "elafiles",
    Path(r"C:\Work\Elatec- reader\TWN4DevPack520"),
)


def default_devpack_path() -> Path:
    for path in DEFAULT_DEVPACK_CANDIDATES:
        if (path / "Tools" / "makeapp.exe").exists():
            return path.resolve()
    return (ROOT / "elafiles").resolve()


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {"devpack_path": str(default_devpack_path())}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("devpack_path", str(default_devpack_path()))
    return data


def save_settings(data: dict) -> Path:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return SETTINGS_PATH


def get_devpack_path() -> Path:
    raw = str(load_settings().get("devpack_path") or "").strip()
    path = Path(raw).expanduser() if raw else default_devpack_path()
    return path.resolve()


def set_devpack_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    data = load_settings()
    data["devpack_path"] = str(resolved)
    save_settings(data)
    return resolved


def validate_devpack(path: Path) -> list[str]:
    """Vrátí seznam chybějících položek (prázdné = OK)."""
    missing: list[str] = []
    checks = [
        ("Tools/makeapp.exe", path / "Tools" / "makeapp.exe"),
        (
            "Tools/Yagarto-20110328/bin/arm-none-eabi-gcc.exe",
            path / "Tools" / "Yagarto-20110328" / "bin" / "arm-none-eabi-gcc.exe",
        ),
        ("Tools/sys/libapp.a", path / "Tools" / "sys" / "libapp.a"),
        ("Apps/App_STD207_Standard_temp.c", path / "Apps" / "App_STD207_Standard_temp.c"),
        ("Apps/TWN4_CCx520.bix", path / "Apps" / "TWN4_CCx520.bix"),
        ("Apps/TWN4_MCx520.bix", path / "Apps" / "TWN4_MCx520.bix"),
        ("Apps/TWN4_NCx520.bix", path / "Apps" / "TWN4_NCx520.bix"),
    ]
    for label, item in checks:
        if not item.exists():
            missing.append(label)
    return missing
