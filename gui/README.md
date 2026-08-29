# ELATEC UID Tool – desktopové GUI (NiceGUI)

Desktopové rozhraní pro analyzátor UID. Volá `elatec_uid_tool` přes `services.py`.

Technologie: [NiceGUI](https://nicegui.io/documentation) v **nativním režimu** ([pywebview](https://pywebview.flowrl.com/)).

## Požadavky

- Windows 10/11 (nativní režim = Edge WebView2)
- Python 3.10+
- Nainstalovaný projekt (`install_windows.bat` / `elaUIDtool.bat`)
- ELATEC TWN4 s firmware **PRS** pro načítání karet
- Pro **Vytvořit FW**: DevPack v `elafiles/`

## Spuštění

```text
gui\run_gui.bat
```

Prohlížeč: `gui\run_gui_browser.bat` nebo `python gui\app.py --browser`.

## Záložky

| Záložka | Popis |
|---------|--------|
| **Čtečka** | Firmware, typ zařízení, podporované technologie |
| **Načtení karty** | COM port, DB kód, načtení + analýza |
| **Offline analýza** | RAW hex + očekávaný kód bez čtečky |

## Po shodě

- karta nejlepší shody (encoding, facility/card, reverse bit/byte),
- **Vytvořit FW (CDC)** / **Vytvořit FW (UART)** → `.bix` do `FW_elatec/export/out/`,
- export JSON do `results/`,
- seznam dalších kandidátů.

Podporované encodingy: plain DEC/HEX, Wiegand 3+5 (+ strip nul), PAC digit-concat, H10301, card/facility only, scale 4/6 — viz hlavní [README](../README.md).

## Struktura

```text
gui/
├── app.py              # NiceGUI UI
├── services.py         # obal nad elatec_uid_tool
├── requirements.txt    # nicegui, pywebview
├── run_gui.bat
├── run_gui_browser.bat
└── README.md
```
