from collections import deque
import threading
import unittest

from elatec_uid_tool.protocol import ElatecError
from elatec_uid_tool.registration_client import RegistrationCancelled, capture_registration


class FakeReader:
    """Streams separate CR frames; persists the second output across COM reopen."""
    def __init__(self, hf="04112233", lf="0102030405", hf_format="HEX", lf_format="HEX", *,
                 wrong_second=False, early=False, locked=False, extra=False, timeout=False, bad_exit=False):
        self.hf, self.lf = hf, lf
        self.hf_format, self.lf_format = hf_format, lf_format
        self.wrong_second, self.early, self.locked, self.extra, self.timeout = wrong_second, early, locked, extra, timeout
        self.pending = deque()
        self.bad_exit = bad_exit
        self.commands = []
        self.connections = []
        self.empty_reads = 0

    def frame(self, value):
        self.pending.extend(value.encode("ascii") + b"\r")

    def __call__(self, port, **kwargs):
        reader = self

        class Port:
            closed = False
            dtr = False

            def reset_input_buffer(self):
                reader.pending.clear()

            def read(self, size):
                if reader.pending:
                    return bytes([reader.pending.popleft()])
                reader.empty_reads += 1
                return b""

            def close(self):
                self.closed = True

            def write(self, data):
                for command in data.decode("ascii").split("\r"):
                    if not command:
                        continue
                    reader.commands.append(command)
                    if command == "!Q" and reader.bad_exit:
                        reader.pending.extend(b"\xff\r")
                        continue
                    reader.frame(f"ACK {command[1]} D2R0.15")
                    if command == "!T":
                        # Reader may enter the test from an old LOCKED session.
                        reader.frame("STATUS D2R0.15 stage=LOCKED")
                        reader.frame(f"CONFIG HF={reader.hf_format} LF={reader.lf_format}")
                    elif command == "!G" and not reader.timeout:
                        if reader.locked:
                            reader.frame("STATE action=INVALID_PAIR")
                        else:
                            if reader.early:
                                reader.frame(reader.hf or reader.lf)
                            reader.frame(f"PAIR D2R0.15 HF={reader.hf or '-'} LF={reader.lf or '-'} tags={int(reader.hf is not None) + int(reader.lf is not None)}")
                            reader.frame(reader.hf or reader.lf)
                            reader.frame("BAD" if reader.wrong_second else (reader.lf if reader.hf and reader.lf else ""))
                            if reader.extra:
                                reader.frame("1234")
                            reader.frame("STATE action=" + ("SEND_SECOND" if reader.hf and reader.lf else "END_SINGLE"))
                return len(data)
        connection = Port()
        self.connections.append(connection)
        return connection


class RegistrationClientTests(unittest.TestCase):
    def test_four_format_combinations_receive_real_frames(self):
        for hf_format, hf in (("HEX", "04112233"), ("DEC", "68231731")):
            for lf_format, lf in (("HEX", "0102030405"), ("DEC", "4328719365")):
                reader = FakeReader(hf, lf, hf_format, lf_format)
                result = capture_registration("COM7", serial_factory=reader)
                self.assertEqual(result.frames, (hf, lf))
                self.assertEqual((result.hf_format, result.lf_format), (hf_format, lf_format))
                self.assertEqual(len(reader.connections), 2)
                self.assertTrue(all(port.closed for port in reader.connections))
                self.assertEqual(reader.commands, ["!T", "!N", "!G", "!P", "!Q"])

    def test_single_technology_receives_empty_second_frame(self):
        for hf, lf in (("04112233", None), (None, "0102030405")):
            reader = FakeReader(hf, lf)
            result = capture_registration("COM7", serial_factory=reader)
            self.assertEqual(result.frames, (hf or lf, ""))
            self.assertEqual((result.hf, result.lf), (hf, lf))

    def test_rejects_early_wrong_extra_and_locked_frames(self):
        for option in ("early", "wrong_second", "extra", "locked"):
            reader = FakeReader(**{option: True})
            with self.subTest(option=option), self.assertRaises(ElatecError):
                capture_registration("COM7", serial_factory=reader, wait=0.1)
            self.assertTrue(all(port.closed for port in reader.connections))
            self.assertEqual(reader.commands[-3:], ["!P", "!N", "!Q"])

    def test_cancel_and_timeout_restore_normal_mode_and_release_port(self):
        for cancelled in (True, False):
            reader = FakeReader(timeout=True)
            cancel = threading.Event()

            def progress(text):
                if cancelled and text.startswith("Přilož"):
                    cancel.set()
            with self.subTest(cancelled=cancelled), self.assertRaises(RegistrationCancelled if cancelled else ElatecError):
                capture_registration("COM7", serial_factory=reader, cancel=cancel, on_progress=progress, wait=0.01)
            self.assertTrue(reader.connections[0].closed)
            self.assertEqual(reader.commands[-3:], ["!P", "!N", "!Q"])
            if cancelled:
                self.assertTrue(cancel.is_set())

    def test_failed_mode_restore_is_reported_instead_of_success(self):
        reader = FakeReader(bad_exit=True)
        with self.assertRaisesRegex(ElatecError, "odpoj a znovu připoj"):
            capture_registration("COM7", serial_factory=reader)
        self.assertTrue(all(port.closed for port in reader.connections))
