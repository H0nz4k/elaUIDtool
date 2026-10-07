#!/usr/bin/env python3
"""C testy stavu a volitelně adaptéru s reálnými SDK hlavičkami (bez čtečky)."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "elatec_uid_tool" / "fw_templates" / "registration"
TESTS = ROOT / "tests" / "firmware"
sys.path.insert(0, str(ROOT / "src"))

from elatec_uid_tool.registration import RegistrationConfig, registration_sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--devpack")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="d2r-tests-") as directory:
        work = Path(directory)
        core = work / "core.exe"
        flags = [args.cc, "-std=c99", "-Wall", "-Wextra", "-Werror", f"-I{SOURCE}"]
        subprocess.run(flags + ["-pedantic", str(SOURCE / "dual_core.c"),
                               str(TESTS / "test_dual_core.c"), "-o", str(core)], check=True)
        subprocess.run([str(core)], check=True)
        if args.devpack:
            flags += ["-Wno-builtin-declaration-mismatch", "-DMAKEFIRMWARE",
                      f"-I{Path(args.devpack).resolve() / 'Tools' / 'sys'}"]
            adapter = work / "adapter.o"
            subprocess.run(flags + ["-Dmain=d2_app_main", "-c", str(SOURCE / "App_D2R_DualRegistration.c"),
                                    "-o", str(adapter)], check=True)
            test = work / "adapter.exe"
            subprocess.run(flags + [str(adapter), str(SOURCE / "dual_core.c"),
                                    str(SOURCE / "registration_signal.c"), str(SOURCE / "registration_trace.c"),
                                    str(TESTS / "test_sdk_adapter.c"), "-o", str(test)], check=True)
            for scenario in ("repeat", "extended", "dropout", "missing-hf", "missing-lf", "oversize", "zero",
                             "collision", "no-band", "trace", "host-down", "lf-once", "slow-search", "paused"):
                subprocess.run([str(test), scenario], check=True)
            trace = work / "trace.exe"
            subprocess.run(flags + [str(SOURCE / "dual_core.c"), str(SOURCE / "registration_trace.c"),
                                    str(TESTS / "test_registration_trace.c"), "-o", str(trace)], check=True)
            subprocess.run([str(trace)], check=True)
            for hf, lf in (("DEC", "HEX"), ("HEX", "DEC"), ("DEC", "DEC")):
                folder = work / f"HF-{hf}_LF-{lf}"
                folder.mkdir()
                for name, content in registration_sources(RegistrationConfig(hf, lf)).items():
                    (folder / name).write_text(content, encoding="utf-8")
                # Quoted includes must resolve the newly generated per-band config.
                profile_flags = [flag for flag in flags if flag != f"-I{SOURCE}"] + [f"-I{folder}"]
                profile_adapter = folder / "adapter.o"
                subprocess.run(profile_flags + ["-Dmain=d2_app_main", "-c", str(folder / "App_D2R_DualRegistration.c"),
                                                "-o", str(profile_adapter)], check=True)
                profile_test = folder / "adapter.exe"
                subprocess.run(profile_flags + [str(profile_adapter), str(folder / "dual_core.c"),
                                               str(folder / "registration_signal.c"), str(folder / "registration_trace.c"),
                                               str(TESTS / "test_sdk_adapter.c"), "-o", str(profile_test)], check=True)
                print(f"SDK format profile: HF {hf}, LF {lf}", flush=True)
                for scenario in ("repeat", "extended", "missing-hf", "missing-lf", "trace", "slow-search"):
                    subprocess.run([str(profile_test), scenario], check=True)


if __name__ == "__main__":
    main()
