#!/usr/bin/env python3
"""Optional end-to-end desktop GUI check (Playwright; no physical reader/DB)."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def serve(port: int) -> None:
    sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "src")]
    import app as desktop
    if os.environ.get("ELA_TEST_DEVPACK"):
        import builder_tab
        from elatec_uid_tool.twn4_build import ToolchainOptions
        original = builder_tab.build_project
        options = ToolchainOptions(os.environ.get("ELA_TEST_GCC"), os.environ.get("ELA_TEST_OBJCOPY"),
                                   os.environ.get("ELA_TEST_MAKEAPP_RUNTIME"))
        builder_tab.build_project = lambda *args, **kwargs: original(*args, **kwargs, toolchain=options)
    desktop.ui.run(host="127.0.0.1", port=port, show=False, reload=False, native=False, storage_secret="gui-test")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", type=int)
    parser.add_argument("--gui-executable")
    parser.add_argument("--browser-executable")
    parser.add_argument("--screenshots")
    args = parser.parse_args()
    if args.serve:
        serve(args.serve)
        return
    from playwright.sync_api import expect, sync_playwright
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    settings_root = Path(args.gui_executable).resolve().parent if args.gui_executable else ROOT
    settings = settings_root / "user_settings.json"
    previous = settings.read_bytes() if settings.exists() else None
    settings.write_text(json.dumps({"devpack_path": os.environ.get("ELA_TEST_DEVPACK", str(ROOT / "elafiles"))}), encoding="utf-8")
    command = [args.gui_executable, "--browser", "--port", str(port)] if args.gui_executable else [sys.executable, str(__file__), "--serve", str(port)]
    with tempfile.TemporaryDirectory(prefix="builder-gui-") as temporary:
        log_path = Path(temporary) / "server.log"
        with log_path.open("w", encoding="utf-8") as log:
            server = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            url = f"http://127.0.0.1:{port}"
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("GUI exited: " + log_path.read_text(encoding="utf-8"))
                try:
                    urllib.request.urlopen(url, timeout=.5).close()
                    break
                except Exception:
                    time.sleep(.2)
            else:
                raise RuntimeError("GUI did not start")
            with sync_playwright() as playwright:
                options = {"headless": True, "args": ["--no-sandbox"]}
                if os.name != "nt":
                    options["args"] += ["--single-process", "--no-zygote"]
                if args.browser_executable:
                    options["executable_path"] = args.browser_executable
                browser = playwright.chromium.launch(**options)
                page = browser.new_page(viewport={"width": 1280, "height": 1100})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)

                def field(label):
                    return page.get_by_label(label, exact=True).and_(page.locator(":visible"))

                def choose(label, value):
                    field(label).click()
                    page.get_by_role("option", name=value, exact=True).click()

                def screenshot(name):
                    if args.screenshots:
                        directory = Path(args.screenshots)
                        directory.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(directory / name), full_page=True)

                print("GUI: found conversion -> project", flush=True)
                field("Kód z čtečky (RAW UID hex)").fill("AE1C56CF")
                field("Kód z databáze").fill("08607342")
                page.get_by_role("button", name="Porovnat a najít pravidlo", exact=True).click()
                page.get_by_role("button", name="Upravit ve FW builderu", exact=True).click()
                expect(page.get_by_text("HF: 08607342", exact=True)).to_be_visible()
                expect(field("HF · RAW HEX pro náhled")).to_have_value("AE1C56CF")
                screenshot("builder-found-rule.png")

                print("GUI: independent rules and live preview", flush=True)
                choose("Konverzní předvolba", "Reverze bajtů · HEX")
                page.get_by_role("button", name="Použít pro HF", exact=True).click()
                expect(page.get_by_text("HF: CF561CAE", exact=True)).to_be_visible()
                field("HF · RAW HEX pro náhled").fill("813F9A04")
                expect(page.get_by_text("HF: 049A3F81", exact=True)).to_be_visible()
                page.get_by_role("tab", name="LF · 125 / 134,2 kHz", exact=True).click()
                expect(page.get_by_label("HF · RAW HEX pro náhled", exact=True)).to_be_hidden()
                choose("Formát", "DEC")
                expect(page.get_by_text("LF: 356519242776", exact=True)).to_be_visible()

                page.get_by_role("tab", name="Pípání a LED", exact=True).click()
                expect(page.get_by_label("LF · RAW HEX pro náhled", exact=True)).to_be_hidden()
                field("Hlasitost (%)").fill("42")
                field("Pípnutí").fill("3")
                field("Bliknutí").fill("2")
                screenshot("builder-feedback.png")
                page.get_by_text("Čtečka pro export", exact=True).and_(page.locator(":visible")).click()
                field("TWN4 MULTITECH 3 M LF HF").click()
                images = page.locator("img:visible")
                assert all(images.evaluate_all("es => es.map(e => e.complete && e.naturalWidth > 0)")), "Reader images must load"

                print("GUI: preset and project JSON roundtrip", flush=True)
                field("Název projektu").fill("QA builder")
                page.get_by_role("tab", name="Předvolby a projekt", exact=True).click()
                page.get_by_role("button", name="Uložit vlastní předvolbu", exact=True).click()
                expect(page.get_by_text("Předvolba uložena: QA builder", exact=True)).to_be_visible()
                with page.expect_download() as download_info:
                    page.get_by_role("button", name="Export projektu JSON", exact=True).click()
                download = download_info.value
                project_file = Path(temporary) / "project.json"
                download.save_as(project_file)
                project = json.loads(project_file.read_text(encoding="utf-8"))
                assert project["hf"]["reverse_bytes"] and project["lf"]["output_format"] == "DEC"
                assert project["success"]["volume"] == 42 and project["success"]["beeps"] == 3 and project["success"]["flashes"] == 2
                assert project["reader_model"] == "multitech3-m-lf-hf"
                choose("Předvolba celého projektu", "UID · původní HEX")
                page.get_by_role("button", name="Načíst předvolbu", exact=True).click()
                expect(field("Název projektu")).to_have_value("Moje konverze")
                page.get_by_role("tab", name="Předvolby a projekt", exact=True).click()
                choose("Předvolba celého projektu", "Moje · QA builder")
                page.get_by_role("button", name="Načíst předvolbu", exact=True).click()
                expect(field("Název projektu")).to_have_value("QA builder")
                page.get_by_role("tab", name="Předvolby a projekt", exact=True).click()
                project["name"] = "Imported QA"
                project_file.write_text(json.dumps(project), encoding="utf-8")
                page.locator('input[type="file"]').set_input_files(project_file)
                expect(field("Název projektu")).to_have_value("Imported QA")

                if os.environ.get("ELA_TEST_DEVPACK"):
                    print("GUI: real SDK BIX and sources download", flush=True)
                    page.get_by_role("button", name="Vytvořit BIX", exact=True).click()
                    expect(page.get_by_text("Firmware je sestavený", exact=True)).to_be_visible(timeout=30000)
                    with page.expect_download() as info:
                        page.get_by_role("button", name="Uložit BIX jako…", exact=True).click()
                    bix = Path(temporary) / "reader.bix"
                    info.value.save_as(bix)
                    assert bix.stat().st_size > 700000
                    with page.expect_download() as info:
                        page.get_by_role("button", name="Zdroje ZIP", exact=True).click()
                    assert info.value.suggested_filename.endswith(".sources.zip")
                    page.get_by_role("button", name="Zavřít", exact=True).click()

                print("GUI: selected candidate from table", flush=True)
                page.get_by_text("Porovnání", exact=True).first.click()
                page.get_by_role("button", name="Zobrazit všechny (10)", exact=True).click()
                dialog = page.get_by_role("dialog")
                dialog.locator("tbody").get_by_role("checkbox").nth(1).click()
                page.get_by_role("button", name="Upravit vybraný ve FW builderu", exact=True).click()
                expect(page.get_by_text("HF: 8607342", exact=True)).to_be_visible()
                assert not errors, errors
                assert "Traceback" not in log_path.read_text(encoding="utf-8"), log_path.read_text(encoding="utf-8")
                screenshot("builder-final.png")
                browser.close()
                print("GUI: all checks passed", flush=True)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
            if previous is None:
                settings.unlink(missing_ok=True)
            else:
                settings.write_bytes(previous)
            log_text = log_path.read_text(encoding="utf-8")
            if "Traceback" in log_text:
                print(log_text[-6000:], file=sys.stderr)


if __name__ == "__main__":
    main()
