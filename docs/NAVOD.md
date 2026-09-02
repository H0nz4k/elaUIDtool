# Návod – ELATEC UID Tool 0.4.x

Kompletní postup: instalace → Windows GUI → porovnání / načtení → sestavení `.bix` → nahrání do čtečky.

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

### DevPack (pro sestavení FW)

Výchozí je **TWN4DevPack520**. Zkopíruj ho do `elafiles/` (gitignore), nebo v GUI → **Nastavení** zadej cestu k `TWN4DevPackxxx`.

Musí existovat:

```text
…\Tools\makeapp.exe
…\Tools\Yagarto-20110328\bin\arm-none-eabi-gcc.exe
…\Apps\App_STD207_Standard_temp.c
…\Apps\TWN4_CCx520.bix
…\Apps\TWN4_MCx520.bix
…\Apps\TWN4_NCx520.bix
```

## 2. Spuštění (Windows okno)

| Co | Jak |
|----|-----|
| **Desktopové GUI** | `gui\run_gui.bat` |
| Menu CLI | `elaUIDtool.bat` |
| Build FW z BAT | `build_fw.bat` |

Aplikace běží **jen jako nativní Windows okno** (prohlížeč není podporován).

Před načtením karty přes COM **zavři Director** (jinak je port obsazený).

## 3. GUI – typický postup pro kolegy

### A) Bez čipu a bez PRS (doporučeno)

1. Záložka **Porovnání**.
2. **Kód z čtečky** = RAW UID hex (např. `E9B20DFF` nebo `813F9A04`).
3. **Kód z databáze** = identifikátor z DB (např. `01345801` nebo `049A3F81`).
4. **Porovnat a najít pravidlo**.
5. U shody → **Vytvořit FW (CDC)**.

### B) S fyzickou čtečkou (PRS)

1. Záložka **Čtečka** → ověř PRS.
2. Záložka **Načtení karty** → DB kód → přilož kartu.
3. **Vytvořit FW (CDC/UART)**.

### C) Nastavení DevPacku

Záložka **Nastavení** → cesta k `TWN4DevPack520` (nebo novějšímu) → Uložit → Ověřit.

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

Build = AppBlaster logika DevPack 520:

`App_STD207_Standard_temp.c` + `appconfig.c` + `makeapp -iCCx -iMCx -iNCx`.

### A) GUI

Po shodě: **Vytvořit FW (CDC)**.

### B) BAT

```text
build_fw.bat
build_fw.bat cdc AE1C56CF 08607342 0x80
```

### C) CLI

```powershell
.venv\Scripts\python -m elatec_uid_tool export-fw --raw E9B20DFF --bits 32 --expected 01345801 --channel cdc --tag-type 0x80
```

### Výstup

```text
FW_elatec\export\out\appconfig.c
FW_elatec\export\out\appconfig.h
FW_elatec\export\out\TWN4_xCx520_EXP_CDC.bix
```

Důležité pro `makeapp`:  
`-v4 -tTWN4 -nTWN4 -b0520 -iTWN4_CCx520.bix -iTWN4_MCx520.bix -iTWN4_NCx520.bix`  
Bez NCx AppBlaster hlásí „not compatible“.

## 6. Nahrání do čtečky

1. Spusť **AppBlaster** z DevPacku.
2. **Program Firmware Image** → **Select Image** → vyber `.bix`.
3. **Program Image**.
4. Ověř přiložením stolní karty (`01345801` / `08607342`).

## 7. Provoz Jarov

FW se nestaví na jednu kartu, ale na **stejné pravidlo**.

```powershell
.venv\Scripts\python -m elatec_uid_tool capture --expected 03921353
```

## 8. Troubleshooting

| Problém | Řešení |
|---------|--------|
| Port se neotevře | Zavři Director / jiný COM nástroj |
| „not compatible“ | Použij `.bix` z aktuálního exportu (CCx+MCx+NCx), ne starý image |
| GCC / makeapp chybí | Nastav DevPack520 v GUI → Nastavení |
| Po EXP nefunguje tool přes COM | Je nahraný produkční FW; pro analýzu nahraj PRS zpět |
