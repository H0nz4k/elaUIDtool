# TWN4 User App – Wiegand 3+5 (FFFCCCCC)

Produkční firmware pro čtečky **TWN4 MultiTech 2 USB** a **TWN4 MultiTech 3 M LF HF**.

## Co dělá

```text
MIFARE UID
  → reverse byte order
  → First Bit 8 / 24 bitů
  → facility (8 bit) × 100000 + card (16 bit)
  → výstup 8 číslic + CR
```

Ověřené páry z `elaUIDtool`:

| RAW UID    | DB kód   |
|------------|----------|
| `AE1C56CF` | `08607342` |
| `E9B20DFF` | `01345801` |

## Výstupní kanál (volitelný při buildu)

| Příkaz | Kanál | Typické použití |
|--------|--------|-----------------|
| `build.bat` / `build.bat cdc` | `CHANNEL_USB` | USB CDC virtuální COM (PID `0x0420`) |
| `build.bat uart` | `CHANNEL_COM1` | UART onboard, 9600 8N1 |
| `build.bat both` | oba | dvě `.bix` najednou |

Makro ve zdrojáku: `W35_HOST_CHANNEL` (ne `HOST_CHANNEL` – to je v API ID parametru).

Základní image: `elafiles/Firmware/TWN4_xCx520_STD207_Multi_CDC_Standard.bix`  
(univerzální Multi CDC – vhodné pro MultiTech 2/3 s USB CDC větví `xCx`).

Sestavení ověřeno proti DevPacku **520** v `elafiles/`.

## Požadavky

1. DevPack ve složce `elafiles/` (aktuálně **TWN4DevPack520** – toolchain + `makeapp` + `xCx520` image).
2. Windows + AppBlaster pro nahrání `.bix`.

## Sestavení

```text
cd FW_elatec\wiegand35
build.bat cdc
build.bat uart
```

Výstup:

```text
out\TWN4_xCx520_W35_CDC.bix
out\TWN4_xCx520_W35_UART.bix
```

## Nahrání

1. Ulož si stávající produkční firmware.
2. AppBlaster → **Program Firmware Image** → vyber `.bix` → **Program Image**.
3. Ověř výstup (CDC port nebo UART) přiložením testovací karty.

## Poznámky

- Standardní AppBlaster „Decimal“ **nestačí** – dal by prostý 24bit decimal (`5643438`), ne `08607342`.
- Keyboard image (`xKx`) tento projekt záměrně nepoužívá; výstup je sériový text pro docházkové / přístupové SW.
- LF / jiné tag typy zatím nejsou aktivní – šablona je cílená na ověřený MIFARE případ.
- Složka `out/` je lokální artefakt (lze smazat / ignorovat v Gitu).

## Další krok (elaUIDtool)

Později může analyzátor generovat tuto app (nebo parametry) přímo z nalezeného pravidla `encoding=wiegand_3_5`.
