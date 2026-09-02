#!/usr/bin/env python3
"""Vytvoří releases/elaUIDtool-X.Y.Z/ se vším potřebným pro kolegy (bez .venv a DevPacku)."""

from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "src" / "elatec_uid_tool" / "__init__.py"

INCLUDE_DIRS = (
    "src",
    "gui",
    "docs",
    "tests",
    "scripts",
    "FW_elatec",
)

INCLUDE_FILES = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "requirements.txt",
    "elaUIDtool.bat",
    "install_windows.bat",
    "build_fw.bat",
    "prepare_reader.bat",
    "run_interactive.bat",
    "run_tests.bat",
    "run_reference_test.bat",
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "elafiles",
    "files520",
    "results",
    "data",
    "dist",
    "releases",
    "out",
    "out_test",
    ".egg-info",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".bix",
    ".elf",
    ".hex",
    ".lst",
    ".map",
    ".zip",
    ".log",
}


def current_version() -> str:
    text = INIT.read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "(\d+\.\d+\.\d+)"$', text, re.MULTILINE)
    if not match:
        raise SystemExit("Nelze najít __version__")
    return match.group(1)


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if path.name == "user_settings.json":
        return True
    return False


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for item in src.rglob("*"):
        if should_skip(item):
            continue
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def write_start_here(dest: Path, version: str) -> None:
    dest.write_text(
        f"""# START HERE – elaUIDtool {version}

## 1. Instalace

1. Nainstaluj Python 3.10+ (Add to PATH).
2. Dvojklik:

```text
elaUIDtool.bat
```

## 2. Spuštění GUI

```text
gui\\run_gui.bat
```

Otevře se Windows okno.

## 3. Porovnání kódů (bez čipu)

1. Záložka **Porovnání**
2. Kód z čtečky = RAW hex (např. E9B20DFF)
3. Kód z databáze (např. 01345801)
4. **Porovnat a najít pravidlo**
5. **Vytvořit FW (CDC)**

## 4. DevPack (jen pro tvorbu FW)

Zkopíruj TWN4DevPack520 do složky `elafiles\\` vedle tohoto toolu,
nebo v GUI → Nastavení zadej cestu.

Potřebuješ mimo jiné:

```text
elafiles\\Tools\\makeapp.exe
elafiles\\Apps\\App_STD207_Standard_temp.c
elafiles\\Apps\\TWN4_CCx520.bix
elafiles\\Apps\\TWN4_MCx520.bix
elafiles\\Apps\\TWN4_NCx520.bix
```

## 5. Nahrání FW

AppBlaster → Program Firmware Image →

```text
FW_elatec\\export\\out\\TWN4_xCx520_EXP_CDC.bix
```

→ Program Image.

Více v README.md a docs\\NAVOD.md.
""",
        encoding="utf-8",
        newline="\n",
    )


def write_elafiles_readme(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "README.txt").write_text(
        """Sem zkopíruj obsah ELATEC TWN4DevPack520 (nebo nastav cestu v GUI).

Očekávaná struktura:
  Tools\\makeapp.exe
  Tools\\Yagarto-20110328\\...
  Apps\\App_STD207_Standard_temp.c
  Apps\\TWN4_CCx520.bix
  Apps\\TWN4_MCx520.bix
  Apps\\TWN4_NCx520.bix
  Firmware\\TWN4_xCx520_STD207_Multi_CDC_Standard.bix

DevPack je proprietární software ELATEC – nedistribuuj ho spolu s tímto tooluem
bez licence.
""",
        encoding="utf-8",
        newline="\n",
    )


def make_zip(folder: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in folder.rglob("*"):
            if file.is_file():
                zf.write(file, arcname=str(file.relative_to(folder.parent)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Balíček releases/elaUIDtool-X.Y.Z")
    parser.add_argument("--version", help="Override verze (default z __init__.py)")
    parser.add_argument("--no-zip", action="store_true", help="Nevytvářej ZIP")
    args = parser.parse_args(argv)

    version = args.version or current_version()
    out_root = ROOT / "releases"
    out_dir = out_root / f"elaUIDtool-{version}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    for name in INCLUDE_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, out_dir / name)

    for name in INCLUDE_DIRS:
        copy_tree(ROOT / name, out_dir / name)

    # GUI requirements
    gui_req = ROOT / "gui" / "requirements.txt"
    if gui_req.exists():
        (out_dir / "gui").mkdir(exist_ok=True)
        shutil.copy2(gui_req, out_dir / "gui" / "requirements.txt")

    write_start_here(out_dir / "START_HERE.md", version)
    write_elafiles_readme(out_dir / "elafiles")
    (out_dir / "VERSION").write_text(version + "\n", encoding="utf-8")

    zip_path = out_root / f"elaUIDtool-{version}.zip"
    if not args.no_zip:
        make_zip(out_dir, zip_path)

    print(f"OK: {out_dir}")
    if not args.no_zip:
        print(f"ZIP: {zip_path} ({zip_path.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
