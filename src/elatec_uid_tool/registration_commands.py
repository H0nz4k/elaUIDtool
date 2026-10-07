"""Příkazy pro registraci HF/LF a její firmware."""
from dataclasses import asdict
import json
from pathlib import Path

from .registration import RegistrationConfig, build_registration_firmware
from .registration_client import capture_registration
from .twn4_build import ToolchainOptions


def toolchain_from_args(args) -> ToolchainOptions:
    return ToolchainOptions(getattr(args, "gcc", None), getattr(args, "objcopy", None),
                            getattr(args, "makeapp_runtime", None))


def command_export_registration(args) -> int:
    result = build_registration_firmware(
        RegistrationConfig(args.hf_format, args.lf_format, args.other_search_ms),
        reader_model=args.reader_model, devpack=Path(args.devpack),
        output_dir=Path(args.output_dir) if args.output_dir else None,
        toolchain=toolchain_from_args(args),
    )
    print(f"BIX: {result.bix_path}")
    print(f"Konfigurace a kontrolní součet: {result.manifest_path}")
    print("Nahraj BIX přes AppBlaster → Program Firmware Image.")
    return 0


def command_test_registration(args) -> int:
    print("Zavři Jídelnu a AppBlaster. Karta musí být mimo čtečku.")
    result = capture_registration(args.port, wait=args.wait, on_progress=print)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0
