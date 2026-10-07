# ELATEC UID Tool – Windows desktop GUI (NiceGUI + nativní okno)

Desktopová aplikace pro kolegy: offline porovnání kódu z čtečky vs DB, načtení karty přes PRS, sestavení FW (Jarov / STD207).

**Návod:** [docs/NAVOD.md](../docs/NAVOD.md)

## Spuštění

```text
gui\run_gui.bat
```

Nebo `elaUIDtool.bat` → volba **4**.

Aplikace se standardně spouští jako Windows okno. Pro ověření rozhraní lze
použít `python gui/app.py --browser`.

## Záložky

1. **Porovnání** – kód z čtečky (RAW hex) + kód z DB → pravidlo + **Vytvořit FW** (bez chipu / bez PRS).
2. **Načtení karty** – COM + Simple Protocol.
3. **Registrace HF/LF** – jeden nebo dva čipy při jednom přiložení, samostatné HEX/DEC,
   výběr modelu podle fotografie, sestavení registračního BIX a krátký test jedné karty.
4. **FW builder** – převzetí libovolné shody, samostatná pravidla HF/LF, předvolby a projekt JSON,
   živý náhled, pípání/LED, rozhraní a export BIX se zdroji/manifestem.
5. **Čtečka** – info o zařízení (PRS).
6. **Nastavení** – cesta k `TWN4DevPack520` (5.20).

## DevPack

Výchozí: `elafiles/` nebo `C:\Work\Elatec- reader\TWN4DevPack520`.  
Podporované jsou připravené `Apps/App_STD207_Standard_temp.c` + `TWN4_{C,M,N}Cx520.bix`
i původní `Apps/Samples/Standard/App_STD207_Standard.c` +
`Firmware/TWN4_xCx520_STD207_Multi_CDC_Standard.bix`.

Registrace nevyžaduje PRS; test využívá D2R0.15. Postup:
[docs/REGISTRATION.md](../docs/REGISTRATION.md).

Builder používá lokální SDK i pro klávesnicový systémový základ
`Firmware/TWN4_xKx520_STD207_Multi_Keyboard_Standard.bix`.
Podrobný postup a omezení: [docs/FW_BUILDER.md](../docs/FW_BUILDER.md).
