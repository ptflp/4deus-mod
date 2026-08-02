"""Virtual uinput keyboard used for system-level key chords."""

import fcntl
import os
import struct


KEY_CODES = {
    "KEY_ESC": 1,
    "KEY_1": 2,
    "KEY_2": 3,
    "KEY_3": 4,
    "KEY_4": 5,
    "KEY_5": 6,
    "KEY_6": 7,
    "KEY_7": 8,
    "KEY_8": 9,
    "KEY_9": 10,
    "KEY_0": 11,
    "KEY_MINUS": 12,
    "KEY_EQUAL": 13,
    "KEY_BACKSPACE": 14,
    "KEY_TAB": 15,
    "KEY_Q": 16,
    "KEY_W": 17,
    "KEY_E": 18,
    "KEY_R": 19,
    "KEY_T": 20,
    "KEY_Y": 21,
    "KEY_U": 22,
    "KEY_I": 23,
    "KEY_O": 24,
    "KEY_P": 25,
    "KEY_LEFTBRACE": 26,
    "KEY_RIGHTBRACE": 27,
    "KEY_ENTER": 28,
    "KEY_A": 30,
    "KEY_S": 31,
    "KEY_D": 32,
    "KEY_F": 33,
    "KEY_G": 34,
    "KEY_H": 35,
    "KEY_J": 36,
    "KEY_K": 37,
    "KEY_L": 38,
    "KEY_SEMICOLON": 39,
    "KEY_APOSTROPHE": 40,
    "KEY_GRAVE": 41,
    "KEY_LEFTSHIFT": 42,
    "KEY_BACKSLASH": 43,
    "KEY_Z": 44,
    "KEY_X": 45,
    "KEY_C": 46,
    "KEY_V": 47,
    "KEY_B": 48,
    "KEY_N": 49,
    "KEY_M": 50,
    "KEY_COMMA": 51,
    "KEY_DOT": 52,
    "KEY_SLASH": 53,
    "KEY_SPACE": 57,
    "KEY_F1": 59,
    "KEY_F2": 60,
    "KEY_F3": 61,
    "KEY_F4": 62,
    "KEY_F5": 63,
    "KEY_F6": 64,
    "KEY_F7": 65,
    "KEY_F8": 66,
    "KEY_F9": 67,
    "KEY_F10": 68,
    "KEY_F11": 87,
    "KEY_F12": 88,
    "KEY_HOME": 102,
    "KEY_UP": 103,
    "KEY_PAGEUP": 104,
    "KEY_LEFT": 105,
    "KEY_RIGHT": 106,
    "KEY_END": 107,
    "KEY_DOWN": 108,
    "KEY_PAGEDOWN": 109,
    "KEY_INSERT": 110,
    "KEY_DELETE": 111,
    "KEY_LEFTMETA": 125,
    "KEY_LEFTCTRL": 29,
    "KEY_LEFTALT": 56,
}
KEY_LEFTCTRL = 29
KEY_LEFTALT = 56
KEY_LEFTSHIFT = 42
KEY_LEFTMETA = 125
MODIFIER_KEY_CODES = (
    KEY_LEFTCTRL,
    KEY_LEFTALT,
    KEY_LEFTSHIFT,
    KEY_LEFTMETA,
)

EV_SYN = 0
EV_KEY = 1
SYN_REPORT = 0
BUS_USB = 3

UI_DEV_CREATE = (ord("U") << 8) | 1
UI_DEV_DESTROY = (ord("U") << 8) | 2
UI_DEV_SETUP = (1 << 30) | (92 << 16) | (ord("U") << 8) | 3
UI_SET_EVBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 100
UI_SET_KEYBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 101


class VirtualKeyboard:
    def __init__(self):
        self.prepared = False
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            for key_code in sorted(
                {*KEY_CODES.values(), KEY_LEFTCTRL, KEY_LEFTALT}
            ):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, key_code)
            setup = struct.pack(
                "HHHH80sI",
                BUS_USB,
                0x28DE,
                0x1205,
                1,
                b"4deus Mod Virtual Keyboard",
                0,
            )
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except Exception:
            os.close(self.fd)
            raise

    def prepare(self) -> bool:
        """Neutralize a newly hot-plugged keyboard before its first chord."""
        if self.prepared:
            return False
        for key_code in MODIFIER_KEY_CODES:
            self._write_event(EV_KEY, key_code, 0)
        self._write_event(EV_SYN, SYN_REPORT, 0)
        self.prepared = True
        return True

    def write_key(self, key_code: int, value: int):
        self._write_event(EV_KEY, key_code, value)
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def close(self):
        if self.fd is None:
            return
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)
            self.fd = None
            self.prepared = False

    def _write_event(self, event_type: int, code: int, value: int):
        os.write(
            self.fd,
            struct.pack("llHHi", 0, 0, event_type, code, value),
        )
