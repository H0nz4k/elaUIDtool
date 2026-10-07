# Registrace HF/LF

Tento režim přenáší funkční postup z Hanz TWN4 Dual Registration 0.1.4 do
elaUIDtool. Nový firmware má identifikaci **D2R0.15** a umožňuje samostatný
formát HEX/DEC pro každé pásmo. Není potřeba nahrazovat `Ctids90w.exe` ani
aktualizovat Jídelnu.

## Vytvoření BIX

1. V **Nastavení** zadej kořen lokálního **TWN4DevPack520 (5.20)** s adresáři
   `Tools`, `Apps`, `Firmware`.
2. Otevři **Registrace HF/LF** a vyber čtečku podle fotografie:
   **TWN4 MULTITECH 2 USB** nebo **TWN4 MULTITECH 3 M LF HF**.
3. Vyber **Výstup HF** a **Výstup LF**, každý zvlášť HEX nebo DEC.
4. Klikni na **Vytvořit registrační BIX** a případně **Uložit BIX jako…**.
5. V AppBlasteru použij **Program Firmware Image → Select Image → Program Image**.
6. Po nahrání zavři AppBlaster i Jídelnu a v nové záložce spusť **Otestovat jednu kartu**.
   Přilož kartu až po výzvě a drž ji na čtečce do výsledku.

Volby v GUI mění nově sestavený BIX. Uložení voleb samo nemění již nahraný
firmware. Test ukazuje formáty a kódy skutečně nahraného firmware, nikoli
očekávání podle momentálně vybraných voleb GUI.

Výstup je USB CDC (virtuální COM). U vestavného modulu MultiTech 3 musí být
vyvedeno USB a příslušná zvuková/světelná signalizace. Volba modelu je
identifikace v exportu; oba exporty obsahují původní CCx/MCx/NCx systémové
rodiny 5.20. AppBlaster zvolí kompatibilní systém podle připojeného zařízení.
Názvy modelů nejsou náhradou kontroly kompatibility konkrétní HW revize v AppBlasteru.

Příklady cest:

```text
FW_elatec/export/registration/multitech2-usb/HF-HEX_LF-DEC/
FW_elatec/export/registration/multitech3-m-lf-hf/HF-DEC_LF-HEX/
```

Vedle BIX se ukládá vygenerovaná konfigurace, C zdroje, HEX, log a JSON
s modelem, formáty, dobou hledání a SHA-256. SDK a výsledné BIX nepatří do Gitu.
Developer Pack se s aplikací nedistribuuje.

## Čtení

Na začátku se zkouší HF; nenalezené pásmo se střídá s LF. Po nalezení první
technologie se hledá pouze ta druhá. Čtečka nejprve uloží výsledky do paměti
a teprve potom je odešle. Mezi HF a LF není nutné kartu zvedat.

| Nalezeno | Identifikátory do COM | Oznámení |
| --- | --- | --- |
| HF + LF | HF, potom LF | 2 hlasitá pípnutí a 2 zelená bliknutí |
| Jen HF | HF jednou | 1 pípnutí a 1 zelené bliknutí |
| Jen LF | LF jednou | 1 pípnutí a 1 zelené bliknutí |

Každý pulz má 60 ms zapnuto a 60 ms vypnuto; zvuk i LED běží současně.
UID se odešle s ukončením **CR**, bez LF. U jediné technologie následuje
prázdný rámec CR, aby Jídelna ukončila druhé pole. Nejde o další identifikátor
a první kód se neopakuje. Dvojice rámců má odstup nejméně 200 ms; firmware
zachová připravené kódy přes zavření/znovuotevření COM.

Čtečka aktivuje všechny podporované/licencované fyzické LF/HF typy z
`GetSupportedTagTypes`; BLE a NFC peer-to-peer jsou vyřazené. LF skupina SDK
může zahrnovat i 134,2 kHz. Nelze aktivovat technologii nepodporovanou konkrétní
čtečkou nebo licencí.

Chybějící technologie se hledá standardně **2000 ms od prvního úspěšného
čtení**. Dvojice se odešle ihned po nalezení obou čipů. U jediného čipu je třeba
počkat na tento limit. Absenci druhého čipu nelze prokázat okamžitě: slabší
čip dualní karty může při krátkém limitu zůstat nenalezený. Doba volání RF SDK
ovlivňuje skutečný čas; úspěšné poslední čtení má přednost před vypršením limitu.

Po dokončení se stejná přidržená karta znovu neposílá. Nové čtení se odjistí
až po odebrání (alespoň 300 ms potvrzené nepřítomnosti). Při registraci drž
na čtečce jen jednu kartu; bez společné identity dvou čipů nelze z UID ověřit,
že HF a LF fyzicky patří do téže plastové karty.

## HEX a DEC

HEX obsahuje plný UID ze SDK, velká písmena, původní délku. Skutečné nuly
v UID se zachovají; žádné nuly se nepřidávají na délku 16.
DEC je nezáporná číselná hodnota téhož celého HEX UID, bez nul zleva,
bez změny pořadí bajtů, bez PAC/Wiegand výřezu a bez mezikroku přes float.

| Celý HEX UID | HEX výstup | DEC výstup |
| --- | --- | --- |
| `04112233` | `04112233` | `68231731` |
| `0102030405` | `0102030405` | `4328719365` |
| `FFFFFFFFFFFFFFFF` | `FFFFFFFFFFFFFFFF` | `18446744073709551615` |

Limit prototypu je **64 bitů UID**: max. 16 HEX nebo 20 DEC číslic. Delší
UID (např. 10bajtové MIFARE UID), nulové/neplatné UID a shodné výsledné kódy
se odmítnou a čtečka signalizuje chybu červeně. Ani DEC se nezkracuje.
Jídelna pracuje s polem o 16 znacích: pro dlouhé UID s více než 16 DEC
číslicemi použij HEX, jinak by kód přesáhl její pole. Ve smíšených formátech
se kontroluje také kolize výsledných textů po doplnění nul v Jídelně.

V Jídelně zapni **Povolit duální karty** a použij interní COM čtečku. Nastav
délku a formát přijatých kódů tak, aby Jídelna již neměnila požadované UID.
Při změně HEX↔DEC se změní uložená hodnota; musí odpovídat kódům používaným
ostatními čtečkami klienta. Po stornu registrace v Jídelně čtečka nedostane
informaci o zrušení; před novou registrací po rozpracovaném čtení ji odpoj/připoj.

## Test jedné karty

Test využívá opt-in příkazy D2R (`!T`, `!N`, `!G`). Nedělá PRS dotazy a
nečte databázi. Kontroluje souhrn nálezu i **skutečné dva sériové rámce**,
včetně prázdného druhého rámce pro jediný čip. Po prvním kódu zavře a znovu
otevře COM bez vymazání čekajícího druhého rámce. Odmítá předčasný kód,
nesprávné pořadí i nadbytečný kód. Po skončení/zastavení obnoví běžný výstup
bez diagnostických zpráv a uvolní port. Během testu musí být Jídelna zavřená.

Záložky **Čtečka** a **Načtení karty** nadále vyžadují PRS firmware. Pro D2R
použij test v **Registrace HF/LF**.

## CLI a ověření

```powershell
python -m elatec_uid_tool export-registration-fw --devpack C:\TWN4DevPack520 --reader-model multitech2-usb --hf-format HEX --lf-format DEC
python -m elatec_uid_tool test-registration --port COM7
python -m unittest discover -s tests -v
python scripts/test_registration_firmware.py --devpack C:\TWN4DevPack520
```

Na Linuxu lze pro sestavení zadat `--gcc`, `--objcopy` a `--makeapp-runtime`
(Mono) bez změny běžného Windows postupu. Automatický reálný build test se
aktivuje proměnnými `ELA_TEST_DEVPACK`, `ELA_TEST_GCC`, `ELA_TEST_OBJCOPY`,
`ELA_TEST_MAKEAPP_RUNTIME`. Proprietární SDK není součástí CI.

Přenos 0.1.4 vychází z uživatelova úspěšného testu v Jídelně. Nová konfigurace
0.15 je ověřena testy stavu/SDK adaptéru a sestavením BIX; fyzické chování
nových formátů a obou konkrétních modelů vyžaduje ověření na zařízení.
