import asyncio
import fcntl
import logging
import os
import struct
import sys

import decky_plugin


logger = decky_plugin.logger
logger.setLevel(logging.INFO)

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

try:
    from app_bridge import AppBridgeManager
except Exception:
    AppBridgeManager = None
    logger.exception(
        "App Bridge is unavailable; keyboard features will remain active"
    )

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
    def __init__(self):
        self.keyboard = None
        self.input_lock = asyncio.Lock()
        self.held_key_codes = set()
        self.app_bridge = (
            AppBridgeManager(
                home=decky_plugin.DECKY_USER_HOME,
                plugin_root=PLUGIN_ROOT,
            )
            if AppBridgeManager is not None
            else None
        )

    async def _main(self):
        try:
            self.keyboard = VirtualKeyboard()
            logger.info("Created 4deus Mod uinput keyboard")
        except Exception:
            logger.exception("Failed to create 4deus Mod uinput keyboard")

    async def _unload(self):
        if self.keyboard is not None:
            self.keyboard.close()
            self.keyboard = None

    async def send_system_key(
        self,
        key_name: str,
        with_control: bool = False,
        with_alt: bool = False,
        with_shift: bool = False,
        with_meta: bool = False,
    ):
        key_code = KEY_CODES.get(key_name)
        keyboard = self.keyboard
        if keyboard is None or key_code is None:
            logger.error("Cannot send system key: %s", key_name)
            return False

        async with self.input_lock:
            chord_modifiers = [
                (with_control, KEY_LEFTCTRL),
                (with_alt, KEY_LEFTALT),
                (with_shift, KEY_LEFTSHIFT),
                (with_meta, KEY_LEFTMETA),
            ]
            pressed_modifiers = []
            target_was_held = key_code in self.held_key_codes
            try:
                for enabled, modifier in chord_modifiers:
                    if enabled and modifier not in self.held_key_codes:
                        keyboard.write_key(modifier, 1)
                        pressed_modifiers.append(modifier)
                keyboard.write_key(key_code, 1)
                await asyncio.sleep(0.03)
                return True
            except Exception:
                logger.exception("Failed to send system key: %s", key_name)
                return False
            finally:
                try:
                    if not target_was_held:
                        keyboard.write_key(key_code, 0)
                    for modifier in reversed(pressed_modifiers):
                        keyboard.write_key(modifier, 0)
                except Exception:
                    logger.exception("Failed to release virtual keyboard keys")

    async def set_system_key_state(self, key_name: str, pressed: bool):
        key_code = KEY_CODES.get(key_name)
        keyboard = self.keyboard
        if keyboard is None or key_code is None:
            logger.error("Cannot set system key state: %s", key_name)
            return False

        async with self.input_lock:
            try:
                if pressed and key_code not in self.held_key_codes:
                    keyboard.write_key(key_code, 1)
                    self.held_key_codes.add(key_code)
                elif not pressed and key_code in self.held_key_codes:
                    keyboard.write_key(key_code, 0)
                    self.held_key_codes.remove(key_code)
                return True
            except Exception:
                logger.exception(
                    "Failed to set system key state: %s=%s",
                    key_name,
                    pressed,
                )
                return False

    async def log_keyboard_diagnostics(self, payload: str):
        if not isinstance(payload, str):
            return False
        logger.info("Keyboard diagnostics: %s", payload[:4000])
        return True

    async def get_app_bridge_status(self):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        return self.app_bridge.status()

    async def list_app_bridge_applications(self):
        if self.app_bridge is None:
            return []
        return self.app_bridge.list_applications()

    async def save_app_bridge_profile(self, profile):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        try:
            return self.app_bridge.save_profile(profile)
        except Exception as error:
            logger.exception("Failed to save App Bridge profile")
            return {"error": str(error)}

    async def prepare_parsec_app_bridge(self):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        try:
            return self.app_bridge.prepare_parsec()
        except Exception as error:
            logger.exception("Failed to prepare Parsec App Bridge profile")
            return {"error": str(error)}

    async def prepare_rustdesk_app_bridge(self):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        try:
            return self.app_bridge.prepare_rustdesk()
        except Exception as error:
            logger.exception("Failed to prepare RustDesk App Bridge profile")
            return {"error": str(error)}
