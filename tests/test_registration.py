import unittest

from elatec_uid_tool.cli import build_parser
from elatec_uid_tool.reader_models import get_reader_model
from elatec_uid_tool.registration import RegistrationConfig, format_uid, registration_sources


class RegistrationTests(unittest.TestCase):
    def test_full_uid_formats_preserve_significance(self):
        cases = [("04112233", "68231731"), ("0102030405", "4328719365"),
                 ("00000001", "1"), ("FFFFFFFFFFFFFFFF", "18446744073709551615")]
        for hexadecimal, decimal in cases:
            with self.subTest(uid=hexadecimal):
                self.assertEqual(format_uid(hexadecimal, "HEX"), hexadecimal)
                self.assertEqual(format_uid(hexadecimal, "DEC"), decimal)

    def test_rejects_invalid_or_oversized_uid(self):
        for uid in ("", "00000000", "XYZ", "0102030405060708090A"):
            with self.subTest(uid=uid), self.assertRaises(ValueError):
                format_uid(uid, "HEX")

    def test_validate_config_and_model(self):
        self.assertEqual(RegistrationConfig("dec", "hex").hf_format, "DEC")
        for config in (("ABC", "HEX", 2000), ("HEX", "HEX", 0), ("HEX", "HEX", 2.5),
                       ("HEX", "HEX", 10001), ("HEX", "HEX", True)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                RegistrationConfig(*config)
        with self.assertRaises(ValueError):
            get_reader_model("other")

    def test_registration_sources_available_as_package_data(self):
        # Also exercised from an installed wheel in release validation.
        self.assertIn("App_D2R_DualRegistration.c", registration_sources(RegistrationConfig()))

    def test_cli_supports_models_and_independent_radix(self):
        parser = build_parser()
        args = parser.parse_args(["export-registration-fw", "--reader-model", "multitech3-m-lf-hf",
                                  "--hf-format", "dec", "--lf-format", "hex"])
        self.assertEqual((args.hf_format, args.lf_format), ("DEC", "HEX"))
        self.assertEqual(parser.parse_args(["test-registration", "--port", "COM7"]).port, "COM7")
