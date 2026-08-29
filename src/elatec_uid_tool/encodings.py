"""Atypické a strukturované převody UID → DB kód.

Vychází z ověřeného PAC/iCLASS FW (H10301 + digit-concat / strip nul),
běžných Wiegand layoutů (H10301 26-bit, 8+16 payload) a praxe AppBlasteru.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal


Encoding = Literal[
    "plain",
    "wiegand_3_5",
    "wiegand_3_5_strip",
    "facility_card_concat",
    "card_16",
    "facility_8",
    "scale_4",
    "scale_6",
    "h10301_3_5",
    "h10301_concat",
    "h10301_card",
    "h10301_strip",
]


@dataclass(frozen=True)
class StructuredHit:
    encoding: Encoding
    facility_code: int | None
    card_number: int | None
    encoded: int
    display: str
    output_format: str
    note: str
    # Preferovaný počet bitů okna, ze kterého hit pochází (pro skóre).
    preferred_bits: int


def split_facility_card_8_16(value: int) -> tuple[int, int]:
    value_24 = value & 0xFFFFFF
    return (value_24 >> 16) & 0xFF, value_24 & 0xFFFF


def encode_wiegand_3_5(value_bits_numeric: int) -> tuple[int, int, int, str]:
    """facility (8 bit) + card (16 bit) → FFFCCCCC (facility×100000+card)."""
    facility, card = split_facility_card_8_16(value_bits_numeric)
    encoded = facility * 100_000 + card
    display = f"{facility:03d}{card:05d}"
    return facility, card, encoded, display


def encode_facility_card_concat(facility: int, card: int) -> tuple[int, str]:
    """PAC digit-concat: FC a card slepí desítkově bez fixní šířky.

    Odpovídá FW FIN_kraceni_kodu_PAC_ID_bez_0/appconfig_spravny_pac_a_dec.c:
    FullCode = FC; while (ID) { FullCode *= 10; ID /= 10; } FullCode += card;
    """
    if card <= 0:
        return facility, str(facility)
    digits = len(str(card))
    encoded = facility * (10**digits) + card
    return encoded, str(encoded)


def strip_leading_zeros(text: str) -> str:
    stripped = text.lstrip("0")
    return stripped if stripped else "0"


def parse_h10301(bits: str) -> tuple[int, int] | None:
    """H10301 / Wiegand 26: P(1) + FC(8) + Card(16) + P(1)."""
    if len(bits) != 26:
        return None
    facility = int(bits[1:9], 2)
    card = int(bits[9:25], 2)
    return facility, card


def _scale(facility: int, card: int, card_digits: int) -> tuple[int, str]:
    encoded = facility * (10**card_digits) + card
    display = f"{facility}{card:0{card_digits}d}"
    return encoded, display


def iter_payload_8_16_hits(numeric: int) -> Iterator[StructuredHit]:
    """Převody z 24bit payloadu (nebo spodních 24 bitů delšího okna)."""
    facility, card, enc, disp = encode_wiegand_3_5(numeric)

    yield StructuredHit(
        encoding="wiegand_3_5",
        facility_code=facility,
        card_number=card,
        encoded=enc,
        display=disp,
        output_format="Decimal (Wiegand 3+5)",
        note="facility×100000+card, 8 číslic FFFCCCCC",
        preferred_bits=24,
    )

    stripped = strip_leading_zeros(disp)
    yield StructuredHit(
        encoding="wiegand_3_5_strip",
        facility_code=facility,
        card_number=card,
        encoded=int(stripped),
        display=stripped,
        output_format="Decimal (Wiegand 3+5, bez vedoucích 0)",
        note="Stejné jako 3+5, ale výstup bez vedoucích nul (PAC/host)",
        preferred_bits=24,
    )

    c_enc, c_disp = encode_facility_card_concat(facility, card)
    yield StructuredHit(
        encoding="facility_card_concat",
        facility_code=facility,
        card_number=card,
        encoded=c_enc,
        display=c_disp,
        output_format="Decimal (PAC digit-concat)",
        note="FC a card slepeny desítkově (Thales/PAC styl)",
        preferred_bits=24,
    )

    yield StructuredHit(
        encoding="card_16",
        facility_code=facility,
        card_number=card,
        encoded=card,
        display=str(card),
        output_format="Decimal (card 16-bit)",
        note="Jen číslo karty (spodních 16 bitů) – typické HID Prox",
        preferred_bits=16,
    )

    yield StructuredHit(
        encoding="facility_8",
        facility_code=facility,
        card_number=card,
        encoded=facility,
        display=str(facility),
        output_format="Decimal (facility 8-bit)",
        note="Jen facility code (horních 8 bitů payloadu)",
        preferred_bits=8,
    )

    for digits, enc_name, label in (
        (4, "scale_4", "Decimal (facility×10000+card)"),
        (6, "scale_6", "Decimal (facility×1000000+card)"),
    ):
        s_enc, s_disp = _scale(facility, card, digits)
        yield StructuredHit(
            encoding=enc_name,  # type: ignore[arg-type]
            facility_code=facility,
            card_number=card,
            encoded=s_enc,
            display=s_disp,
            output_format=label,
            note=f"facility×10^{digits}+card",
            preferred_bits=24,
        )


def iter_h10301_hits(bits: str) -> Iterator[StructuredHit]:
    parsed = parse_h10301(bits)
    if parsed is None:
        return
    facility, card = parsed
    payload = (facility << 16) | card

    for hit in iter_payload_8_16_hits(payload):
        # Mapovat na h10301-* varianty u hlavních typů
        if hit.encoding == "wiegand_3_5":
            yield StructuredHit(
                encoding="h10301_3_5",
                facility_code=facility,
                card_number=card,
                encoded=hit.encoded,
                display=hit.display,
                output_format="Decimal (H10301 → Wiegand 3+5)",
                note="26bit H10301 (skip parity) → facility×100000+card",
                preferred_bits=26,
            )
        elif hit.encoding == "facility_card_concat":
            yield StructuredHit(
                encoding="h10301_concat",
                facility_code=facility,
                card_number=card,
                encoded=hit.encoded,
                display=hit.display,
                output_format="Decimal (H10301 → PAC concat)",
                note="26bit H10301 → digit-concat (PAC FW)",
                preferred_bits=26,
            )
        elif hit.encoding == "card_16":
            yield StructuredHit(
                encoding="h10301_card",
                facility_code=facility,
                card_number=card,
                encoded=hit.encoded,
                display=hit.display,
                output_format="Decimal (H10301 card)",
                note="26bit H10301 → jen card (bits 9–24)",
                preferred_bits=26,
            )
        elif hit.encoding == "wiegand_3_5_strip":
            yield StructuredHit(
                encoding="h10301_strip",
                facility_code=facility,
                card_number=card,
                encoded=hit.encoded,
                display=hit.display,
                output_format="Decimal (H10301 3+5 bez vedoucích 0)",
                note="H10301 → 3+5 → strip leading zeros",
                preferred_bits=26,
            )


def encoding_needs_custom_fw(encoding: Encoding) -> bool:
    return encoding not in ("plain",)
