"""UID Tool – NiceGUI desktop GUI (přepracované)."""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
from datetime import datetime
import multiprocessing
from pathlib import Path
import sys

from nicegui import app, ui

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

# ── Globální log (sdílený přes CPython GIL) ───────────────────────────────────

LOG: deque[dict] = deque(maxlen=200)


def log_add(text: str) -> None:
    LOG.appendleft({"time": datetime.now().strftime("%H:%M:%S"), "text": text})


# ── Sdílený stav aplikace ─────────────────────────────────────────────────────

class State:
    last_capture: CaptureResult | None = None
    last_offline: dict | None = None


state = State()

# ── Design tokeny ─────────────────────────────────────────────────────────────

TABS = [
    ("reader",  "usb",          "Čtečka"),
    ("capture", "contactless",  "Načtení karty"),
    ("offline", "analytics",    "Offline analýza"),
]
DEFAULT_TAB = "reader"

# Karta obsahu
CARD = "w-full rounded-xl border border-grey-3 p-4"
LBL  = "text-grey-7 text-sm font-medium"           # popisek pole
VAL  = "text-grey-10 text-sm font-semibold font-mono"  # hodnota pole
SEC  = "text-xs font-bold uppercase tracking-wider text-grey-9"  # nadpis sekce

# Záložky
_TAB_BASE   = (
    "flex-1 rounded-xl border-2 cursor-pointer py-4 px-2 "
    "flex flex-col items-center gap-1 transition-colors select-none"
)
_TAB_ACTIVE = "border-primary bg-primary"
_TAB_IDLE   = "border-grey-4 bg-white"
_ICO_A      = "text-white"
_ICO_I      = "text-grey-6"
_LBL_A      = "font-bold text-xs uppercase text-center text-white"
_LBL_I      = "font-bold text-xs uppercase text-center text-grey-6"

# ── Utility funkce ─────────────────────────────────────────────────────────────

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
    ui.notify(msg, type="negative", multi_line=True, close_button=True,
               position="top-right", timeout=0)


def kv_grid(pairs: list[tuple[str, str]]) -> None:
    """2-sloupcová mřížka popisek → hodnota."""
    with ui.grid(columns=2).classes("w-full gap-x-6 gap-y-0"):
        for k, v in pairs:
            ui.label(f"{k}:").classes(LBL)
            ui.label(str(v)).classes(VAL)


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


# ── Sdílené UI komponenty ─────────────────────────────────────────────────────

def best_match_card(m: dict, *, tag_type: int | None = None) -> None:
    """Karta nejlepší shody – zobrazuje se inline + nabídka sestavení FW."""
    with ui.card().classes(f"{CARD} border-primary/30 bg-blue-50"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("check_circle", size="xs").classes("text-positive")
            ui.label("Nejlepší shoda").classes(SEC)
            ui.badge(f"skóre {m['rank_score']:.1f}", color="primary")
            if m.get("encoding") == "wiegand_3_5":
                ui.badge("Wiegand 3+5", color="secondary")
            elif m.get("encoding") and m.get("encoding") != "plain":
                ui.badge(str(m["encoding"]), color="secondary")
        pairs = [
            ("Selected HEX",   m["output_hex"]),
            ("Selected DEC",   m["output_decimal"]),
            ("Output Bits",    m["output_bits_mode"]),
            ("First Bit",      str(m["first_bit"]) if m["first_bit"] is not None else "–"),
            ("Number of Bits", str(m["number_of_bits"])),
            ("Output Format",  m["output_format"]),
            ("Reverse Bit",    yn(m["reverse_bit_order"])),
            ("Reverse Byte",   yn(m["reverse_byte_order"])),
        ]
        if m.get("encoding") == "wiegand_3_5":
            pairs.extend([
                ("Facility", m.get("facility_code")),
                ("Card No.", m.get("card_number")),
                ("Length",   m.get("length", "8 digits")),
            ])
        elif m.get("encoding") and m.get("encoding") != "plain":
            pairs.extend([
                ("Encoding", m.get("encoding")),
                ("Facility", m.get("facility_code")),
                ("Card No.", m.get("card_number")),
            ])
            if m.get("encoding_note"):
                pairs.append(("Poznámka", m["encoding_note"]))
        kv_grid([(k, str(v)) for k, v in pairs if v is not None])
        if m.get("encoding") and m.get("encoding") != "plain":
            ui.label(
                "Poznámka: standardní AppBlaster Decimal nestačí – "
                "použijte Vytvořit FW níže."
            ).classes("text-caption text-grey-7 mt-2")

        ui.separator().classes("my-3")
        ui.label("Firmware pro čtečku").classes(SEC)
        ui.label(
            "Sestaví flashovatelný .bix se stejným pravidlem "
            "(bit/byte reverse, HEX/DEC, Wiegand 3+5). Vyžaduje DevPack v elafiles/."
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
    return [{
        "n":    i + 1,
        "sc":   f"{m['rank_score']:.1f}",
        "hex":  m["output_hex"],
        "dec":  m["output_decimal"],
        "bits": m["output_bits_mode"],
        "fb":   str(m["first_bit"]) if m["first_bit"] is not None else "–",
        "nb":   m["number_of_bits"],
        "fmt":  m["output_format"],
        "enc":  "3+5" if m.get("encoding") == "wiegand_3_5" else "plain",
        "rb":   yn(m["reverse_bit_order"]),
        "rby":  yn(m["reverse_byte_order"]),
    } for i, m in enumerate(matches)]


_CAND_COLS = [
    {"name": "n",    "label": "#",       "field": "n",   "align": "center", "sortable": True},
    {"name": "sc",   "label": "Skóre",   "field": "sc",  "align": "center", "sortable": True},
    {"name": "hex",  "label": "HEX",     "field": "hex", "align": "left"},
    {"name": "dec",  "label": "DEC",     "field": "dec", "align": "left"},
    {"name": "enc",  "label": "Encoding","field": "enc", "align": "center"},
    {"name": "bits", "label": "Bits",    "field": "bits","align": "left"},
    {"name": "fb",   "label": "1st Bit", "field": "fb",  "align": "center"},
    {"name": "nb",   "label": "# Bits",  "field": "nb",  "align": "center"},
    {"name": "fmt",  "label": "Formát",  "field": "fmt", "align": "left"},
    {"name": "rb",   "label": "Rev Bit", "field": "rb",  "align": "center"},
    {"name": "rby",  "label": "Rev Byte","field": "rby", "align": "center"},
]


# ── Záložka: Čtečka ───────────────────────────────────────────────────────────

def build_reader_tab() -> None:
    with ui.card().classes(f"{CARD} bg-blue-50 border-primary/20"):
        ui.label("Jak začít").classes(SEC)
        ui.separator().classes("my-1")
        for step in [
            "1.  Připoj čtečku přes USB.",
            "2.  Vyber COM port ze seznamu  (★ ELATEC = doporučeno).",
            "3.  Klikni Načíst info – ověř verzi PRS firmwaru.",
            "4.  Přejdi na záložku Načtení karty.",
        ]:
            ui.label(step).classes("text-body2 text-grey-8")

    port_sel = ui.select({}, label="COM port").classes("w-full").props("outlined dense")

    with ui.row().classes("gap-2"):
        ui.button("Obnovit", icon="refresh",
                  on_click=lambda: refresh_ports(port_sel)
                  ).props("flat dense color=primary")
        load_btn = ui.button("Načíst info", icon="usb").props("color=primary unelevated")

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
                        ui.icon("error_outline").classes("text-negative mt-1 shrink-0")
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
        kv_grid([
            ("Verze",       d["version"] or "(prázdná)"),
            ("Device Type", f"{d['device_type']} ({d['device_type_hex']})"),
            ("LF mask",     d["lf_supported_mask"]),
            ("HF mask",     d["hf_supported_mask"]),
        ])

    rows = d["supported_technologies"]
    if rows:
        ui.label("Podporované technologie").classes(f"{SEC} mt-2")
        cols = [
            {"name": "tag_type",  "label": "TagType",   "field": "tag_type",  "align": "left"},
            {"name": "group",     "label": "Skupina",   "field": "group",     "align": "left"},
            {"name": "frequency", "label": "Frekvence", "field": "frequency", "align": "left"},
            {"name": "name",      "label": "Název",     "field": "name",      "align": "left"},
        ]
        ui.table(columns=cols, rows=rows, row_key="tag_type"
                 ).props("dense flat bordered").classes("w-full")


# ── Záložka: Načtení karty ────────────────────────────────────────────────────

def build_capture_tab() -> None:
    port_sel = ui.select({}, label="COM port").classes("w-full").props("outlined dense")

    with ui.row().classes("w-full gap-3 items-end"):
        exp_in = ui.input(label="Kód z databáze", placeholder="12583124"
                          ).classes("flex-1").props("outlined dense")
        fmt_sel = ui.select(
            {"auto": "AUTO", "decimal": "Desetinný", "hexadecimal": "Hex"},
            value="auto", label="Formát"
        ).classes("w-36").props("outlined dense")
        wait_in = ui.number(label="Čekání (s)", value=30, min=5, max=120, step=5
                            ).classes("w-28").props("outlined dense")

    status_lbl = ui.label("").classes("text-primary font-medium text-body2 min-h-[20px]")
    result_area = ui.column().classes("w-full gap-3")

    # Dialog kandidátů – vytvořen jednou, data se obnovu přes refreshable
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
        exp  = (exp_in.value or "").strip()
        if not port: notify_err("Vyber COM port."); return
        if not exp:  notify_err("Zadej kód z databáze."); return

        result_area.clear()
        status_lbl.text = "Spouštím…"
        cap_btn.disable()
        log_add(f"→ Capture {port} | kód: {exp}")

        def on_prog(msg: str) -> None:
            status_lbl.text = msg
            log_add(f"  {msg}")

        try:
            result: CaptureResult = await run_io(
                capture_and_analyze, port, exp, fmt_sel.value,
                wait=float(wait_in.value or 30), on_progress=on_prog,
            )
            state.last_capture = result
            d = capture_result_to_dict(result)
            matches = d["matches"]
            log_add(f"← {len(matches)} kandidátů")
            status_lbl.text = ""

            with result_area:
                with ui.card().classes(CARD):
                    ui.label("Nalezené médium").classes(f"{SEC} mb-1")
                    kv_grid([
                        ("TagType",    d["card"]["tag_type"]),
                        ("Typ",        d["card"]["name"]),
                        ("Skupina",    d["card"]["group"]),
                        ("Frekvence",  d["card"]["frequency"]),
                        ("RAW UID",    d["card"]["raw_id_hex"]),
                        ("Počet bitů", str(d["card"]["raw_bit_count"])),
                        ("RAW DEC",    d["card"]["raw_decimal"]),
                    ])

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

                        ui.button("Exportovat JSON", icon="save",
                                  on_click=do_export).props("flat color=primary")
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
        ui.button("Obnovit", icon="refresh",
                  on_click=lambda: refresh_ports(port_sel)
                  ).props("flat dense color=primary")
        cap_btn = ui.button("Načíst kartu", icon="contactless",
                            on_click=do_capture).props("color=primary unelevated")

    ui.timer(0.4, lambda: refresh_ports(port_sel), once=True)


# ── Záložka: Offline analýza ──────────────────────────────────────────────────

def build_offline_tab() -> None:
    with ui.row().classes("w-full gap-3 items-end"):
        raw_in  = ui.input(label="RAW UID (hex)", placeholder="3D00C000D4"
                           ).classes("flex-1").props("outlined dense")
        bits_in = ui.number(label="Počet bitů", value=None, min=1, max=512
                            ).classes("w-36").props("outlined dense clearable")

    with ui.row().classes("w-full gap-3 items-end"):
        exp_in  = ui.input(label="Očekávaný kód", placeholder="12583124"
                           ).classes("flex-1").props("outlined dense")
        fmt_sel = ui.select(
            {"auto": "AUTO", "decimal": "Desetinný", "hexadecimal": "Hex"},
            value="auto", label="Formát"
        ).classes("w-48").props("outlined dense")

    ui.label("Ref. test: 3D00C000D4 · 40 bitů · kód 12583124"
             ).classes("text-caption text-grey-5")

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
            notify_err("Vyplň RAW UID i očekávaný kód.")
            return
        bits = int(bits_in.value) if bits_in.value else None
        result_area.clear()
        analyze_btn.disable()
        log_add(f"→ Offline {raw} | kód: {exp}")
        try:
            d = await run_io(run_offline_analysis, raw, bits, exp, fmt_sel.value)
            state.last_offline = d
            matches = d["matches"]
            log_add(f"← {len(matches)} kandidátů")

            with result_area:
                with ui.card().classes(CARD):
                    kv_grid([
                        ("RAW HEX",  d["raw_hex"]),
                        ("RAW bitů", str(d["bit_count"])),
                        ("RAW DEC",  d["raw_decimal"]),
                        ("Kód",      d["expected"]),
                    ])
                if matches:
                    best_match_card(matches[0])
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

    analyze_btn = ui.button("Analyzovat", icon="analytics",
                            on_click=do_analyze).props("color=primary unelevated")


# ── Hlavní stránka ────────────────────────────────────────────────────────────

USE_NATIVE = False


@ui.page("/")
def main_page() -> None:
    ui.colors(primary="#1565C0", secondary="#26A69A", accent="#FF7043")
    ui.add_head_html("""
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

      /* Přebití výchozího Quasar fontu pro všechny komponenty */
      body, .q-field, .q-btn, .q-item, .q-table,
      .q-card, .q-badge, .q-banner, .q-dialog,
      .q-tab, .q-tabs, .q-tooltip {
        font-family: 'Inter', 'Segoe UI', ui-sans-serif, system-ui, sans-serif !important;
      }

      /* Lepší čitelnost malých textů */
      .text-xs  { font-size: 0.75rem;  line-height: 1.4; }
      .text-sm  { font-size: 0.825rem; line-height: 1.5; }
      .text-body2 { font-size: 0.875rem; line-height: 1.5; }
    </style>""")

    tab_els: dict[str, dict]    = {}
    tab_panels: dict[str, ui.column] = {}

    def switch_tab(name: str) -> None:
        for key, els in tab_els.items():
            active = key == name
            els["card"].classes(
                add=_TAB_ACTIVE if active else _TAB_IDLE,
                remove=_TAB_IDLE  if active else _TAB_ACTIVE,
            )
            els["icon"].classes(
                add=_ICO_A if active else _ICO_I,
                remove=_ICO_I  if active else _ICO_A,
            )
            els["lbl"].classes(
                add=_LBL_A if active else _LBL_I,
                remove=_LBL_I  if active else _LBL_A,
            )
        for key, panel in tab_panels.items():
            panel.set_visibility(key == name)

    # ── Log dialog (vždy na nejvyšší vrstvě jako overlay) ──────────────────────
    log_dlg = ui.dialog()
    with log_dlg, ui.card().classes("w-full max-w-3xl"):
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label("Log příkazů").classes(SEC)
            ui.button(icon="close", on_click=log_dlg.close).props("flat round dense")

        @ui.refreshable
        def log_content() -> None:
            for entry in list(LOG)[:100]:
                with ui.row().classes("gap-3 items-baseline py-0 no-wrap"):
                    ui.label(entry["time"]).classes(
                        "text-grey-5 font-mono text-xs w-16 shrink-0"
                    )
                    ui.label(entry["text"]).classes("font-mono text-xs text-grey-10")

        with ui.element("div").classes(
            "w-full bg-grey-1 rounded p-2 overflow-y-auto"
        ).style("max-height: min(60vh, 480px);"):
            log_content()

        ui.timer(1.0, log_content.refresh)

    # ── Header ─────────────────────────────────────────────────────────────────
    log_strip_ref: dict = {"el": None, "visible": False}

    def toggle_log_strip() -> None:
        strip = log_strip_ref["el"]
        if strip is None:
            return
        log_strip_ref["visible"] = not log_strip_ref["visible"]
        strip.style(
            "display:flex;" if log_strip_ref["visible"] else "display:none;"
        )

    with ui.header(elevated=True).classes(
        "items-center px-4 gap-2 bg-primary"
    ).style("min-height:48px; height:48px;"):
        ui.icon("contactless", size="sm").classes("text-white")
        ui.label("UID Tool").classes("text-subtitle1 font-bold text-white")
        ui.space()
        ui.label(f"v{__version__}").classes("text-caption text-blue-200")
        ui.button(icon="terminal", on_click=toggle_log_strip).props(
            "flat round dense color=white"
        ).tooltip("Zobrazit / skrýt log příkazů")

    # ── Hlavní sloupec ─────────────────────────────────────────────────────────
    with ui.column().classes("w-full gap-0 overflow-hidden").style(
        "height: calc(100vh - 48px);"
    ):
        # Záložky
        with ui.row().classes("w-full gap-3 px-4 pt-3 pb-1 shrink-0 no-wrap"):
            for name, icon_name, label_text in TABS:
                active = name == DEFAULT_TAB
                with ui.element("div").classes(
                    f"{_TAB_BASE} {_TAB_ACTIVE if active else _TAB_IDLE}"
                ).on("click", lambda _e, n=name: switch_tab(n)) as card:
                    icon_el = ui.icon(icon_name, size="sm").classes(
                        _ICO_A if active else _ICO_I
                    )
                    lbl_el  = ui.label(label_text).classes(
                        _LBL_A if active else _LBL_I
                    )
                tab_els[name] = {"card": card, "icon": icon_el, "lbl": lbl_el}

        # Obsah záložek
        with ui.column().classes(
            "w-full flex-grow min-h-0 overflow-y-auto px-4 py-3"
        ):
            with ui.column().classes("w-full max-w-3xl mx-auto gap-3") as p_reader:
                build_reader_tab()
            tab_panels["reader"] = p_reader

            with ui.column().classes(
                "w-full max-w-3xl mx-auto gap-3 hidden"
            ) as p_capture:
                build_capture_tab()
            tab_panels["capture"] = p_capture

            with ui.column().classes(
                "w-full max-w-3xl mx-auto gap-3 hidden"
            ) as p_offline:
                build_offline_tab()
            tab_panels["offline"] = p_offline

        # Log strip – dolní pruh, výchozí skrytý
        with ui.row().classes(
            "w-full shrink-0 px-4 py-1 gap-2 items-center bg-grey-9"
        ).style("display:none; min-height:28px;") as log_strip:
            ui.icon("terminal", size="xs").classes("text-green-400")
            last_lbl = ui.label("–").classes(
                "font-mono text-xs text-green-400 flex-grow truncate"
            )
            ui.button(
                icon="open_in_new",
                on_click=lambda: (log_content.refresh(), log_dlg.open()),
            ).props("flat round dense size=xs color=green").tooltip(
                "Otevřít log v novém okně"
            )

        log_strip_ref["el"] = log_strip

        def _update_last() -> None:
            if LOG:
                last_lbl.text = f"{LOG[0]['time']}  {LOG[0]['text']}"

        ui.timer(0.5, _update_last)

    # Maximalizace nativního okna
    if USE_NATIVE:
        async def _maximize() -> None:
            try:
                w = app.native.main_window
                if w:
                    await w.maximize()
            except Exception:
                pass
        ui.timer(0.5, _maximize, once=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UID Tool GUI")
    p.add_argument("--browser", action="store_true",
                   help="Spustit v prohlížeči místo nativního okna")
    return p.parse_args()


def main() -> None:
    global USE_NATIVE
    args    = parse_args()
    USE_NATIVE = not args.browser

    if USE_NATIVE:
        app.native.window_args.update({
            "resizable":   True,
            "min_size":    (860, 620),
            "text_select": True,
        })
        app.native.start_args["private_mode"] = False

    ui.run(
        title="UID Tool",
        favicon="📡",
        reload=False,
        native=USE_NATIVE,
        window_size=(1100, 780) if USE_NATIVE else None,
        show=not USE_NATIVE,
        host="127.0.0.1",
        port=8080 if not USE_NATIVE else None,
        storage_secret="uid-tool-gui",
    )


if __name__ in {"__main__", "__mp_main__"}:
    multiprocessing.freeze_support()
    main()
