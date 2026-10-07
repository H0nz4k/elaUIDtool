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
    from elatec_uid_tool.twn4_build import validate_devpack as validate

    return validate(path)


def get_registration_settings() -> dict:
    from elatec_uid_tool.reader_models import DEFAULT_READER_MODEL, get_reader_model
    from elatec_uid_tool.registration import RegistrationConfig

    raw = load_settings().get("registration") or {}
    try:
        config = RegistrationConfig(raw.get("hf_format", "HEX"), raw.get("lf_format", "HEX"),
                                    raw.get("other_search_ms", 2000))
        model = get_reader_model(raw.get("reader_model", DEFAULT_READER_MODEL))
    except (ValueError, TypeError, AttributeError):
        config = RegistrationConfig()
        model = get_reader_model(DEFAULT_READER_MODEL)
    return {"reader_model": model.key, "hf_format": config.hf_format,
            "lf_format": config.lf_format, "other_search_ms": config.other_search_ms}


def set_registration_settings(model: str, hf_format: str, lf_format: str, other_search_ms: int) -> dict:
    from elatec_uid_tool.reader_models import get_reader_model
    from elatec_uid_tool.registration import RegistrationConfig

    config = RegistrationConfig(hf_format, lf_format, other_search_ms)
    value = {"reader_model": get_reader_model(model).key, "hf_format": config.hf_format,
             "lf_format": config.lf_format, "other_search_ms": config.other_search_ms}
    data = load_settings()
    data["registration"] = value
    save_settings(data)
    return value
