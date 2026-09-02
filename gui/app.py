"""UID Tool – Windows desktop GUI (NiceGUI native window)."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
import multiprocessing
from pathlib import Path
import sys

from nicegui import app, native, ui

from app_paths import app_root

ROOT = app_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
GUI_DIR = Path(__file__).resolve().parent
if str(GUI_DIR) not in sys.path:
    sys.path.insert(0, str(GUI_DIR))
# PyInstaller / vývoj: src na PYTHONPATH
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from elatec_uid_tool import __version__  # noqa: E402
from elatec_uid_tool.protocol import ElatecError  # noqa: E402

from services import (  # noqa: E402
    CaptureResult,
    capture_and_analyze,
    capture_result_to_dict,
    explain_port_error,
    export_firmware_bix,
    list_ports,
    read_reader_info,
    reader_info_to_dict,
    run_offline_analysis,
    save_capture_json,
)
from settings_store import (  # noqa: E402
    default_devpack_path,
    get_devpack_path,
    set_devpack_path,
    validate_devpack,
)

LOG: deque[dict] = deque(maxlen=200)


def log_add(text: str) -> None:
    LOG.appendleft({"time": datetime.now().strftime("%H:%M:%S"), "text": text})


class State:
    last_capture: CaptureResult | None = None
    last_offline: dict | None = None


state = State()

TABS = [
    ("compare", "compare_arrows", "Porovnání"),
    ("capture", "contactless", "Načtení karty"),
    ("reader", "usb", "Čtečka"),
    ("settings", "settings", "Nastavení"),
]
DEFAULT_TAB = "compare"

CARD = "w-full rounded-xl border border-grey-3 p-4"
LBL = "text-grey-7 text-sm font-medium"
VAL = "text-grey-10 text-sm font-semibold font-mono"
SEC = "text-xs font-bold uppercase tracking-wider text-grey-9"

_TAB_BASE = (
    "flex-1 rounded-xl border-2 cursor-pointer py-4 px-2 "
    "flex flex-col items-center gap-1 transition-colors select-none"
)
_TAB_ACTIVE = "border-primary bg-primary"
_TAB_IDLE = "border-grey-4 bg-white"
_ICO_A = "text-white"
_ICO_I = "text-grey-6"
_LBL_A = "font-bold text-xs uppercase text-center text-white"
_LBL_I = "font-bold text-xs uppercase text-center text-grey-6"


async def run_io(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


def yn(v: bool) -> str:
    return "Ano" if v else "Ne"


def port_label(device: str, desc: str, elatec: bool) -> str:
    if elatec:
        return f"{device}  ★ ELATEC"
    short = (desc or "").split("(")[0].strip()
    return f"{device}  {short[:24]}" if short else device


def notify_ok(msg: str) -> None:
    log_add(f"✓ {msg}")
    ui.notify(msg, type="positive", position="top-right")


def notify_err(msg: str) -> None:
    log_add(f"✗ {msg}")
    ui.notify(
        msg,
        type="negative",
        multi_line=True,
        close_button=True,
        position="top-right",
        timeout=0,
    )


def kv_grid(pairs: list[tuple[str, str]]) -> None:
    with ui.grid(columns=2).classes("w-full gap-x-6 gap-y-0"):
        for k, v in pairs:
            ui.label(f"{k}:").classes(LBL)
            ui.label(str(v)).classes(VAL)


def encoding_badge(enc: str | None) -> str:
    if enc == "wiegand_3_5":
        return "3+5"
    if enc and enc != "plain":
        return str(enc)
    return "plain"


async def refresh_ports(sel: ui.select) -> None:
    log_add("Obnovuji porty…")
    try:
        entries, rec = await run_io(list_ports)
    except ElatecError as exc:
        notify_err(str(exc))
        return
    if not entries:
        sel.options = {}
        sel.value = None
        notify_err("Žádný sériový port nenalezen.")
        return
    sel.options = {
        e.device: port_label(e.device, e.description, e.is_probable_elatec)
        for e in entries
    }
    sel.value = entries[rec].device if rec is not None else entries[0].device
    log_add(f"Porty: {list(sel.options.keys())}")


def best_match_card(m: dict, *, tag_type: int | None = None) -> None:
    with ui.card().classes(f"{CARD} border-primary/30 bg-blue-50"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("check_circle", size="xs").classes("text-positive")
            ui.label("Nejlepší shoda").classes(SEC)
            ui.badge(f"skóre {m['rank_score']:.1f}", color="primary")
            ui.badge(encoding_badge(m.get("encoding")), color="secondary")
        pairs = [
            ("Selected HEX", m["output_hex"]),
            ("Selected DEC", m["output_decimal"]),
            ("Output Bits", m["output_bits_mode"]),
            ("First Bit", str(m["first_bit"]) if m["first_bit"] is not None else "–"),
            ("Number of Bits", str(m["number_of_bits"])),
            ("Output Format", m["output_format"]),
            ("Reverse Bit", yn(m["reverse_bit_order"])),
            ("Reverse Byte", yn(m["reverse_byte_order"])),
        ]
        if m.get("encoding") and m.get("encoding") != "plain":
            pairs.extend(
                [
                    ("Encoding", m.get("encoding")),
                    ("Facility", m.get("facility_code")),
                    ("Card No.", m.get("card_number")),
                ]
            )
            if m.get("encoding_note"):
                pairs.append(("Poznámka", m["encoding_note"]))
        kv_grid([(k, str(v)) for k, v in pairs if v is not None])
        if m.get("encoding") and m.get("encoding") != "plain":
            ui.label(
                "Standardní AppBlaster Decimal nestačí – použijte Vytvořit FW níže."
            ).classes("text-caption text-grey-7 mt-2")

        ui.separator().classes("my-3")
        ui.label("Firmware pro čtečku").classes(SEC)
        ui.label(
            "Sestaví .bix stejným způsobem jako Jarov "
            "(STD207 + appconfig + CCx/MCx/NCx). Cestu k DevPacku nastavíte v Nastavení."
        ).classes("text-caption text-grey-7 mb-2")

        async def make_fw(channel: str, match=m, tt=tag_type) -> None:
            try:
                path = await run_io(
                    export_firmware_bix, match, channel, tag_type=tt
                )
                notify_ok(f"FW hotovo ({channel.upper()}): {path.name}")
                log_add(f"BIX → {path}")
            except Exception as exc:
                notify_err(str(exc))

        with ui.row().classes("gap-2 flex-wrap"):
            ui.button(
                "Vytvořit FW (CDC)",
                icon="usb",
                on_click=lambda: make_fw("cdc"),
            ).props("color=primary")
            ui.button(
                "Vytvořit FW (UART)",
                icon="cable",
                on_click=lambda: make_fw("uart"),
            ).props("outline color=primary")


def parse_tag_type(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    return int(text, 0)


def _candidates_rows(matches: list[dict]) -> list[dict]:
    return [
        {
            "n": i + 1,
            "sc": f"{m['rank_score']:.1f}",
            "hex": m["output_hex"],
            "dec": m["output_decimal"],
            "bits": m["output_bits_mode"],
            "fb": str(m["first_bit"]) if m["first_bit"] is not None else "–",
            "nb": m["number_of_bits"],
            "fmt": m["output_format"],
            "enc": encoding_badge(m.get("encoding")),
            "rb": yn(m["reverse_bit_order"]),
            "rby": yn(m["reverse_byte_order"]),
        }
        for i, m in enumerate(matches)
    ]


_CAND_COLS = [
    {"name": "n", "label": "#", "field": "n", "align": "center", "sortable": True},
    {"name": "sc", "label": "Skóre", "field": "sc", "align": "center", "sortable": True},
    {"name": "hex", "label": "HEX", "field": "hex", "align": "left"},
    {"name": "dec", "label": "DEC", "field": "dec", "align": "left"},
    {"name": "enc", "label": "Encoding", "field": "enc", "align": "center"},
    {"name": "bits", "label": "Bits", "field": "bits", "align": "left"},
    {"name": "fb", "label": "1st Bit", "field": "fb", "align": "center"},
    {"name": "nb", "label": "# Bits", "field": "nb", "align": "center"},
    {"name": "fmt", "label": "Formát", "field": "fmt", "align": "left"},
    {"name": "rb", "label": "Rev Bit", "field": "rb", "align": "center"},
    {"name": "rby", "label": "Rev Byte", "field": "rby", "align": "center"},
]


# ── Záložka: Porovnání (bez čtečky / chipu) ───────────────────────────────────

def build_compare_tab() -> None:
    with ui.card().classes(f"{CARD} bg-blue-50 border-primary/20"):
        ui.label("Bez čipu a bez Simple Protocol").classes(SEC)
        ui.separator().classes("my-1")
        ui.label(
            "Zadej kód, který vrací čtečka (RAW UID / hex z Trace), "
            "a kód z databáze. Tool najde pravidlo (reverse byte, Wiegand 3+5, …) "
            "a nabídne sestavení FW."
        ).classes("text-body2 text-grey-8")
        ui.label(
            "Příklady: čtečka E9B20DFF → DB 01345801  ·  čtečka 813F9A04 → DB 049A3F81"
        ).classes("text-caption text-grey-6 mt-1")

    with ui.row().classes("w-full gap-3 items-end"):
        raw_in = ui.input(
            label="Kód z čtečky (RAW UID hex)",
            placeholder="E9B20DFF",
        ).classes("flex-1").props("outlined dense")
        bits_in = ui.number(
            label="Počet bitů",
            value=None,
            min=1,
            max=512,
        ).classes("w-36").props("outlined dense clearable")

    with ui.row().classes("w-full gap-3 items-end"):
        exp_in = ui.input(
            label="Kód z databáze",
            placeholder="01345801",
        ).classes("flex-1").props("outlined dense")
        fmt_sel = ui.select(
            {"auto": "AUTO", "decimal": "Desetinný", "hexadecimal": "Hex"},
            value="auto",
            label="Formát DB",
        ).classes("w-48").props("outlined dense")

    with ui.row().classes("w-full gap-3 items-end"):
        tag_in = ui.input(
            label="TagType (volitelně)",
            placeholder="0x80 = MIFARE",
            value="0x80",
        ).classes("w-56").props("outlined dense")

    result_area = ui.column().classes("w-full gap-3")

    all_state: dict = {"matches": []}
    all_dlg = ui.dialog().props("maximized")
    with all_dlg, ui.card().classes("w-full h-full rounded-none gap-0"):
        with ui.row().classes("w-full items-center justify-between shrink-0 p-4 pb-2"):
            ui.label("Všichni kandidáti").classes(SEC)
            ui.button(icon="close", on_click=all_dlg.close).props("flat round dense")

        @ui.refreshable
        def all_table_content() -> None:
            if not all_state["matches"]:
                return
            ui.table(
                columns=_CAND_COLS,
                rows=_candidates_rows(all_state["matches"]),
                row_key="n",
            ).props("dense flat bordered virtual-scroll").classes("w-full").style(
                "height: calc(100vh - 80px);"
            )

        with ui.element("div").classes("w-full flex-grow overflow-hidden px-4"):
            all_table_content()

    async def show_all(matches: list[dict]) -> None:
        all_state["matches"] = matches
        all_table_content.refresh()
        all_dlg.open()

    async def do_analyze() -> None:
        raw = (raw_in.value or "").strip()
        exp = (exp_in.value or "").strip()
        if not raw or not exp:
            notify_err("Vyplň kód z čtečky i kód z databáze.")
            return
        bits = int(bits_in.value) if bits_in.value else None
        try:
            tag_type = parse_tag_type(tag_in.value)
        except ValueError:
            notify_err("TagType musí být číslo (např. 0x80).")
            return
        result_area.clear()
        analyze_btn.disable()
        log_add(f"→ Porovnání čtečka={raw} | DB={exp}")
        try:
            d = await run_io(run_offline_analysis, raw, bits, exp, fmt_sel.value)
            state.last_offline = d
            matches = d["matches"]
            log_add(f"← {len(matches)} kandidátů")

            with result_area:
                with ui.card().classes(CARD):
                    kv_grid(
                        [
                            ("Čtečka (RAW)", d["raw_hex"]),
                            ("Počet bitů", str(d["bit_count"])),
                            ("RAW DEC", d["raw_decimal"]),
                            ("Databáze", d["expected"]),
                        ]
                    )
                if matches:
                    best_match_card(matches[0], tag_type=tag_type)
                    if len(matches) > 1:
                        ui.button(
                            f"Zobrazit všechny ({len(matches)})",
                            icon="format_list_numbered",
                            on_click=lambda m=matches: show_all(m),
                        ).props("outline color=primary")
                else:
                    ui.label("Nebyla nalezena žádná shoda.").classes(
                        "text-negative font-medium"
                    )

            (notify_ok if matches else notify_err)(
                f"Nalezeno {len(matches)} kandidátů."
            )
        except (ElatecError, ValueError) as exc:
            log_add(f"ERR {exc}")
            notify_err(str(exc))
        finally:
            analyze_btn.enable()

    analyze_btn = ui.button(
        "Porovnat a najít pravidlo",
        icon="compare_arrows",
        on_click=do_analyze,
    ).props("color=primary unelevated")


# ── Záložka: Čtečka ───────────────────────────────────────────────────────────

def build_reader_tab() -> None:
    with ui.card().classes(f"{CARD} bg-blue-50 border-primary/20"):
        ui.label("Jak začít (s fyzickou čtečkou)").classes(SEC)
        ui.separator().classes("my-1")
        for step in [
            "1. Připoj čtečku přes USB (firmware PRS / Simple Protocol).",
            "2. Vyber COM port (★ ELATEC = doporučeno).",
            "3. Načti info – ověř verzi PRS.",
            "4. Přejdi na Načtení karty, nebo použij Porovnání bez čtečky.",
        ]:
            ui.label(step).classes("text-body2 text-grey-8")

    port_sel = ui.select({}, label="COM port").classes("w-full").props("outlined dense")

    with ui.row().classes("gap-2"):
        ui.button(
            "Obnovit",
            icon="refresh",
            on_click=lambda: refresh_ports(port_sel),
        ).props("flat dense color=primary")
        load_btn = ui.button("Načíst info", icon="usb").props(
            "color=primary unelevated"
        )

    info_area = ui.column().classes("w-full gap-3")

    async def do_load() -> None:
        if not port_sel.value:
            notify_err("Vyber COM port.")
            return
        info_area.clear()
        load_btn.disable()
        log_add(f"→ {port_sel.value}: reader info")
        try:
            info = await run_io(read_reader_info, port_sel.value)
            d = reader_info_to_dict(info)
            log_add(f"← verze: {d['version']}")
            info_area.clear()
            with info_area:
                _render_reader_result(d)
            notify_ok("Informace o čtečce načteny.")
        except ElatecError as exc:
            msg = explain_port_error(port_sel.value, exc)
            log_add(f"ERR {msg[:80]}")
            info_area.clear()
            with info_area:
                with ui.card().classes(f"{CARD} border-red-300 bg-red-50"):
                    with ui.row().classes("gap-2 items-start"):
                        ui.icon("error_outline").classes(
                            "text-negative mt-1 shrink-0"
                        )
                        ui.label(msg).classes("text-negative text-body2")
        finally:
            load_btn.enable()

    load_btn.on("click", do_load)
    ui.timer(0.4, lambda: refresh_ports(port_sel), once=True)


def _render_reader_result(d: dict) -> None:
    prs = d["has_prs_firmware"]
    with ui.card().classes(CARD):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("usb", size="xs").classes("text-primary")
            ui.label(d["port"]).classes("font-bold text-grey-10")
            ui.space()
            ui.badge(
                "PRS ✓" if prs else "PRS chybí – zkontroluj firmware",
                color="positive" if prs else "warning",
            )
        kv_grid(
            [
                ("Verze", d["version"] or "(prázdná)"),
                ("Device Type", f"{d['device_type']} ({d['device_type_hex']})"),
                ("LF mask", d["lf_supported_mask"]),
                ("HF mask", d["hf_supported_mask"]),
            ]
        )

    rows = d["supported_technologies"]
    if rows:
        ui.label("Podporované technologie").classes(f"{SEC} mt-2")
        cols = [
            {"name": "tag_type", "label": "TagType", "field": "tag_type", "align": "left"},
            {"name": "group", "label": "Skupina", "field": "group", "align": "left"},
            {
                "name": "frequency",
                "label": "Frekvence",
                "field": "frequency",
                "align": "left",
            },
            {"name": "name", "label": "Název", "field": "name", "align": "left"},
        ]
        ui.table(columns=cols, rows=rows, row_key="tag_type").props(
            "dense flat bordered"
        ).classes("w-full")


# ── Záložka: Načtení karty ────────────────────────────────────────────────────

def build_capture_tab() -> None:
    port_sel = ui.select({}, label="COM port").classes("w-full").props("outlined dense")

    with ui.row().classes("w-full gap-3 items-end"):
        exp_in = ui.input(
            label="Kód z databáze",
            placeholder="12583124",
        ).classes("flex-1").props("outlined dense")
        fmt_sel = ui.select(
            {"auto": "AUTO", "decimal": "Desetinný", "hexadecimal": "Hex"},
            value="auto",
            label="Formát",
        ).classes("w-36").props("outlined dense")
        wait_in = ui.number(
            label="Čekání (s)",
            value=30,
            min=5,
            max=120,
            step=5,
        ).classes("w-28").props("outlined dense")

    status_lbl = ui.label("").classes(
        "text-primary font-medium text-body2 min-h-[20px]"
    )
    result_area = ui.column().classes("w-full gap-3")

    cand_state: dict = {"matches": []}
    cand_dlg = ui.dialog().props("maximized")
    with cand_dlg, ui.card().classes("w-full h-full rounded-none gap-0"):
        with ui.row().classes("w-full items-center justify-between shrink-0 p-4 pb-2"):
            ui.label("Kandidáti").classes(SEC)
            ui.button(icon="close", on_click=cand_dlg.close).props("flat round dense")

        @ui.refreshable
        def cand_table_content() -> None:
            if not cand_state["matches"]:
                return
            ui.table(
                columns=_CAND_COLS,
                rows=_candidates_rows(cand_state["matches"]),
                row_key="n",
            ).props("dense flat bordered virtual-scroll").classes("w-full").style(
                "height: calc(100vh - 80px);"
            )

        with ui.element("div").classes("w-full flex-grow overflow-hidden px-4"):
            cand_table_content()

    async def show_candidates(matches: list[dict]) -> None:
        cand_state["matches"] = matches
        cand_table_content.refresh()
        cand_dlg.open()

    async def do_capture() -> None:
        port = port_sel.value
        exp = (exp_in.value or "").strip()
        if not port:
            notify_err("Vyber COM port.")
            return
        if not exp:
            notify_err("Zadej kód z databáze.")
            return

        result_area.clear()
        status_lbl.text = "Spouštím…"
        cap_btn.disable()
        log_add(f"→ Capture {port} | kód: {exp}")

        def on_prog(msg: str) -> None:
            status_lbl.text = msg
            log_add(f"  {msg}")

        try:
            result: CaptureResult = await run_io(
                capture_and_analyze,
                port,
                exp,
                fmt_sel.value,
                wait=float(wait_in.value or 30),
                on_progress=on_prog,
            )
            state.last_capture = result
            d = capture_result_to_dict(result)
            matches = d["matches"]
            log_add(f"← {len(matches)} kandidátů")
            status_lbl.text = ""

            with result_area:
                with ui.card().classes(CARD):
                    ui.label("Nalezené médium").classes(f"{SEC} mb-1")
                    kv_grid(
                        [
                            ("TagType", d["card"]["tag_type"]),
                            ("Typ", d["card"]["name"]),
                            ("Skupina", d["card"]["group"]),
                            ("Frekvence", d["card"]["frequency"]),
                            ("RAW UID", d["card"]["raw_id_hex"]),
                            ("Počet bitů", str(d["card"]["raw_bit_count"])),
                            ("RAW DEC", d["card"]["raw_decimal"]),
                        ]
                    )

                if matches:
                    best_match_card(
                        matches[0],
                        tag_type=parse_tag_type(d["card"].get("tag_type")),
                    )

                    with ui.row().classes("gap-2 flex-wrap"):
                        if len(matches) > 1:
                            ui.button(
                                f"Zobrazit všechny kandidáty ({len(matches)})",
                                icon="format_list_numbered",
                                on_click=lambda m=matches: show_candidates(m),
                            ).props("outline color=primary")

                        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                        out_p = ROOT / "results" / f"elatec-{stamp}.json"

                        async def do_export(p=out_p, r=result) -> None:
                            try:
                                path = await run_io(save_capture_json, r, p)
                                notify_ok(f"Uloženo: {path.name}")
                            except Exception as exc:
                                notify_err(str(exc))

                        ui.button(
                            "Exportovat JSON",
                            icon="save",
                            on_click=do_export,
                        ).props("flat color=primary")
                else:
                    ui.label("Nebyla nalezena žádná shoda.").classes(
                        "text-negative font-medium"
                    )

            notify_ok(f"Hotovo – {len(matches)} kandidátů.")

        except ElatecError as exc:
            msg = explain_port_error(port, exc)
            log_add(f"ERR {msg[:80]}")
            status_lbl.text = ""
            notify_err(msg)
        except Exception as exc:
            log_add(f"ERR {exc}")
            status_lbl.text = ""
            notify_err(str(exc))
        finally:
            cap_btn.enable()

    with ui.row().classes("gap-2"):
        ui.button(
            "Obnovit",
            icon="refresh",
            on_click=lambda: refresh_ports(port_sel),
        ).props("flat dense color=primary")
        cap_btn = ui.button(
            "Načíst kartu",
            icon="contactless",
            on_click=do_capture,
        ).props("color=primary unelevated")

    ui.timer(0.4, lambda: refresh_ports(port_sel), once=True)


# ── Záložka: Nastavení ────────────────────────────────────────────────────────

def build_settings_tab() -> None:
    with ui.card().classes(f"{CARD} bg-blue-50 border-primary/20"):
        ui.label("TWN4 Developer Pack").classes(SEC)
        ui.separator().classes("my-1")
        ui.label(
            "Výchozí je TWN4DevPack520 (složka elafiles/ nebo instalace DevPacku). "
            "Pro novější DevPackxxx změň cestu níže – musí obsahovat Tools/ a Apps/ "
            "s CCx/MCx/NCx a App_STD207_Standard_temp.c."
        ).classes("text-body2 text-grey-8")

    path_in = ui.input(
        label="Cesta k DevPacku",
        value=str(get_devpack_path()),
    ).classes("w-full").props("outlined dense")

    status = ui.label("").classes("text-body2")

    def refresh_status() -> None:
        path = Path(path_in.value or "").expanduser()
        if not path.exists():
            status.text = f"Cesta neexistuje: {path}"
            status.classes(replace="text-negative text-body2")
            return
        missing = validate_devpack(path)
        if missing:
            status.text = "Neúplný DevPack – chybí: " + ", ".join(missing[:5])
            status.classes(replace="text-warning text-body2")
        else:
            status.text = f"DevPack OK: {path.resolve()}"
            status.classes(replace="text-positive text-body2")

    refresh_status()

    async def do_browse() -> None:
        try:
            window = app.native.main_window
            if window is None:
                notify_err("Okno není připravené – cestu zadej ručně.")
                return
            files = await window.create_file_dialog(dialog_type=2)
        except Exception as exc:
            notify_err(
                "Výběr složky selhal – cestu zadej ručně do pole.\n"
                f"Detail: {exc}"
            )
            return
        if files:
            path_in.value = str(files[0])
            refresh_status()

    async def do_save() -> None:
        raw = (path_in.value or "").strip()
        if not raw:
            notify_err("Zadej cestu k DevPacku.")
            return
        path = set_devpack_path(raw)
        path_in.value = str(path)
        refresh_status()
        missing = validate_devpack(path)
        if missing:
            notify_err(
                "Uloženo, ale DevPack není kompletní pro build FW.\n"
                + "\n".join(missing[:6])
            )
        else:
            notify_ok(f"DevPack uložen: {path}")

    async def do_reset() -> None:
        path = set_devpack_path(default_devpack_path())
        path_in.value = str(path)
        refresh_status()
        notify_ok(f"Obnoveno: {path}")

    with ui.row().classes("gap-2 flex-wrap"):
        ui.button("Procházet…", icon="folder_open", on_click=do_browse).props(
            "outline color=primary"
        )
        ui.button("Uložit", icon="save", on_click=do_save).props(
            "color=primary unelevated"
        )
        ui.button("Výchozí", icon="restart_alt", on_click=do_reset).props(
            "flat color=primary"
        )
        ui.button("Ověřit", icon="fact_check", on_click=refresh_status).props(
            "flat color=primary"
        )

    ui.separator().classes("my-3")
    ui.label("Jak nahrát .bix").classes(SEC)
    ui.label(
        "AppBlaster → Program Firmware Image → Select Image → "
        "FW_elatec\\export\\out\\TWN4_xCx520_EXP_CDC.bix → Program Image."
    ).classes("text-body2 text-grey-8")


# ── Hlavní stránka ────────────────────────────────────────────────────────────

@ui.page("/")
def main_page() -> None:
    ui.colors(primary="#1565C0", secondary="#26A69A", accent="#FF7043")
    ui.add_head_html(
        """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
      *, *::before, *::after {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeLegibility;
        box-sizing: border-box;
      }
      html, body {
        overflow: hidden;
        height: 100%;
        margin: 0;
        font-family: 'Inter', 'Segoe UI', ui-sans-serif, system-ui, sans-serif !important;
        font-size: 14px;
      }
      .nicegui-content { height: 100%; }
      body, .q-field, .q-btn, .q-item, .q-table,
      .q-card, .q-badge, .q-banner, .q-dialog,
      .q-tab, .q-tabs, .q-tooltip {
        font-family: 'Inter', 'Segoe UI', ui-sans-serif, system-ui, sans-serif !important;
      }
      .text-xs  { font-size: 0.75rem;  line-height: 1.4; }
      .text-sm  { font-size: 0.825rem; line-height: 1.5; }
      .text-body2 { font-size: 0.875rem; line-height: 1.5; }
    </style>"""
    )

    tab_els: dict[str, dict] = {}
    tab_panels: dict[str, ui.column] = {}

    def switch_tab(name: str) -> None:
        for key, els in tab_els.items():
            active = key == name
            els["card"].classes(
                add=_TAB_ACTIVE if active else _TAB_IDLE,
                remove=_TAB_IDLE if active else _TAB_ACTIVE,
            )
            els["icon"].classes(
                add=_ICO_A if active else _ICO_I,
                remove=_ICO_I if active else _ICO_A,
            )
            els["lbl"].classes(
                add=_LBL_A if active else _LBL_I,
                remove=_LBL_I if active else _LBL_A,
            )
        for key, panel in tab_panels.items():
            panel.set_visibility(key == name)

    log_dlg = ui.dialog()
    with log_dlg, ui.card().classes("w-full max-w-3xl"):
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label("Log příkazů").classes(SEC)
            ui.button(icon="close", on_click=log_dlg.close).props("flat round dense")

        @ui.refreshable
        def log_content() -> None:
            entries = list(LOG)[:100]
            if not entries:
                ui.label("Zatím žádné záznamy.").classes("text-grey-6 text-sm")
                return
            for entry in entries:
                with ui.row().classes("gap-3 items-baseline py-0.5 no-wrap"):
                    ui.label(entry["time"]).classes(
                        "text-grey-5 font-mono text-xs w-16 shrink-0"
                    )
                    ui.label(entry["text"]).classes("font-mono text-xs text-grey-10")

        with ui.element("div").classes(
            "w-full bg-grey-1 rounded p-2 overflow-y-auto"
        ).style("max-height: min(60vh, 480px);"):
            log_content()

        ui.timer(1.0, log_content.refresh)

    @ui.refreshable
    def log_panel_lines() -> None:
        entries = list(LOG)[:6]
        if not entries:
            ui.label("Log je prázdný – akce se budou zobrazovat zde.").classes(
                "font-mono text-xs text-grey-5"
            )
            return
        for entry in entries:
            with ui.row().classes("w-full gap-2 items-start no-wrap"):
                ui.label(entry["time"]).classes(
                    "font-mono text-xs text-green-600 shrink-0 w-14"
                )
                ui.label(entry["text"]).classes(
                    "font-mono text-xs text-grey-2 break-all"
                )

    with ui.header(elevated=True).classes("items-center px-4 gap-3 bg-primary").style(
        "min-height:52px; height:52px;"
    ):
        ui.icon("contactless", size="sm").classes("text-white")
        ui.label("UID Tool").classes("text-subtitle1 font-bold text-white")
        ui.badge("HanzG").props("outline color=white").classes("text-white")
        ui.space()
        ui.label(f"v{__version__}").classes("text-caption text-blue-200")
        ui.button(
            icon="open_in_full",
            on_click=lambda: (log_content.refresh(), log_dlg.open()),
        ).props("flat round dense color=white").tooltip("Otevřít celý log")

    with ui.column().classes("w-full gap-0 overflow-hidden").style(
        "height: calc(100vh - 52px);"
    ):
        with ui.row().classes("w-full gap-3 px-4 pt-3 pb-1 shrink-0 no-wrap"):
            for name, icon_name, label_text in TABS:
                active = name == DEFAULT_TAB
                with ui.element("div").classes(
                    f"{_TAB_BASE} {_TAB_ACTIVE if active else _TAB_IDLE}"
                ).on("click", lambda _e, n=name: switch_tab(n)) as card:
                    icon_el = ui.icon(icon_name, size="sm").classes(
                        _ICO_A if active else _ICO_I
                    )
                    lbl_el = ui.label(label_text).classes(
                        _LBL_A if active else _LBL_I
                    )
                tab_els[name] = {"card": card, "icon": icon_el, "lbl": lbl_el}

        with ui.column().classes(
            "w-full flex-grow min-h-0 overflow-y-auto px-4 py-3"
        ):
            with ui.column().classes("w-full max-w-3xl mx-auto gap-3") as p_compare:
                build_compare_tab()
            tab_panels["compare"] = p_compare

            with ui.column().classes(
                "w-full max-w-3xl mx-auto gap-3 hidden"
            ) as p_capture:
                build_capture_tab()
            tab_panels["capture"] = p_capture

            with ui.column().classes(
                "w-full max-w-3xl mx-auto gap-3 hidden"
            ) as p_reader:
                build_reader_tab()
            tab_panels["reader"] = p_reader

            with ui.column().classes(
                "w-full max-w-3xl mx-auto gap-3 hidden"
            ) as p_settings:
                build_settings_tab()
            tab_panels["settings"] = p_settings

        with ui.column().classes(
            "w-full shrink-0 border-t border-grey-8 bg-grey-10"
        ).style("min-height:132px; max-height:160px;"):
            with ui.row().classes(
                "w-full items-center px-4 pt-2 pb-1 gap-2 shrink-0"
            ):
                ui.icon("terminal", size="xs").classes("text-green-400")
                ui.label("Log").classes(
                    "text-caption text-green-400 font-bold uppercase tracking-wide"
                )
                ui.space()
                ui.label("HanzG").classes("text-caption text-grey-6 font-medium")
                ui.button(
                    icon="open_in_full",
                    on_click=lambda: (log_content.refresh(), log_dlg.open()),
                ).props("flat round dense size=sm color=green").tooltip(
                    "Celý log"
                )
            with ui.element("div").classes(
                "w-full px-4 pb-2 overflow-y-auto flex-grow"
            ).style("min-height:90px;"):
                log_panel_lines()

        ui.timer(0.5, log_panel_lines.refresh)

    async def _maximize() -> None:
        try:
            w = app.native.main_window
            if w:
                await w.maximize()
        except Exception:
            pass

    ui.timer(0.5, _maximize, once=True)


def _icon_path() -> Path:
    """Ikona okna / taskbaru – vývoj, PyInstaller _MEIPASS i vedle EXE."""
    from app_paths import bundle_root

    candidates = [
        Path(__file__).resolve().parent / "assets" / "icon.ico",
        bundle_root() / "assets" / "icon.ico",
        bundle_root() / "gui" / "assets" / "icon.ico",
        app_root() / "gui" / "assets" / "icon.ico",
        app_root() / "assets" / "icon.ico",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def main() -> None:
    # Native args musí být nastaveny PŘED freeze_support (PyInstaller subprocess).
    icon = _icon_path()
    app.native.window_args.update(
        {
            "resizable": True,
            "min_size": (860, 620),
            "text_select": True,
        }
    )
    app.native.start_args["private_mode"] = False

    ui.run(
        title=f"UID Tool v{__version__} · HanzG",
        favicon=str(icon) if icon.is_file() else "📡",
        reload=False,
        native=True,
        window_size=(1100, 780),
        show=False,
        port=native.find_open_port(),
        storage_secret="uid-tool-gui",
    )


if __name__ in {"__main__", "__mp_main__"}:
    multiprocessing.freeze_support()
    main()
