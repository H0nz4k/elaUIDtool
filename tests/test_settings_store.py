import tempfile
import unittest
from pathlib import Path
import sys

GUI = Path(__file__).resolve().parents[1] / "gui"
sys.path.insert(0, str(GUI))

import settings_store  # noqa: E402


class SettingsStoreTests(unittest.TestCase):
    def test_roundtrip_devpack_path(self):
        original = settings_store.SETTINGS_PATH
        with tempfile.TemporaryDirectory() as tmp:
            settings_store.SETTINGS_PATH = Path(tmp) / "user_settings.json"
            try:
                path = settings_store.set_devpack_path(tmp)
                self.assertEqual(settings_store.get_devpack_path(), path)
                data = settings_store.load_settings()
                self.assertEqual(data["devpack_path"], str(path))
            finally:
                settings_store.SETTINGS_PATH = original

    def test_validate_missing_devpack(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = settings_store.validate_devpack(Path(tmp))
            self.assertIn("Tools/makeapp.exe", missing)
            self.assertIn("Apps/TWN4_NCx520.bix", missing)


if __name__ == "__main__":
    unittest.main()
