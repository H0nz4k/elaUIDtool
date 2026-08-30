# ELATEC UID Tool – desktopové GUI (NiceGUI)

Desktopové rozhraní pro analyzátor UID. Volá `elatec_uid_tool` přes `services.py`.

**Podrobný návod:** [docs/NAVOD.md](../docs/NAVOD.md)

## Spuštění

```text
gui\run_gui.bat
```

Nebo z menu `elaUIDtool.bat` → volba **4**.

Prohlížeč: `gui\run_gui_browser.bat`.

## Po shodě

- karta nejlepší shody (encoding, facility/card),
- **Vytvořit FW (CDC/UART)** → `FW_elatec/export/out/*.bix`,
- export JSON, seznam kandidátů.

Build bez GUI: `build_fw.bat` v kořeni projektu.
