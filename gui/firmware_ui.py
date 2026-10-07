"""Výběr čtečky s lokálními produktovými obrázky a uložení sestaveného BIX."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from nicegui import app, ui

from app_paths import app_root, bundle_root
from elatec_uid_tool.reader_models import DEFAULT_READER_MODEL, READER_MODELS, get_reader_model


def reader_image(model_key: str) -> Path:
    filename = get_reader_model(model_key).image
    for root in (Path(__file__).resolve().parent / "assets", bundle_root() / "assets",
                 bundle_root() / "gui" / "assets", app_root() / "gui" / "assets"):
        path = root / "readers" / filename
        if path.is_file():
            return path
    raise FileNotFoundError(f"Chybí produktový obrázek: {filename}")


def reader_picker(selected: str, on_change: Callable[[str], None]) -> dict[str, ui.element]:
    cards = {}

    def select(key: str) -> None:
        for model_key, card in cards.items():
            card.classes(add="border-primary bg-blue-50" if model_key == key else "border-grey-3 bg-white",
                         remove="border-grey-3 bg-white" if model_key == key else "border-primary bg-blue-50")
            card.props(f"aria-pressed={'true' if model_key == key else 'false'}")
        on_change(key)

    with ui.row().classes("w-full gap-3 no-wrap items-stretch"):
        for model in READER_MODELS:
            with ui.card().classes("flex-1 min-w-0 shadow-none border-2 rounded-xl cursor-pointer p-3").props(
                f'role=button tabindex=0 aria-label="{model.name}"'
            ) as card:
                card.on("click", lambda _e, key=model.key: select(key))
                card.on("keydown.enter", lambda _e, key=model.key: select(key))
                card.on("keydown.space.prevent", lambda _e, key=model.key: select(key))
                ui.image(str(reader_image(model.key))).props("fit=contain no-spinner").classes("w-full").style("height: 145px")
                ui.label(model.name).classes("text-sm font-bold")
                ui.label(model.description).classes("text-xs text-grey-7")
            cards[model.key] = card
    select(selected)
    return cards


async def choose_reader(default: str = DEFAULT_READER_MODEL) -> str | None:
    selection = {"key": default}
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl p-5"):
        ui.label("Vyber čtečku pro export BIX").classes("text-lg font-bold")
        reader_picker(default, lambda key: selection.update(key=key))
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Zrušit", on_click=lambda: dialog.submit(None)).props("flat")
            ui.button("Sestavit BIX", icon="download", on_click=lambda: dialog.submit(selection["key"]))
    return await dialog


async def show_bix_result(path: Path) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-xl p-5"):
        ui.icon("check_circle", color="positive", size="md")
        ui.label("Firmware je sestavený").classes("text-lg font-bold")
        ui.label(path.name).classes("font-mono text-sm break-all")
        ui.label(str(path.parent)).classes("text-xs text-grey-7 break-all")
        ui.label("V AppBlasteru: Program Firmware Image → Select Image → Program Image.").classes("text-sm")

        async def save_as() -> None:
            window = app.native.main_window
            if window:
                from webview import FileDialog
                files = await window.create_file_dialog(dialog_type=FileDialog.SAVE, save_filename=path.name,
                                                       file_types=("Firmware (*.bix)",))
                if files:
                    import shutil
                    dest = Path(files[0])
                    if dest.suffix.lower() != ".bix":
                        dest = dest.with_suffix(".bix")
                    if dest.resolve() != path.resolve():
                        shutil.copy2(path, dest)
                    ui.notify(f"Uloženo: {dest}", type="positive")
            else:
                ui.download.file(path)

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Uložit BIX jako…", icon="save_alt", on_click=save_as)
            ui.button("Zavřít", on_click=dialog.close).props("flat")
    dialog.open()
