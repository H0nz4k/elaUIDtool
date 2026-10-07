"""Read DevPack 5.20's BIX v4 container without decrypting any payload.

makeapp uses one OS image from each -i input. A Multi Standard input contains
three OS images, so supply their unchanged flashinfo/code pairs separately.
"""
from dataclasses import dataclass
from pathlib import Path
import struct

MAGIC_V4 = bytes.fromhex("FE AF 00 04")


@dataclass(frozen=True)
class Section:
    name: str
    low: int
    high: int
    segments: tuple[tuple[int, bytes], ...]
    encoded: bytes

    def value(self, address: int) -> bytes | None:
        return next((data for start, data in self.segments if start == address), None)


def parse(data: bytes) -> list[Section]:
    if len(data) < 8 or data[:4] != MAGIC_V4:
        raise ValueError("Očekáván BIX v4 z DevPacku 5.20.")
    count = struct.unpack_from("<I", data, 4)[0]
    if count == 0 or count > 64:
        raise ValueError("Neplatný počet sekcí BIX.")
    position = 8
    sections = []

    def words(n: int) -> tuple[int, ...]:
        nonlocal position
        if position + n * 4 > len(data):
            raise ValueError("Zkrácená hlavička BIX.")
        values = struct.unpack_from("<" + "I" * n, data, position)
        position += n * 4
        return values

    for _ in range(count):
        start = position
        end = data.find(b"\0", position, position + 65)
        if end < 0:
            raise ValueError("Neplatný název sekce BIX.")
        try:
            name = data[position:end].decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("Neplatný název sekce BIX.") from error
        if not name:
            raise ValueError("Prázdný název sekce BIX.")
        position = end + 1
        low, high, word_size, segment_count = words(4)
        if word_size != 8 or low > high or segment_count > 65536:
            raise ValueError("Nepodporovaná sekce BIX; očekávány 8bitové segmenty.")
        segments = []
        for _ in range(segment_count):
            address, length = words(2)
            if address < low or address + length > high + 1 or position + length > len(data):
                raise ValueError("Neplatný nebo zkrácený segment BIX.")
            segments.append((address, data[position:position + length]))
            position += length
        sections.append(Section(name, low, high, tuple(segments), data[start:position]))
    if position != len(data):
        raise ValueError("Neočekávaná data za poslední sekcí BIX.")
    return sections


def system_pairs(sections: list[Section]) -> list[tuple[Section, Section]]:
    pairs = []
    for index, section in enumerate(sections):
        if section.name != "flashinfo":
            continue
        if index + 1 >= len(sections) or sections[index + 1].name != "code":
            raise ValueError("Systémový obraz BIX nemá navazující sekci code.")
        if section.value(0x100) != b"TWN4\0":
            raise ValueError("Systémový obraz není určen pro TWN4.")
        version = section.value(0x20)
        if not version or version[:2] != bytes.fromhex("05 20"):
            raise ValueError("Vyžadován systémový obraz TWN4 verze 5.20.")
        pairs.append((section, sections[index + 1]))
    return pairs


def extract_system_images(source: Path, destination: Path) -> list[Path]:
    pairs = system_pairs(parse(source.read_bytes()))
    if len(pairs) != 3:
        raise ValueError("SDK Multi CDC základ musí obsahovat tři systémové obrazy.")
    paths = []
    for index, (info, code) in enumerate(pairs, start=1):
        path = destination / f"TWN4_CDC520_OS{index}.bix"
        # No modifications to vendor metadata or encrypted system code.
        path.write_bytes(MAGIC_V4 + struct.pack("<I", 2) + info.encoded + code.encoded)
        paths.append(path)
    return paths


def validate_multi(data: bytes) -> None:
    sections = parse(data)
    pairs = system_pairs(sections)
    if len(pairs) != 3 or len({info.value(0x10) for info, _ in pairs}) != 3:
        raise ValueError("Výstup neobsahuje tři různé rodiny TWN4 z SDK 5.20.")
    names = [section.name for section in sections]
    if names.count("appinfo") != 1 or names.count("appcode") != 1:
        raise ValueError("Výstup nemá právě jednu vlastní aplikaci.")
