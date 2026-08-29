from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Literal


ExpectedFormat = Literal["auto", "decimal", "hexadecimal"]
Encoding = Literal["plain", "wiegand_3_5"]


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
        if self.encoding == "wiegand_3_5":
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


def encode_wiegand_3_5(value_bits_numeric: int) -> tuple[int, int, int, str]:
    """facility (8 bit) + card (16 bit) → 8místný desítkový kód FFFCCCCC."""
    value_24 = value_bits_numeric & 0xFFFFFF
    facility = (value_24 >> 16) & 0xFF
    card = value_24 & 0xFFFF
    encoded = facility * 100_000 + card
    display = f"{facility:03d}{card:05d}"
    return facility, card, encoded, display


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
    }
    score += preferred.get(number_of_bits, min(number_of_bits, 64) * 0.25)

    if first_bit == 0 and number_of_bits == source_bit_count:
        score += 45.0
    if automatic_text_match:
        score += 30.0

    if encoding == "wiegand_3_5":
        # Preferuj přesně 24bitové okno (facility+card) a bajtový offset.
        score += 90.0
        if number_of_bits == 24:
            score += 100.0
        elif number_of_bits > 24:
            # Delší okna fungují jen díky masce 0xFFFFFF – jsou méně přesná.
            score -= 40.0 + (number_of_bits - 24) * 2.0
        if first_bit % 8 == 0:
            score += 25.0

    # Při shodném výsledku preferujeme menší offset.
    score -= first_bit * 0.02
    return score


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

                # ── Wiegand 3+5 (FFFCCCCC) ──────────────────────────────────
                # facility (8 bit) × 100000 + card (16 bit), typicky z 24bit okna
                if expected.format == "decimal" and number_of_bits >= 24:
                    facility, card, encoded, display = encode_wiegand_3_5(numeric)
                    if encoded == expected.numeric_value:
                        automatic_text_match = (
                            display == expected.original.strip()
                            or str(encoded) == expected.normalized_text
                        )
                        key = (
                            rev_bits,
                            rev_bytes,
                            first_bit,
                            number_of_bits,
                            "Decimal",
                            "wiegand_3_5",
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
                                        encoding="wiegand_3_5",
                                    ),
                                    reverse_bit_order=rev_bits,
                                    reverse_byte_order=rev_bytes,
                                    first_bit=first_bit,
                                    number_of_bits=number_of_bits,
                                    output_format="Decimal (Wiegand 3+5)",
                                    output_decimal=display,
                                    output_hex=hex_text,
                                    selected_bits=selected,
                                    is_all_bits=is_all,
                                    encoding="wiegand_3_5",
                                    facility_code=facility,
                                    card_number=card,
                                )
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
