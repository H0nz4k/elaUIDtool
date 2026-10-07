"""Nový režim registrace HF/LF: sestavení a krátký test jedné karty."""
from __future__ import annotations

import asyncio
import threading

from nicegui import ui

from elatec_uid_tool.registration import RegistrationConfig, format_uid
from elatec_uid_tool.registration_client import RegistrationCancelled, capture_registration
from firmware_ui import reader_picker, show_bix_result
from services import explain_port_error, export_registration_bix
from settings_store import get_registration_settings, set_registration_settings


def build_registration_tab(*, refresh_ports, run_io, log_add, notify_ok, notify_err) -> None:
    saved = get_registration_settings()
    selection = {"model": saved["reader_model"]}
    with ui.card().classes("w-full rounded-xl border border-grey-3 p-4 shadow-none"):
        ui.label("Registrace HF/LF").classes("text-lg font-bold")
        ui.label("Jedno přiložení karty. Čtečka zjistí dostupné technologie a odešle HF před LF.").classes("text-sm text-grey-8")
        ui.label("Čtečka pro export").classes("text-sm font-semibold mt-2")
        reader_picker(selection["model"], lambda model: selection.update(model=model))
        with ui.row().classes("w-full gap-4 mt-2"):
            hf_format = ui.select(["HEX", "DEC"], value=saved["hf_format"], label="Výstup HF · 13,56 MHz").classes("flex-1").props("outlined dense")
            lf_format = ui.select(["HEX", "DEC"], value=saved["lf_format"], label="Výstup LF · 125 kHz").classes("flex-1").props("outlined dense")
        ui.label("HEX: celý UID, původní délka, velká písmena. DEC: celé UID jako nezáporné číslo. Bez přidaných nul a bez zkracování.").classes("text-xs text-grey-7")
        decimal_note = ui.label("DEC může mít až 20 číslic. U dlouhých UID ověř délku pole v cílovém systému; Jídelna používá 16 znaků.").classes("text-xs text-warning")

        def radix_changed() -> None:
            decimal_note.set_visibility("DEC" in (hf_format.value, lf_format.value))
            preview.refresh()

        hf_format.on_value_change(radix_changed)
        lf_format.on_value_change(radix_changed)
        decimal_note.set_visibility("DEC" in (hf_format.value, lf_format.value))

        @ui.refreshable
        def preview() -> None:
            with ui.row().classes("gap-6 text-xs text-grey-7"):
                ui.label(f"Příklad HF: 04112233 → {format_uid('04112233', hf_format.value)}")
                ui.label(f"Příklad LF: 0102030405 → {format_uid('0102030405', lf_format.value)}")
        preview()

        with ui.expansion("Doba hledání druhé technologie", icon="tune").classes("w-full"):
            search_ms = ui.number(label="Čekání po prvním nalezeném čipu (ms)", value=saved["other_search_ms"], min=500, max=10000, step=100, precision=0).classes("w-full").props("outlined dense")
            ui.label("Výchozí 2000 ms. Dvojice se odešle hned po nalezení obou čipů. Jediný čip až po uplynutí této doby; příliš krátké čekání může minout slabší čip.").classes("text-xs text-grey-7")

        def config() -> RegistrationConfig:
            value = search_ms.value
            if value is None or int(value) != value:
                raise ValueError("Zadej celou dobu čekání v milisekundách.")
            return RegistrationConfig(hf_format.value, lf_format.value, int(value))

        def save() -> RegistrationConfig:
            value = config()
            set_registration_settings(selection["model"], value.hf_format, value.lf_format, value.other_search_ms)
            return value

        async def build() -> None:
            build_button.disable()
            try:
                value, model = save(), selection["model"]
                log_add(f"Sestavuji registraci: HF {value.hf_format}, LF {value.lf_format}…")
                path = await run_io(export_registration_bix, value, model)
                log_add(f"BIX → {path}")
                await show_bix_result(path)
            except Exception as exc:
                notify_err(str(exc))
            finally:
                build_button.enable()

        def save_only() -> None:
            try:
                save()
                notify_ok("Nastavení registrace uloženo. Ve čtečce se projeví po nahrání nového BIX.")
            except ValueError as exc:
                notify_err(str(exc))

        with ui.row().classes("gap-2 mt-2"):
            build_button = ui.button("Vytvořit registrační BIX", icon="download", on_click=build)
            ui.button("Uložit volby", icon="save", on_click=save_only).props("outline")
        ui.label("Pro sestavení potřebuješ lokální DevPack 5.20. Cestu nastav v Nastavení. Firmware se do čtečky nahrává přes AppBlaster.").classes("text-xs text-grey-7")

    with ui.card().classes("w-full rounded-xl border border-grey-3 p-4 shadow-none"):
        ui.label("Chování po přiložení").classes("text-sm font-bold")
        ui.table(columns=[
            {"name": "found", "label": "Nalezeno", "field": "found", "align": "left"},
            {"name": "sent", "label": "Odesláno", "field": "sent", "align": "left"},
            {"name": "signal", "label": "Oznámení", "field": "signal", "align": "left"},
        ], rows=[
            {"found": "HF + LF", "sent": "HF, potom LF", "signal": "2 rychlá hlasitá pípnutí + 2 zelená bliknutí"},
            {"found": "Jen HF", "sent": "HF jednou", "signal": "1 pípnutí + 1 zelené bliknutí"},
            {"found": "Jen LF", "sent": "LF jednou", "signal": "1 pípnutí + 1 zelené bliknutí"},
        ], row_key="found").classes("w-full").props("flat bordered dense hide-bottom wrap-cells")
        ui.label("V Jídelně zapni duální karty a použij interní čtečku přes COM. U jedné technologie prázdný druhý řádek ukončí druhé čtení. Další karta se přijme po odebrání předchozí.").classes("text-xs text-grey-7")

    with ui.card().classes("w-full rounded-xl border border-grey-3 p-4 shadow-none"):
        ui.label("Ověřit jednu kartu").classes("text-sm font-bold")
        ui.label("Nahraj vytvořený registrační firmware a zavři Jídelnu i AppBlaster. Před spuštěním testu musí být karta mimo čtečku. Test nezapisuje do databáze.").classes("text-xs text-grey-7")
        with ui.row().classes("w-full items-center gap-2"):
            port = ui.select({}, label="COM port").classes("flex-1").props("outlined dense")
            refresh_button = ui.button(icon="refresh", on_click=lambda: refresh_ports(port)).props("flat round")
        status = ui.label("Připraveno. Spusť test, pak přilož jednu kartu.").classes("text-sm")
        with ui.row().classes("w-full gap-4"):
            hf_result = ui.input(label="HF — skutečně odeslaný kód").classes("flex-1").props("outlined dense readonly")
            lf_result = ui.input(label="LF — skutečně odeslaný kód").classes("flex-1").props("outlined dense readonly")
        cancel = threading.Event()

        async def test() -> None:
            if not port.value:
                notify_err("Vyber COM port čtečky.")
                return
            device = port.value
            cancel.clear()
            test_button.disable()
            port.disable()
            refresh_button.disable()
            stop_button.enable()
            hf_result.value = lf_result.value = ""
            loop = asyncio.get_running_loop()

            def progress(message: str) -> None:
                loop.call_soon_threadsafe(setattr, status, "text", message)

            try:
                result = await run_io(capture_registration, device, cancel=cancel, on_progress=progress)
                hf_result.value, lf_result.value = result.hf or "—", result.lf or "—"
                count = int(result.hf is not None) + int(result.lf is not None)
                status.text = f"Přijato {count} identifikátorů. Firmware {result.firmware}: HF {result.hf_format}, LF {result.lf_format}. Odeber kartu."
                log_add(f"Test {device}: {count} identifikátorů, pořadí a předání přes znovuotevření COM ověřeno.")
            except RegistrationCancelled:
                status.text = "Test zastaven. Odeber kartu před dalším testem."
            except Exception as exc:
                status.text = "Test se nepodařil. Odeber kartu a zkontroluj firmware i COM port."
                notify_err(explain_port_error(device, exc))
            finally:
                test_button.enable()
                port.enable()
                refresh_button.enable()
                stop_button.disable()

        with ui.row().classes("gap-2"):
            test_button = ui.button("Otestovat jednu kartu", icon="contactless", on_click=test)
            stop_button = ui.button("Zastavit", icon="stop", on_click=cancel.set).props("outline")
            stop_button.disable()
        ui.timer(0.4, lambda: refresh_ports(port, quiet=True), once=True)
