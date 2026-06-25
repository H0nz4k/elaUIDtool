import argparse
from datetime import datetime
from pathlib import Path
import json

from .analyzer import normalize_raw_hex
from .match_output import print_matches
from .medium_output import print_medium_info, print_reader_info
from .ports import resolve_port, select_port_interactively
from .protocol import ElatecError, SimpleProtocolClient
from .reader_commands import _read
from .tagtypes import get_tag_type_info


def _signature(item):
    return [item.reverse_bit_order, item.reverse_byte_order, item.first_bit, item.number_of_bits, item.output_format]


def _remember(path, key, matches):
    file = Path(path)
    data = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {"media_types": {}}
    media = data["media_types"].setdefault(key, [])
    media.append([_signature(item) for item in matches])
    common = {tuple(item) for item in media[0]}
    for observation in media[1:]:
        common &= {tuple(item) for item in observation}
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(media), [item for item in matches if tuple(_signature(item)) in common]


def command_capture(args):
    port = resolve_port(args.port, args.timeout)
    with SimpleProtocolClient(port, timeout=args.timeout) as client:
        info = client.read_info()
        print_reader_info(info)
        tag = _read(client, info, args.wait, args.poll_interval, args.max_id_bytes)
    kind = get_tag_type_info(tag.tag_type)
    print_medium_info(tag, kind)
    matches = print_matches(tag.id_hex, tag.id_bit_count, args.expected, args.expected_format, args.max_results, args.show_all_candidates)
    if args.sample_store and matches:
        count, common = _remember(args.sample_store, kind.definition, matches)
        print(f"Vzorků typu {kind.definition}: {count}; společných pravidel: {len(common)}")
    return 0


def command_analyze(args):
    bits = args.bits or len(normalize_raw_hex(args.raw)) * 4
    print_matches(args.raw, bits, args.expected, args.expected_format, args.max_results, args.show_all_candidates)
    return 0


def command_interactive(args):
    print("ELATEC UID Tool - interaktivní režim")
    expected = input("Zadej požadovaný kód z databáze: ").strip()
    if not expected:
        raise ElatecError("Požadovaný kód nesmí být prázdný.")
    port = select_port_interactively(args.timeout)
    return command_capture(argparse.Namespace(
        port=port, timeout=args.timeout, wait=args.wait,
        poll_interval=args.poll_interval, max_id_bytes=args.max_id_bytes,
        expected=expected, expected_format="auto", max_results=args.max_results,
        show_all_candidates=args.show_all_candidates,
        sample_store=args.sample_store,
        output=f"results/elatec-{datetime.now():%Y%m%d-%H%M%S}.json",
    ))
