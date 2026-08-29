from __future__ import annotations

from .analyzer import analyze_uid, normalize_raw_hex, raw_decimal


def yes_no(value: bool) -> str:
    return "Ano" if value else "Ne"


_ENCODING_LABELS = {
    "plain": None,
    "wiegand_3_5": "Wiegand 3+5 (FFFCCCCC)",
    "wiegand_3_5_strip": "Wiegand 3+5 bez vedoucích 0",
    "facility_card_concat": "PAC digit-concat (FC+card)",
    "card_16": "Jen card (16 bit)",
    "facility_8": "Jen facility (8 bit)",
    "scale_4": "facility×10000+card",
    "scale_6": "facility×1000000+card",
    "h10301_3_5": "H10301 → Wiegand 3+5",
    "h10301_concat": "H10301 → PAC concat",
    "h10301_card": "H10301 → card",
    "h10301_strip": "H10301 → 3+5 bez vedoucích 0",
}


def _settings(match):
    rows = [
        ("Selected HEX", match.output_hex),
        ("Selected DEC", match.output_decimal),
        ("Reverse Bit Order", yes_no(match.reverse_bit_order)),
        ("Reverse Byte Order", yes_no(match.reverse_byte_order)),
        ("Output Bits", "All Bits" if match.is_all_bits else "Some Bits"),
        ("First Bit", 0 if match.is_all_bits else match.first_bit),
        ("Number of Bits", match.number_of_bits),
        ("Output Format", match.output_format),
    ]
    enc = getattr(match, "encoding", "plain")
    label = _ENCODING_LABELS.get(enc)
    if label:
        rows.append(("Encoding", label))
    if match.facility_code is not None:
        rows.append(("Facility Code", match.facility_code))
    if match.card_number is not None:
        rows.append(("Card Number", match.card_number))
    if enc == "plain":
        rows.append(("Length", "Automatic"))
    else:
        rows.append(("Length", "Custom FW / export-fw"))
    note = getattr(match, "encoding_note", None)
    if note:
        rows.append(("Poznámka", note))
    return tuple(rows)


def _print_settings(match, prefix=""):
    for label, value in _settings(match):
        print(f"{prefix}{label + ':':<20}{value}")
    if getattr(match, "encoding", "plain") != "plain":
        print(
            f"{prefix}Poznámka:           Standardní AppBlaster Decimal nestačí – "
            "použijte export-fw / Vytvořit FW."
        )

def print_matches(raw_hex, bit_count, expected_text, expected_format, max_results, show_all_candidates=False):
    expected, matches = analyze_uid(raw_hex, bit_count, expected_text, expected_format, max_results)
    print("\nANALÝZA\n" + "-" * 72)
    print(f"RAW HEX:           {normalize_raw_hex(raw_hex)}")
    print(f"RAW bitů:          {bit_count}")
    print(f"Celé RAW jako DEC: {raw_decimal(raw_hex, bit_count)}")
    print(f"Očekávaný kód:     {expected.original}")
    print(f"Formát:            {expected.format}")
    if not matches:
        print("\nNebyla nalezena žádná shoda.")
        return matches
    print("\nDOPORUČENÉ NASTAVENÍ APPBLASTERU\n" + "-" * 72)
    _print_settings(matches[0])
    if len(matches) > 1 and not show_all_candidates:
        print(f"\nAlternativy jsou skryté ({len(matches) - 1}).")
        print("Vznikají hlavně ztrátou vedoucích nul v desetinném výstupu.")
        print("Pro výpis použij --show-all-candidates.")
    if show_all_candidates:
        print("\nVŠECHNY ČÍSELNĚ SHODNÉ VARIANTY\n" + "-" * 72)
        for index, match in enumerate(matches, 1):
            print(f"\n#{index}  skóre {match.rank_score:.1f}")
            _print_settings(match, "  ")
    return matches
