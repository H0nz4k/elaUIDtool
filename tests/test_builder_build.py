from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from elatec_uid_tool.analyzer import analyze_uid
from elatec_uid_tool.bix_container import parse, system_pairs
from elatec_uid_tool.builder import BuilderProject, DataRule, Feedback, project_from_match
from elatec_uid_tool.builder_firmware import build_project
from elatec_uid_tool.reader_models import READER_MODELS
from elatec_uid_tool.twn4_build import BASE_NAME, KEYBOARD_BASE_NAME, ToolchainOptions


@unittest.skipUnless(os.environ.get("ELA_TEST_DEVPACK"), "Reálný SDK build: nastav ELA_TEST_DEVPACK")
class BuilderBuildTests(unittest.TestCase):
    def test_models_channels_and_registration_preserve_all_system_images(self):
        pack = Path(os.environ["ELA_TEST_DEVPACK"])
        options = ToolchainOptions(os.environ.get("ELA_TEST_GCC"), os.environ.get("ELA_TEST_OBJCOPY"),
                                   os.environ.get("ELA_TEST_MAKEAPP_RUNTIME"))
        _, matches = analyze_uid("AE1C56CF", 32, "08607342", "decimal", 30)
        match = next(m for m in matches if m.encoding == "wiegand_3_5")
        projects = [BuilderProject(),
                    BuilderProject(channel="keyboard", usb_serial="deviceuid", keyboard_layout="german", keyboard_alt_codes=True),
                    BuilderProject(channel="uart", uart_baud=115200, uart_parity="even", uart_stop_bits=2),
                    replace(project_from_match(match, tag_type=0x80), success=Feedback(volume=42, beeps=3, flashes=2)),
                    BuilderProject(hf=DataRule(and_mask="FFFFFFFF", xor_mask="1", prefix="ID:\t", byte_separator=":"),
                                   repeat_ms=500, remote_wakeup=True, terminator="CRLF"),
                    BuilderProject(mode="registration", hf=DataRule(reverse_bytes=True), lf=DataRule(output_format="DEC"),
                                   other_search_ms=750, rf_pause_ms=50, handoff_ms=250),
                    BuilderProject(hf=DataRule(output_format="ASCII"), lf=DataRule(output_format="BIN"))]
        with tempfile.TemporaryDirectory() as directory:
            for model in READER_MODELS:
                for project in projects:
                    project = replace(project, reader_model=model.key)
                    original = system_pairs(parse((pack / "Firmware" / (KEYBOARD_BASE_NAME if project.channel == "keyboard" else BASE_NAME)).read_bytes()))
                    with self.subTest(model=model.key, channel=project.channel, mode=project.mode):
                        result = build_project(project, devpack=pack, output_dir=Path(directory), toolchain=options)
                        actual = system_pairs(parse(result.bix_path.read_bytes()))
                        self.assertEqual([(a.encoded, b.encoded) for a, b in actual],
                                         [(a.encoded, b.encoded) for a, b in original])
                        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
                        self.assertEqual(manifest["sha256"], hashlib.sha256(result.bix_path.read_bytes()).hexdigest())
                        self.assertEqual(manifest["project"], json.loads(project.to_json()))
                        self.assertEqual(manifest["usb_type"], "keyboard" if project.channel == "keyboard" else "cdc")
                        self.assertEqual(BuilderProject.from_json(result.project_path.read_text(encoding="utf-8")), project)
                        with zipfile.ZipFile(result.source_zip) as archive:
                            self.assertIn("data_rule.c", archive.namelist())
                            self.assertIn("feedback.c", archive.namelist())
                            self.assertNotIn("twn4.sys.h", archive.namelist())
                            self.assertEqual(BuilderProject.from_json(archive.read("project.json").decode("utf-8")), project)


if __name__ == "__main__":
    unittest.main()
