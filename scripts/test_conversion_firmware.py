#!/usr/bin/env python3
"""Run the generated legacy ReadType1 conversion against analyzer fixtures."""
from __future__ import annotations

import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from elatec_uid_tool.analyzer import analyze_uid
from elatec_uid_tool.fw_export import _read_type1_parts


def main() -> None:
    fixtures = []
    for raw, expected, fmt in (("AE1C56CF", "08607342", "decimal"),
                               ("AE1C56CF", "867342", "decimal"),
                               ("3D00C000D4", "12583124", "decimal"),
                               ("813F9A04", "049A3F81", "hexadecimal")):
        fixtures.extend((raw, match) for match in analyze_uid(raw, len(raw) * 4, expected, fmt, 100)[1])
    source = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char byte;
static void CopyBits(byte *dest, int offset, const byte *src, int first, int count) {
    int i;
    for (i = 0; i < count; i++) {
        int bit = (src[(first+i)/8] >> (7-(first+i)%8)) & 1;
        byte mask = (byte)(1u << (7-(offset+i)%8));
        if (bit) dest[(offset+i)/8] |= mask;
        else dest[(offset+i)/8] &= (byte)~mask;
    }
}
static void ConvertBinaryToString(const byte *data, int first, int count, char *out, int radix, int minimum, int maximum) {
    uint64_t value = 0;
    char reverse[80];
    int i, n = 0;
    for (i=0; i<count; i++) value = (value<<1) | ((data[(first+i)/8] >> (7-(first+i)%8)) & 1);
    do { reverse[n++] = "0123456789ABCDEF"[value % radix]; value /= radix; } while (value);
    while (n < minimum) reverse[n++] = '0';
    if (n > maximum) { out[0] = 0; return; }
    for (i=0; i<n; i++) out[i] = reverse[n-1-i];
    out[n] = 0;
}
'''
    for index, (_, match) in enumerate(fixtures):
        helpers, body = _read_type1_parts(match)
        for name in ("GetBitMSB", "ReverseBitOrder", "ReverseByteOrder"):
            helpers = helpers.replace(name, name + str(index))
            body = body.replace(name, name + str(index))
        source += helpers + f"\nbool read{index}(const byte *ID, int IDBitCnt, char *CardString, int MaxCardStringLen) {{\n{body}\n}}\n"
    with tempfile.TemporaryDirectory(prefix="legacy-conversion-") as temporary:
        directory = Path(temporary)
        c = directory / "conversion.c"
        c.write_text(source, encoding="utf-8")
        library = directory / "conversion.so"
        subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Wno-unused-function", "-Wno-unused-parameter", "-fPIC", "-shared",
                        str(c), "-o", str(library)], check=True)
        loaded = ctypes.CDLL(str(library))
        for index, (raw, match) in enumerate(fixtures):
            read = getattr(loaded, "read" + str(index))
            read.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
            read.restype = ctypes.c_bool
            data = (ctypes.c_uint8 * len(bytes.fromhex(raw)))(*bytes.fromhex(raw))
            output = ctypes.create_string_buffer(80)
            assert read(data, len(raw)*4, output, 79)
            actual = output.value.decode("ascii")
            radix = 16 if match.encoding == "plain" and "Hex" in match.output_format else 10
            expected = int(match.output_hex, 16) if radix == 16 else int(match.output_decimal)
            assert int(actual, radix) == expected, (raw, match, actual)
            if radix == 16:
                assert len(actual) == (match.number_of_bits+3)//4
            if match.encoding in ("wiegand_3_5", "h10301_3_5"):
                assert actual == match.output_decimal
    print(f"Legacy generated ReadType1: {len(fixtures)} analyzer conversions passed.")


if __name__ == "__main__":
    main()
