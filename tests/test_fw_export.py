import unittest
from pathlib import Path

from elatec_uid_tool.analyzer import analyze_uid
from elatec_uid_tool.fw_export import DEFAULT_DEVPACK, generate_app_source, generate_appconfig_c


class FirmwareExportSourceTests(unittest.TestCase):
    def test_wiegand_appconfig_contains_formula(self):
        _, matches = analyze_uid("AE1C56CF", 32, "08607342", "auto", 20)
        wiegand = next(m for m in matches if m.encoding == "wiegand_3_5")
        src = generate_appconfig_c(wiegand, channel="cdc", tag_type=0x80)
        self.assertIn("facility * 100000u + card", src)
        self.assertIn("ReadType1", src)
        self.assertIn("CompLEDInit", src)
        self.assertIn("SetHostChannel(CHANNEL_USB)", src)
        self.assertNotIn("int main", src)

    def test_wiegand_source_contains_formula(self):
        _, matches = analyze_uid("AE1C56CF", 32, "08607342", "auto", 20)
        wiegand = next(m for m in matches if m.encoding == "wiegand_3_5")
        src = generate_app_source(wiegand, channel="cdc", tag_type=0x80)
        self.assertIn("facility * 100000u + card", src)
        self.assertIn("CFG_REVERSE_BYTE true", src)
        self.assertIn("CHANNEL_USB", src)
        self.assertIn("TAGMASK(0x80)", src)

    def test_pac_concat_source(self):
        _, matches = analyze_uid("AE1C56CF", 32, "867342", "decimal", 30)
        hit = next(m for m in matches if m.encoding == "facility_card_concat")
        src = generate_app_source(hit, channel="cdc", tag_type=0x80)
        self.assertIn("code *= 10u", src)
        self.assertIn("GetBitMSB", src)

    def test_plain_decimal_em4102_window(self):
        _, matches = analyze_uid("3D00C000D4", 40, "12583124", "decimal", 20)
        best = matches[0]
        src = generate_app_source(best, channel="uart", tag_type=0x40)
        self.assertIn("CFG_FIRST_BIT    8", src)
        self.assertIn("CFG_NUM_BITS     32", src)
        self.assertIn("CFG_REVERSE_BIT  false", src)
        self.assertIn("CFG_REVERSE_BYTE false", src)
        self.assertIn("ConvertBinaryToString", src)
        self.assertIn("CHANNEL_COM1", src)
        self.assertIn("SetCOMParameters", src)
        self.assertNotIn("facility * 100000u", src)

    def test_hex_output_uses_radix_16(self):
        _, matches = analyze_uid("AE1C56CF", 32, "CF561CAE", "hexadecimal", 20)
        hex_matches = [m for m in matches if "Hex" in m.output_format]
        self.assertTrue(hex_matches)
        src = generate_app_source(hex_matches[0], channel="cdc")
        self.assertIn("ConvertBinaryToString(CardData, 0, CardDataBitCnt, CardString, 16,", src)


@unittest.skipUnless(
    (DEFAULT_DEVPACK / "Apps" / "TWN4_NCx520.bix").exists(),
    "Family BIX CCx/MCx/NCx nejsou v elafiles/Apps",
)
class FirmwareExportMakeappInputTests(unittest.TestCase):
    def test_uses_ccx_mcx_ncx_family_images(self):
        from elatec_uid_tool.fw_export import _makeapp_input_bixes

        base = DEFAULT_DEVPACK / "Firmware" / "TWN4_xCx520_STD207_Multi_CDC_Standard.bix"
        out = Path(__file__).resolve().parents[1] / "FW_elatec" / "export" / "out_test"
        out.mkdir(parents=True, exist_ok=True)
        inputs = _makeapp_input_bixes(DEFAULT_DEVPACK.resolve(), base, out)
        names = [p.name for p in inputs]
        self.assertEqual(
            names,
            ["TWN4_CCx520.bix", "TWN4_MCx520.bix", "TWN4_NCx520.bix"],
        )


@unittest.skipUnless(
    (DEFAULT_DEVPACK / "Tools" / "makeapp.exe").exists(),
    "DevPack elafiles/ není k dispozici",
)
class FirmwareExportBuildTests(unittest.TestCase):
    def test_build_wiegand_cdc(self):
        from elatec_uid_tool.fw_export import build_firmware

        _, matches = analyze_uid("AE1C56CF", 32, "08607342", "auto", 20)
        wiegand = next(m for m in matches if m.encoding == "wiegand_3_5")
        out = Path(__file__).resolve().parents[1] / "FW_elatec" / "export" / "out_test"
        result = build_firmware(
            wiegand,
            channel="cdc",
            tag_type=0x80,
            output_dir=out,
        )
        self.assertTrue(result.bix_path.exists())
        self.assertTrue(result.appconfig_h.exists())
        self.assertEqual(result.source_c.name, "appconfig.c")
        packed = result.bix_path.read_bytes()
        self.assertGreater(len(packed), 700_000)
        self.assertGreaterEqual(packed.count(b"flashinfo"), 3)
        self.assertIn(b"nCFmi", packed)


if __name__ == "__main__":
    unittest.main()
