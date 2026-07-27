import asyncio
import fcntl
import logging
import os
import struct

import decky_plugin


logger = decky_plugin.logger
logger.setLevel(logging.INFO)

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
    "KEY_LEFT": 105,
    "KEY_RIGHT": 106,
    "KEY_DELETE": 111,
}
KEY_LEFTCTRL = 29

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
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            for key_code in sorted({*KEY_CODES.values(), KEY_LEFTCTRL}):
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

    def _write_event(self, event_type: int, code: int, value: int):
        os.write(
            self.fd,
            struct.pack("llHHi", 0, 0, event_type, code, value),
        )


class Plugin:
    keyboard = None
    input_lock = asyncio.Lock()

    async def _main(self):
        try:
            Plugin.keyboard = VirtualKeyboard()
            logger.info("Created 4deus Mod uinput keyboard")
        except Exception:
            logger.exception("Failed to create 4deus Mod uinput keyboard")

    async def _unload(self):
        if Plugin.keyboard is not None:
            Plugin.keyboard.close()
            Plugin.keyboard = None

    async def send_system_key(self, key_name: str, with_control: bool = False):
        key_code = KEY_CODES.get(key_name)
        keyboard = Plugin.keyboard
        if keyboard is None or key_code is None:
            logger.error("Cannot send system key: %s", key_name)
            return False

        async with Plugin.input_lock:
            try:
                if with_control:
                    self._write_key(KEY_LEFTCTRL, 1)
                self._write_key(key_code, 1)
                await asyncio.sleep(0.03)
                self._write_key(key_code, 0)
                if with_control:
                    self._write_key(KEY_LEFTCTRL, 0)
                return True
            except Exception:
                logger.exception("Failed to send system key: %s", key_name)
                self._release_keys(key_code, with_control)
                return False

    @staticmethod
    def _write_key(key_code: int, value: int):
        Plugin.keyboard.write_key(key_code, value)

    def _release_keys(self, key_code: int, with_control: bool):
        keyboard = Plugin.keyboard
        if keyboard is None:
            return
        try:
            self._write_key(key_code, 0)
            if with_control:
                self._write_key(KEY_LEFTCTRL, 0)
        except Exception:
            logger.exception("Failed to release virtual keyboard keys")
