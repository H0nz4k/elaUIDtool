# ELATEC UID Tool – Windows desktop GUI (NiceGUI + nativní okno)

Desktopová aplikace pro kolegy: offline porovnání kódu z čtečky vs DB, načtení karty přes PRS, sestavení FW (Jarov / STD207).

**Návod:** [docs/NAVOD.md](../docs/NAVOD.md)

## Spuštění

```text
gui\run_gui.bat
```

Nebo `elaUIDtool.bat` → volba **4**.

Aplikace běží **jen jako Windows okno** (ne prohlížeč).

## Záložky

1. **Porovnání** – kód z čtečky (RAW hex) + kód z DB → pravidlo + **Vytvořit FW** (bez chipu / bez PRS).
2. **Načtení karty** – COM + Simple Protocol.
3. **Čtečka** – info o zařízení.
4. **Nastavení** – cesta k `TWN4DevPack520` (nebo novějšímu DevPackxxx).

## DevPack

Výchozí: `elafiles/` nebo `C:\Work\Elatec- reader\TWN4DevPack520`.  
Pro build FW musí být v DevPacku `Apps/` s `App_STD207_Standard_temp.c` a `TWN4_{C,M,N}Cx520.bix`.
