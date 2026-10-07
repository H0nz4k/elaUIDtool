#!/usr/bin/env python3
"""Compare the actual portable C firmware converter with preview and analyzer fixtures."""
from __future__ import annotations
import argparse
import ctypes
from dataclasses import replace
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from elatec_uid_tool.analyzer import analyze_uid
from elatec_uid_tool.builder import DataRule, ENCODINGS, FORMATS, RULE_PRESETS, apply_rule


class CRule(ctypes.Structure):
    _fields_ = [(key, ctypes.c_int) for key in ("reverse_bits", "reverse_bytes", "first_bit", "bit_count", "encoding",
                 "radix", "length_mode", "length", "lowercase", "strip_zeros", "append_00")] + [
                 (key, ctypes.c_char_p) for key in ("and_mask", "xor_mask", "separator", "prefix", "suffix")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--devpack", help="Volitelně ověří SDK adaptér registrace BLD se skutečnými hlavičkami")
    args = parser.parse_args()
    source = ROOT / "src" / "elatec_uid_tool" / "fw_templates" / "builder"
    with tempfile.TemporaryDirectory(prefix="bld-tests-") as directory:
        library = Path(directory) / "converter.so"
        subprocess.run([args.cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fPIC", "-shared",
                        str(source / "data_rule.c"), "-o", str(library)], check=True)
        convert = ctypes.CDLL(str(library)).bld_convert
        convert.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.POINTER(CRule), ctypes.c_char_p, ctypes.c_int]
        convert.restype = ctypes.c_int
        checks = 0

        def check(raw: str, bits: int, rule: DataRule) -> None:
            nonlocal checks
            data = (ctypes.c_uint8 * len(bytes.fromhex(raw)))(*bytes.fromhex(raw))
            numeric = [int(rule.reverse_bits), int(rule.reverse_bytes), rule.first_bit, rule.bit_count,
                       ENCODINGS.index(rule.encoding), FORMATS[rule.output_format],
                       ("auto", "minimum", "exact").index(rule.length_mode), rule.length,
                       int(rule.lowercase), int(rule.strip_zeros), int(rule.append_00)]
            strings = [s.encode("ascii") for s in (rule.and_mask, rule.xor_mask, rule.byte_separator, rule.prefix, rule.suffix)]
            c_rule = CRule(*numeric, *strings)
            output = ctypes.create_string_buffer(512)
            try:
                expected = apply_rule(raw, rule, bits)[2]
            except ValueError:
                expected = None
            accepted = convert(data, bits, ctypes.byref(c_rule), output, len(output))
            actual = output.value.decode("ascii") if accepted else None
            assert actual == expected, (raw, bits, rule, actual, expected)
            if accepted:
                too_small = ctypes.create_string_buffer(max(1, len(output.value)))
                assert not convert(data, bits, ctypes.byref(c_rule), too_small, len(too_small)), "Must refuse a short destination"
            checks += 1

        for raw, expected, fmt in (("AE1C56CF", "08607342", "decimal"), ("AE1C56CF", "867342", "decimal"),
                                   ("3D00C000D4", "12583124", "decimal"), ("813F9A04", "049A3F81", "hexadecimal")):
            _, matches = analyze_uid(raw, len(raw) * 4, expected, fmt, 100)
            for match in matches:
                check(raw, len(raw) * 4, DataRule.from_match(match))
        for rule in RULE_PRESETS.values():
            for raw in ("0000010203", "813F9A04", "0102030405", "FFFFFFFFFFFFFFFF", "AA561CAE"):
                check(raw, len(raw) * 4, rule)
        for encoding in ENCODINGS:
            for count in (8, 16, 24, 26, 32, 64, 80, 256):
                raw = "AA" * ((count + 7) // 8)
                check(raw, count, DataRule(encoding=encoding, output_format="DEC"))
        for fmt in FORMATS:
            for raw in ("00", "01", "FFFFFFFFFFFFFFFF", "FF" * 32, "54455354"):
                check(raw, len(raw) * 4, DataRule(output_format=fmt))
        randomizer = random.Random(20261007)
        for _ in range(600):
            size = randomizer.randint(1, 32)
            raw = randomizer.randbytes(size).hex()
            bits = randomizer.randint(1, size * 8)
            first = randomizer.randrange(bits)
            count = randomizer.randint(1, bits - first)
            fmt = randomizer.choice(tuple(FORMATS))
            rule = DataRule(reverse_bits=bool(randomizer.getrandbits(1)), reverse_bytes=bool(randomizer.getrandbits(1)),
                            first_bit=first, bit_count=count, output_format=fmt,
                            length_mode=randomizer.choice(("auto", "minimum", "exact")), length=randomizer.randint(1, 64),
                            strip_zeros=bool(randomizer.getrandbits(1)), append_00=bool(randomizer.getrandbits(1)),
                            lowercase=bool(randomizer.getrandbits(1)), prefix="ID:\t", suffix=";",
                            and_mask=f"{randomizer.getrandbits(count):X}", xor_mask=f"{randomizer.getrandbits(count):X}",
                            byte_separator=":" if fmt == "HEX" and randomizer.getrandbits(1) else "")
            check(raw, bits, rule)
        print(f"Builder C converter: {checks} preview/analyzer cases and short-buffer checks passed.")
        if args.devpack:
            from elatec_uid_tool.builder import BuilderProject, Feedback
            from elatec_uid_tool.builder_firmware import builder_sources
            for scenario in ("held", "wrong", "host-down", "repeat", "reject"):
                folder = Path(directory) / ("uid-" + scenario)
                folder.mkdir()
                rule = DataRule(reverse_bytes=True, length_mode="exact" if scenario == "reject" else "auto",
                                length=2 if scenario == "reject" else 0)
                project = BuilderProject(hf=rule, repeat_ms=100 if scenario == "repeat" else 0,
                    success=Feedback(volume=42, frequency=3500, beeps=3, flashes=2, on_ms=25, off_ms=40),
                    error=Feedback(volume=77, frequency=1500, led="red"))
                for name, text in builder_sources(project).items():
                    (folder / name).write_text(text, encoding="utf-8")
                flags = [args.cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-builtin-declaration-mismatch",
                         "-DMAKEFIRMWARE", f"-I{folder}", f"-I{Path(args.devpack).resolve() / 'Tools' / 'sys'}"]
                adapter, test = folder / "adapter.o", folder / "test.exe"
                subprocess.run(flags + ["-Dmain=bld_uid_main", "-c", str(folder / "App_BLD_UID.c"), "-o", str(adapter)], check=True)
                subprocess.run(flags + [str(adapter), str(folder / "data_rule.c"), str(folder / "feedback.c"),
                    str(ROOT / "tests" / "firmware" / "test_builder_sdk.c"), "-o", str(test)], check=True)
                subprocess.run([str(test), scenario], check=True)
            for hf, lf in (("HEX", "HEX"), ("DEC", "HEX"), ("HEX", "DEC"), ("DEC", "DEC")):
                folder = Path(directory) / f"HF-{hf}_LF-{lf}"
                folder.mkdir()
                project = BuilderProject(mode="registration", hf=DataRule(output_format=hf), lf=DataRule(output_format=lf))
                for name, text in builder_sources(project).items():
                    (folder / name).write_text(text, encoding="utf-8")
                flags = [args.cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-builtin-declaration-mismatch",
                         "-DMAKEFIRMWARE", f"-I{folder}", f"-I{Path(args.devpack).resolve() / 'Tools' / 'sys'}"]
                adapter = folder / "adapter.o"
                subprocess.run(flags + ["-Dmain=d2_app_main", "-c", str(folder / "App_D2R_DualRegistration.c"), "-o", str(adapter)], check=True)
                test = folder / "adapter.exe"
                subprocess.run(flags + [str(adapter)] + [str(folder / name) for name in
                    ("dual_core.c", "data_rule.c", "feedback.c", "registration_signal.c", "registration_trace.c")] +
                    [str(ROOT / "tests" / "firmware" / "test_sdk_adapter.c"), "-o", str(test)], check=True)
                print(f"Builder SDK profile: HF {hf}, LF {lf}", flush=True)
                for scenario in ("repeat", "missing-hf", "missing-lf", "dropout", "slow-search"):
                    subprocess.run([str(test), scenario], check=True)


if __name__ == "__main__":
    main()
