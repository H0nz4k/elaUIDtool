from dataclasses import replace
import json
import tempfile
from pathlib import Path
import unittest

from elatec_uid_tool.analyzer import analyze_uid
from elatec_uid_tool.builder import (
    BuilderProject, DataRule, Feedback, RULE_PRESETS, apply_rule, decode_escapes, preview,
    project_from_match, save_project,
)
from elatec_uid_tool.builder_firmware import builder_sources, c_string


class BuilderTests(unittest.TestCase):
    def test_terkom_byte_reverse(self):
        rule = RULE_PRESETS["Reverze bajtů · HEX"]
        self.assertEqual(apply_rule("813F9A04", rule)[2], "049A3F81")

    def test_full_uid_not_zero_padded(self):
        self.assertEqual(apply_rule("04112233", DataRule())[2], "04112233")
        self.assertEqual(apply_rule("04112233", DataRule(output_format="DEC"))[2], "68231731")

    def test_full_256_bit_decimal_is_exact(self):
        value = apply_rule("FF" * 32, DataRule(output_format="DEC"))[2]
        self.assertEqual(value, str(2**256 - 1))

    def test_real_analyzer_candidates_produce_expected_numeric_output(self):
        for raw, expected, fmt in (("AE1C56CF", "08607342", "decimal"),
                                   ("AE1C56CF", "867342", "decimal"),
                                   ("3D00C000D4", "12583124", "decimal"),
                                   ("813F9A04", "049A3F81", "hexadecimal")):
            _, matches = analyze_uid(raw, len(raw) * 4, expected, fmt, 100)
            self.assertTrue(matches)
            for match in matches:
                with self.subTest(raw=raw, encoding=match.encoding, format=match.output_format):
                    output = preview(project_from_match(match), raw).value
                    self.assertEqual(int(output, 16 if fmt == "hexadecimal" else 10), int(expected, 16 if fmt == "hexadecimal" else 10))

    def test_wiegand_uses_low_24_bits_of_long_window(self):
        rule = DataRule(encoding="wiegand_3_5", output_format="DEC")
        self.assertEqual(apply_rule("AA561CAE", rule)[2], "08607342")

    def test_h10301_skips_parity(self):
        payload = (86 << 16) | 7342
        bits = f"0{payload:024b}1"
        raw = f"{int(bits.ljust(32, '0'), 2):08X}"
        rule = DataRule(bit_count=26, encoding="h10301_3_5", output_format="DEC")
        self.assertEqual(apply_rule(raw, rule, 26)[2], "08607342")
        with self.assertRaises(ValueError):
            apply_rule(raw, replace(rule, bit_count=25), 26)

    def test_masks_and_framing(self):
        rule = DataRule(first_bit=8, bit_count=16, and_mask="0FFF", xor_mask="0001",
                        prefix="ID:", suffix="!", byte_separator=":")
        output = preview(BuilderProject(hf=rule, terminator="CRLF"), "AA1234FF")
        self.assertEqual(output.value, "ID:02:35!")
        self.assertEqual(output.framed, "ID:02:35!\r\n")
        self.assertEqual(bytes.fromhex(output.wire_hex), b"ID:02:35!\r\n")

    def test_mask_overflow_and_invalid_reverse_rejected(self):
        with self.assertRaises(ValueError):
            apply_rule("FF", DataRule(xor_mask="100"))
        with self.assertRaises(ValueError):
            apply_rule("FFFF", DataRule(reverse_bytes=True), 13)

    def test_exact_length_never_truncates(self):
        with self.assertRaises(ValueError):
            apply_rule("FFFF", DataRule(length_mode="exact", length=2))
        self.assertEqual(apply_rule("FF", DataRule(length_mode="exact", length=4))[2], "00FF")

    def test_binary_octal_ascii(self):
        self.assertEqual(apply_rule("AA", DataRule(output_format="BIN"))[2], "10101010")
        self.assertEqual(apply_rule("FF", DataRule(output_format="OCT"))[2], "377")
        self.assertEqual(apply_rule("54455354", DataRule(output_format="ASCII"))[2], "TEST")
        with self.assertRaises(ValueError):
            apply_rule("54450054", DataRule(output_format="ASCII"))

    def test_remove_zeros_lowercase_padding_append(self):
        rule = DataRule(strip_zeros=True, lowercase=True, length_mode="minimum", length=4, append_00=True)
        self.assertEqual(apply_rule("0000AB", rule)[2], "00ab00")

    def test_independent_hf_lf_rules(self):
        p = BuilderProject(hf=DataRule(reverse_bytes=True), lf=DataRule(output_format="DEC"))
        self.assertEqual(preview(p, "813F9A04", "HF").value, "049A3F81")
        self.assertEqual(preview(p, "530233EC18", "LF").value, str(int("530233EC18", 16)))

    def test_json_roundtrip_with_every_option(self):
        p = BuilderProject(name="Čtečka test", hf=DataRule(reverse_bits=True, and_mask="FF"),
                           channel="uart", uart_baud=115200, uart_parity="even", uart_stop_bits=2,
                           hf_tags=(0x80, 0x82), lf_tags=(), success=Feedback(volume=45, beeps=3, flashes=2),
                           usb_serial="production", remote_wakeup=True)
        self.assertEqual(BuilderProject.from_json(p.to_json()), p)
        with tempfile.TemporaryDirectory() as directory:
            path = save_project(Path(directory) / "project.json", p)
            self.assertEqual(BuilderProject.from_json(path.read_text(encoding="utf-8")), p)

    def test_registration_restricts_jidelna_frames(self):
        with self.assertRaises(ValueError):
            BuilderProject(mode="registration", channel="keyboard")
        with self.assertRaises(ValueError):
            BuilderProject(mode="registration", hf=DataRule(prefix="ID:"))
        with self.assertRaises(ValueError):
            preview(BuilderProject(mode="registration", hf=DataRule(output_format="DEC")), "FFFFFFFFFFFFFFFF")
        with self.assertRaises(ValueError):
            preview(BuilderProject(mode="registration"), "00")

    def test_unsupported_settings_are_rejected(self):
        for data in ({"schema": 2}, {"unknown": True}, {"hf_tags": [0x88]}, {"repeat_ms": 1},
                     {"hf": {"first_bit": True}}, {"success": {"volume": 101}}, {"hf_tags": [], "lf_tags": []}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                BuilderProject.from_dict(data)

    def test_project_includes_hardware_and_masks_from_match(self):
        _, matches = analyze_uid("813F9A04", 32, "049A3F81", "hexadecimal", 10)
        p = project_from_match(matches[0], tag_type=0x80)
        self.assertEqual(p.hf_tags, (0x80,))
        self.assertEqual(p.lf_tags, ())

    def test_c_injection_and_escape_handling(self):
        text = '"; while(1); /*\\\rA'
        literal = c_string(text)
        self.assertIn("\\042", literal)
        self.assertIn("\\134", literal)
        self.assertIn("\\015A", literal)
        self.assertEqual(decode_escapes(r"ID:\tOK\r\n"), "ID:\tOK\r\n")
        with self.assertRaises(ValueError):
            decode_escapes(r"\xFF")

    def test_cdc_keyboard_uart_manifest_and_feedback(self):
        for channel in ("cdc", "keyboard", "uart"):
            p = BuilderProject(channel=channel, success=Feedback(volume=42, frequency=3500, beeps=3, flashes=2),
                               usb_serial="deviceuid", remote_wakeup=True, keyboard_layout="german")
            files = builder_sources(p)
            self.assertIn("42, 3500, 3, 2", files["feedback.c"])
            self.assertIn("USB_SERIALNUMBER_DEVICEUID", files["feedback.c"])
            self.assertIn("USB_KEYBOARDLAYOUT_GERMAN", files["feedback.c"])
            self.assertIn("USB_PID_KEYBOARD" if channel == "keyboard" else "USB_PID_CDC", files["feedback.c"])
            if channel == "uart":
                self.assertIn("parameters.BaudRate = 19200", files["feedback.c"])

    def test_registration_retains_cache_state_machine(self):
        p = BuilderProject(mode="registration", other_search_ms=750, handoff_ms=250, rf_pause_ms=50,
                           lf=DataRule(output_format="DEC"))
        files = builder_sources(p)
        self.assertIn("D2_OTHER_SEARCH_MS 750u", files["dual_config.h"])
        self.assertIn("D2_HANDOFF_MS 250u", files["dual_config.h"])
        self.assertIn("bld_convert(raw, bits, rule", files["App_D2R_DualRegistration.c"])
        self.assertIn("strlen(converted) > 16", files["App_D2R_DualRegistration.c"])
        self.assertIn("bld_feedback(&BLD_DUAL_SUCCESS)", files["registration_signal.c"])


if __name__ == "__main__":
    unittest.main()
