import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from elatec_uid_tool.bix_container import parse, system_pairs
from elatec_uid_tool.reader_models import READER_MODELS
from elatec_uid_tool.registration import RegistrationConfig, build_registration_firmware
from elatec_uid_tool.twn4_build import BASE_NAME, ToolchainOptions


@unittest.skipUnless(os.environ.get("ELA_TEST_DEVPACK"), "Volitelný reálný build: nastav ELA_TEST_DEVPACK")
class RegistrationBuildTests(unittest.TestCase):
    def test_both_models_and_all_format_pairs_preserve_sdk_system_images(self):
        pack = Path(os.environ["ELA_TEST_DEVPACK"])
        original = system_pairs(parse((pack / "Firmware" / BASE_NAME).read_bytes()))
        options = ToolchainOptions(os.environ.get("ELA_TEST_GCC"), os.environ.get("ELA_TEST_OBJCOPY"),
                                   os.environ.get("ELA_TEST_MAKEAPP_RUNTIME"))
        with tempfile.TemporaryDirectory() as directory:
            for model in READER_MODELS:
                for hf in ("HEX", "DEC"):
                    for lf in ("HEX", "DEC"):
                        with self.subTest(model=model.key, hf=hf, lf=lf):
                            result = build_registration_firmware(
                                RegistrationConfig(hf, lf), reader_model=model.key, devpack=pack,
                                output_dir=Path(directory), toolchain=options,
                            )
                            data = result.bix_path.read_bytes()
                            actual = system_pairs(parse(data))
                            self.assertEqual([(a.encoded, b.encoded) for a, b in actual],
                                             [(a.encoded, b.encoded) for a, b in original])
                            manifest = json.loads(result.manifest_path.read_text())
                            self.assertEqual(manifest["sha256"], hashlib.sha256(data).hexdigest())
                            self.assertEqual((manifest["hf_format"], manifest["lf_format"]), (hf, lf))
                            self.assertEqual(manifest["reader_model"], model.name)
