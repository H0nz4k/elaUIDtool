from pathlib import Path
import time
from .firmware import find_programming_tools, find_prs_images
from .medium_output import print_medium_info, print_reader_info
from .ports import resolve_port
from .protocol import ElatecError, SimpleProtocolClient
from .tagtypes import get_tag_type_info


def _read(client, info, wait, poll, size):
    client.set_tag_types(info.lf_supported_mask, info.hf_supported_mask)
    print(f"Přilož kartu. Čekám maximálně {wait:.1f} s.")
    end = time.monotonic() + wait
    while time.monotonic() < end:
        tag = client.search_tag(max_id_bytes=size)
        if tag is not None:
            client.set_rf_off()
            return tag
        time.sleep(poll)
    client.set_rf_off()
    raise ElatecError("Médium nebylo nalezeno.")


def command_reader_info(args):
    port = resolve_port(args.port, args.timeout)
    with SimpleProtocolClient(port, timeout=args.timeout) as client:
        print_reader_info(client.read_info())
    return 0


def command_test_medium(args):
    port = resolve_port(args.port, args.timeout)
    with SimpleProtocolClient(port, timeout=args.timeout) as client:
        info = client.read_info()
        print_reader_info(info)
        tag = _read(client, info, args.wait, args.poll_interval, args.max_id_bytes)
    print_medium_info(tag, get_tag_type_info(tag.tag_type))
    return 0


def _show(root):
    if not root.is_dir():
        print(f"Složka nebyla nalezena: {root}")
        return 1
    images = find_prs_images(root)
    tools = find_programming_tools(root)
    print(f"Složka: {root}")
    print(f"PRS image: {len(images)}")
    for item in images:
        print(f"  {item.path}")
    print(f"Nástroje: {len(tools)}")
    for item in tools:
        print(f"  {item}")
    return 0


def command_prepare_reader(args):
    return _show(Path(args.devpack).expanduser().resolve())


def command_update_reader(args):
    print("UPDATE READER – PŘÍPRAVA")
    print("Tato verze pouze kontroluje lokální soubory.")
    return _show(Path(args.devpack).expanduser().resolve())
