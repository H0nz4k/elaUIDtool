# Návod – ELATEC UID Tool 0.3.x

Kompletní postup: instalace → GUI/CLI → analýza shody → sestavení `.bix` → nahrání do čtečky.

## 1. Instalace

1. Nainstaluj **Python 3.10+** (zapni *Add Python to PATH*).
2. V kořeni projektu spusť:

```text
elaUIDtool.bat
```

Vytvoří `.venv`, nainstaluje balíček a zobrazí menu.

Ručně:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m pip install -r gui\requirements.txt
```

### DevPack (jen pro sestavení FW)

Zkopíruj ELATEC Developer Pack **520** do složky `elafiles/` (v `.gitignore`, necommitovat).

Musí existovat např.:

```text
elafiles\Tools\makeapp.exe
elafiles\Tools\Yagarto-20110328\bin\arm-none-eabi-gcc.exe
elafiles\Firmware\TWN4_xCx520_STD207_Multi_CDC_Standard.bix
```

## 2. Spuštění aplikace

| Co | Jak |
|----|-----|
| **Desktopové GUI** | `gui\run_gui.bat` |
| GUI v prohlížeči | `gui\run_gui_browser.bat` |
| Menu CLI | `elaUIDtool.bat` |
| Interaktivní analýza | volba **2** v menu, nebo `run_interactive.bat` |

Před načtením karty **zavři Director** (jinak je COM port obsazený).

## 3. GUI – typický postup

1. Záložka **Čtečka** → obnov porty → ověř firmware (ideálně **PRS**).
2. Záložka **Načtení karty** → zadej DB kód (např. `01345801`) → načti kartu.
3. U **Nejlepší shody** zkontroluj encoding (Wiegand 3+5, plain, PAC, …).
4. Tlačítka **Vytvořit FW (CDC)** / **Vytvořit FW (UART)** → `.bix` do `FW_elatec\export\out\`.
5. Volitelně **Exportovat JSON** do `results\`.

Offline bez čtečky: záložka **Offline analýza** (RAW hex + DB kód).

## 4. CLI – analýza

```powershell
.venv\Scripts\python -m elatec_uid_tool analyze --raw E9B20DFF --bits 32 --expected 01345801
.venv\Scripts\python -m elatec_uid_tool analyze --raw AE1C56CF --bits 32 --expected 08607342
.venv\Scripts\python -m elatec_uid_tool capture --expected 01345801
```

Ověřené páry (Jarov / stůl):

| RAW UID | DB kód | Encoding |
|---------|--------|----------|
| `E9B20DFF` | `01345801` | Wiegand 3+5 (FC 13, card 45801) |
| `AE1C56CF` | `08607342` | Wiegand 3+5 (FC 86, card 7342) |

Pravidlo MIFARE → DB:

```text
Reverse Byte Order: Ano
First Bit:          8
Number of Bits:     24
Encoding:           facility × 100000 + card   (8 číslic FFFCCCCC)
```

## 5. Build firmware (`.bix`)

### A) Jednoduchý BAT (doporučeno)

```text
build_fw.bat
build_fw.bat cdc
build_fw.bat uart
build_fw.bat both
```

Výchozí referenční karta: `E9B20DFF` / `01345801`. Vlastní hodnoty:

```text
build_fw.bat cdc AE1C56CF 08607342 0x80
```

### B) CLI

```powershell
.venv\Scripts\python -m elatec_uid_tool export-fw --raw E9B20DFF --bits 32 --expected 01345801 --channel cdc --tag-type 0x80
```

### C) Ruční Wiegand projekt

```text
FW_elatec\wiegand35\build.bat cdc
```

### Výstup

```text
FW_elatec\export\out\TWN4_xCx520_EXP_CDC.bix
FW_elatec\export\out\TWN4_xCx520_EXP_UART.bix
```

- **CDC** = USB virtuální COM (MultiTech 2/3)
- **UART** = COM1 9600 8N1

## 6. Nahrání do čtečky

1. Spusť **AppBlaster** z DevPacku.
2. **Program Firmware Image** → **Select Image** → vyber `.bix`.
3. **Program Image**.
4. Ověř přiložením stolní karty (`01345801` / `08607342`).

Standardní AppBlaster „Decimal“ **nestačí** na Wiegand 3+5 — musí být vlastní User App (tento export).

## 7. Provoz Jarov

FW se nestaví na jednu kartu, ale na **stejné pravidlo**. Karty `03921353` / `12607299` ověř až fyzicky:

```powershell
.venv\Scripts\python -m elatec_uid_tool capture --expected 03921353
```

Očekávaná shoda: zase Wiegand 3+5 (pro `03921353` → FC 39, card 21353).

## 8. Testy před releasem

```text
run_tests.bat
```

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python scripts\check_version.py
```

## 9. Verze a GitHub

- Verze: `src/elatec_uid_tool/__init__.py`
- CHANGELOG: `CHANGELOG.md`
- Release helper: `python scripts/release.py X.Y.Z`
- Repozitář: https://github.com/H0nz4k/elaUIDtool

Další dokumenty: [README](../README.md), [Architektura](ARCHITECTURE.md), [Příprava čtečky](READER_PREPARATION.md), [Verzování](VERSIONING.md).
