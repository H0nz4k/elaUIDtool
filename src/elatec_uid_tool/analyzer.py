from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Literal

from .encodings import (
    Encoding,
    StructuredHit,
    encode_wiegand_3_5,
    iter_h10301_hits,
    iter_payload_8_16_hits,
)


ExpectedFormat = Literal["auto", "decimal", "hexadecimal"]

# Re-export for existing imports
__all__ = [
    "ExpectedFormat",
    "Encoding",
    "ExpectedValue",
    "MatchCandidate",
    "analyze_uid",
    "encode_wiegand_3_5",
    "normalize_raw_hex",
    "parse_expected",
    "raw_decimal",
    "reverse_bit_order",
    "reverse_byte_order",
]


@dataclass(frozen=True)
class ExpectedValue:
    original: str
    format: str
    numeric_value: int
    normalized_text: str


@dataclass(frozen=True)
class MatchCandidate:
    rank_score: float
    reverse_bit_order: bool
    reverse_byte_order: bool
    first_bit: int
    number_of_bits: int
    output_format: str
    output_decimal: str
    output_hex: str
    selected_bits: str
    is_all_bits: bool
    encoding: Encoding = "plain"
    facility_code: int | None = None
    card_number: int | None = None
    encoding_note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def appblaster_settings(self) -> dict:
        settings = {
            "bit_manipulation": {
                "reverse_bit_order": self.reverse_bit_order,
                "reverse_byte_order": self.reverse_byte_order,
            },
            "output_bits": {
                "mode": "all_bits" if self.is_all_bits else "some_bits",
                "first_bit": 0 if self.is_all_bits else self.first_bit,
                "number_of_bits": self.number_of_bits,
            },
            "output_format": self.output_format,
            "encoding": self.encoding,
            "length": "automatic",
        }
        if self.encoding_note:
            settings["note"] = self.encoding_note
        if self.encoding != "plain":
            settings["length"] = "custom_firmware"
            settings["facility_card"] = {
                "facility_code": self.facility_code,
                "card_number": self.card_number,
                "display": self.output_decimal,
                "note": self.encoding_note
                or (
                    "Standardní AppBlaster Decimal nestačí – "
                    "použijte Vytvořit FW / export-fw."
                ),
            }
        if self.encoding in ("wiegand_3_5", "h10301_3_5"):
            settings["length"] = "wiegand_3_5_fixed_8"
            settings["wiegand_3_5"] = {
                "facility_code": self.facility_code,
                "card_number": self.card_number,
                "formula": "facility * 100000 + card",
                "display": f"{self.facility_code:03d}{self.card_number:05d}",
                "note": (
                    "Standardní AppBlaster Decimal nestačí – je potřeba "
                    "vlastní formátování facility×100000+card (8 číslic)."
                ),
            }
        return settings


def normalize_raw_hex(raw_hex: str) -> str:
    value = re.sub(r"[\s:_-]", "", raw_hex).upper()
    if value.startswith("0X"):
        value = value[2:]
    if not value:
        raise ValueError("RAW HEX je prázdný.")
    if not re.fullmatch(r"[0-9A-F]+", value):
        raise ValueError(f"RAW HEX obsahuje neplatné znaky: {raw_hex!r}")
    if len(value) % 2:
        raise ValueError(
            "RAW HEX musí mít sudý počet číslic, aby bylo zachováno pořadí bajtů."
        )
    return value


def parse_expected(value: str, expected_format: ExpectedFormat) -> ExpectedValue:
    text = value.strip()
    if not text:
        raise ValueError("Očekávaný kód je prázdný.")

    fmt = expected_format
    if fmt == "auto":
        if text.lower().startswith("0x") or re.search(r"[A-Fa-f]", text):
            fmt = "hexadecimal"
        else:
            fmt = "decimal"

    if fmt == "decimal":
        if not re.fullmatch(r"\d+", text):
            raise ValueError("Desetinný očekávaný kód musí obsahovat pouze číslice.")
        numeric = int(text, 10)
        normalized = str(numeric)
    elif fmt == "hexadecimal":
        normalized_input = text[2:] if text.lower().startswith("0x") else text
        normalized_input = re.sub(r"[\s:_-]", "", normalized_input)
        if not re.fullmatch(r"[0-9A-Fa-f]+", normalized_input):
            raise ValueError("Hexadecimální očekávaný kód není platný.")
        numeric = int(normalized_input, 16)
        normalized = normalized_input.upper().lstrip("0") or "0"
    else:
        raise ValueError(f"Nepodporovaný formát: {fmt}")

    return ExpectedValue(text, fmt, numeric, normalized)


def bytes_to_bit_string(data: bytes, bit_count: int) -> str:
    if bit_count < 1:
        raise ValueError("Počet bitů musí být kladný.")
    available = len(data) * 8
    if bit_count > available:
        raise ValueError(
            f"Požadováno {bit_count} bitů, ale RAW data mají jen {available}."
        )
    return "".join(f"{byte:08b}" for byte in data)[:bit_count]


def reverse_bit_order(bits: str) -> str:
    return bits[::-1]


def reverse_byte_order(bits: str) -> str:
    if len(bits) % 8:
        raise ValueError(
            "Reverse Byte Order je v MVP podporován jen pro délku dělitelnou 8."
        )
    chunks = [bits[i : i + 8] for i in range(0, len(bits), 8)]
    return "".join(reversed(chunks))


def _transform_bits(
    original_bits: str,
    reverse_bits: bool,
    reverse_bytes: bool,
) -> str | None:
    bits = original_bits
    if reverse_bits:
        bits = reverse_bit_order(bits)
    if reverse_bytes:
        if len(bits) % 8:
            return None
        bits = reverse_byte_order(bits)
    return bits


def _candidate_score(
    *,
    reverse_bits: bool,
    reverse_bytes: bool,
    first_bit: int,
    number_of_bits: int,
    source_bit_count: int,
    automatic_text_match: bool,
    encoding: Encoding = "plain",
) -> float:
    score = 1000.0

    # Jednodušší pravidla mají přednost.
    score -= 120.0 * int(reverse_bits)
    score -= 100.0 * int(reverse_bytes)

    # Bajtově zarovnané konfigurace bývají praktičtější a lépe odpovídají GUI.
    if first_bit % 8 == 0:
        score += 35.0
    if number_of_bits % 8 == 0:
        score += 35.0

    # Běžné identifikační délky.
    preferred = {
        32: 120.0,
        40: 110.0,
        64: 100.0,
        56: 90.0,
        48: 85.0,
        24: 80.0,
        16: 60.0,
        26: 55.0,
        34: 50.0,
        35: 48.0,
        37: 46.0,
        8: 40.0,
    }
    score += preferred.get(number_of_bits, min(number_of_bits, 64) * 0.25)

    if first_bit == 0 and number_of_bits == source_bit_count:
        score += 45.0
    if automatic_text_match:
        score += 30.0

    encoding_bonus = {
        "plain": 0.0,
        "wiegand_3_5": 190.0,
        "wiegand_3_5_strip": 150.0,
        "facility_card_concat": 170.0,
        "h10301_3_5": 200.0,
        "h10301_concat": 185.0,
        "h10301_card": 160.0,
        "h10301_strip": 155.0,
        "card_16": 110.0,
        "facility_8": 40.0,
        "scale_4": 100.0,
        "scale_6": 100.0,
    }
    score += encoding_bonus.get(encoding, 50.0)

    if encoding in (
        "wiegand_3_5",
        "wiegand_3_5_strip",
        "facility_card_concat",
        "scale_4",
        "scale_6",
        "card_16",
        "facility_8",
    ):
        if number_of_bits == 24:
            score += 100.0
        elif number_of_bits > 24:
            score -= 40.0 + (number_of_bits - 24) * 2.0
        if first_bit % 8 == 0:
            score += 25.0

    if encoding.startswith("h10301") and number_of_bits == 26:
        score += 120.0

    # Při shodném výsledku preferujeme menší offset.
    score -= first_bit * 0.02
    return score


def _hit_matches_expected(hit: StructuredHit, expected: ExpectedValue) -> bool:
    if expected.format != "decimal":
        return False
    if hit.encoded == expected.numeric_value:
        return True
    # Přesná textová shoda včetně vedoucích nul (08607342 vs 8607342).
    original = expected.original.strip()
    return hit.display == original or hit.display.lstrip("0") == original.lstrip("0")


def _append_structured(
    candidates: list[MatchCandidate],
    seen: set[tuple],
    *,
    hit: StructuredHit,
    rev_bits: bool,
    rev_bytes: bool,
    first_bit: int,
    number_of_bits: int,
    source_len: int,
    selected: str,
    hex_text: str,
    is_all: bool,
    expected: ExpectedValue,
) -> None:
    if not _hit_matches_expected(hit, expected):
        return
    automatic_text_match = (
        hit.display == expected.original.strip()
        or str(hit.encoded) == expected.normalized_text
    )
    key = (
        rev_bits,
        rev_bytes,
        first_bit,
        number_of_bits,
        hit.output_format,
        hit.encoding,
    )
    if key in seen:
        return
    seen.add(key)
    candidates.append(
        MatchCandidate(
            rank_score=_candidate_score(
                reverse_bits=rev_bits,
                reverse_bytes=rev_bytes,
                first_bit=first_bit,
                number_of_bits=number_of_bits,
                source_bit_count=source_len,
                automatic_text_match=automatic_text_match,
                encoding=hit.encoding,
            ),
            reverse_bit_order=rev_bits,
            reverse_byte_order=rev_bytes,
            first_bit=first_bit,
            number_of_bits=number_of_bits,
            output_format=hit.output_format,
            output_decimal=hit.display,
            output_hex=hex_text,
            selected_bits=selected,
            is_all_bits=is_all,
            encoding=hit.encoding,
            facility_code=hit.facility_code,
            card_number=hit.card_number,
            encoding_note=hit.note,
        )
    )


def analyze_uid(
    raw_hex: str,
    bit_count: int,
    expected_value: str,
    expected_format: ExpectedFormat = "auto",
    max_results: int = 20,
) -> tuple[ExpectedValue, list[MatchCandidate]]:
    normalized_raw = normalize_raw_hex(raw_hex)
    data = bytes.fromhex(normalized_raw)
    original_bits = bytes_to_bit_string(data, bit_count)
    expected = parse_expected(expected_value, expected_format)

    candidates: list[MatchCandidate] = []
    seen: set[tuple] = set()

    transforms = (
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    )

    for rev_bits, rev_bytes in transforms:
        transformed = _transform_bits(original_bits, rev_bits, rev_bytes)
        if transformed is None:
            continue

        source_len = len(transformed)
        for first_bit in range(source_len):
            for number_of_bits in range(1, source_len - first_bit + 1):
                selected = transformed[first_bit : first_bit + number_of_bits]
                numeric = int(selected, 2)
                hex_width = max(1, math.ceil(number_of_bits / 4))
                hex_text = f"{numeric:0{hex_width}X}"
                is_all = first_bit == 0 and number_of_bits == source_len

                # ── prostá shoda DEC / HEX ──────────────────────────────────
                if numeric == expected.numeric_value:
                    if expected.format == "decimal":
                        automatic_text_match = str(numeric) == expected.normalized_text
                        output_format = "Decimal"
                        output_decimal = str(numeric)
                    else:
                        automatic_text_match = f"{numeric:X}" == expected.normalized_text
                        output_format = "Hexadecimal"
                        output_decimal = str(numeric)

                    key = (
                        rev_bits,
                        rev_bytes,
                        first_bit,
                        number_of_bits,
                        output_format,
                        "plain",
                    )
                    if key not in seen:
                        seen.add(key)
                        candidates.append(
                            MatchCandidate(
                                rank_score=_candidate_score(
                                    reverse_bits=rev_bits,
                                    reverse_bytes=rev_bytes,
                                    first_bit=first_bit,
                                    number_of_bits=number_of_bits,
                                    source_bit_count=source_len,
                                    automatic_text_match=automatic_text_match,
                                    encoding="plain",
                                ),
                                reverse_bit_order=rev_bits,
                                reverse_byte_order=rev_bytes,
                                first_bit=first_bit,
                                number_of_bits=number_of_bits,
                                output_format=output_format,
                                output_decimal=output_decimal,
                                output_hex=hex_text,
                                selected_bits=selected,
                                is_all_bits=is_all,
                                encoding="plain",
                            )
                        )

                # ── strukturované převody z 24bit+ payloadu ─────────────────
                if expected.format == "decimal" and number_of_bits >= 24:
                    for hit in iter_payload_8_16_hits(numeric):
                        _append_structured(
                            candidates,
                            seen,
                            hit=hit,
                            rev_bits=rev_bits,
                            rev_bytes=rev_bytes,
                            first_bit=first_bit,
                            number_of_bits=number_of_bits,
                            source_len=source_len,
                            selected=selected,
                            hex_text=hex_text,
                            is_all=is_all,
                            expected=expected,
                        )

                # ── H10301 / Wiegand 26 (PAC iCLASS layout) ────────────────
                if expected.format == "decimal" and number_of_bits == 26:
                    for hit in iter_h10301_hits(selected):
                        _append_structured(
                            candidates,
                            seen,
                            hit=hit,
                            rev_bits=rev_bits,
                            rev_bytes=rev_bytes,
                            first_bit=first_bit,
                            number_of_bits=number_of_bits,
                            source_len=source_len,
                            selected=selected,
                            hex_text=hex_text,
                            is_all=is_all,
                            expected=expected,
                        )

    candidates.sort(
        key=lambda item: (
            -item.rank_score,
            item.reverse_bit_order,
            item.reverse_byte_order,
            item.first_bit,
            -item.number_of_bits,
        )
    )
    return expected, candidates[:max_results]


def raw_decimal(raw_hex: str, bit_count: int) -> int:
    normalized = normalize_raw_hex(raw_hex)
    bits = bytes_to_bit_string(bytes.fromhex(normalized), bit_count)
    return int(bits, 2)
