"""Služební vrstva GUI – volá existující elatec_uid_tool bez úprav zdrojového kódu."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Callable

from elatec_uid_tool import __version__
from elatec_uid_tool.analyzer import (
    MatchCandidate,
    analyze_uid,
    normalize_raw_hex,
    raw_decimal,
)
from elatec_uid_tool.ports import (
    is_probable_elatec_port,
    recommended_port_index,
    resolve_port_selection,
)
from elatec_uid_tool.protocol import (
    ElatecError,
    ReaderInfo,
    SerialCommunicationError,
    SimpleProtocolClient,
    TagRead,
    enumerate_ports,
)
from elatec_uid_tool.fw_export import HostChannel, build_firmware
from elatec_uid_tool.tagtypes import decode_supported_masks, get_tag_type_info


@dataclass(frozen=True)
class PortEntry:
    device: str
    description: str
    hwid: str
    is_probable_elatec: bool
    list_index: int


@dataclass(frozen=True)
class CaptureResult:
    reader_info: ReaderInfo
    tag: TagRead
    tag_info: dict[str, Any]
    expected: str
    expected_format: str
    matches: list[MatchCandidate]
    raw_decimal: str


def list_ports() -> tuple[list[PortEntry], int | None]:
    ports = enumerate_ports()
    recommended = recommended_port_index(ports)
    entries = [
        PortEntry(
            device=device,
            description=description,
            hwid=hwid,
            is_probable_elatec=is_probable_elatec_port((device, description, hwid)),
            list_index=index,
        )
        for index, (device, description, hwid) in enumerate(ports, start=1)
    ]
    return entries, recommended


def resolve_port(device_or_index: str, ports: list[PortEntry]) -> tuple[str, str | None]:
    raw_ports = [(p.device, p.description, p.hwid) for p in ports]
    default_index = recommended_port_index(raw_ports)
    return resolve_port_selection(device_or_index, raw_ports, default_index)


def read_reader_info(port: str, timeout: float = 1.2) -> ReaderInfo:
    try:
        with SimpleProtocolClient(port, timeout=timeout) as client:
            return client.read_info()
    except SerialCommunicationError as exc:
        raise ElatecError(
            f"Čtečka na {port} neodpovídá protokolu ELATEC Simple Protocol.\n\n"
            "Je potřeba PRS firmware (Simple Protocol).\n"
            f"Technický detail: {exc}"
        ) from exc


def explain_port_error(port: str | None, error: Exception) -> str:
    text = str(error)
    lower = text.lower()
    device = port or "COM port"
    port_busy = (
        "nelze otevřít" in lower
        or "could not open" in lower
        or "access is denied" in lower
        or "permission" in lower
        or "being used" in lower
        or "používá appblaster" in lower
    )
    if port_busy:
        return (
            f"Port {device} se nepodařilo otevřít.\n\n"
            "Čtečka je v seznamu zařízení viditelná, ale port pravděpodobně "
            "používá jiná aplikace – např. AppBlaster Director, sériový terminál "
            "nebo jiný nástroj pracující s COM portem.\n\n"
            "Zavři tyto programy a zkus akci zopakovat.\n\n"
            f"Detail: {text}"
        )
    return text


def reader_info_to_dict(info: ReaderInfo) -> dict[str, Any]:
    supported = decode_supported_masks(info.lf_supported_mask, info.hf_supported_mask)
    return {
        "port": info.port,
        "version": info.version,
        "device_type": info.device_type,
        "device_type_hex": f"0x{info.device_type:02X}",
        "lf_supported_mask": f"0x{info.lf_supported_mask:08X}",
        "hf_supported_mask": f"0x{info.hf_supported_mask:08X}",
        "has_prs_firmware": "PRS" in info.version.upper(),
        "supported_technologies": [
            {
                "tag_type": f"0x{item.tag_type:02X}",
                "group": item.group,
                "frequency": item.frequency,
                "name": item.name,
            }
            for item in supported
        ],
    }


def match_to_display(match: MatchCandidate) -> dict[str, Any]:
    mode = "All Bits" if match.is_all_bits else "Some Bits"
    length = "Automatic" if match.encoding == "plain" else "Custom FW"
    return {
        "rank_score": match.rank_score,
        "output_hex": match.output_hex,
        "output_decimal": match.output_decimal,
        "reverse_bit_order": match.reverse_bit_order,
        "reverse_byte_order": match.reverse_byte_order,
        "output_bits_mode": mode,
        "first_bit": match.first_bit if not match.is_all_bits else None,
        "number_of_bits": match.number_of_bits,
        "output_format": match.output_format,
        "encoding": match.encoding,
        "encoding_note": match.encoding_note,
        "facility_code": match.facility_code,
        "card_number": match.card_number,
        "selected_bits": match.selected_bits,
        "is_all_bits": match.is_all_bits,
        "length": length,
        "appblaster": match.appblaster_settings(),
    }


def match_from_display(data: dict[str, Any]) -> MatchCandidate:
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


def export_firmware_bix(
    match_data: dict[str, Any],
    channel: HostChannel,
    *,
    tag_type: int | None = None,
) -> Path:
    match = match_from_display(match_data)
    result = build_firmware(match, channel=channel, tag_type=tag_type)
    return result.bix_path


def run_offline_analysis(
    raw_hex: str,
    bit_count: int | None,
    expected: str,
    expected_format: str = "auto",
    max_results: int = 10,
) -> dict[str, Any]:
    raw = normalize_raw_hex(raw_hex)
    bits = bit_count if bit_count is not None else len(raw) * 4
    expected_parsed, matches = analyze_uid(
        raw_hex=raw,
        bit_count=bits,
        expected_value=expected,
        expected_format=expected_format,
        max_results=max_results,
    )
    return {
        "raw_hex": raw,
        "bit_count": bits,
        "raw_decimal": raw_decimal(raw, bits),
        "expected": expected_parsed.original,
        "expected_format": expected_parsed.format,
        "matches": [match_to_display(m) for m in matches],
    }


def capture_and_analyze(
    port: str,
    expected: str,
    expected_format: str = "auto",
    *,
    timeout: float = 1.2,
    wait: float = 30.0,
    poll_interval: float = 0.12,
    max_id_bytes: int = 32,
    max_results: int = 10,
    on_progress: Callable[[str], None] | None = None,
) -> CaptureResult:
    if on_progress:
        on_progress("Připojuji se k čtečce…")

    with SimpleProtocolClient(port, timeout=timeout) as client:
        try:
            info = client.read_info()
        except SerialCommunicationError as exc:
            raise ElatecError(
                f"Čtečka na {port} neodpovídá protokolu ELATEC Simple Protocol.\n\n"
                "Je potřeba PRS firmware (Simple Protocol).\n"
                f"Technický detail: {exc}"
            ) from exc

        if on_progress:
            on_progress("Aktivuji podporované technologie…")
        client.set_tag_types(info.lf_supported_mask, info.hf_supported_mask)

        if on_progress:
            on_progress(f"Přilož kartu (čekám max. {wait:.0f} s)…")

        deadline = time.monotonic() + wait
        tag: TagRead | None = None
        while time.monotonic() < deadline:
            tag = client.search_tag(max_id_bytes)
            if tag is not None:
                break
            time.sleep(poll_interval)

        if tag is None:
            raise ElatecError("V časovém limitu nebyla nalezena karta.")

        try:
            client.set_rf_off()
        except ElatecError:
            pass

    tag_info_obj = get_tag_type_info(tag.tag_type)
    tag_info = {
        "tag_type": f"0x{tag.tag_type:02X}",
        "definition": tag_info_obj.definition,
        "name": tag_info_obj.name,
        "group": tag_info_obj.group,
        "frequency": tag_info_obj.frequency,
    }

    _, matches = analyze_uid(
        raw_hex=tag.id_hex,
        bit_count=tag.id_bit_count,
        expected_value=expected,
        expected_format=expected_format,
        max_results=max_results,
    )

    return CaptureResult(
        reader_info=info,
        tag=tag,
        tag_info=tag_info,
        expected=expected,
        expected_format=expected_format,
        matches=matches,
        raw_decimal=raw_decimal(tag.id_hex, tag.id_bit_count),
    )


def capture_result_to_dict(result: CaptureResult) -> dict[str, Any]:
    return {
        "reader": reader_info_to_dict(result.reader_info),
        "card": {
            **result.tag_info,
            "raw_id_hex": result.tag.id_hex,
            "raw_bit_count": result.tag.id_bit_count,
            "raw_decimal": result.raw_decimal,
        },
        "expected": {
            "value": result.expected,
            "format": result.expected_format,
        },
        "matches": [match_to_display(m) for m in result.matches],
    }


def save_capture_json(result: CaptureResult, output: Path) -> Path:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    tag_info_obj = get_tag_type_info(result.tag.tag_type)
    data = {
        "schema": 1,
        "tool": {"name": "elatec-uid-tool-gui", "version": __version__},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reader": asdict(result.reader_info),
        "card": {
            "tag_type": result.tag.tag_type,
            "tag_type_hex": f"0x{result.tag.tag_type:02X}",
            "definition": tag_info_obj.definition,
            "name": tag_info_obj.name,
            "group": tag_info_obj.group,
            "frequency": tag_info_obj.frequency,
            "raw_id_hex": result.tag.id_hex,
            "raw_bit_count": result.tag.id_bit_count,
        },
        "expected": {
            "value": result.expected,
            "format": result.expected_format,
        },
        "matches": [
            {**item.to_dict(), "appblaster": item.appblaster_settings()}
            for item in result.matches
        ],
    }
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output
