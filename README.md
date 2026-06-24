# ELATEC – kód identifikace

Terminálový nástroj pro analýzu UID z čteček **ELATEC TWN4** a nalezení konfigurace AppBlasteru, která reprodukuje identifikátor uložený v existující databázi.

Aktuální verze: **0.1.3**

## Ověřený referenční případ

```text
RAW UID:          3D00C000D4
RAW délka:        40 bitů
DB identifikátor: 12583124
```

Nalezené a fyzicky ověřené nastavení AppBlasteru:

```text
Output Bits:        Some Bits
First Bit:          8
Number of Bits:     32
Output Format:      Decimal
Length:             Automatic
Reverse Bit Order:  No
Reverse Byte Order: No
```

## Funkce

- komunikace s TWN4 přes Simple Protocol v ASCII režimu,
- zjištění verze firmware a typu zařízení,
- zjištění LF/HF technologií podporovaných konkrétní čtečkou,
- načtení `TagType`, počtu bitů a raw UID,
- základní identifikace média a frekvenční skupiny,
- hledání bitového výřezu a změn bit/byte order,
- doporučení konkrétního nastavení AppBlasteru,
- export výsledků do JSON,
- offline analýza bez připojené čtečky.

## Požadavky

- Windows 10/11,
- Python 3.10 nebo novější,
- ELATEC TWN4 s firmware `PRS` pro Simple Protocol,
- `pyserial` – nainstaluje se automaticky.

Director může zobrazovat port jako `USB (COM13)`. Jde o virtuální COM port. Před spuštěním tohoto programu musí být Director odpojený nebo zavřený, protože COM port může v jednu chvíli používat jen jedna aplikace.

## Instalace

```text
1. Spusť install_windows.bat
2. Spusť run_interactive.bat
```

Ruční instalace:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e .
```

## Použití

Interaktivní režim:

```powershell
.venv\Scripts\python -m elatec_uid_tool interactive
```

Seznam portů:

```powershell
.venv\Scripts\python -m elatec_uid_tool ports
```

Informace o čtečce:

```powershell
.venv\Scripts\python -m elatec_uid_tool reader-info --port COM13
```

Načtení karty a analýza:

```powershell
.venv\Scripts\python -m elatec_uid_tool capture --port COM13 --expected 12583124
```

Offline referenční test:

```powershell
.venv\Scripts\python -m elatec_uid_tool analyze --raw 3D00C000D4 --bits 40 --expected 12583124
```

## Testy

```text
run_tests.bat
```

Nebo:

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python scripts\check_version.py
```

## Dokumentace

- [Architektura](docs/ARCHITECTURE.md)
- [Příprava čtečky](docs/READER_PREPARATION.md)
- [Verzování a release proces](docs/VERSIONING.md)
- [Historie změn](CHANGELOG.md)
- [Pravidla přispívání](CONTRIBUTING.md)
- [Publikování na GitHub](docs/GITHUB_SETUP.md)

## Verzování

Projekt používá Semantic Versioning. Aktuální verze je `0.1.3`; vydané verze se označují anotovanými Git tagy ve tvaru `vMAJOR.MINOR.PATCH`.

Každá významná změna se zapisuje do `CHANGELOG.md` pod sekci `Unreleased`. Podrobný postup vydání je v `docs/VERSIONING.md`.

## Aktuální omezení

- automatický export AppBlaster projektu zatím není implementovaný,
- přesný fingerprint některých HF médií zatím není implementovaný,
- hledání společného pravidla nad více kartami je v TODO,
- bezpečné automatické nahrání PRS firmware je zatím v návrhu,
- proprietární ELATEC Developer Pack a PDF dokumentace nejsou součástí repozitáře.
