# ELATEC – kód identifikace

Terminálový a desktopový nástroj pro analýzu UID z čteček **ELATEC TWN4** a nalezení konfigurace AppBlasteru (nebo vlastního firmware), která reprodukuje identifikátor uložený v existující databázi.

Aktuální verze: **0.3.1**  
Repozitář: [https://github.com/H0nz4k/elaUIDtool](https://github.com/H0nz4k/elaUIDtool)

**Kompletní návod:** [docs/NAVOD.md](docs/NAVOD.md)

## Rychlý start

```text
1. elaUIDtool.bat              ← instalace + CLI menu
2. gui\run_gui.bat             ← desktopová aplikace
3. build_fw.bat                ← sestaví .bix (Wiegand 3+5, vyžaduje elafiles/)
```

Nahrání `.bix` v AppBlasteru: **Program Firmware Image → Select Image → Program Image**.

## Ověřené referenční případy

### EM4102 (LF) – plain Decimal

```text
RAW UID:          3D00C000D4
RAW délka:        40 bitů
DB identifikátor: 12583124
```

```text
Output Bits:        Some Bits
First Bit:          8
Number of Bits:     32
Output Format:      Decimal
Reverse Bit/Byte:   No / No
Encoding:           plain
```

### MIFARE (HF) – Wiegand 3+5 (Jarov / stůl)

```text
RAW UID:          E9B20DFF  →  DB 01345801   (facility 13, card 45801)
RAW UID:          AE1C56CF  →  DB 08607342   (facility 86, card 7342)
```

```text
Reverse Byte Order: Yes
First Bit:          8
Number of Bits:     24
Encoding:           wiegand_3_5  (facility×100000 + card → FFFCCCCC)
```

Karty `03921353` / `12607299` mají stejné pravidlo, ale zatím nejsou fyzicky ověřené v toolu.

### HID iCLASS / PAC (historický FW)

V `FW_elatec/FIN_kraceni_kodu_PAC_ID_bez_0/` je ověřený User App (H10301 + digit-concat / strip nul).  
Stejné převody jsou v analyzátoru: `facility_card_concat`, `h10301_*`, `wiegand_3_5_strip`.

## Funkce

- komunikace s TWN4 přes Simple Protocol (ASCII),
- verze firmware, typ zařízení, LF/HF masky,
- načtení `TagType`, bitové délky a RAW UID,
- hledání bitového okna + reverse bit/byte order,
- strukturované encodingy (Wiegand / PAC / H10301 / …),
- doporučení nastavení AppBlasteru,
- export JSON,
- sestavení flashovatelného `.bix` (`export-fw`, GUI, `build_fw.bat`),
- offline analýza, desktopové GUI.

## Podporované encodingy

| Encoding | Popis | Příklad |
|----------|--------|---------|
| `plain` | Decimal / Hex z bitového okna | `12583124` |
| `wiegand_3_5` | facility×100000+card | `08607342` |
| `wiegand_3_5_strip` | 3+5 bez vedoucích nul | `8607342` |
| `facility_card_concat` | PAC digit-concat | `867342` |
| `card_16` / `facility_8` | jen card / jen facility | `7342` / `86` |
| `scale_4` / `scale_6` | ×10⁴ / ×10⁶ | — |
| `h10301_*` | 26bit H10301 → 3+5 / concat / card / strip | — |

U strukturovaných encodingů **AppBlaster Decimal nestačí** → použij `build_fw.bat` / **Vytvořit FW**.

## Požadavky

- Windows 10/11, Python 3.10+
- TWN4 s firmware **PRS** (čtení karet)
- Pro build `.bix`: DevPack v `elafiles/` (gitignore)

Director drží COM port — před toolu ho zavři.

## Instalace a spuštění

```text
elaUIDtool.bat          # menu: test média, interactive, update reader, GUI, build FW
gui\run_gui.bat         # nativní okno
gui\run_gui_browser.bat # prohlížeč
build_fw.bat            # export .bix (výchozí E9B20DFF → 01345801)
run_tests.bat           # unit testy
```

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m pip install -r gui\requirements.txt
```

## CLI příklady

```powershell
.venv\Scripts\python -m elatec_uid_tool interactive
.venv\Scripts\python -m elatec_uid_tool ports
.venv\Scripts\python -m elatec_uid_tool reader-info --port COM13
.venv\Scripts\python -m elatec_uid_tool test-medium
.venv\Scripts\python -m elatec_uid_tool capture --expected 01345801
.venv\Scripts\python -m elatec_uid_tool analyze --raw E9B20DFF --bits 32 --expected 01345801
.venv\Scripts\python -m elatec_uid_tool export-fw --raw E9B20DFF --bits 32 --expected 01345801 --channel cdc --tag-type 0x80
.venv\Scripts\python -m elatec_uid_tool export-fw --from-json results\elatec-….json --channel both
```

Výstup FW: `FW_elatec/export/out/TWN4_xCx520_EXP_CDC.bix` (nebo `_UART`).

`build_fw.bat cdc AE1C56CF 08607342 0x80` — vlastní RAW / expected / tag-type.

## Struktura

```text
src/elatec_uid_tool/   # analyzer, encodings, fw_export, CLI
gui/                   # NiceGUI desktop
docs/NAVOD.md          # podrobný návod
build_fw.bat           # jedním klikem .bix
FW_elatec/
  wiegand35/           # ruční Wiegand 3+5 projekt
  FIN_kraceni_…/       # historický PAC FW (zdroj)
  export/out/          # generované .bix (gitignore)
tests/
scripts/release.py     # bump verze + CHANGELOG
```

## Testy a release

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python scripts\check_version.py
.venv\Scripts\python scripts\release.py 0.3.2
```

Postup tagu: [docs/VERSIONING.md](docs/VERSIONING.md).

## Dokumentace

- [Návod (NAVOD)](docs/NAVOD.md)
- [Architektura](docs/ARCHITECTURE.md)
- [Příprava čtečky](docs/READER_PREPARATION.md)
- [Verzování](docs/VERSIONING.md)
- [CHANGELOG](CHANGELOG.md)
- [GUI](gui/README.md)
- [Wiegand35 FW](FW_elatec/wiegand35/README.md)

## Aktuální omezení

- automatický export AppBlaster `.abp` zatím ne,
- živé `ICLASS_GetPACBits` přes Simple Protocol zatím ne,
- H10306/H10304/Corporate 1000 zatím ne (doplní se podle RAW+DB),
- DevPack a proprietární ELATEC PDF nejsou v repozitáři.
