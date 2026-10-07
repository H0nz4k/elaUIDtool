"""Desktop firmware builder; every editable setting goes into the generated app."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from nicegui import app, ui

from elatec_uid_tool.builder import (
    BuilderProject, DataRule, ENCODINGS, FORMATS, Feedback, PHYSICAL_HF, RULE_PRESETS,
    decode_escapes, escaped, preview, project_from_match,
)
from elatec_uid_tool.builder_firmware import build_project
from elatec_uid_tool.tagtypes import HF_NAMES, LF_NAMES
from elatec_uid_tool.twn4_build import validate_devpack
from firmware_ui import reader_picker, show_bix_result
from services import match_from_display
from settings_store import get_devpack_path, load_settings, save_settings

BUILTIN_PROJECTS = {
    "UID · původní HEX": BuilderProject(),
    "Jídelna · HF + LF": BuilderProject(name="Registrace Jídelny", mode="registration"),
    "Tichá čtečka": BuilderProject(name="Tichá čtečka", success=Feedback(volume=0, beeps=0),
                                   dual_success=Feedback(volume=0, beeps=0, flashes=2),
                                   error=Feedback(volume=0, beeps=0, led="red")),
    "Klávesnice · reverze / DEC": BuilderProject(name="Klávesnice DEC", channel="keyboard",
                                                hf=RULE_PRESETS["Reverze bajtů · DEC"],
                                                lf=RULE_PRESETS["Celé UID · DEC"]),
}
ENCODING_LABELS = {key: key for key in ENCODINGS}
ENCODING_LABELS.update(plain="Číslo UID", wiegand_3_5="Wiegand 3+5 (FFFCCCCC)",
                       facility_card_concat="PAC: facility + card", card_16="Pouze číslo karty (16 bitů)",
                       facility_8="Pouze facility (8 bitů)", h10301_3_5="H10301 26 bitů → Wiegand 3+5",
                       h10301_concat="H10301 → PAC", h10301_card="H10301 → číslo karty")


def _integer(value) -> int:
    if value is None or isinstance(value, bool) or float(value) != int(value):
        raise ValueError("Číselné volby musí být celá čísla.")
    return int(value)


async def save_download(path: Path) -> None:
    window = app.native.main_window
    if window:
        from webview import FileDialog
        files = await window.create_file_dialog(dialog_type=FileDialog.SAVE, save_filename=path.name)
        if files:
            import shutil
            dest = Path(files[0])
            if dest.resolve() != path.resolve():
                shutil.copy2(path, dest)
            ui.notify(f"Uloženo: {dest}", type="positive")
    else:
        ui.download.file(path)


class BuilderTab:
    def __init__(self, *, run_io, notify_ok, notify_err, log_add, switch_tab) -> None:
        self.run_io, self.notify_ok, self.notify_err = run_io, notify_ok, notify_err
        self.log_add, self.switch_tab = log_add, switch_tab
        data = load_settings()
        try:
            self.project = BuilderProject.from_dict(data.get("builder_project", {}))
        except ValueError:
            self.project = BuilderProject()
        self.samples = {"HF": ("813F9A04", 32), "LF": ("530233EC18", 40)}
        self.origin = "Vlastní projekt"
        self.render = ui.refreshable(self._render)
        self.render()

    def _persist(self, project: BuilderProject) -> None:
        settings = load_settings()
        settings["builder_project"] = project.to_dict()
        save_settings(settings)
        self.project = project

    def use_match(self, data: dict, tag_type: int | None = None, raw_hex: str | None = None,
                  bit_count: int | None = None) -> None:
        try:
            base = project_from_match(match_from_display(data), tag_type=tag_type)
            # Keep reader choice and feedback; apply conversion to the correct band only.
            try:
                current = self.collect()
            except (ValueError, TypeError):
                current = self.project
            changes = {"mode": "uid", "name": base.name, "hf_tags": base.hf_tags, "lf_tags": base.lf_tags}
            band = "LF" if tag_type in LF_NAMES else "HF"
            changes[band.lower()] = base.lf if band == "LF" else base.hf
            if tag_type is None:
                changes.update(hf=base.hf, lf=base.lf)
            project = replace(current, **changes)
            if raw_hex:
                self.samples[band] = (raw_hex, bit_count or len(raw_hex) * 4)
            self.origin = "Převzato z nalezené shody"
            self._persist(project)
            self.main_tabs.set_value("Data a konverze")
            self.band_tabs.set_value("LF · 125 / 134,2 kHz" if band == "LF" else "HF · 13,56 MHz")
            self.render.refresh()
            self.switch_tab("builder")
            self.notify_ok("Pravidlo převzato do FW builderu. Zkontroluj náhled a sestav BIX.")
        except Exception as exc:
            self.notify_err(str(exc))

    def _render(self) -> None:
        self._sample_values()
        main_tab = self.main_tabs.value if hasattr(self, "main_tabs") else "Data a konverze"
        band_tab = self.band_tabs.value if hasattr(self, "band_tabs") else "HF · 13,56 MHz"
        p = self.project
        self.fields, self.rules, self.feedbacks = {}, {}, {}
        self.selected_model = p.reader_model
        self.preview_refresh = ui.refreshable(self._preview)
        self._updating = True

        def select(label, key, options, value):
            widget = ui.select(options, label=label, value=value).classes("flex-1 min-w-40").props("outlined dense")
            widget.on_value_change(self.changed)
            self.fields[key] = widget
            return widget

        def number(label, key, value, low, high):
            widget = ui.number(label=label, value=value, min=low, max=high, step=1).classes("flex-1 min-w-40").props("outlined dense")
            widget.on_value_change(self.changed)
            self.fields[key] = widget
            return widget

        with ui.card().classes("w-full rounded-xl border border-grey-3 p-4 shadow-none gap-3"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.icon("tune", color="primary", size="md")
                ui.label("FW builder").classes("text-xl font-bold")
                ui.badge("BLD0.60 · UID + HF/LF", color="primary").props("outline")
                ui.space()
                ui.label(self.origin).classes("text-xs text-grey-7")
            ui.label("Pravidla pro další karty, ne pevně zadané číslo. Náhled a čtečka používají stejné pořadí úprav.").classes("text-sm text-grey-8")
            with ui.row().classes("w-full gap-3"):
                self.fields["name"] = ui.input("Název projektu", value=p.name).classes("flex-1").props("outlined dense")
                self.fields["name"].on_value_change(self.changed)
                select("Režim", "mode", {"uid": "Konverze UID", "registration": "Registrace Jídelny · HF → LF"}, p.mode)
                select("Výstup", "channel", {"cdc": "USB CDC · COM", "keyboard": "USB klávesnice", "uart": "UART · COM1"}, p.channel)
            with ui.expansion("Čtečka pro export", icon="contactless", value=False).classes("w-full"):
                reader_picker(p.reader_model, self.select_model)
            with ui.tabs().classes("w-full") as tabs:
                data_tab = ui.tab("Data a konverze")
                signal_tab = ui.tab("Pípání a LED")
                reader_tab = ui.tab("Čtení a výstup")
                projects_tab = ui.tab("Předvolby a projekt")
            self.main_tabs = tabs
            with ui.tab_panels(tabs, value=main_tab).classes("w-full bg-transparent"):
                with ui.tab_panel(data_tab).classes("p-0"):
                    ui.label("Reverze bitů → reverze bajtů → výběr bitů → AND/XOR → konverze → formát → délka → textový rámec.").classes("text-xs text-grey-7")
                    with ui.tabs().classes("w-full") as bands:
                        hf = ui.tab("HF · 13,56 MHz")
                        lf = ui.tab("LF · 125 / 134,2 kHz")
                    self.band_tabs = bands
                    with ui.tab_panels(bands, value=band_tab).classes("w-full bg-transparent p-0"):
                        for band, tab in (("HF", hf), ("LF", lf)):
                            with ui.tab_panel(tab).classes("p-1"):
                                self._rule_editor(band, getattr(p, band.lower()))
                    with ui.card().classes("w-full bg-blue-50 shadow-none p-3"):
                        ui.label("Živý náhled výstupu").classes("font-bold")
                        self.preview_refresh()
                    ui.label("Přesná délka odmítne delší kód. Úpravy mohou zmenšit prostor identifikátorů; ověř pravidlo na více kartách.").classes("text-xs text-grey-7")
                with ui.tab_panel(signal_tab).classes("p-0 gap-2"):
                    select("Klidová LED", "idle_led", {"off": "Zhasnuto", "green": "Zelená", "red": "Červená", "both": "Obě LED"}, p.idle_led)
                    ui.label("Zvuk a světlo se spustí současně. Počet pípnutí a bliknutí lze nastavit zvlášť; hlasitost 0 vypne zvuk.").classes("text-xs text-grey-7")
                    for key, title in (("startup", "Zapnutí čtečky"), ("success", "Nalezen jeden čip"),
                                       ("dual_success", "Nalezena dvojice HF + LF"), ("error", "Chyba převodu / dvojice")):
                        with ui.expansion(title, icon="volume_up", value=key == "success").classes("w-full border rounded-lg"):
                            self._feedback_editor(key, getattr(p, key))
                with ui.tab_panel(reader_tab).classes("p-0 gap-3"):
                    with ui.row().classes("w-full gap-3"):
                        number("Odebrání karty (ms)", "removal_ms", p.removal_ms, 100, 10000)
                        number("Opakování (ms, 0 = vypnuto)", "repeat_ms", p.repeat_ms, 0, 60000)
                        select("Konec řádku", "terminator", {"CR": "CR · Enter", "LF": "LF", "CRLF": "CR + LF", "TAB": "Tabulátor", "NONE": "Bez zakončení"}, p.terminator)
                    with ui.expansion("Registrace HF/LF · časování", icon="timer").classes("w-full"):
                        with ui.row().classes("w-full gap-3"):
                            number("Hledání druhé technologie (ms)", "other_search_ms", p.other_search_ms, 500, 10000)
                            number("Předání mezi kódy (ms)", "handoff_ms", p.handoff_ms, 200, 5000)
                            number("Přepnutí RF pásma (ms)", "rf_pause_ms", p.rf_pause_ms, 10, 300)
                        ui.label("Pro Jídelnu: CDC + CR, bez opakování a bez textových prefixů. U jednoho čipu druhé čtení ukončí prázdný CR. Pole má 16 znaků; dlouhé DEC se odmítne.").classes("text-xs text-grey-7")
                    with ui.expansion("Povolené technologie", icon="sensors").classes("w-full"):
                        for key, names, allowed in (("hf_tags", HF_NAMES, PHYSICAL_HF), ("lf_tags", LF_NAMES, tuple(LF_NAMES))):
                            tags = getattr(p, key)
                            all_widget = ui.checkbox("Všechny podporované " + key[:2].upper(), value=tags is None)
                            widget = ui.select({t: names[t][1] for t in allowed}, value=list(tags or ()), multiple=True,
                                               label=key[:2].upper() + " technologie").classes("w-full").props("outlined dense use-chips")
                            if tags is None:
                                widget.disable()
                            def changed_tags(_e, w=widget, a=all_widget):
                                w.set_enabled(not a.value)
                                self.changed()
                            all_widget.on_value_change(changed_tags)
                            widget.on_value_change(self.changed)
                            self.fields[key] = (all_widget, widget)
                        ui.label("Seznam se při spuštění protne s technologiemi podporovanými a licencovanými na čtečce. BLE a NFC P2P nejsou fyzické UID karty.").classes("text-xs text-grey-7")
                    with ui.expansion("UART · 8 datových bitů", icon="cable").classes("w-full"):
                        with ui.row().classes("w-full gap-3"):
                            select("Baud rate", "uart_baud", [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200], p.uart_baud)
                            select("Parita", "uart_parity", {"none": "Žádná", "even": "Sudá", "odd": "Lichá"}, p.uart_parity)
                            select("Stop bity", "uart_stop_bits", [1, 2], p.uart_stop_bits)
                        ui.label("UART potřebuje odpovídající fyzické rozhraní modulu; stolní USB čtečka používá CDC nebo klávesnici.").classes("text-xs text-grey-7")
                    with ui.expansion("USB a klávesnice", icon="keyboard").classes("w-full"):
                        with ui.row().classes("w-full gap-3"):
                            select("USB sériové číslo", "usb_serial", {"off": "Vypnuté", "deviceuid": "UID zařízení", "production": "Výrobní číslo"}, p.usb_serial)
                            select("Rozložení klávesnice", "keyboard_layout", {"english": "Anglické", "german": "Německé", "french": "Francouzské"}, p.keyboard_layout)
                            number("Interval kláves (ms)", "keyboard_repeat_ms", p.keyboard_repeat_ms, 1, 255)
                        for key, label in (("remote_wakeup", "USB Remote Wakeup"), ("keyboard_alt_codes", "Klávesnice: posílat Alt kódy")):
                            w = ui.checkbox(label, value=getattr(p, key))
                            w.on_value_change(self.changed)
                            self.fields[key] = w
                with ui.tab_panel(projects_tab).classes("p-0 gap-3"):
                    self._projects_editor()
            with ui.row().classes("w-full items-center gap-3"):
                build_btn = ui.button("Vytvořit BIX", icon="memory")
                build_btn.on_click(lambda: self.build(build_btn))
                ui.button("Export projektu JSON", icon="save_alt", on_click=self.export_project).props("outline")
                ui.space()
                self.validation = ui.label("").classes("text-xs text-grey-7")
            ui.label("Zdroj dat: UID. Builder nevytváří projekty pro čtení chráněných sektorů, DESFire souborů, OSDP ani správu klíčů. Nahrání BIX probíhá přes AppBlaster.").classes("text-xs text-grey-7")
        self._updating = False
        self.changed()

    def select_model(self, key: str) -> None:
        self.selected_model = key
        if not self._updating:
            self.changed()

    def _rule_editor(self, band: str, rule: DataRule) -> None:
        widgets = self.rules[band.lower()] = {}
        with ui.row().classes("w-full items-center gap-3"):
            preset = ui.select(list(RULE_PRESETS), label="Konverzní předvolba", value=None).classes("flex-1").props("outlined dense")
            def apply():
                if preset.value:
                    try:
                        p = replace(self.collect(), **{band.lower(): RULE_PRESETS[preset.value]})
                        self.project = p
                        self.render.refresh()
                    except Exception as exc:
                        self.notify_err(str(exc))
            ui.button("Použít pro " + band, on_click=apply).props("outline")
        with ui.row().classes("w-full gap-3"):
            for key, label in (("reverse_bits", "Reverze bitů"), ("reverse_bytes", "Reverze bajtů")):
                widgets[key] = ui.checkbox(label, value=getattr(rule, key))
            for key, label in (("first_bit", "První bit (od 0, zleva)"), ("bit_count", "Počet bitů (0 = do konce)")):
                widgets[key] = ui.number(label=label, value=getattr(rule, key), min=0, max=256, step=1).classes("flex-1").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            widgets["encoding"] = ui.select(ENCODING_LABELS, value=rule.encoding, label="Konverze").classes("flex-1").props("outlined dense")
            widgets["output_format"] = ui.select(list(FORMATS), value=rule.output_format, label="Formát").classes("w-28").props("outlined dense")
            widgets["length_mode"] = ui.select({"auto": "Automatická", "minimum": "Minimální", "exact": "Přesná"}, value=rule.length_mode, label="Délka").classes("w-36").props("outlined dense")
            widgets["length"] = ui.number(label="Znaků", value=rule.length, min=0, max=256, step=1).classes("w-24").props("outlined dense")
        with ui.expansion("Další úpravy dat a textu", icon="transform").classes("w-full"):
            with ui.row().classes("w-full gap-3"):
                for key, label in (("and_mask", "AND maska (HEX)"), ("xor_mask", "XOR maska (HEX)")):
                    widgets[key] = ui.input(label, value=getattr(rule, key)).classes("flex-1").props("outlined dense")
            with ui.row().classes("w-full gap-3"):
                for key, label in (("lowercase", "Malá písmena"), ("strip_zeros", "Odstranit úvodní nuly"), ("append_00", "Přidat 00 na konec textu")):
                    widgets[key] = ui.checkbox(label, value=getattr(rule, key))
            with ui.row().classes("w-full gap-3"):
                for key, label in (("prefix", "Prefix"), ("suffix", "Suffix")):
                    widgets[key] = ui.input(label, value=escaped(getattr(rule, key))).classes("flex-1").props("outlined dense")
                widgets["byte_separator"] = ui.select({"": "Bez oddělovače", ":": "Dvojtečka", "-": "Pomlčka", " ": "Mezera"}, value=rule.byte_separator, label="HEX bajty").classes("flex-1").props("outlined dense")
            ui.label(r"Prefix/suffix: ASCII text, lze použít \r, \n, \t, \b, \e, \\. AND/XOR se počítá po výběru bitů. ASCII formát přijímá tisknutelné bajty.").classes("text-xs text-grey-7")
        raw, bits = self.samples[band]
        with ui.row().classes("w-full gap-3"):
            raw_w = ui.input(band + " · RAW HEX pro náhled", value=raw).classes("flex-1").props("outlined dense")
            bit_w = ui.number(band + " · Platných bitů", value=bits, min=1, max=256, step=1).classes("w-40").props("outlined dense")
        self.samples[band] = (raw_w, bit_w)
        for widget in [*widgets.values(), raw_w, bit_w]:
            widget.on_value_change(self.changed)

    def _feedback_editor(self, key: str, pattern: Feedback) -> None:
        widgets = self.feedbacks[key] = {}
        with ui.row().classes("w-full gap-3"):
            for name, label, low, high in (("volume", "Hlasitost (%)", 0, 100), ("frequency", "Frekvence (Hz)", 100, 10000),
                                           ("beeps", "Pípnutí", 0, 10), ("flashes", "Bliknutí", 0, 10)):
                widgets[name] = ui.number(label=label, value=getattr(pattern, name), min=low, max=high, step=1).classes("flex-1 min-w-24").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            widgets["led"] = ui.select({"off": "Zhasnuto", "red": "Červená", "green": "Zelená", "both": "Obě"}, label="LED", value=pattern.led).classes("flex-1").props("outlined dense")
            for name, label in (("on_ms", "Doba pulzu (ms)"), ("off_ms", "Pauza (ms)")):
                widgets[name] = ui.number(label=label, value=getattr(pattern, name), min=10, max=1000, step=1).classes("flex-1").props("outlined dense")
        for widget in widgets.values():
            widget.on_value_change(self.changed)

    def collect(self) -> BuilderProject:
        values = {key: widget.value for key, widget in self.fields.items() if key not in ("hf_tags", "lf_tags")}
        for key in ("removal_ms", "repeat_ms", "other_search_ms", "handoff_ms", "rf_pause_ms", "uart_baud", "uart_stop_bits", "keyboard_repeat_ms"):
            values[key] = _integer(values[key])
        for key in ("hf_tags", "lf_tags"):
            all_w, w = self.fields[key]
            values[key] = None if all_w.value else tuple(w.value or ())
        for band, widgets in self.rules.items():
            rule = {key: widget.value for key, widget in widgets.items()}
            for key in ("first_bit", "bit_count", "length"):
                rule[key] = _integer(rule[key])
            for key in ("prefix", "suffix"):
                rule[key] = decode_escapes(rule[key] or "")
            values[band] = DataRule(**rule)
        for key, widgets in self.feedbacks.items():
            pattern = {name: w.value if name == "led" else _integer(w.value) for name, w in widgets.items()}
            values[key] = Feedback(**pattern)
        return BuilderProject(**values, reader_model=self.selected_model)

    def changed(self, _e=None) -> None:
        if self._updating:
            return
        try:
            self.collect()
            self.validation.text = "Projekt je platný"
        except (ValueError, TypeError) as exc:
            self.validation.text = str(exc)
        self.preview_refresh.refresh()

    def _preview(self) -> None:
        try:
            project = self.collect()
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            ui.label("Náhled: " + str(exc)).classes("text-sm text-warning")
            return
        for band in ("HF", "LF"):
            raw_w, bits_w = self.samples[band]
            try:
                result = preview(project, raw_w.value, band, _integer(bits_w.value))
                with ui.column().classes("w-full gap-0"):
                    ui.label(f"{band}: {result.value}").classes("text-base font-bold font-mono break-all")
                    ui.label("Bity po úpravě: " + result.selected_bits).classes("text-xs font-mono break-all text-grey-7")
                    ui.label("Odešle: " + escaped(result.framed)).classes("text-xs font-mono break-all")
                    ui.label("Bajty: " + result.wire_hex).classes("text-xs font-mono break-all text-grey-7")
            except (ValueError, TypeError, AttributeError) as exc:
                ui.label(f"{band}: {exc}").classes("text-sm text-warning")

    def _sample_values(self) -> None:
        for band, (raw, bits) in self.samples.items():
            if hasattr(raw, "value"):
                self.samples[band] = (raw.value, bits.value if bits.value is not None else 32)

    def _projects_editor(self) -> None:
        custom = load_settings().get("builder_presets", {})
        if not isinstance(custom, dict):
            custom = {}
        choices = {"builtin:" + name: name for name in BUILTIN_PROJECTS}
        choices.update({"user:" + name: "Moje · " + name for name in custom})
        with ui.row().classes("w-full gap-3"):
            select = ui.select(choices, value=next(iter(choices)), label="Předvolba celého projektu").classes("flex-1").props("outlined dense")
            def apply():
                try:
                    kind, name = select.value.split(":", 1)
                    project = BUILTIN_PROJECTS[name] if kind == "builtin" else BuilderProject.from_dict(custom[name])
                    self._sample_values()
                    self._persist(project)
                    self.origin = "Předvolba: " + name
                    self.render.refresh()
                except Exception as exc:
                    self.notify_err(str(exc))
            ui.button("Načíst předvolbu", on_click=apply).props("outline")
        def save():
            try:
                p = self.collect()
                data = load_settings()
                presets = data.get("builder_presets")
                presets = dict(presets) if isinstance(presets, dict) else {}
                presets[p.name] = p.to_dict()
                data.update(builder_presets=presets, builder_project=p.to_dict())
                save_settings(data)
                self.project = p
                self._sample_values()
                self.render.refresh()
                self.notify_ok("Předvolba uložena: " + p.name)
            except Exception as exc:
                self.notify_err(str(exc))
        def delete():
            if not select.value.startswith("user:"):
                self.notify_err("Vestavěné předvolby jsou součástí programu.")
                return
            name = select.value.split(":", 1)[1]
            data = load_settings()
            presets = data.get("builder_presets", {})
            presets.pop(name, None)
            data["builder_presets"] = presets
            save_settings(data)
            self.project = self.collect()
            self._sample_values()
            self.render.refresh()
            self.notify_ok("Předvolba odstraněna: " + name)
        with ui.row().classes("gap-3"):
            ui.button("Uložit vlastní předvolbu", icon="bookmark", on_click=save).props("outline")
            ui.button("Odstranit vybranou", icon="delete_outline", on_click=delete).props("flat")
        async def upload(e):
            try:
                if e.file.size() > 65536:
                    raise ValueError("Projekt JSON je příliš velký (max. 64 KiB).")
                text = await e.file.text()
                p = BuilderProject.from_json(text)
                self._sample_values()
                self._persist(p)
                self.origin = "Import projektu JSON"
                self.render.refresh()
                self.notify_ok("Projekt načten: " + p.name)
            except Exception as exc:
                self.notify_err(str(exc))
        ui.upload(label="Import projektu JSON", on_upload=upload, auto_upload=True, max_file_size=65536).props('accept=".json"').classes("w-full")
        ui.label("Projekt obsahuje pravidla, časování i signalizaci. Vygenerovaný BIX dostane projekt, manifest se SHA-256 a ZIP zdrojů bez SDK.").classes("text-xs text-grey-7")

    async def export_project(self) -> None:
        try:
            p = self.collect()
            self._persist(p)
            name = re.sub(r"[^a-zA-Z0-9_-]", "_", p.name).strip("_") or "firmware"
            # Do not write user projects into vendor SDK or derive a target from imported paths.
            from app_paths import app_root
            path = app_root() / "data" / "builder_projects" / (name + ".project.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(p.to_json(), encoding="utf-8")
            await save_download(path)
        except Exception as exc:
            self.notify_err(str(exc))

    async def build(self, button) -> None:
        button.disable()
        button.props("loading")
        try:
            p = self.collect()
            pack = get_devpack_path()
            missing = validate_devpack(pack, standard=False, usb_type="keyboard" if p.channel == "keyboard" else "cdc")
            if missing:
                raise ValueError(f"DevPack 5.20 není kompletní: {pack}\n" + "\n".join(missing) + "\nCestu nastav v Nastavení.")
            self._persist(p)
            self.log_add("Sestavuji BIX: " + p.name)
            result = await self.run_io(build_project, p, devpack=pack)
            self.notify_ok("BIX sestaven: " + result.bix_path.name)
            await show_bix_result(result.bix_path, extra_files={
                "Projekt JSON": result.project_path, "Manifest": result.manifest_path, "Zdroje ZIP": result.source_zip,
            })
        except Exception as exc:
            self.notify_err(str(exc))
        finally:
            button.enable()
            button.props(remove="loading")


def build_builder_tab(**kwargs) -> BuilderTab:
    return BuilderTab(**kwargs)
