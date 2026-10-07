"""Test jednoho přiložení přes D2R CDC; přijímá skutečné výstupní rámce, bez DB."""
from __future__ import annotations

from dataclasses import dataclass
import re
import threading
import time
from typing import Callable

import serial

from .protocol import ElatecError


class RegistrationCancelled(ElatecError):
    pass


@dataclass(frozen=True)
class RegistrationResult:
    hf: str | None
    lf: str | None
    hf_format: str
    lf_format: str
    firmware: str
    frames: tuple[str, str]


class _Session:
    def __init__(self, port: str, cancel: threading.Event, serial_factory):
        self.port = port
        self.cancel = cancel
        self.factory = serial_factory
        self.connection = None
        self.buffer = bytearray()
        self.formats = None
        self.firmware = ""

    def open(self) -> None:
        self.connection = self.factory(self.port, baudrate=19200, timeout=0.1, write_timeout=1)
        self.connection.dtr = True
        self.buffer.clear()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def line(self, deadline: float) -> str:
        while time.monotonic() < deadline:
            if self.cancel.is_set():
                raise RegistrationCancelled("Test zastaven.")
            value = self.connection.read(1)
            if not value:
                continue
            if value == b"\r":
                try:
                    text = self.buffer.decode("ascii")
                except UnicodeDecodeError as exc:
                    raise ElatecError("Čtečka neposílá ASCII D2R protokol. Nahraj registrační BIX.") from exc
                self.buffer.clear()
                return text
            self.buffer.extend(value)
            if len(self.buffer) > 600 or value == b"\n":
                raise ElatecError("Neplatný rámec čtečky; očekáván ASCII výstup zakončený CR.")
        raise ElatecError("Čtení vypršelo. Odeber kartu a zkus test znovu.")

    def inspect(self, line: str, *, errors: bool = True) -> None:
        config = re.fullmatch(r"CONFIG HF=(HEX|DEC) LF=(HEX|DEC)", line)
        if config:
            self.formats = config.groups()
        if errors and ("stage=LOCKED" in line or "action=INVALID_PAIR" in line):
            raise ElatecError("Čtečka odmítla UID nebo shodné výsledné kódy. Odeber kartu a spusť nový test.")

    def command(self, command: str, timeout: float = 4) -> None:
        self.connection.write(f"!{command}\r".encode("ascii"))
        deadline = time.monotonic() + timeout
        while True:
            line = self.line(deadline)
            self.inspect(line, errors=False)
            match = re.fullmatch(rf"ACK {command} (D2R0\.\d+|BLD0\.60)", line)
            if match:
                self.firmware = match.group(1)
                return
            if line.startswith(f"DENIED {command}"):
                raise ElatecError(f"Firmware odmítl příkaz {command}.")
            if re.fullmatch(r"[0-9A-F]{1,20}", line) or line.startswith("PAIR "):
                raise ElatecError("Karta byla načtena před spuštěním testu. Odeber ji a zkus test znovu.")


def _parse_pair(line: str, formats: tuple[str, str]) -> tuple[str | None, str | None]:
    match = re.fullmatch(r"PAIR (?:D2R0\.\d+|BLD0\.60) HF=([0-9A-F]+|-) LF=([0-9A-F]+|-) tags=([12])", line)
    if not match:
        raise ElatecError("Neplatný souhrn HF/LF z firmware.")
    codes = tuple(None if value == "-" else value for value in match.groups()[:2])
    if sum(value is not None for value in codes) != int(match.group(3)):
        raise ElatecError("Počet nalezených technologií nesouhlasí se souhrnem.")
    for code, radix in zip(codes, formats):
        if code is None:
            continue
        pattern = r"[0-9A-F]{1,16}" if radix == "HEX" else r"[1-9][0-9]{0,19}"
        if not re.fullmatch(pattern, code) or not 0 < int(code, 16 if radix == "HEX" else 10) <= 2**64 - 1:
            raise ElatecError(f"Neplatný {radix} identifikátor: {code}")
    if codes[0] is not None and codes[1] is not None and codes[0].lstrip("0") == codes[1].lstrip("0"):
        raise ElatecError("Výsledné identifikátory jsou shodné.")
    return codes


def capture_registration(
    port: str, *, wait: float = 30, cancel: threading.Event | None = None,
    on_progress: Callable[[str], None] | None = None, serial_factory=None,
) -> RegistrationResult:
    """Vyžaduje D2R0.15+. Simuluje i zavření/otevření portu po prvním kódu."""
    if wait <= 0:
        raise ValueError("Doba čekání musí být kladná.")
    session = _Session(port, cancel or threading.Event(), serial_factory or serial.Serial)
    armed = False
    completed = False
    try:
        session.open()
        session.connection.reset_input_buffer()
        if on_progress:
            on_progress("Připojuji registrační firmware… Karta musí být mimo čtečku.")
        session.command("T")
        # T sends STATUS/CONFIG/VERSION after ACK. N waits behind these frames.
        session.command("N")
        if session.formats is None:
            raise ElatecError("Nahraj registrační firmware D2R0.15 nebo novější vytvořený tímto nástrojem.")
        session.command("G")
        armed = True
        if on_progress:
            on_progress("Přilož jednu kartu a drž ji na čtečce. Hledám HF i LF…")
        deadline = time.monotonic() + wait
        pair = None
        frames = []
        while len(frames) < 2:
            line = session.line(deadline)
            session.inspect(line)
            if line.startswith("PAIR "):
                if pair is not None or frames:
                    raise ElatecError("Firmware poslal více souhrnů pro jedno přiložení.")
                pair = _parse_pair(line, session.formats)
            elif line == "" or re.fullmatch(r"[0-9A-F]{1,20}", line):
                if pair is None:
                    raise ElatecError("Kód přišel před dokončením detekce HF/LF.")
                expected = (pair[0] or pair[1]) if not frames else (pair[1] if all(pair) else "")
                if line != expected:
                    raise ElatecError("Výstupní rámec neodpovídá souhrnu nebo pořadí HF → LF.")
                frames.append(line)
                if len(frames) == 1:
                    # Do not purge on reopen: the second code may be buffered.
                    session.close()
                    session.open()
        # Verify completion and reject extra IDs, rather than trusting PAIR alone.
        while True:
            line = session.line(deadline)
            session.inspect(line)
            if line.startswith("STATE ") and (
                "action=SEND_SECOND" in line or "action=END_SINGLE" in line
            ):
                break
            if line == "" or re.fullmatch(r"[0-9A-F]{1,20}", line) or line.startswith("PAIR "):
                raise ElatecError("Firmware poslal další neočekávaný identifikátor.")
        completed = True
        return RegistrationResult(pair[0], pair[1], *session.formats, session.firmware, tuple(frames))
    except serial.SerialException as exc:
        recovery = " Před otevřením Jídelny čtečku odpoj a připoj." if armed else ""
        raise ElatecError(f"Nelze komunikovat s portem {port}: {exc}.{recovery}") from exc
    finally:
        # Exit opt-in diagnostics even after cancellation; no logs enter Jidelna.
        if session.connection is not None:
            try:
                session.cancel = threading.Event()
                session.connection.write(b"!P\r")
                if armed and not completed:
                    session.connection.write(b"!N\r")
                session.connection.write(b"!Q\r")
                deadline = time.monotonic() + 2
                while not session.line(deadline).startswith("ACK Q "):
                    pass
            except (ElatecError, serial.SerialException, OSError) as exc:
                raise ElatecError(
                    "Nepodařilo se potvrdit ukončení testovacího režimu. "
                    "Před otevřením Jídelny čtečku odpoj a znovu připoj."
                ) from exc
            finally:
                session.close()
