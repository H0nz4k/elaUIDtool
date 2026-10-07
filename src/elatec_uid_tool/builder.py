"""Validated UID firmware projects, shared live preview and reusable presets."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
import re
from pathlib import Path

from .analyzer import MatchCandidate, bytes_to_bit_string, normalize_raw_hex
from .encodings import Encoding
from .reader_models import DEFAULT_READER_MODEL, get_reader_model
from .tagtypes import HF_NAMES, LF_NAMES

FORMATS = {"HEX": 16, "DEC": 10, "BIN": 2, "OCT": 8, "ASCII": 0}
ENCODINGS = (
    "plain", "wiegand_3_5", "wiegand_3_5_strip", "facility_card_concat", "card_16",
    "facility_8", "scale_4", "scale_6", "h10301_3_5", "h10301_concat", "h10301_card", "h10301_strip",
)
PHYSICAL_HF = tuple(t for t in HF_NAMES if t not in (0x87, 0x88, 0x8B))
SCHEMA_VERSION = 1


def _integer(value, low: int, high: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{label}: povolený rozsah je {low}–{high}.")


def _text(value: str, max_length: int, label: str) -> None:
    if not isinstance(value, str) or len(value) > max_length or any(ord(c) > 126 or ord(c) == 0 for c in value):
        raise ValueError(f"{label}: nejvýše {max_length} ASCII znaků, bez NUL.")


def decode_escapes(text: str) -> str:
    """Explicit ASCII escapes; never evaluate entered text or C expressions."""
    result = []
    index = 0
    mapping = {"r": "\r", "n": "\n", "t": "\t", "b": "\b", "e": "\x1b", "\\": "\\"}
    while index < len(text):
        char = text[index]
        index += 1
        if char == "\\":
            if index >= len(text) or text[index] not in mapping:
                raise ValueError(r"Povolené escape sekvence: \r, \n, \t, \b, \e a \\.")
            char = mapping[text[index]]
            index += 1
        result.append(char)
    return "".join(result)


def escaped(text: str) -> str:
    return text.encode("unicode_escape").decode("ascii")


@dataclass(frozen=True)
class DataRule:
    reverse_bits: bool = False
    reverse_bytes: bool = False
    first_bit: int = 0
    bit_count: int = 0  # 0 = remaining bits, including variable-length UIDs
    encoding: str = "plain"
    output_format: str = "HEX"
    length_mode: str = "auto"
    length: int = 0
    lowercase: bool = False
    strip_zeros: bool = False
    append_00: bool = False
    and_mask: str = ""
    xor_mask: str = ""
    byte_separator: str = ""
    prefix: str = ""
    suffix: str = ""

    def __post_init__(self) -> None:
        for key in ("reverse_bits", "reverse_bytes", "lowercase", "strip_zeros", "append_00"):
            if not isinstance(getattr(self, key), bool):
                raise ValueError(f"{key} musí být logická hodnota.")
        _integer(self.first_bit, 0, 255, "První bit")
        _integer(self.bit_count, 0, 256, "Počet bitů")
        if self.bit_count and self.first_bit + self.bit_count > 256:
            raise ValueError("Vybrané okno přesahuje 256 bitů.")
        if self.encoding not in ENCODINGS or self.output_format not in FORMATS:
            raise ValueError("Neplatný formát nebo strukturovaná konverze.")
        if self.length_mode not in ("auto", "minimum", "exact"):
            raise ValueError("Délka musí být automatická, minimální nebo přesná.")
        _integer(self.length, 0, 256, "Délka výstupu")
        if self.length_mode != "auto" and not self.length:
            raise ValueError("Minimální/přesná délka musí být kladná.")
        for key in ("and_mask", "xor_mask"):
            value = getattr(self, key).strip().upper().removeprefix("0X")
            if value and not re.fullmatch(r"[0-9A-F]{1,64}", value):
                raise ValueError("AND a XOR maska musí být HEX, nejvýše 256 bitů.")
            object.__setattr__(self, key, value)
        for key in ("prefix", "suffix"):
            _text(getattr(self, key), 32, key)
        if self.byte_separator not in ("", ":", "-", " "):
            raise ValueError("Oddělovač bajtů: prázdný, dvojtečka, pomlčka nebo mezera.")
        if self.byte_separator and self.output_format != "HEX":
            raise ValueError("Oddělovač bajtů je určen pro HEX výstup.")
        if self.encoding != "plain" and self.output_format == "ASCII":
            raise ValueError("ASCII nepodporuje facility/card konverze.")

    @classmethod
    def from_match(cls, match: MatchCandidate) -> "DataRule":
        fmt = "HEX" if match.encoding == "plain" and "Hex" in match.output_format else "DEC"
        width = 8 if match.encoding in ("wiegand_3_5", "h10301_3_5") else 0
        return cls(reverse_bits=match.reverse_bit_order, reverse_bytes=match.reverse_byte_order,
                   first_bit=0 if match.is_all_bits else match.first_bit,
                   bit_count=0 if match.is_all_bits else match.number_of_bits, encoding=match.encoding,
                   output_format=fmt, length_mode="minimum" if width else "auto", length=width)


@dataclass(frozen=True)
class Feedback:
    volume: int = 100
    frequency: int = 4000
    beeps: int = 1
    led: str = "green"
    flashes: int = 1
    on_ms: int = 60
    off_ms: int = 60

    def __post_init__(self) -> None:
        for key, low, high in (("volume", 0, 100), ("frequency", 100, 10000), ("beeps", 0, 10),
                               ("flashes", 0, 10), ("on_ms", 10, 1000), ("off_ms", 10, 1000)):
            _integer(getattr(self, key), low, high, key)
        if self.led not in ("off", "red", "green", "both"):
            raise ValueError("LED musí být off, red, green nebo both.")


@dataclass(frozen=True)
class BuilderProject:
    name: str = "Moje konverze"
    reader_model: str = DEFAULT_READER_MODEL
    mode: str = "uid"  # uid, registration (Jidelna-compatible HF -> LF)
    channel: str = "cdc"  # cdc, keyboard, uart
    hf: DataRule = field(default_factory=DataRule)
    lf: DataRule = field(default_factory=DataRule)
    hf_tags: tuple[int, ...] | None = None  # None = all supported physical types
    lf_tags: tuple[int, ...] | None = None
    terminator: str = "CR"
    removal_ms: int = 300
    repeat_ms: int = 0  # 0 = once per physical presentation
    other_search_ms: int = 2000
    handoff_ms: int = 200
    rf_pause_ms: int = 100
    uart_baud: int = 19200
    uart_parity: str = "none"
    uart_stop_bits: int = 1
    idle_led: str = "green"
    startup: Feedback = field(default_factory=lambda: Feedback(volume=30, frequency=2000, beeps=0, flashes=0))
    success: Feedback = field(default_factory=Feedback)
    dual_success: Feedback = field(default_factory=lambda: Feedback(beeps=2, flashes=2))
    error: Feedback = field(default_factory=lambda: Feedback(frequency=1500, led="red"))
    usb_serial: str = "off"
    remote_wakeup: bool = False
    keyboard_layout: str = "english"
    keyboard_alt_codes: bool = False
    keyboard_repeat_ms: int = 10
    schema: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not 1 <= len(self.name.strip()) <= 80:
            raise ValueError("Název projektu musí mít 1–80 znaků.")
        get_reader_model(self.reader_model)
        if self.mode not in ("uid", "registration") or self.channel not in ("cdc", "keyboard", "uart"):
            raise ValueError("Neplatný režim nebo výstupní rozhraní.")
        if self.terminator not in ("CR", "LF", "CRLF", "TAB", "NONE"):
            raise ValueError("Neplatné ukončení výstupu.")
        for key, low, high in (("removal_ms", 100, 10000), ("repeat_ms", 0, 60000),
                              ("other_search_ms", 500, 10000), ("handoff_ms", 200, 5000),
                              ("rf_pause_ms", 10, 300), ("keyboard_repeat_ms", 1, 255)):
            _integer(getattr(self, key), low, high, key)
        if self.repeat_ms and self.repeat_ms < 100:
            raise ValueError("Opakování musí být vypnuté nebo alespoň 100 ms.")
        if self.uart_baud not in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200):
            raise ValueError("Nepodporovaná rychlost UART.")
        if self.uart_parity not in ("none", "even", "odd") or self.uart_stop_bits not in (1, 2):
            raise ValueError("Nepodporované parametry UART.")
        if self.idle_led not in ("off", "red", "green", "both"):
            raise ValueError("Neplatná klidová LED.")
        if self.usb_serial not in ("off", "deviceuid", "production"):
            raise ValueError("Neplatné USB sériové číslo.")
        if self.keyboard_layout not in ("english", "german", "french"):
            raise ValueError("SDK nabízí anglické, německé a francouzské rozložení klávesnice.")
        if not isinstance(self.remote_wakeup, bool) or not isinstance(self.keyboard_alt_codes, bool):
            raise ValueError("USB volby musí být logické hodnoty.")
        if type(self.schema) is not int or self.schema != SCHEMA_VERSION:
            raise ValueError("Nepodporovaná verze projektu.")
        for key, allowed in (("hf_tags", PHYSICAL_HF), ("lf_tags", tuple(LF_NAMES))):
            tags = getattr(self, key)
            if tags is not None:
                if not isinstance(tags, (list, tuple)) or any(type(t) is not int or t not in allowed for t in tags):
                    raise ValueError("Projekt obsahuje nepodporovanou technologii.")
                object.__setattr__(self, key, tuple(sorted(set(tags))))
        if self.hf_tags == () and self.lf_tags == ():
            raise ValueError("Musí být zapnutá alespoň jedna technologie.")
        if not isinstance(self.hf, DataRule) or not isinstance(self.lf, DataRule):
            raise ValueError("HF a LF vyžadují platná převodní pravidla.")
        if any(not isinstance(getattr(self, key), Feedback) for key in ("startup", "success", "dual_success", "error")):
            raise ValueError("Projekt vyžaduje platnou konfiguraci signalizace.")
        if self.mode == "registration":
            if self.channel != "cdc" or self.terminator != "CR" or self.repeat_ms:
                raise ValueError("Registrace Jídelny vyžaduje USB CDC, CR a vypnuté opakování.")
            if self.hf_tags == () or self.lf_tags == ():
                raise ValueError("Registrace musí hledat HF i LF.")
            for rule in (self.hf, self.lf):
                if rule.output_format not in ("HEX", "DEC") or rule.prefix or rule.suffix or rule.byte_separator or rule.lowercase:
                    raise ValueError("Registrace: pouze velký HEX/DEC bez prefixu, suffixu a oddělovače.")
                if rule.length > 16:
                    raise ValueError("Pole Jídelny má nejvýše 16 znaků.")

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_dict(cls, data: dict) -> "BuilderProject":
        if not isinstance(data, dict):
            raise ValueError("Projekt musí být JSON objekt.")
        values = dict(data)
        try:
            for key, kind in (("hf", DataRule), ("lf", DataRule), ("startup", Feedback),
                              ("success", Feedback), ("dual_success", Feedback), ("error", Feedback)):
                if key in values:
                    values[key] = kind(**values[key])
            return cls(**values)
        except (TypeError, AttributeError) as exc:
            raise ValueError(f"Neplatný projekt: {exc}") from exc

    @classmethod
    def from_json(cls, text: str) -> "BuilderProject":
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Neplatný JSON projektu: {exc.msg}") from exc


@dataclass(frozen=True)
class Preview:
    raw_hex: str
    input_bits: int
    transformed_hex: str
    selected_bits: str
    value: str
    framed: str
    wire_hex: str


def _structured(bits: str, encoding: str) -> tuple[int, int]:
    if encoding.startswith("h10301"):
        if len(bits) != 26:
            raise ValueError("H10301 vyžaduje přesně 26 bitů (parita + 8 + 16 + parita).")
        payload = int(bits[1:25], 2)
    else:
        # Analyzer uses the LOW 24 bits, including windows larger than 24 bits.
        payload = int(bits, 2) & 0xFFFFFF
    facility, card = payload >> 16, payload & 0xFFFF
    if encoding in ("wiegand_3_5", "h10301_3_5"):
        return facility * 100000 + card, 8
    if encoding in ("wiegand_3_5_strip", "h10301_strip"):
        return facility * 100000 + card, 0
    if encoding in ("facility_card_concat", "h10301_concat"):
        return facility * (10 ** len(str(card))) + card if card else facility, 0
    if encoding in ("card_16", "h10301_card"):
        return card, 0
    if encoding == "facility_8":
        return facility, 0
    return facility * (10000 if encoding == "scale_4" else 1000000) + card, 0


def apply_rule(raw_hex: str, rule: DataRule, bit_count: int | None = None) -> tuple[str, str, str]:
    raw = normalize_raw_hex(raw_hex)
    bits = bytes_to_bit_string(bytes.fromhex(raw), bit_count if bit_count is not None else len(raw) * 4)
    if len(bits) > 256:
        raise ValueError("Firmware podporuje nejvýše 256 bitů RAW UID.")
    if rule.reverse_bits:
        bits = bits[::-1]
    if rule.reverse_bytes:
        if len(bits) % 8:
            raise ValueError("Reverze bajtů vyžaduje počet bitů dělitelný osmi.")
        bits = "".join(reversed([bits[i:i + 8] for i in range(0, len(bits), 8)]))
    transformed = f"{int(bits, 2):0{(len(bits) + 3) // 4}X}"
    count = rule.bit_count or len(bits) - rule.first_bit
    if count < 1 or rule.first_bit + count > len(bits):
        raise ValueError("Vybrané bity přesahují délku načteného UID.")
    selected = bits[rule.first_bit:rule.first_bit + count]
    numeric = int(selected, 2)
    for name, operator in (("and_mask", lambda a, b: a & b), ("xor_mask", lambda a, b: a ^ b)):
        mask = getattr(rule, name)
        if mask:
            if int(mask, 16).bit_length() > count:
                raise ValueError("AND/XOR maska přesahuje vybrané bity.")
            numeric = operator(numeric, int(mask, 16))
    selected = f"{numeric:0{count}b}"
    width = 0
    if rule.encoding != "plain":
        numeric, width = _structured(selected, rule.encoding)
    if rule.output_format == "ASCII":
        if count % 8:
            raise ValueError("ASCII vyžaduje celý počet bajtů.")
        data = numeric.to_bytes(count // 8, "big")
        if any(c < 32 or c > 126 for c in data):
            raise ValueError("ASCII výstup vyžaduje tisknutelné znaky 0x20–0x7E.")
        text = data.decode("ascii")
    else:
        fmt = {"HEX": "X", "DEC": "d", "BIN": "b", "OCT": "o"}[rule.output_format]
        text = format(numeric, fmt)
        if rule.output_format == "HEX" and rule.encoding == "plain":
            text = text.zfill((count + 3) // 4)
        if width and rule.output_format == "DEC":
            text = text.zfill(width)
    if rule.strip_zeros:
        text = text.lstrip("0") or "0"
    if rule.length_mode != "auto":
        if rule.length_mode == "exact" and len(text) > rule.length:
            raise ValueError("Výsledek je delší než přesná délka; firmware ho odmítne, nezkrátí.")
        text = text.rjust(rule.length, " " if rule.output_format == "ASCII" else "0")
    if rule.append_00:
        text += "00"
    if rule.lowercase:
        text = text.lower()
    if rule.byte_separator:
        if len(text) % 2:
            raise ValueError("Oddělovač HEX bajtů vyžaduje sudý počet znaků.")
        text = rule.byte_separator.join(text[i:i + 2] for i in range(0, len(text), 2))
    return transformed, selected, rule.prefix + text + rule.suffix


def preview(project: BuilderProject, raw_hex: str, band: str = "HF", bit_count: int | None = None) -> Preview:
    if band not in ("HF", "LF"):
        raise ValueError("Zvol HF nebo LF.")
    raw = normalize_raw_hex(raw_hex)
    bits = bit_count if bit_count is not None else len(raw) * 4
    transformed, selected, text = apply_rule(raw, project.hf if band == "HF" else project.lf, bits)
    if project.mode == "registration" and (bits > 64 or len(text) > 16 or not text.strip("0")):
        raise ValueError("Registrace Jídelny: RAW UID nejvýše 64 bitů a nenulový výsledek do 16 znaků.")
    terminator = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "TAB": "\t", "NONE": ""}[project.terminator]
    framed = text + terminator
    return Preview(raw, bits, transformed, selected, text, framed, framed.encode("ascii").hex(" ").upper())


RULE_PRESETS = {
    "Celé UID · HEX": DataRule(),
    "Celé UID · DEC": DataRule(output_format="DEC"),
    "Reverze bajtů · HEX": DataRule(reverse_bytes=True),
    "Reverze bajtů · DEC": DataRule(reverse_bytes=True, output_format="DEC"),
    "Reverze bitů · DEC": DataRule(reverse_bits=True, output_format="DEC"),
    "EM · vynechat první bajt / DEC": DataRule(first_bit=8, bit_count=32, output_format="DEC"),
    "Jídelna/Terkom · reverze bajtů + 00": DataRule(reverse_bytes=True, append_00=True),
    "Wiegand 3+5 · spodních 24 bitů": DataRule(encoding="wiegand_3_5", output_format="DEC"),
    "PAC · facility + card": DataRule(encoding="facility_card_concat", output_format="DEC"),
    "H10301 · 26 bitů → 3+5": DataRule(bit_count=26, encoding="h10301_3_5", output_format="DEC"),
    "HID · pouze číslo karty": DataRule(encoding="card_16", output_format="DEC"),
    "UID · HEX s dvojtečkami": DataRule(byte_separator=":"),
}


def project_from_match(match: MatchCandidate, *, tag_type: int | None = None, channel: str = "cdc") -> BuilderProject:
    rule = DataRule.from_match(match)
    changes = {"hf": rule, "lf": rule, "channel": channel, "name": "Konverze z nalezené shody"}
    if tag_type in LF_NAMES:
        changes.update(lf_tags=(tag_type,), hf_tags=())
    elif tag_type in PHYSICAL_HF:
        changes.update(hf_tags=(tag_type,), lf_tags=())
    return BuilderProject(**changes)


def save_project(path: Path, project: BuilderProject) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(project.to_json(), encoding="utf-8")
    temporary.replace(path)
    return path
