# FW builder · elaUIDtool 0.6.0

Builder vytváří vlastní TWN4 User App **BLD0.60** z pravidel pro UID. Pracuje
s **TWN4 MULTITECH 2 USB** a **TWN4 MULTITECH 3 M LF HF**, používá lokální
DevPack 5.20 a jeho původní systémové obrazy. SDK není součástí aplikace.

## Z nalezeného čísla na opakovatelné pravidlo

1. V **Porovnání** zadej RAW UID a číslo z cílového systému, nebo použij
   **Načtení karty** s PRS firmwarem.
2. U shody klikni **Upravit ve FW builderu**. V tabulce všech kandidátů lze
   vybrat konkrétní pravidlo a použít stejné tlačítko.
3. Builder převezme reverzi, bitové okno i konverzi a vloží načtené UID do náhledu.
   Při známém TagType omezí technologie na tento typ.
4. Zkontroluj výsledek a uprav signalizaci nebo výstup. Pro další kontrolu
   změň RAW UID v náhledu na jinou kartu.
5. Vyber čtečku podle fotografie a klikni **Vytvořit BIX**.
6. Ulož BIX a nahraj ho v AppBlasteru přes **Program Firmware Image**.

Firmware obsahuje **pravidlo pro další karty**, nikoli pevně zadané číslo jedné
karty. HF a LF mají samostatná pravidla. Pokud vybereš libovolné technologie,
stejné pravidlo se použije na všechny povolené typy daného pásma.

## Data a konverze

Úpravy probíhají v tomto pořadí:

1. reverze všech platných bitů, potom reverze celých bajtů;
2. výběr bitů zleva od bitu 0 (`Počet bitů = 0` znamená do konce);
3. AND maska, potom XOR maska; HEX masky se zarovnávají zprava;
4. převod čísla nebo strukturovaný facility/card formát;
5. HEX / DEC / BIN / OCT / tisknutelné ASCII;
6. odstranění úvodních nul, požadovaná délka, text `00`, malá písmena;
7. HEX oddělovač bajtů, prefix, suffix, konec řádku.

| Volba | Chování |
|---|---|
| Automatická délka | HEX zachová délku vybraných bitů; DEC/BIN/OCT nemají doplněné nuly |
| Minimální délka | Kratší výstup se doplní zleva; delší zůstane celý |
| Přesná délka | Kratší se doplní; delší je chyba, nikdy se potichu nekrátí |
| ASCII | Celé bajty 0x20–0x7E; NUL a netisknutelné bajty jsou chyba |
| AND/XOR | Maska nesmí přesahovat vybrané bity |
| Reverze bajtů | Platná délka RAW musí být dělitelná osmi |
| Prefix/suffix | Nejvýše 32 ASCII znaků pro každé pole, s `\r`, `\n`, `\t`, `\b`, `\e`, `\\` |

Obecný UID režim podporuje až **256 bitů**, včetně přesného DEC převodu bez
plovoucí čárky nebo přetečení 64bitového čísla. RAW vstup do náhledu má celý
počet bajtů; platných bitů může být méně. Wiegand/PAC payload používá spodních
24 bitů vybraného okna. H10301 vyžaduje přesně 26 bitů a vynechá oba paritní
bity; neověřuje jejich paritu. Tyto formáty čtou obsah UID, nevytvářejí fyzický
Wiegand výstup na vodičích.

Vestavěné předvolby obsahují původní UID, DEC, reverzi bitů/bajtů, EM s
vynecháním prvního bajtu, reverzi + `00`, Wiegand 3+5, PAC, H10301,
pouze číslo karty a HEX s dvojtečkami. Prefix, suffix a `00` jsou textové
úpravy, ne numerické operace na hodnotě UID.

## Pípání a LED

Zvlášť lze nastavit **zapnutí**, **jeden čip**, **HF+LF dvojici** a **chybu**:

- hlasitost 0–100 %, frekvenci 100–10000 Hz;
- počet pípnutí a počet bliknutí 0–10;
- červenou, zelenou, obě LED nebo zhasnuto;
- délku pulzu a pauzu 10–1000 ms.

Pípání a blikání začíná ve stejný okamžik. Hlasitost 0 nebo počet pípnutí 0
vypne zvuk. Po vzoru se obnoví klidová LED. Delší vzory úměrně prodlouží
obsluhu události. Default při jednom čipu je jeden 60ms pulz, u dvojice dva.

## Čtení a výstup

| Rozhraní | Systémový základ |
|---|---|
| USB CDC / virtuální COM | Původní Multi CDC 5.20 nebo rodiny CCx/MCx/NCx |
| USB klávesnice | Původní Multi Keyboard 5.20 nebo rodiny CKx/MKx/NKx |
| UART COM1 | CDC základ; 8 datových bitů, baud/parita/stop bity podle projektu |

Klávesnice používá vlastní keyboard OS obrazy, nikoli pouze jiné PID CDC.
SDK podporuje anglické, německé a francouzské rozložení, Alt kódy a interval
odesílání znaků. USB sériové číslo může být vypnuté, UID zařízení nebo výrobní
číslo. Remote Wakeup je volitelné. UART vyžaduje skutečně vyvedené rozhraní
modulu; USB stolní čtečka používá CDC nebo klávesnici.

Technologie se při startu protnou s maskou skutečně podporovanou/licencovanou
na zařízení. BLE a NFC P2P se nepovažují za fyzické LF/HF karty. Odebrání
karty se potvrzuje po nastavené době bez detekce; výchozí je 300 ms.
Opakování držené karty je vypnuté, volitelně lze zadat periodu od 100 ms.
Vypnutí HF/LF ze seznamu znamená vypnutí daného pásma. Prázdná obě pásma
jsou neplatná konfigurace.

## Režim registrace Jídelny

Používá osvědčený stavový automat D2R: nejprve hledá HF, bez výsledku
střídá pásma, po první technologii hledá pouze druhou. Teprve poté odešle:

| Nalezeno | Skutečné výstupní řádky |
|---|---|
| HF + LF | HF + CR, pak LF + CR |
| Jen HF | HF + CR, pak prázdný CR k ukončení druhého čtení |
| Jen LF | LF + CR, pak prázdný CR k ukončení druhého čtení |

Jedno přiložení, bez zvedání mezi kódy. Pár přežije zavření a znovuotevření
COM po prvním kódu. Doba hledání druhé technologie je 2000 ms; předání mezi
řádky alespoň 200 ms; přepnutí RF 100 ms. Vše lze upravit v daných mezích.
Na další kartu se čeká až po odebrání předchozí.

Tento režim vyžaduje CDC, CR a vypnuté opakování. Pravidla musí vracet
nenulový velký HEX nebo DEC **do 16 znaků**, bez textových prefixů/suffixů.
RAW UID smí mít nejvýše 64 bitů. Shodné výsledné identifikátory se odmítnou
i po odstranění úvodních nul. Dlouhé DEC se odmítne, použij HEX nebo vědomě
zvol vhodné datové okno. Zachycení obou technologií není důkaz, že fyzicky
patří ke stejné kartě; přikládej vždy jednu kartu.

Test **Registrace HF/LF → Ověřit jednu kartu** přijímá D2R0.15 i registrační
BLD0.60. Testuje skutečné řádky a COM handoff, bez DB. Obecný UID builder
není PRS firmware a neodpovídá příkazům záložky **Čtečka**.

## Předvolby a výstupní soubory

Vlastní předvolba uloží celý projekt do lokálního nastavení. JSON lze
exportovat a později importovat. Název projektu pojmenuje předvolbu; načtením
vestavěné předvolby se obnoví všechny její volby. Export BIX uloží:

- `.bix` — obraz k nahrání;
- `.project.json` — celý upravitelný projekt;
- `.json` — manifest, SHA-256, základ a použité volby;
- `.sources.zip` — generované C/H zdroje a projekt, bez proprietárního SDK;
- build log, ELF/HEX/map — pro lokální kontrolu sestavení.

Název BIX obsahuje model a otisk celého projektu; odlišné konfigurace se
nepřepíšou. Build ověří všechny tři nezměněné OS obrazy a vrací BIX až po
úspěšném dokončení. Přesný hardware stále vyžaduje praktický test.

## CLI

```bash
elatec-uid project-from-match --raw 813F9A04 --expected 049A3F81 --expected-format hexadecimal --tag-type 0x80 --output reader.project.json
elatec-uid preview-project --project reader.project.json --raw 813F9A04 --band HF
elatec-uid build-project --project reader.project.json --devpack C:\\TWN4DevPack520
```

Z výsledků lze použít `--from-json capture.json --match-index 0`; index je
od nuly. Na Linuxu build vyžaduje vlastní ARM GCC/objcopy a Mono přes
`--gcc`, `--objcopy`, `--makeapp-runtime`.

## Rozsah

Builder pokrývá **UID konverze a registraci HF/LF**. Nepokrývá čtení
chráněných MIFARE sektorů, DESFire souborů, LEGIC segmentů, správu klíčů,
OSDP, BLE ani bezpečnostní provisioning zařízení. Neimportuje vendor `.abp`
projekty; používá vlastní validovaný JSON. AppBlaster zůstává nástrojem pro
nahrání BIX. Referenční popis konfigurovatelných projektů:
ELATEC *TWN4 AppBlaster User Guide*, DocRev13, sekce 8.
