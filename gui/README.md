# ELATEC UID Tool – desktopové GUI (NiceGUI)

Desktopové rozhraní pro stávající analyzátor UID. **Nepřepisuje** kód v `src/` – pouze volá modul `elatec_uid_tool` přes tenkou vrstvu `services.py`.

Technologie: [NiceGUI](https://nicegui.io/documentation) v **nativním režimu** ([pywebview](https://pywebview.flowrl.com/)) – běží jako samostatné okno aplikace, ne v prohlížeči.

## Požadavky

- Windows 10/11 (nativní režim používá Edge WebView2)
- Python 3.10+
- Nainstalovaný projekt (`install_windows.bat`)
- ELATEC TWN4 s firmware **PRS** (Simple Protocol) pro načítání karet

## Spuštění

```text
1. install_windows.bat        (pokud ještě neběželo)
2. gui\run_gui.bat
```

Otevře se **desktopové okno** aplikace (bez adresního řádku prohlížeče).

Volitelně v prohlížeči:

```text
gui\run_gui_browser.bat
```

nebo:

```powershell
.venv\Scripts\python gui\app.py --browser
```

Ruční spuštění desktopového okna:

```powershell
.venv\Scripts\python -m pip install -r gui\requirements.txt
.venv\Scripts\python gui\app.py
```

## Záložky

| Záložka | Popis |
|---------|--------|
| **Načtení karty** | Výběr COM portu, zadání DB kódu, načtení karty a analýza transformací |
| **Offline analýza** | Analýza bez čtečky – RAW hex + očekávaný kód (referenční test: `3D00C000D4` / `12583124`) |
| **Čtečka** | Informace o firmware, typu zařízení a podporovaných technologiích |

## Export

Výsledky načtení karty lze uložit do `results/elatec-YYYYMMDD-HHMMSS.json` – stejný formát jako CLI příkaz `capture`.

## Struktura

```text
gui/
├── app.py              # NiceGUI UI (nativní okno / --browser)
├── services.py         # obal nad elatec_uid_tool (bez úprav src/)
├── requirements.txt    # nicegui, pywebview
├── run_gui.bat         # spouštěč – desktopové okno
├── run_gui_browser.bat # volitelně v prohlížeči
└── README.md
```
