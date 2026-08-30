#!/usr/bin/env python3
"""Přesune Unreleased CHANGELOG do nové verze a aktualizuje __version__."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "src" / "elatec_uid_tool" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_LINE = re.compile(r'^__version__ = "(\d+\.\d+\.\d+)"$', re.MULTILINE)


def parse_version(text: str) -> tuple[int, int, int]:
    match = SEMVER.match(text)
    if not match:
        raise SystemExit(f"Neplatná verze: {text!r} (očekáváno MAJOR.MINOR.PATCH)")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def current_version() -> str:
    text = INIT.read_text(encoding="utf-8")
    match = VERSION_LINE.search(text)
    if not match:
        raise SystemExit("Nelze najít __version__ v __init__.py")
    return match.group(1)


def bump_init(new_version: str) -> None:
    text = INIT.read_text(encoding="utf-8")
    updated, count = VERSION_LINE.subn(f'__version__ = "{new_version}"', text, count=1)
    if count != 1:
        raise SystemExit("Aktualizace __version__ nebyla jednoznačná.")
    INIT.write_text(updated, encoding="utf-8")


def bump_changelog(new_version: str, today: str) -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    if f"## [{new_version}]" in text:
        raise SystemExit(f"CHANGELOG už obsahuje sekci [{new_version}].")
    if "## [Unreleased]" not in text:
        raise SystemExit("CHANGELOG neobsahuje sekci [Unreleased].")

    pattern = re.compile(
        r"## \[Unreleased\]\n(?P<body>.*?)(?=\n## \[)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise SystemExit("Nelze najít tělo sekce [Unreleased].")

    body = match.group("body").strip("\n")
    if not body.strip():
        body = "### Changed\n\n- Dokumentace a release balíček.\n"

    replacement = (
        f"## [Unreleased]\n\n"
        f"## [{new_version}] - {today}\n\n"
        f"{body}\n\n"
    )
    updated = pattern.sub(replacement, text, count=1)
    CHANGELOG.write_text(updated, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release helper pro elaUIDtool")
    parser.add_argument("version", help="Nová verze MAJOR.MINOR.PATCH")
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="Datum v CHANGELOG (YYYY-MM-DD)",
    )
    args = parser.parse_args(argv)

    new = args.version
    parse_version(new)
    old = current_version()
    if parse_version(new) <= parse_version(old):
        raise SystemExit(f"Nová verze {new} musí být vyšší než aktuální {old}.")

    bump_init(new)
    bump_changelog(new, args.date)
    print(f"OK: {old} -> {new}")
    print("Další kroky: testy, commit, git tag -a v{0} -m \"...\", push".format(new))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
