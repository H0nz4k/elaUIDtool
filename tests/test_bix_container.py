import struct
from pathlib import Path
import tempfile
import unittest

from elatec_uid_tool.bix_container import MAGIC_V4, extract_system_images, parse, system_pairs, validate_multi


def section(name, segments, low=0, high=0xFFF):
    data = name.encode('ascii') + b'\0' + struct.pack('<IIII', low, high, 8, len(segments))
    return data + b''.join(struct.pack('<II', address, len(value)) + value
                           for address, value in segments)


def container(sections):
    return MAGIC_V4 + struct.pack('<I', len(sections)) + b''.join(sections)


def multi():
    parts = []
    for kind in (0x80, 0x82, 0x83):
        parts.append(section('flashinfo', [(0x10, bytes([kind])), (0x20, b'\x05\x20\x05\x07'),
                                           (0x100, b'TWN4\0')]))
        # A fake marker inside code must never be mistaken for metadata.
        parts.append(section('code', [(0, b'flashinfo\0nCFmi\0' + bytes([kind]))]))
    parts.extend([section('appinfo', [(0, b'a')]), section('appcode', [(0, b'b')])])
    return container(parts)


class BixTests(unittest.TestCase):
    def test_multi_valid(self):
        validate_multi(multi())
        self.assertEqual(len(system_pairs(parse(multi()))), 3)

    def test_extraction_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / 'multi.bix'
            original.write_bytes(multi())
            paths = extract_system_images(original, root)
            self.assertEqual(len(paths), 3)
            pairs = system_pairs(parse(multi()))
            for path, pair in zip(paths, pairs):
                self.assertEqual(path.read_bytes(), container([pair[0].encoded, pair[1].encoded]))

    def test_truncation(self):
        data = multi()
        for end in (0, 4, 7, 20, 50, len(data) - 1):
            with self.subTest(end=end), self.assertRaises(ValueError):
                parse(data[:end])

    def test_trailing_bytes(self):
        with self.assertRaises(ValueError):
            parse(multi() + b'garbage')

    def test_segment_outside_range(self):
        with self.assertRaises(ValueError):
            parse(container([section('code', [(0x1000, b'abc')])]))

    def test_reject_one_family(self):
        pair = system_pairs(parse(multi()))[0]
        with self.assertRaises(ValueError):
            validate_multi(container([pair[0].encoded, pair[1].encoded]))

    def test_reject_other_sdk(self):
        with self.assertRaises(ValueError):
            validate_multi(multi().replace(b'\x05\x20\x05\x07', b'\x04\x80\x05\x07'))


if __name__ == '__main__':
    unittest.main()
