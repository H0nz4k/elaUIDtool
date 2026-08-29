import unittest

from elatec_uid_tool.analyzer import (
    analyze_uid,
    reverse_bit_order,
    reverse_byte_order,
)


class AnalyzerTests(unittest.TestCase):
    def test_reference_card(self):
        _, matches = analyze_uid("3D00C000D4", 40, "12583124", "decimal", 20)
        self.assertTrue(matches)
        self.assertEqual(matches[0].first_bit, 8)
        self.assertEqual(matches[0].number_of_bits, 32)
        self.assertFalse(matches[0].reverse_bit_order)
        self.assertFalse(matches[0].reverse_byte_order)

    def test_reverse_bit_order_matches_appblaster_example(self):
        bits = f"{0x1234:016b}"
        self.assertEqual(int(reverse_bit_order(bits), 2), 0x2C48)

    def test_reverse_byte_order_matches_appblaster_example(self):
        bits = f"{0x1234:016b}"
        self.assertEqual(int(reverse_byte_order(bits), 2), 0x3412)

    def test_wiegand_3_5_mifare_card(self):
        _, matches = analyze_uid(
            raw_hex="AE1C56CF",
            bit_count=32,
            expected_value="08607342",
            expected_format="auto",
            max_results=20,
        )
        wiegand = [m for m in matches if m.encoding == "wiegand_3_5"]
        self.assertTrue(wiegand)
        best = wiegand[0]
        self.assertEqual(best.output_decimal, "08607342")
        self.assertEqual(best.facility_code, 86)
        self.assertEqual(best.card_number, 7342)
        self.assertTrue(best.reverse_byte_order)
        self.assertFalse(best.reverse_bit_order)
        self.assertEqual(best.number_of_bits, 24)
        self.assertEqual(best.first_bit, 8)

    def test_wiegand_3_5_second_mifare_card(self):
        _, matches = analyze_uid(
            raw_hex="E9B20DFF",
            bit_count=32,
            expected_value="01345801",
            expected_format="auto",
            max_results=10,
        )
        self.assertTrue(matches)
        self.assertEqual(matches[0].encoding, "wiegand_3_5")
        self.assertEqual(matches[0].output_decimal, "01345801")
        self.assertEqual(matches[0].facility_code, 13)
        self.assertEqual(matches[0].card_number, 45801)


if __name__ == "__main__":
    unittest.main()
