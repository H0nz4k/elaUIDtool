# ELATEC – kód identifikace

Terminálový a desktopový nástroj pro analýzu UID z čteček **ELATEC TWN4** a nalezení konfigurace AppBlasteru (nebo vlastního firmware), která reprodukuje identifikátor uložený v existující databázi.

Aktuální verze: **0.3.0**  
Repozitář: [https://github.com/H0nz4k/elaUIDtool](https://github.com/H0nz4k/elaUIDtool)

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
Length:             Automatic
Reverse Bit Order:  No
Reverse Byte Order: No
Encoding:           plain
```

### MIFARE (HF) – Wiegand 3+5

```text
RAW UID:          AE1C56CF  →  DB 08607342
RAW UID:          E9B20DFF  →  DB 01345801
```

```text
Reverse Byte Order: Yes
First Bit:          8
Number of Bits:     24
Encoding:           wiegand_3_5  (facility×100000 + card → FFFCCCCC)
```

### HID iCLASS / PAC (historický FW)

V `FW_elatec/FIN_kraceni_kodu_PAC_ID_bez_0/` je ověřený User App pro Thales/PAC:

- čtení PAC bitů přes `ICLASS_GetPACBits` (H10301 26 bit),
- FC = bity 1–8, card = bity 9–24 (bit 0 a 25 = parita),
- výstup jako `%03u%05u`, `facility×100000+card`, nebo **digit-concat** + strip vedoucích nul.

Tyto převody jsou dnes součástí analyzátoru (`facility_card_concat`, `h10301_*`, `wiegand_3_5_strip`).

## Funkce

- komunikace s TWN4 přes Simple Protocol (ASCII),
- verze firmware, typ zařízení, LF/HF masky,
- načtení `TagType`, bitové délky a RAW UID,
- hledání bitového okna + reverse bit/byte order,
- strukturované encodingy (Wiegand / PAC / H10301 / …),
- doporučení nastavení AppBlasteru,
- export JSON výsledků,
- sestavení flashovatelného `.bix` (`export-fw`, GUI **Vytvořit FW**),
- offline analýza bez čtečky,
- desktopové GUI (`gui/run_gui.bat`).

## Podporované encodingy

| Encoding | Popis | Typický výstup |
|----------|--------|----------------|
| `plain` | prostý Decimal / Hexadecimal z bitového okna | `12583124` |
| `wiegand_3_5` | facility (8) × 100000 + card (16) | `08607342` |
| `wiegand_3_5_strip` | totéž bez vedoucích nul | `8607342` |
| `facility_card_concat` | PAC digit-concat (FC a card slepeny desítkově) | `867342` |
| `card_16` | jen spodních 16 bitů (card) | `7342` |
| `facility_8` | jen horních 8 bitů (facility) | `86` |
| `scale_4` / `scale_6` | facility × 10⁴ / 10⁶ + card | — |
| `h10301_3_5` | 26bit H10301 → Wiegand 3+5 | `08607342` |
| `h10301_concat` | 26bit H10301 → PAC digit-concat | `867342` |
| `h10301_card` | 26bit H10301 → jen card | `7342` |
| `h10301_strip` | H10301 → 3+5 bez vedoucích nul | `8607342` |

Analyzátor zkouší i kombinace **Reverse Bit Order** / **Reverse Byte Order** a všechny rozumné bitové výřezy. U strukturovaných encodingů standardní AppBlaster Decimal nestačí — použijte **export-fw** / **Vytvořit FW**.

Zatím neimplementováno (při potřebě doplníme podle konkrétního RAW+DB páru): H10306 34-bit, H10304 37-bit, Corporate 1000, proprietární Lenel/SH layouty, živé `ICLASS_GetPACBits` přes Simple Protocol.

## Požadavky

- Windows 10/11,
- Python 3.10+,
- ELATEC TWN4 s firmware **PRS** (Simple Protocol) pro čtení karet,
- pro sestavení `.bix`: lokální DevPack ve složce `elafiles/` (nebo dříve `files520/`).

Director může držet COM port (`USB (COMxx)`). Před spuštěním toolu Director odpojte / zavřete.

## Instalace

```text
elaUIDtool.bat
```

Při prvním spuštění vytvoří `.venv`, nainstaluje projekt a nabídne menu:

```text
1. Tests - otestovat médium a vypsat jeho typ
2. Interactive mode - hledání UID a pravidla pro AppBlaster
3. Update reader - příprava PRS a vlastního firmware
0. Konec
```

Ruční instalace:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e .
```

GUI závislosti:

```powershell
.venv\Scripts\python -m pip install -r gui\requirements.txt
```

## Použití

### Interaktivní režim / capture / analyze

```powershell
.venv\Scripts\python -m elatec_uid_tool interactive
.venv\Scripts\python -m elatec_uid_tool interactive --show-all-candidates
.venv\Scripts\python -m elatec_uid_tool ports
.venv\Scripts\python -m elatec_uid_tool reader-info --port COM13
.venv\Scripts\python -m elatec_uid_tool test-medium
.venv\Scripts\python -m elatec_uid_tool capture --port COM13 --expected 12583124
.venv\Scripts\python -m elatec_uid_tool analyze --raw 3D00C000D4 --bits 40 --expected 12583124
.venv\Scripts\python -m elatec_uid_tool analyze --raw AE1C56CF --bits 32 --expected 08607342
```

Jedna připojená čtečka ELATEC se vybere automaticky (USB VID `09D8`).

Po úspěšné analýze se anonymizovaný vzorek uloží do `data/samples.json` (SHA-256 otisk + kandidátní pravidla, ne syrová UID). Složka `data/` je v `.gitignore`.

### Desktopové GUI

```text
gui\run_gui.bat
```

Záložky: **Čtečka → Načtení karty → Offline analýza**.  
U nejlepší shody: **Vytvořit FW (CDC)** / **Vytvořit FW (UART)** + export JSON.

Volitelně v prohlížeči: `gui\run_gui_browser.bat`.

### Export firmware (`.bix`)

Vyžaduje DevPack v `elafiles/` (Tools + base image `TWN4_xCx520_STD207_Multi_CDC_Standard.bix`).

```powershell
.venv\Scripts\python -m elatec_uid_tool export-fw --raw AE1C56CF --bits 32 --expected 08607342 --channel cdc --tag-type 0x80
.venv\Scripts\python -m elatec_uid_tool export-fw --raw 3D00C000D4 --bits 40 --expected 12583124 --channel both --tag-type 0x40
.venv\Scripts\python -m elatec_uid_tool export-fw --from-json results\elatec-….json --channel uart
.venv\Scripts\python -m elatec_uid_tool export-fw --raw AE1C56CF --bits 32 --expected 867342 --channel cdc --tag-type 0x80
```

Parametry:

| Parametr | Význam |
|----------|--------|
| `--raw` / `--bits` / `--expected` | offline shoda |
| `--from-json` | výsledek `capture` / GUI exportu |
| `--match-index` | která shoda (0 = nejlepší) |
| `--channel` | `cdc` \| `uart` \| `both` |
| `--tag-type` | např. `0x80` MIFARE, `0x40` EM4102 |
| `--devpack` | cesta k DevPacku (výchozí `elafiles`) |
| `--output-dir` | výchozí `FW_elatec/export/out` |

Výstup:

```text
FW_elatec/export/out/App_EXP_CDC.c
FW_elatec/export/out/TWN4_xCx520_EXP_CDC.bix
```

Nahrání v AppBlasteru: **Program Firmware Image → Select Image → Program Image**.

Generovaný FW aplikuje stejné pravidlo jako shoda (bit window, reverse bit/byte, Decimal/Hex, Wiegand/PAC/H10301).

### Update reader

```powershell
.venv\Scripts\python -m elatec_uid_tool update-reader --devpack files520
```

`files520/` i `elafiles/` jsou lokální a v `.gitignore` — proprietární ELATEC balíčky se necommitují.

## Struktura projektu

```text
src/elatec_uid_tool/
  analyzer.py      # bitová okna + shody
  encodings.py     # Wiegand / PAC / H10301 / …
  fw_export.py     # generování C + build .bix
  fw_commands.py   # CLI export-fw
  cli.py           # vstupní bod
gui/               # NiceGUI desktop
FW_elatec/
  wiegand35/       # ruční Wiegand 3+5 User App
  FIN_kraceni_kodu_PAC_ID_bez_0/  # historický PAC FW (zdroj)
  export/out/      # generované .bix (gitignore)
tests/
```

## Testy

```text
run_tests.bat
```

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python scripts\check_version.py
```

## Dokumentace

- [Architektura](docs/ARCHITECTURE.md)
- [Příprava čtečky](docs/READER_PREPARATION.md)
- [Verzování a release](docs/VERSIONING.md)
- [CHANGELOG](CHANGELOG.md)
- [CONTRIBUTING](CONTRIBUTING.md)
- [GitHub setup](docs/GITHUB_SETUP.md)
- [GUI README](gui/README.md)

## Verzování

Semantic Versioning. Aktuální verze `0.3.0`, tagy `vMAJOR.MINOR.PATCH`. Změny zapisujte do `CHANGELOG.md` pod `Unreleased`.

## Aktuální omezení

- automatický export AppBlaster `.abp` projektu zatím není,
- živé čtení PAC bitů z iCLASS přes Simple Protocol zatím ne (jen offline/H10301 layout a historický C FW),
- některé HF fingerprinty a společné pravidlo nad více kartami jsou v TODO,
- automatické nahrání PRS firmware je v návrhu,
- DevPack a PDF dokumentace ELATEC nejsou v repozitáři.
