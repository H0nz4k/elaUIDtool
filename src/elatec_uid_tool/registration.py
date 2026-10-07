"""Konfigurace a export automatické registrace jedné HF/LF karty."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files as resource_files
from pathlib import Path
import re

from .fw_export import DEFAULT_DEVPACK, EXPORT_DIR
from .reader_models import DEFAULT_READER_MODEL, get_reader_model
from .twn4_build import AppBuildResult, ToolchainOptions, build_user_app


@dataclass(frozen=True)
class RegistrationConfig:
    hf_format: str = "HEX"
    lf_format: str = "HEX"
    other_search_ms: int = 2000

    def __post_init__(self) -> None:
        for name in ("hf_format", "lf_format"):
            value = getattr(self, name)
            if not isinstance(value, str) or value.upper() not in ("HEX", "DEC"):
                raise ValueError("Formát HF i LF musí být HEX nebo DEC.")
            object.__setattr__(self, name, value.upper())
        if isinstance(self.other_search_ms, bool) or not isinstance(self.other_search_ms, int) or not 500 <= self.other_search_ms <= 10000:
            raise ValueError("Hledání druhé technologie musí trvat 500 až 10000 ms.")


def format_uid(uid_hex: str, output_format: str) -> str:
    """Náhled stejného plného UID jako firmware (bez doplňování na 16 znaků)."""
    uid = uid_hex.strip().upper()
    if not re.fullmatch(r"[0-9A-F]{1,16}", uid) or int(uid, 16) == 0:
        raise ValueError("UID musí obsahovat 1–16 HEX číslic a nesmí být nulové.")
    if output_format.upper() == "HEX":
        return uid
    if output_format.upper() == "DEC":
        return str(int(uid, 16))
    raise ValueError("Formát musí být HEX nebo DEC.")


def registration_sources(config: RegistrationConfig) -> dict[str, str]:
    folder = resource_files("elatec_uid_tool").joinpath("fw_templates", "registration")
    sources = {item.name: item.read_text(encoding="utf-8") for item in folder.iterdir()
               if item.name.endswith((".c", ".h"))}
    header = sources["dual_config.h"]
    for name, value in (("D2_HF_RADIX", 16 if config.hf_format == "HEX" else 10),
                        ("D2_LF_RADIX", 16 if config.lf_format == "HEX" else 10),
                        ("D2_OTHER_SEARCH_MS", f"{config.other_search_ms}u")):
        header = re.sub(rf"^#define {name} .+$", f"#define {name} {value}", header, flags=re.MULTILINE)
    sources["dual_config.h"] = header
    return sources


def build_registration_firmware(
    config: RegistrationConfig | None = None, *,
    reader_model: str = DEFAULT_READER_MODEL, devpack: Path | None = None,
    output_dir: Path | None = None, toolchain: ToolchainOptions | None = None,
) -> AppBuildResult:
    config = config or RegistrationConfig()
    model = get_reader_model(reader_model)
    name = f"TWN4_xCx520_D2R015_CDC_{model.key}_HF-{config.hf_format}_LF-{config.lf_format}"
    out = (output_dir or EXPORT_DIR / "registration") / model.key / f"HF-{config.hf_format}_LF-{config.lf_format}"
    return build_user_app(
        pack=devpack or DEFAULT_DEVPACK, output_dir=out, name=name,
        app_chars="D2R", app_version=0x0015, files=registration_sources(config),
        sources=["App_D2R_DualRegistration.c", "dual_core.c", "registration_signal.c", "registration_trace.c"],
        options=toolchain, metadata={
            "mode": "registration", "channel": "USB CDC", "reader_model": model.name,
            "hf_format": config.hf_format, "lf_format": config.lf_format,
            "other_search_ms": config.other_search_ms, "output_order": ["HF", "LF"],
            "uid_max_bits": 64, "uid_padding": False, "single_second_frame": "empty CR",
        },
    )
