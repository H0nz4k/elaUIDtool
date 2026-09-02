"""CLI příkazy pro export TWN4 firmware ze shody."""

from __future__ import annotations

import json
from pathlib import Path

from .analyzer import MatchCandidate, analyze_uid, normalize_raw_hex
from .fw_export import HostChannel, build_firmware, export_channels, match_summary


def _match_from_dict(data: dict) -> MatchCandidate:
    first = data.get("first_bit")
    is_all = bool(data.get("is_all_bits", first is None))
    return MatchCandidate(
        rank_score=float(data.get("rank_score", 0)),
        reverse_bit_order=bool(data["reverse_bit_order"]),
        reverse_byte_order=bool(data["reverse_byte_order"]),
        first_bit=0 if first is None else int(first),
        number_of_bits=int(data["number_of_bits"]),
        output_format=str(data["output_format"]),
        output_decimal=str(data.get("output_decimal", "")),
        output_hex=str(data.get("output_hex", "")),
        selected_bits=str(data.get("selected_bits", "")),
        is_all_bits=is_all,
        encoding=data.get("encoding", "plain"),
        facility_code=data.get("facility_code"),
        card_number=data.get("card_number"),
        encoding_note=data.get("encoding_note"),
    )


def _resolve_match(args) -> tuple[MatchCandidate, int | None]:
    tag_type = getattr(args, "tag_type", None)
    if args.from_json:
        payload = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        matches = payload.get("matches") or []
        if not matches:
            raise ValueError("JSON neobsahuje žádné shody.")
        index = args.match_index
        if index < 0 or index >= len(matches):
            raise ValueError(f"Neplatný --match-index {index} (0..{len(matches) - 1}).")
        item = matches[index]
        # JSON z capture má encoding uvnitř nebo v appblaster
        if "encoding" not in item and "appblaster" in item:
            item = {**item, "encoding": item["appblaster"].get("encoding", "plain")}
            w = item["appblaster"].get("wiegand_3_5") or {}
            item.setdefault("facility_code", w.get("facility_code"))
            item.setdefault("card_number", w.get("card_number"))
        card = payload.get("card") or {}
        if tag_type is None and "tag_type" in card:
            tag_type = int(card["tag_type"])
        return _match_from_dict(item), tag_type

    if not args.raw or not args.expected:
        raise ValueError("Zadej --raw a --expected, nebo --from-json.")

    raw = normalize_raw_hex(args.raw)
    bits = args.bits if args.bits is not None else len(raw) * 4
    _, matches = analyze_uid(
        raw_hex=raw,
        bit_count=bits,
        expected_value=args.expected,
        expected_format=args.expected_format,
        max_results=args.max_results,
    )
    if not matches:
        raise ValueError("Nebyla nalezena žádná shoda pro export FW.")
    index = args.match_index
    if index < 0 or index >= len(matches):
        raise ValueError(f"Neplatný --match-index {index} (0..{len(matches) - 1}).")
    return matches[index], tag_type


def _channels(args) -> list[HostChannel]:
    if args.channel == "both":
        return ["cdc", "uart"]
    return [args.channel]  # type: ignore[list-item]


def command_export_fw(args) -> int:
    match, tag_type = _resolve_match(args)
    print("EXPORT FIRMWARE")
    print("-" * 72)
    print(f"Pravidlo: {match_summary(match)}")
    if tag_type is not None:
        print(f"TagType:  0x{tag_type:02X}")
    print(f"Kanál:    {args.channel}")
    if getattr(args, "base_bix", None):
        print(f"Base BIX: {args.base_bix}")
    print(f"Branch:   {getattr(args, 'branch', '0520')}")
    print()

    results = export_channels(
        match,
        _channels(args),
        tag_type=tag_type,
        devpack=Path(args.devpack) if args.devpack else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        base_bix=Path(args.base_bix) if getattr(args, "base_bix", None) else None,
        branch=getattr(args, "branch", "0520"),
    )
    for item in results:
        print(f"[{item.channel.upper()}]")
        print(f"  appconfig.c: {item.source_c}")
        print(f"  appconfig.h: {item.appconfig_h}")
        print(f"  HEX:         {item.hex_path}")
        print(f"  BIX:         {item.bix_path}")
        print()
    print("Nahraj .bix v AppBlasteru: Program Firmware Image -> Select Image -> Program Image")
    return 0
