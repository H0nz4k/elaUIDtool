"""Generování TWN4 User App (.bix) z nalezené MatchCandidate shody."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import textwrap
from typing import Literal

from .analyzer import MatchCandidate

HostChannel = Literal["cdc", "uart"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEVPACK = REPO_ROOT / "elafiles"
EXPORT_DIR = REPO_ROOT / "FW_elatec" / "export"


@dataclass(frozen=True)
class FirmwareExportResult:
    channel: HostChannel
    source_c: Path
    hex_path: Path
    bix_path: Path
    match_summary: str


def _c_bool(value: bool) -> str:
    return "true" if value else "false"


def _tag_masks(tag_type: int | None) -> tuple[str, str]:
    """Vrátí C výrazy pro LFTAGTYPES / HFTAGTYPES."""
    if tag_type is None:
        return (
            "(TAGMASK(LFTAG_EM4102))",
            "(TAGMASK(HFTAG_MIFARE))",
        )
    if tag_type >= 0x80:
        return ("(NOTAG)", f"(TAGMASK(0x{tag_type:02X}))")
    return (f"(TAGMASK(0x{tag_type:02X}))", "(NOTAG)")


def _radix(match: MatchCandidate) -> int:
    if match.encoding != "plain":
        return 10
    if "Hex" in match.output_format:
        return 16
    return 10


def match_summary(match: MatchCandidate) -> str:
    parts = [
        f"revBit={match.reverse_bit_order}",
        f"revByte={match.reverse_byte_order}",
        f"first={match.first_bit}",
        f"bits={match.number_of_bits}",
        f"fmt={match.output_format}",
        f"enc={match.encoding}",
    ]
    if match.facility_code is not None:
        parts.append(f"fac={match.facility_code}")
    if match.card_number is not None:
        parts.append(f"card={match.card_number}")
    return ", ".join(parts)


def _format_block_structured(encoding: str) -> str:
    """C formátování po naplnění CardData (MSB-first)."""
    if encoding.startswith("h10301"):
        extract = textwrap.dedent(
            """\
            unsigned int facility = 0;
            unsigned int card = 0;
            int i;
            if (CardDataBitCnt < 26)
                return false;
            for (i = 1; i <= 8; i++)
                facility = (facility << 1) | (unsigned int)GetBitMSB(CardData, i);
            for (i = 9; i <= 24; i++)
                card = (card << 1) | (unsigned int)GetBitMSB(CardData, i);
            """
        )
    else:
        extract = textwrap.dedent(
            """\
            unsigned int value24 = 0;
            unsigned int facility;
            unsigned int card;
            int bit;
            if (CardDataBitCnt < 24)
                return false;
            for (bit = 0; bit < 24; bit++)
            {
                if (GetBitMSB(CardData, bit))
                    value24 |= (1u << (23 - bit));
            }
            facility = (value24 >> 16) & 0xFFu;
            card = value24 & 0xFFFFu;
            """
        )

    if encoding in ("wiegand_3_5", "h10301_3_5"):
        finish = (
            'sprintf(CardString, "%08u", facility * 100000u + card);\n'
            "return true;"
        )
    elif encoding in ("wiegand_3_5_strip", "h10301_strip"):
        finish = (
            'sprintf(CardString, "%u", facility * 100000u + card);\n'
            "return true;"
        )
    elif encoding in ("facility_card_concat", "h10301_concat"):
        finish = textwrap.dedent(
            """\
            {
                unsigned int code = facility;
                unsigned int temp = card;
                while (temp >= 1u)
                {
                    code *= 10u;
                    temp /= 10u;
                }
                code += card;
                sprintf(CardString, "%u", code);
                return true;
            }
            """
        ).rstrip()
    elif encoding in ("card_16", "h10301_card"):
        finish = 'sprintf(CardString, "%u", card);\nreturn true;'
    elif encoding == "facility_8":
        finish = 'sprintf(CardString, "%u", facility);\nreturn true;'
    elif encoding == "scale_4":
        finish = (
            'sprintf(CardString, "%u", facility * 10000u + card);\n'
            "return true;"
        )
    elif encoding == "scale_6":
        finish = (
            'sprintf(CardString, "%u", facility * 1000000u + card);\n'
            "return true;"
        )
    else:
        raise ValueError(f"Neznámé encoding pro FW: {encoding}")

    return "{\n" + textwrap.indent(extract + finish, "    ") + "\n}"


def generate_app_source(
    match: MatchCandidate,
    *,
    channel: HostChannel,
    tag_type: int | None = None,
    app_chars: str = "EXP",
    app_version: int = 0x201,
) -> str:
    """Vygeneruje kompletní App_*.c podle shody."""
    del app_chars, app_version  # reserved for future APPCHARS/APPVERSION macros
    host = "CHANNEL_USB" if channel == "cdc" else "CHANNEL_COM1"
    lf_mask, hf_mask = _tag_masks(tag_type)
    radix = _radix(match)
    first_bit = 0 if match.is_all_bits else match.first_bit
    num_bits = match.number_of_bits
    rev_bit = _c_bool(match.reverse_bit_order)
    rev_byte = _c_bool(match.reverse_byte_order)
    structured = match.encoding != "plain"

    uart_block = ""
    if channel == "uart":
        uart_block = textwrap.dedent(
            """\
            {
                TCOMParameters COMParameters;
                COMParameters.BaudRate = 9600;
                COMParameters.WordLength = COM_WORDLENGTH_8;
                COMParameters.Parity = COM_PARITY_NONE;
                COMParameters.StopBits = COM_STOPBITS_1;
                COMParameters.FlowControl = COM_FLOWCONTROL_NONE;
                SetCOMParameters(CHANNEL_COM1, &COMParameters);
            }
            """
        )

    helper_getbit = ""
    if structured:
        helper_getbit = textwrap.dedent(
            """\
            static int GetBitMSB(const byte *bits, int bitIndex)
            {
                int byteIndex = bitIndex / 8;
                int bitInByte = 7 - (bitIndex % 8);
                return (bits[byteIndex] >> bitInByte) & 1;
            }

            """
        )
        format_block = _format_block_structured(match.encoding)
    elif radix == 16:
        format_block = textwrap.dedent(
            f"""\
            {{
                int minDigits = ({num_bits} + 7) / 8 * 2;
                int maxDigits = minDigits;
                if (maxDigits > MaxCardStringLen)
                    maxDigits = MaxCardStringLen;
                if (minDigits > maxDigits)
                    minDigits = maxDigits;
                ConvertBinaryToString(CardData, 0, CardDataBitCnt, CardString, 16, minDigits, maxDigits);
                return true;
            }}
            """
        )
    else:
        format_block = textwrap.dedent(
            """\
            {
                int maxDigits = MaxCardStringLen;
                ConvertBinaryToString(CardData, 0, CardDataBitCnt, CardString, 10, 1, maxDigits);
                return true;
            }
            """
        )

    return f"""\
/* Auto-generated by elatec-uid-tool – do not edit by hand.
 * Rule: {match_summary(match)}
 * Channel: {channel} ({host})
 */
#include "twn4.sys.h"
#include "apptools.h"

#define EXP_HOST_CHANNEL {host}
#define CARDTIMEOUT 2000UL
#define MAXCARDSTRINGLEN 64
#define LFTAGTYPES {lf_mask}
#define HFTAGTYPES {hf_mask}

#define CFG_REVERSE_BIT  {rev_bit}
#define CFG_REVERSE_BYTE {rev_byte}
#define CFG_FIRST_BIT    {first_bit}
#define CFG_NUM_BITS     {num_bits}

static void ReverseBitOrder(byte *Dest, const byte *Source, int BitCnt)
{{
    int i;
    for (i = 0; i < ((BitCnt + 7) / 8); i++)
        Dest[i] = 0;
    for (i = 0; i < BitCnt; i++)
        CopyBits(Dest, i, Source, BitCnt - 1 - i, 1);
}}

static void ReverseByteOrder(byte *Buf, int BitCnt)
{{
    int bytes = BitCnt / 8;
    int i;
    byte tmp;
    if (BitCnt % 8)
        return;
    for (i = 0; i < bytes / 2; i++)
    {{
        tmp = Buf[i];
        Buf[i] = Buf[bytes - 1 - i];
        Buf[bytes - 1 - i] = tmp;
    }}
}}

{helper_getbit}bool ReadCardData(int TagType, const byte *ID, int IDBitCnt, char *CardString, int MaxCardStringLen)
{{
    byte Work[40];
    byte Temp[40];
    byte CardData[40];
    int CardDataBitCnt;
    int i;
    int workBits = IDBitCnt;

    (void)TagType;
    CardString[0] = 0;

    if (IDBitCnt < 1 || IDBitCnt > (int)sizeof(Work) * 8)
        return false;

    for (i = 0; i < ((IDBitCnt + 7) / 8); i++)
        Work[i] = ID[i];

    if (CFG_REVERSE_BIT)
    {{
        ReverseBitOrder(Temp, Work, workBits);
        for (i = 0; i < ((workBits + 7) / 8); i++)
            Work[i] = Temp[i];
    }}

    if (CFG_REVERSE_BYTE)
    {{
        if (workBits % 8)
            return false;
        ReverseByteOrder(Work, workBits);
    }}

    if (CFG_FIRST_BIT < 0 || CFG_NUM_BITS < 1)
        return false;
    if (CFG_FIRST_BIT + CFG_NUM_BITS > workBits)
        return false;

    for (i = 0; i < (int)sizeof(CardData); i++)
        CardData[i] = 0;
    CopyBits(CardData, 0, Work, CFG_FIRST_BIT, CFG_NUM_BITS);
    CardDataBitCnt = CFG_NUM_BITS;

{textwrap.indent(format_block.rstrip(), "    ")}
}}

void OnStartup(void)
{{
    LEDInit(REDLED | GREENLED);
    LEDOn(GREENLED);
    LEDOff(REDLED);
    SetVolume(30);
    BeepLow();
    BeepHigh();
{textwrap.indent(uart_block.rstrip(), "    ") if uart_block else ""}
    SetHostChannel(EXP_HOST_CHANNEL);
    SetTagTypes(LFTAGTYPES, HFTAGTYPES);
}}

void OnNewCardFound(const char *CardString)
{{
    HostWriteString(CardString);
    HostWriteString("\\r");
    LEDOff(GREENLED);
    LEDOn(REDLED);
    LEDBlink(REDLED, 500, 500);
    SetVolume(100);
    BeepHigh();
}}

void OnCardTimeout(const char *CardString)
{{
    (void)CardString;
    LEDOn(GREENLED);
    LEDOff(REDLED);
}}

void OnCardDone(void)
{{
}}

int main(void)
{{
    char OldCardString[MAXCARDSTRINGLEN + 1];
    OnStartup();
    OldCardString[0] = 0;
    while (true)
    {{
        int TagType;
        int IDBitCnt;
        byte ID[32];
        if (SearchTag(&TagType, &IDBitCnt, ID, sizeof(ID)))
        {{
            char NewCardString[MAXCARDSTRINGLEN + 1];
            if (ReadCardData(TagType, ID, IDBitCnt, NewCardString, sizeof(NewCardString) - 1))
            {{
                if (strcmp(NewCardString, OldCardString) != 0)
                {{
                    strcpy(OldCardString, NewCardString);
                    OnNewCardFound(NewCardString);
                }}
                StartTimer(CARDTIMEOUT);
            }}
            OnCardDone();
        }}
        if (TestTimer())
        {{
            OnCardTimeout(OldCardString);
            OldCardString[0] = 0;
        }}
    }}
}}
"""


def _toolchain(devpack: Path) -> dict[str, Path]:
    tools = devpack / "Tools"
    paths = {
        "gcc": tools / "Yagarto-20110328" / "bin" / "arm-none-eabi-gcc.exe",
        "objcopy": tools / "Yagarto-20110328" / "bin" / "arm-none-eabi-objcopy.exe",
        "makeapp": tools / "makeapp.exe",
        "sys": tools / "sys",
        "base_bix": devpack / "Firmware" / "TWN4_xCx520_STD207_Multi_CDC_Standard.bix",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Chybí součásti DevPacku: "
            + ", ".join(f"{m}={paths[m]}" for m in missing)
        )
    return paths


def build_firmware(
    match: MatchCandidate,
    *,
    channel: HostChannel = "cdc",
    tag_type: int | None = None,
    devpack: Path | None = None,
    output_dir: Path | None = None,
) -> FirmwareExportResult:
    """Vygeneruje C, sestaví .hex a zabalí .bix."""
    pack = (devpack or DEFAULT_DEVPACK).resolve()
    out = (output_dir or (EXPORT_DIR / "out")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tools = _toolchain(pack)

    suffix = channel.upper()
    src = out / f"App_EXP_{suffix}.c"
    elf = out / f"App_EXP_{suffix}.elf"
    hex_path = out / f"App_EXP_{suffix}.hex"
    map_path = out / f"App_EXP_{suffix}.map"
    lst_path = out / f"App_EXP_{suffix}.lst"
    bix = out / f"TWN4_xCx520_EXP_{suffix}.bix"

    src.write_text(
        generate_app_source(match, channel=channel, tag_type=tag_type),
        encoding="utf-8",
        newline="\n",
    )

    sys_dir = tools["sys"]
    gcc_cmd = [
        str(tools["gcc"]),
        "-std=c99",
        "-mcpu=cortex-m0",
        "-Os",
        "-ffunction-sections",
        "-gdwarf-2",
        "-mthumb",
        "-fomit-frame-pointer",
        "-Wall",
        "-Wstrict-prototypes",
        f"-Wa,-ahlms={lst_path}",
        "-DAPPCHARS=EXP",
        "-DAPPVERSION=0x201",
        f"-I{sys_dir}",
        str(sys_dir / "twn4.crt.c"),
        str(src),
        "-nostartfiles",
        f"-T{sys_dir / 'app.ld'}",
        f"-Wl,--gc-sections,-e,AppHeader,--no-print-gc-sections,-Map={map_path},--cref,--no-warn-mismatch",
        str(sys_dir / "libapp.a"),
        "-lc",
        "-o",
        str(elf),
    ]
    result = subprocess.run(gcc_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "GCC selhal při sestavení FW.\n"
            + (result.stderr or result.stdout or "")
        )

    obj = subprocess.run(
        [str(tools["objcopy"]), "-O", "ihex", str(elf), str(hex_path)],
        capture_output=True,
        text=True,
    )
    if obj.returncode != 0:
        raise RuntimeError("objcopy selhal.\n" + (obj.stderr or obj.stdout or ""))

    make = subprocess.run(
        [
            str(tools["makeapp"]),
            "-v4",
            "-tTWN4",
            "-nTWN4",
            f"-i{tools['base_bix']}",
            f"-h{hex_path}",
            f"-o{bix}",
        ],
        capture_output=True,
        text=True,
    )
    if make.returncode != 0:
        raise RuntimeError("makeapp selhal.\n" + (make.stderr or make.stdout or ""))

    return FirmwareExportResult(
        channel=channel,
        source_c=src,
        hex_path=hex_path,
        bix_path=bix,
        match_summary=match_summary(match),
    )


def export_channels(
    match: MatchCandidate,
    channels: list[HostChannel],
    **kwargs,
) -> list[FirmwareExportResult]:
    return [build_firmware(match, channel=ch, **kwargs) for ch in channels]
