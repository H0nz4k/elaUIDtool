# ELATEC UID Tool 0.5.0

Windows aplikace pro práci s identifikátory karet na čtečkách **ELATEC TWN4**.

Pomůže ti:
1. **porovnat** kód, který vrací čtečka, s kódem v databázi,
2. **najít pravidlo** převodu (reverse byte, Wiegand 3+5, …),
3. **sestavit firmware** (`.bix`) pro čtečku,
4. volitelně **načíst kartu** přes USB (Simple Protocol / PRS).
5. **registrovat HF/LF kartu** jedním přiložením, s HEX/DEC zvlášť pro každé pásmo.

Repozitář: [https://github.com/H0nz4k/elaUIDtool](https://github.com/H0nz4k/elaUIDtool)  
Podrobný návod: [docs/NAVOD.md](docs/NAVOD.md)
Registrace pro Jídelnu: [docs/REGISTRATION.md](docs/REGISTRATION.md)

---

## Co umí

| Funkce | Popis |
|--------|--------|
| **Porovnání bez čipu** | Zadáš RAW UID z čtečky + kód z DB → tool najde pravidlo |
| **Vytvořit FW** | Sestaví flashovatelný `.bix` (CDC/UART) jako u Jarova |
| **Načtení karty** | Přes COM a PRS firmware načte UID a porovná s DB |
| **Info o čtečce** | Verze FW, LF/HF masky, TagType |
| **Registrace HF/LF** | Automaticky HF+LF / jen HF / jen LF, vlastní USB CDC firmware, test jedné karty bez DB |
| **Modely čteček** | TWN4 MULTITECH 2 USB a TWN4 MULTITECH 3 M LF HF, fotografie při exportu BIX |
| **Nastavení DevPacku** | Cesta k ověřenému `TWN4DevPack520` (5.20) |
| **CLI** | Stejná logika z příkazové řádky |

### Podporované převody

| Encoding | Co dělá | Příklad |
|----------|---------|---------|
| plain Decimal / Hex | bitové okno | `12583124` |
| **Wiegand 3+5** | facility×100000+card | `E9B20DFF` → `01345801` |
| Wiegand 3+5 bez nul | totéž bez vedoucích nul | `8607342` |
| Reverse Byte | otočení bajtů | `813F9A04` → `049A3F81` |
| PAC digit-concat | FC+card jako číslice | `867342` |
| H10301 / card / facility | 26bit a odvozené | — |

U Wiegand 3+5 a PAC **nestačí** standardní AppBlaster Decimal — musíš nahrát vlastní FW z tohoto toolu.

---

## Požadavky

- **Windows 10/11**
- **Python 3.10+** (zapni *Add python.exe to PATH*)
- Pro sestavení FW: **ELATEC TWN4DevPack520 (5.20)** — proprietární, není v ZIPu
- Pro načtení karty přes USB: čtečka s firmware **PRS** (Simple Protocol)
- Před prací s COM **zavři AppBlaster Director** (drží port)

---

## Instalace (kolegové)

1. Rozbal složku `elaUIDtool-0.5.0` (nebo naklonuj repo).
2. Spusť:

```text
elaUIDtool.bat
```

Vytvoří `.venv`, nainstaluje balíček a otevře menu.

3. Pro GUI:

```text
gui\run_gui.bat
```

Otevře se **Windows okno** (ne prohlížeč).

### DevPack (jen když chceš tvořit `.bix`)

1. Zkopíruj `TWN4DevPack520` do složky `elafiles\` vedle toolu,  
   **nebo** v GUI → **Nastavení** zadej cestu k DevPacku.
2. Ověř, že existují:

```text
elafiles\Tools\makeapp.exe
elafiles\Apps\App_STD207_Standard_temp.c
elafiles\Apps\TWN4_CCx520.bix
elafiles\Apps\TWN4_MCx520.bix
elafiles\Apps\TWN4_NCx520.bix
```

Podporovaný je i původní DevPack bez ručně připravených souborů: šablona
`Apps/Samples/Standard/App_STD207_Standard.c` a základ
`Firmware/TWN4_xCx520_STD207_Multi_CDC_Standard.bix`. Tool z něj vyjme tři
systémové obrazy bez změny jejich obsahu. Nepodporovaný systémový základ se odmítne.

---

## Jak používat GUI

### A) Typický postup bez čipu (doporučeno)

1. Otevři `gui\run_gui.bat`.
2. Záložka **Porovnání**.
3. **Kód z čtečky** = RAW UID hex (např. `E9B20DFF`).
4. **Kód z databáze** = hodnota z DB (např. `01345801`).
5. Klikni **Porovnat a najít pravidlo**.
6. U shody → **Vytvořit FW (CDC)** → vyber model podle fotografie.
7. V AppBlasteru nahraj BIX, jehož cestu zobrazí tool (výstup je ve složce vybraného modelu):

```text
FW_elatec\export\out\TWN4_xCx520_EXP_CDC.bix
```

**Program Firmware Image → Select Image → Program Image.**

### B) S fyzickou čtečkou

1. Nahraj do čtečky **PRS** (Simple Protocol).
2. Záložka **Čtečka** → ověř COM a PRS.
3. Záložka **Načtení karty** → zadej DB kód → přilož kartu.
4. **Vytvořit FW (CDC)**.

### C) Nastavení

Záložka **Nastavení** → cesta k DevPacku → **Uložit** → **Ověřit**.

### D) Registrace HF/LF pro Jídelnu

1. **Registrace HF/LF** → vyber **MultiTech 2 USB** nebo **MultiTech 3 M LF HF**.
2. Nastav **Výstup HF** a **Výstup LF** samostatně na HEX/DEC.
3. **Vytvořit registrační BIX** → nahraj přes AppBlaster.
4. Zavři Jídelnu a AppBlaster → **Otestovat jednu kartu** → přilož po výzvě.
5. V Jídelně použij interní čtečku na COM s povolenými duálními kartami.

HF+LF odešle HF potom LF; jediný nalezený čip se odešle jednou. HEX má původní
délku bez přidaných nul. DEC převádí celý UID, bez zkrácení; může mít až 20
číslic, zatímco Jídelna používá 16 znaků. Podrobný postup a časování najdeš
v [návodu k registraci](docs/REGISTRATION.md).

---

## Ověřené příklady

### Jarov / stůl (MIFARE → Wiegand 3+5)

| Čtečka (RAW) | Databáze | Pravidlo |
|--------------|----------|----------|
| `E9B20DFF` | `01345801` | Reverse Byte, First Bit 8, 24 bit, facility×100000+card |
| `AE1C56CF` | `08607342` | stejné |

### Reverse Byte (hex DB)

| Čtečka | Databáze |
|--------|----------|
| `813F9A04` | `049A3F81` |

### EM4102 (LF)

| RAW | DB | Pravidlo |
|-----|-----|----------|
| `3D00C000D4` (40 bit) | `12583124` | First Bit 8, 32 bit, Decimal, bez reverse |

---

## Spouštěče

| Soubor | Účel |
|--------|------|
| `releases\elaUIDtool-*-win64-gui\elaUIDtool.exe` | **pouze GUI** – Windows okno pro kolegy (bez Pythonu) |
| `elaUIDtool.bat` | instalace + menu (vývoj) |
| `gui\run_gui.bat` | GUI z Pythonu (vývoj) |
| `build_fw.bat` | sestavení `.bix` bez GUI |
| `install_windows.bat` | jen instalace `.venv` |
| `run_tests.bat` | unit testy |
| `scripts\build_exe.bat` | sestavení GUI `.exe` (PyInstaller onedir) |

---

## CLI (pro pokročilé)

```powershell
.venv\Scripts\python -m elatec_uid_tool analyze --raw E9B20DFF --bits 32 --expected 01345801
.venv\Scripts\python -m elatec_uid_tool export-fw --raw E9B20DFF --bits 32 --expected 01345801 --channel cdc --tag-type 0x80
.venv\Scripts\python -m elatec_uid_tool capture --expected 01345801
.venv\Scripts\python -m elatec_uid_tool ports
.venv\Scripts\python -m elatec_uid_tool export-registration-fw --reader-model multitech2-usb --hf-format HEX --lf-format DEC
.venv\Scripts\python -m elatec_uid_tool test-registration --port COM7
```

Výstup FW:

```text
FW_elatec\export\out\appconfig.c
FW_elatec\export\out\appconfig.h
FW_elatec\export\out\TWN4_xCx520_EXP_CDC.bix
```

---

## Struktura projektu

```text
elaUIDtool/
  gui/                 Windows GUI (NiceGUI okno)
  src/elatec_uid_tool/ analyzátor, encodingy, export FW
  docs/NAVOD.md        podrobný návod
  FW_elatec/           šablony a výstup .bix
  elafiles/            DevPack520 (lokálně, ne v Gitu)
  releases/            hotové balíčky verzí (pack_release)
  tests/
```

## Balíček pro kolegy

**Doporučeno – jen GUI EXE** (bez Pythonu):

```text
scripts\build_exe.bat
```

Výstup:

```text
releases\elaUIDtool-0.4.1-win64-gui\elaUIDtool.exe
```

Spusť `elaUIDtool.exe`. Porovnání funguje ihned. Pro **Vytvořit FW** zkopíruj DevPack520 do `elafiles\` vedle EXE, nebo nastav cestu v GUI → Nastavení.

Zdrojový (Python) balíček:

```text
scripts\pack_release.bat
```

```text
releases\elaUIDtool-0.4.1-win64-gui.zip
releases\elaUIDtool-0.4.1\
releases\elaUIDtool-0.4.1.zip
```

DevPack se do balíčků nedává (licence ELATEC).

## Časté problémy

| Problém | Řešení |
|---------|--------|
| Port se neotevře | Zavři Director / jiný program na COM |
| „not compatible“ při flashi | Použij `.bix` z aktuálního exportu (musí obsahovat CCx+MCx+**NCx**) |
| GCC / makeapp chybí | Nastav DevPack v GUI → Nastavení |
| Po nahrání EXP tool nečte karty | Je produkční FW; pro analýzu nahraj PRS zpět |
| GUI nejde spustit | Python 3.10+, `elaUIDtool.bat`, pak `gui\run_gui.bat` |

## Changelog / dokumentace

- [CHANGELOG.md](CHANGELOG.md)
- [docs/NAVOD.md](docs/NAVOD.md)
- [docs/VERSIONING.md](docs/VERSIONING.md)
- [gui/README.md](gui/README.md)

## Licence / omezení

- ELATEC DevPack a `.bix` image jsou proprietární — do balíčku toolu se nedávají.
- Automatický flash přes Raspberry zatím není.
- AppBlaster `.abp` export zatím není.

---

## Changelog

Viz [CHANGELOG.md](CHANGELOG.md). Aktuální verze: **0.4.1**.
