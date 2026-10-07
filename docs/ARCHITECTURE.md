# Architektura

- `protocol.py`: komunikace s TWN4.
- `ports.py`: automatický výběr COM portu.
- `tagtypes.py`: popis typu média.
- `analyzer.py`: analýza bitového výřezu.
- `samples.py`: anonymizovaná pravidla podle typu média.
- `commands.py`: uživatelské příkazy.
- `cli.py`: příkazové rozhraní.
- `registration.py`: konfigurace HF/LF a export D2R0.15 ze zabalených C zdrojů.
- `registration_client.py`: opt-in CDC test jedné karty, příjem rámců přes zavření/otevření COM.
- `fw_templates/registration/`: přenosný stavový automat, SDK adaptér, synchronní zvuk/LED a diagnostický protokol.
- `twn4_build.py`, `bix_container.py`: společné sestavení a ověření nezměněných OS obrazů 5.20.
- `reader_models.py`, `gui/firmware_ui.py`: oba modely, lokální fotografie a export BIX.
- `gui/registration_tab.py`: nové nastavení a test registrace, oddělené od PRS čtení.
- `builder.py`: validované datové projekty, převzetí MatchCandidate, předvolby a živý náhled.
- `builder_firmware.py`, `fw_templates/builder/`: generování pravidel, přenosné C jádro (až 256 bitů), signalizace a build celého projektu.
- `gui/builder_tab.py`: projektový editor; všechna pole jsou součástí výsledného firmware.
- Builder registrace využívá původní `dual_core.c`, s vloženým datovým pravidlem, vlastní signalizací a limitem Jídelny 16 znaků.
- CDC a Keyboard mají vlastní vendor OS obrazy; USB PID samo o sobě není přepnutí rozhraní.
- `elaUIDtool.bat`: instalace a menu pro Windows.

Tok dat: médium → TWN4 → RAW UID → porovnání s DB ID → doporučené nastavení AppBlasteru.

Jedna rozpoznaná ELATEC čtečka se vybere automaticky. Více čteček nebo nejasná detekce vyvolá ruční výběr.

Lokální `data/samples.json` ukládá jen anonymizovaný otisk a kandidátní pravidla. Složka `files520/` je lokální a Git ji ignoruje.
