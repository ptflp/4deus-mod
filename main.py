import asyncio
import fcntl
import json
import logging
import os
from pathlib import Path
import pwd
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

try:
    from mangoapp_hotfix import MangoHudFixManager
except Exception:
    MangoHudFixManager = None
    logger.exception(
        "MangoHud System Tool is unavailable; other features will remain active"
    )

try:
    from rustdesk_pointer_fix import RustDeskPointerFixManager
except Exception:
    RustDeskPointerFixManager = None
    logger.exception(
        "RustDesk pointer fix is unavailable; other features will remain active"
    )

try:
    from steamos_application import SteamOsApplicationManager
except Exception:
    SteamOsApplicationManager = None
    logger.exception(
        "SteamOS application System Tool is unavailable; "
        "other features will remain active"
    )

try:
    from trackpad_metrics import (
        TrackpadMetricsMonitor,
        power_cycle_steam_deck_controller,
        reconcile_steam_deck_controller_authorization,
        reinitialize_steam_deck_trackpad_driver,
    )
except Exception:
    TrackpadMetricsMonitor = None
    power_cycle_steam_deck_controller = None
    reconcile_steam_deck_controller_authorization = None
    reinitialize_steam_deck_trackpad_driver = None
    logger.exception(
        "Trackpad metrics are unavailable; other features will remain active"
    )

try:
    from nested_desktop_mouse import (
        DEFAULT_NESTED_DESKTOP_BINDINGS,
        NESTED_DESKTOP_BINDING_ACTIONS,
        NESTED_DESKTOP_BINDING_SOURCES,
        NestedDesktopMouseSupervisor,
        normalize_nested_desktop_bindings,
    )
except Exception:
    NestedDesktopMouseSupervisor = None
    DEFAULT_NESTED_DESKTOP_BINDINGS = {}
    NESTED_DESKTOP_BINDING_ACTIONS = frozenset()
    NESTED_DESKTOP_BINDING_SOURCES = ()

    def normalize_nested_desktop_bindings(_bindings):
        return {}

    logger.exception(
        "Nested Desktop mouse bridge is unavailable; "
        "other features will remain active"
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
        user_home = Path(decky_plugin.DECKY_USER_HOME)
        settings_directory = Path(
            getattr(
                decky_plugin,
                "DECKY_PLUGIN_SETTINGS_DIR",
                user_home / ".config/4deus-mod",
            )
        )
        self.nested_desktop_mouse_settings_path = (
            settings_directory / "nested-desktop-mouse.json"
        )
        self.developer_settings_path = (
            settings_directory / "developer-settings.json"
        )
        self.controller_settings_path = (
            settings_directory / "controller-settings.json"
        )
        self.trackpad_auto_recovery_enabled = (
            self._load_controller_settings()
        )
        (
            self.developer_mode,
            self.trackpad_metrics_enabled,
        ) = self._load_developer_settings()
        self.trackpad_metrics = (
            TrackpadMetricsMonitor(
                settings_directory / "trackpad-metrics-captures",
                metrics_enabled=False,
                recovery_enabled=False,
                recovery_request_callback=(
                    self._recover_trackpad_controller
                ),
            )
            if TrackpadMetricsMonitor is not None
            else None
        )
        (
            self.nested_desktop_mouse_enabled,
            self.nested_desktop_mouse_inertia_enabled,
            self.nested_desktop_bindings_enabled,
            self.nested_desktop_bindings,
            self.rustdesk_pointer_fix_enabled,
            self.rustdesk_scroll_inertia_enabled,
            self.rustdesk_focus_on_input_enabled,
        ) = self._load_nested_desktop_mouse_settings()
        self.event_loop = None
        self.nested_desktop_mouse = (
            NestedDesktopMouseSupervisor(
                plugin_root=PLUGIN_ROOT,
                logger=logger,
                mouse_enabled=self.nested_desktop_mouse_enabled,
                inertia_enabled=(
                    self.nested_desktop_mouse_inertia_enabled
                ),
                bindings_enabled=self.nested_desktop_bindings_enabled,
                bindings=self.nested_desktop_bindings,
                rustdesk_pointer_fix_enabled=(
                    self.rustdesk_pointer_fix_enabled
                ),
                rustdesk_scroll_inertia_enabled=(
                    self.rustdesk_scroll_inertia_enabled
                ),
                rustdesk_focus_on_input_enabled=(
                    self.rustdesk_focus_on_input_enabled
                ),
                run_as_user=self._worker_user(user_home),
                action_callback=self._on_nested_desktop_action,
            )
            if NestedDesktopMouseSupervisor is not None
            else None
        )
        self.nested_desktop_keyboard_visible = False
        self.input_lock = asyncio.Lock()
        self.held_key_codes = set()
        self.app_bridge = (
            AppBridgeManager(
                home=user_home,
                plugin_root=PLUGIN_ROOT,
            )
            if AppBridgeManager is not None
            else None
        )
        self.mangohud_fix = (
            MangoHudFixManager(
                home=user_home,
                plugin_root=PLUGIN_ROOT,
            )
            if MangoHudFixManager is not None
            else None
        )
        self.steamos_application = (
            SteamOsApplicationManager(home=user_home)
            if SteamOsApplicationManager is not None
            else None
        )
        self.rustdesk_pointer_fix = (
            RustDeskPointerFixManager(
                home=user_home,
                plugin_root=PLUGIN_ROOT,
            )
            if RustDeskPointerFixManager is not None
            else None
        )

    @staticmethod
    def _worker_user(user_home: Path) -> str | None:
        if os.geteuid() != 0:
            return None
        try:
            user_id = user_home.stat().st_uid
            return (
                pwd.getpwuid(user_id).pw_name
                if user_id != 0
                else None
            )
        except (KeyError, OSError):
            logger.exception("Unable to resolve the Deck user")
            return None

    async def _main(self):
        self.event_loop = asyncio.get_running_loop()
        reconciler = reconcile_steam_deck_controller_authorization
        if reconciler is not None:
            try:
                await asyncio.to_thread(reconciler)
            except Exception:
                logger.exception(
                    "Failed to reconcile controller authorization at startup"
                )
        try:
            self.keyboard = VirtualKeyboard()
            logger.info("Created 4deus Mod uinput keyboard")
        except Exception:
            logger.exception("Failed to create 4deus Mod uinput keyboard")
        if self.rustdesk_pointer_fix_enabled:
            await self._stage_rustdesk_pointer_fix()
        await self._refresh_installed_steamos_wrapper()
        self._sync_trackpad_metrics()
        if (
            self.nested_desktop_mouse is not None
            and (
                self.nested_desktop_mouse_enabled
                or self.nested_desktop_bindings_enabled
                or self.rustdesk_pointer_fix_enabled
            )
        ):
            self.nested_desktop_mouse.start()

    async def _unload(self):
        if self.trackpad_metrics is not None:
            await asyncio.to_thread(self.trackpad_metrics.stop)
        if self.nested_desktop_mouse is not None:
            await asyncio.to_thread(self.nested_desktop_mouse.stop)
        if self.keyboard is not None:
            self.keyboard.close()
            self.keyboard = None
        self.event_loop = None

    async def _uninstall(self):
        await self._unload()
        if self.mangohud_fix is not None:
            try:
                await asyncio.to_thread(self.mangohud_fix.remove)
            except Exception:
                logger.exception(
                    "Failed to remove MangoHud fix during uninstall"
                )
        if self.rustdesk_pointer_fix is not None:
            try:
                await asyncio.to_thread(self.rustdesk_pointer_fix.remove)
            except Exception:
                logger.exception(
                    "Failed to remove RustDesk pointer fix during uninstall"
                )

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

    async def get_developer_settings_status(self):
        monitor = self.trackpad_metrics
        metrics = (
            monitor.status()
            if monitor is not None
            else {
                "running": False,
                "devicePath": "",
                "sampleCount": 0,
                "retainedSeconds": 0,
                "capacitySeconds": 0,
                "sampleRateHz": 0,
                "latest": None,
                "captures": [],
                "error": "Trackpad metrics backend is unavailable",
            }
        )
        return {
            "developerMode": self.developer_mode,
            "trackpadMetricsEnabled": self.trackpad_metrics_enabled,
            "metrics": {
                "available": monitor is not None,
                **metrics,
            },
        }

    async def set_developer_mode(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_developer_settings_status(),
                "error": "Developer mode must be a boolean",
            }
        try:
            await asyncio.to_thread(
                self._save_developer_settings,
                enabled,
                self.trackpad_metrics_enabled,
            )
            self.developer_mode = enabled
            await asyncio.to_thread(self._sync_trackpad_metrics)
            logger.info(
                "Developer mode %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to change developer mode")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    async def set_trackpad_metrics_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_developer_settings_status(),
                "error": "Trackpad metrics enabled must be a boolean",
            }
        if enabled and not self.developer_mode:
            return {
                **await self.get_developer_settings_status(),
                "error": "Enable developer mode first",
            }
        try:
            await asyncio.to_thread(
                self._save_developer_settings,
                self.developer_mode,
                enabled,
            )
            self.trackpad_metrics_enabled = enabled
            await asyncio.to_thread(self._sync_trackpad_metrics)
            logger.info(
                "Trackpad metrics collection %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to change trackpad metrics collection")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    async def get_trackpad_metrics_window(
        self,
        capture_id: str = "",
        max_samples: int = 600,
    ):
        monitor = self.trackpad_metrics
        if monitor is None:
            return {
                "captureId": capture_id,
                "sampleCount": 0,
                "samples": [],
                "error": "Trackpad metrics backend is unavailable",
            }
        if not isinstance(capture_id, str) or not isinstance(
            max_samples,
            int,
        ):
            return {
                "captureId": "",
                "sampleCount": 0,
                "samples": [],
                "error": "Invalid trackpad metrics window request",
            }
        try:
            return await asyncio.to_thread(
                monitor.window,
                capture_id or None,
                max_samples,
            )
        except Exception as error:
            logger.exception("Failed to read trackpad metrics")
            return {
                "captureId": capture_id,
                "sampleCount": 0,
                "samples": [],
                "error": str(error),
            }

    async def capture_trackpad_metrics(self):
        monitor = self.trackpad_metrics
        if monitor is None:
            return {
                **await self.get_developer_settings_status(),
                "error": "Trackpad metrics backend is unavailable",
            }
        try:
            await asyncio.to_thread(monitor.capture)
            logger.info("Saved a manual trackpad metrics capture")
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to save trackpad metrics")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    async def clear_trackpad_metrics_buffer(self):
        monitor = self.trackpad_metrics
        if monitor is not None:
            await asyncio.to_thread(monitor.clear)
        return await self.get_developer_settings_status()

    async def delete_trackpad_metrics_capture(self, capture_id: str):
        monitor = self.trackpad_metrics
        if monitor is None:
            return await self.get_developer_settings_status()
        if not isinstance(capture_id, str):
            return {
                **await self.get_developer_settings_status(),
                "error": "Invalid trackpad metrics capture ID",
            }
        try:
            await asyncio.to_thread(monitor.delete_capture, capture_id)
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to delete trackpad metrics capture")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    def _sync_trackpad_metrics(self):
        monitor = self.trackpad_metrics
        if monitor is None:
            return
        metrics_enabled = (
            self.developer_mode and self.trackpad_metrics_enabled
        )
        configure = getattr(monitor, "configure", None)
        if configure is not None:
            configure(
                metrics_enabled=metrics_enabled,
                recovery_enabled=self.trackpad_auto_recovery_enabled,
            )
        elif metrics_enabled or self.trackpad_auto_recovery_enabled:
            monitor.start()
        else:
            monitor.stop()

    def _load_developer_settings(self) -> tuple[bool, bool]:
        try:
            payload = json.loads(
                self.developer_settings_path.read_text(encoding="utf-8")
            )
            return (
                payload.get("developerMode", False) is True,
                payload.get("trackpadMetricsEnabled", False) is True,
            )
        except FileNotFoundError:
            return False, False
        except Exception:
            logger.exception("Failed to read developer settings")
            return False, False

    def _save_developer_settings(
        self,
        developer_mode: bool,
        trackpad_metrics_enabled: bool,
    ):
        path = self.developer_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "developerMode": developer_mode,
                    "trackpadMetricsEnabled": trackpad_metrics_enabled,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    async def get_controller_status(self):
        monitor = self.trackpad_metrics
        recovery = (
            monitor.recovery_status()
            if monitor is not None
            else {
                "enabled": self.trackpad_auto_recovery_enabled,
                "monitoring": False,
                "armed": False,
                "pending": False,
                "lastAttemptAtMs": 0,
                "lastSuccessAtMs": 0,
                "successCount": 0,
                "error": "Trackpad recovery backend is unavailable",
            }
        )
        return {
            "available": monitor is not None,
            "autoRecoveryEnabled": self.trackpad_auto_recovery_enabled,
            **recovery,
        }

    async def set_trackpad_auto_recovery_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_controller_status(),
                "error": "Trackpad auto-recovery enabled must be a boolean",
            }
        try:
            await asyncio.to_thread(
                self._save_controller_settings,
                enabled,
            )
            self.trackpad_auto_recovery_enabled = enabled
            await asyncio.to_thread(self._sync_trackpad_metrics)
            logger.info(
                "Trackpad auto-recovery %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_controller_status()
        except Exception as error:
            logger.exception("Failed to change trackpad auto-recovery")
            return {
                **await self.get_controller_status(),
                "error": str(error),
            }

    async def reinitialize_trackpad_controller(self):
        try:
            path = await asyncio.to_thread(
                self._reinitialize_trackpad_controller,
            )
            return {
                **await self.get_controller_status(),
                "devicePath": str(path),
            }
        except Exception as error:
            logger.exception("Failed to reinitialize the trackpad controller")
            return {
                **await self.get_controller_status(),
                "error": str(error),
            }

    async def power_cycle_trackpad_controller(self, force: bool = False):
        if not isinstance(force, bool):
            return {
                **await self.get_controller_status(),
                "error": "Force must be a boolean",
            }
        try:
            path = await asyncio.to_thread(
                self._power_cycle_trackpad_controller,
                force,
            )
            status = await self.get_controller_status()
            status.pop("error", None)
            return {**status, "devicePath": str(path)}
        except Exception as error:
            logger.exception("Failed to power-cycle the trackpad controller")
            return {
                **await self.get_controller_status(),
                "error": str(error),
            }

    def _load_controller_settings(self) -> bool:
        try:
            payload = json.loads(
                self.controller_settings_path.read_text(encoding="utf-8")
            )
            return payload.get("trackpadAutoRecoveryEnabled", True) is not False
        except FileNotFoundError:
            return True
        except Exception:
            logger.exception("Failed to read controller settings")
            return True

    def _save_controller_settings(self, enabled: bool):
        path = self.controller_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"trackpadAutoRecoveryEnabled": enabled},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def _recover_trackpad_controller(self, request_id: int) -> bool:
        path = self._power_cycle_trackpad_controller()
        logger.info(
            "Trackpad recovery request %d power-cycled USB controller at %s",
            request_id,
            path,
        )
        return True

    def _reinitialize_trackpad_controller(self) -> Path:
        reinitializer = reinitialize_steam_deck_trackpad_driver
        if reinitializer is None:
            raise RuntimeError(
                "Trackpad controller recovery backend is unavailable"
            )
        monitor = self.trackpad_metrics
        if monitor is not None:
            with monitor.lock:
                sample = monitor.raw_latest
            if sample is not None and (
                sample.left_touched
                or sample.left_pressed
                or sample.left_pressure > 0
                or sample.right_touched
                or sample.right_pressed
                or sample.right_pressure > 0
            ):
                raise RuntimeError(
                    "Release both trackpads before reinitialization"
                )
        device_path = (
            monitor.device_path
            if monitor is not None
            else None
        )
        return reinitializer(device_path=device_path)

    def _power_cycle_trackpad_controller(
        self,
        force: bool = False,
    ) -> Path:
        power_cycler = power_cycle_steam_deck_controller
        if power_cycler is None:
            raise RuntimeError(
                "Trackpad controller USB recovery backend is unavailable"
            )
        monitor = self.trackpad_metrics
        device_path = None
        if monitor is not None:
            with monitor.lock:
                sample = monitor.raw_latest
                device_path = monitor.device_path
            if not force and sample is not None and (
                sample.left_touched
                or sample.left_pressed
                or sample.left_pressure > 0
                or sample.right_touched
                or sample.right_pressed
                or sample.right_pressure > 0
            ):
                raise RuntimeError(
                    "Release both trackpads before the USB power cycle"
                )
        return power_cycler(device_path=device_path)

    def _on_nested_desktop_action(self, action: str):
        if action not in {"HIDE_KEYBOARD", "SHOW_KEYBOARD"}:
            return
        loop = self.event_loop
        emitter = getattr(decky_plugin, "emit", None)
        if loop is None or emitter is None or loop.is_closed():
            return

        def dispatch():
            loop.create_task(emitter("nested_desktop_action", action))

        loop.call_soon_threadsafe(dispatch)

    async def get_nested_desktop_mouse_status(self):
        bridge = self.nested_desktop_mouse
        return {
            "available": bridge is not None,
            "bindings": dict(self.nested_desktop_bindings),
            "bindingsEnabled": self.nested_desktop_bindings_enabled,
            "enabled": self.nested_desktop_mouse_enabled,
            "inertiaEnabled": (
                self.nested_desktop_mouse_inertia_enabled
            ),
            "rustDeskPointerFixEnabled": (
                self.rustdesk_pointer_fix_enabled
            ),
            "rustDeskScrollInertiaEnabled": (
                self.rustdesk_scroll_inertia_enabled
            ),
            "rustDeskFocusOnInputEnabled": (
                self.rustdesk_focus_on_input_enabled
            ),
            "running": bridge.running() if bridge is not None else False,
            "suspended": self.nested_desktop_keyboard_visible,
        }

    async def set_nested_desktop_keyboard_visible(self, visible: bool):
        if not isinstance(visible, bool):
            return False
        if visible == self.nested_desktop_keyboard_visible:
            return True
        self.nested_desktop_keyboard_visible = visible
        bridge = self.nested_desktop_mouse
        if bridge is not None:
            await asyncio.to_thread(bridge.set_suspended, visible)
        logger.info(
            "Nested Desktop input bridge %s for the Steam keyboard",
            "paused" if visible else "resumed",
        )
        return True

    async def set_nested_desktop_mouse_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": "Enabled must be a boolean",
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                enabled,
                self.nested_desktop_mouse_inertia_enabled,
                self.nested_desktop_bindings_enabled,
                self.nested_desktop_bindings,
                self.rustdesk_pointer_fix_enabled,
            )
            self.nested_desktop_mouse_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_mouse_enabled,
                    enabled,
                )
            logger.info(
                "Nested Desktop mouse bridge %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception(
                "Failed to change the Nested Desktop mouse bridge"
            )
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def set_nested_desktop_mouse_inertia_enabled(
        self,
        enabled: bool,
    ):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": "Inertia enabled must be a boolean",
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                self.nested_desktop_mouse_enabled,
                enabled,
                self.nested_desktop_bindings_enabled,
                self.nested_desktop_bindings,
                self.rustdesk_pointer_fix_enabled,
            )
            self.nested_desktop_mouse_inertia_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_inertia_enabled,
                    enabled,
                )
            logger.info(
                "Nested Desktop trackpad inertia %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception(
                "Failed to change Nested Desktop trackpad inertia"
            )
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def set_rustdesk_pointer_fix_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": "RustDesk pointer fix enabled must be a boolean",
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                self.nested_desktop_mouse_enabled,
                self.nested_desktop_mouse_inertia_enabled,
                self.nested_desktop_bindings_enabled,
                self.nested_desktop_bindings,
                enabled,
            )
            self.rustdesk_pointer_fix_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_rustdesk_pointer_fix_enabled,
                    enabled,
                )
            if enabled:
                await self._install_rustdesk_pointer_fix(restart=True)
            logger.info(
                "RustDesk Nested Desktop pointer fix %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception("Failed to change the RustDesk pointer fix")
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def set_rustdesk_scroll_inertia_enabled(
        self,
        enabled: bool,
    ):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": (
                    "RustDesk scroll inertia enabled must be a boolean"
                ),
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                self.nested_desktop_mouse_enabled,
                self.nested_desktop_mouse_inertia_enabled,
                self.nested_desktop_bindings_enabled,
                self.nested_desktop_bindings,
                self.rustdesk_pointer_fix_enabled,
                enabled,
            )
            self.rustdesk_scroll_inertia_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_rustdesk_scroll_inertia_enabled,
                    enabled,
                )
            logger.info(
                "RustDesk wheel inertia %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception("Failed to change RustDesk wheel inertia")
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def set_rustdesk_focus_on_input_enabled(
        self,
        enabled: bool,
    ):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": (
                    "RustDesk focus on input enabled must be a boolean"
                ),
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                self.nested_desktop_mouse_enabled,
                self.nested_desktop_mouse_inertia_enabled,
                self.nested_desktop_bindings_enabled,
                self.nested_desktop_bindings,
                self.rustdesk_pointer_fix_enabled,
                self.rustdesk_scroll_inertia_enabled,
                enabled,
            )
            self.rustdesk_focus_on_input_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_rustdesk_focus_on_input_enabled,
                    enabled,
                )
            logger.info(
                "RustDesk focus on input %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception("Failed to change RustDesk focus on input")
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def _stage_rustdesk_pointer_fix(self):
        try:
            await self._install_rustdesk_pointer_fix(restart=False)
        except Exception:
            logger.exception("Failed to stage the RustDesk pointer fix")

    async def _refresh_installed_steamos_wrapper(self):
        manager = self.steamos_application
        if manager is None:
            return
        try:
            refreshed = await asyncio.to_thread(
                manager.refresh_installed_wrapper
            )
            if refreshed:
                logger.info(
                    "Updated the installed SteamOS Nested Desktop wrapper"
                )
        except Exception:
            logger.exception(
                "Failed to update the installed SteamOS wrapper"
            )

    async def _install_rustdesk_pointer_fix(self, *, restart: bool):
        manager = self.rustdesk_pointer_fix
        if manager is None or not manager.executable.is_file():
            return None
        result = await asyncio.to_thread(
            manager.install,
            restart=restart,
        )
        logger.info(
            "RustDesk pointer fix %s",
            "installed" if restart else "staged",
        )
        return result

    async def set_nested_desktop_bindings_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": "Bindings enabled must be a boolean",
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                self.nested_desktop_mouse_enabled,
                self.nested_desktop_mouse_inertia_enabled,
                enabled,
                self.nested_desktop_bindings,
                self.rustdesk_pointer_fix_enabled,
            )
            self.nested_desktop_bindings_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_bindings,
                    enabled,
                    self.nested_desktop_bindings,
                )
            logger.info(
                "Nested Desktop bindings %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception("Failed to change Nested Desktop bindings")
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def set_nested_desktop_binding(
        self,
        source: str,
        action: str,
    ):
        if source not in NESTED_DESKTOP_BINDING_SOURCES:
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": f"Unknown binding source: {source}",
            }
        if action not in NESTED_DESKTOP_BINDING_ACTIONS:
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": f"Unknown binding action: {action}",
            }

        bindings = {
            **self.nested_desktop_bindings,
            source: action,
        }
        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                self.nested_desktop_mouse_enabled,
                self.nested_desktop_mouse_inertia_enabled,
                self.nested_desktop_bindings_enabled,
                bindings,
                self.rustdesk_pointer_fix_enabled,
            )
            self.nested_desktop_bindings = bindings
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_bindings,
                    self.nested_desktop_bindings_enabled,
                    bindings,
                )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception("Failed to change a Nested Desktop binding")
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def reset_nested_desktop_bindings(self):
        bindings = dict(DEFAULT_NESTED_DESKTOP_BINDINGS)
        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                self.nested_desktop_mouse_enabled,
                self.nested_desktop_mouse_inertia_enabled,
                self.nested_desktop_bindings_enabled,
                bindings,
                self.rustdesk_pointer_fix_enabled,
            )
            self.nested_desktop_bindings = bindings
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_bindings,
                    self.nested_desktop_bindings_enabled,
                    bindings,
                )
            logger.info("Reset Nested Desktop bindings to Steam defaults")
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception("Failed to reset Nested Desktop bindings")
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    def _load_nested_desktop_mouse_settings(
        self,
    ) -> tuple[bool, bool, bool, dict[str, str], bool, bool, bool]:
        try:
            payload = json.loads(
                self.nested_desktop_mouse_settings_path.read_text(
                    encoding="utf-8"
                )
            )
            return (
                payload.get("enabled", True) is not False,
                payload.get("inertiaEnabled", True) is not False,
                payload.get("bindingsEnabled", True) is not False,
                normalize_nested_desktop_bindings(payload.get("bindings")),
                payload.get("rustDeskPointerFixEnabled", True) is not False,
                payload.get("rustDeskScrollInertiaEnabled", False) is True,
                payload.get("rustDeskFocusOnInputEnabled", False) is True,
            )
        except FileNotFoundError:
            return (
                True,
                True,
                True,
                dict(DEFAULT_NESTED_DESKTOP_BINDINGS),
                True,
                False,
                False,
            )
        except Exception:
            logger.exception(
                "Failed to read the Nested Desktop mouse bridge settings"
            )
            return (
                True,
                True,
                True,
                dict(DEFAULT_NESTED_DESKTOP_BINDINGS),
                True,
                False,
                False,
            )

    def _save_nested_desktop_mouse_settings(
        self,
        enabled: bool,
        inertia_enabled: bool,
        bindings_enabled: bool,
        bindings: dict[str, str],
        rustdesk_pointer_fix_enabled: bool,
        rustdesk_scroll_inertia_enabled: bool | None = None,
        rustdesk_focus_on_input_enabled: bool | None = None,
    ):
        if rustdesk_scroll_inertia_enabled is None:
            rustdesk_scroll_inertia_enabled = (
                self.rustdesk_scroll_inertia_enabled
            )
        if rustdesk_focus_on_input_enabled is None:
            rustdesk_focus_on_input_enabled = (
                self.rustdesk_focus_on_input_enabled
            )
        path = self.nested_desktop_mouse_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "enabled": enabled,
                    "inertiaEnabled": inertia_enabled,
                    "bindingsEnabled": bindings_enabled,
                    "bindings": normalize_nested_desktop_bindings(bindings),
                    "rustDeskPointerFixEnabled": (
                        rustdesk_pointer_fix_enabled
                    ),
                    "rustDeskScrollInertiaEnabled": (
                        rustdesk_scroll_inertia_enabled
                    ),
                    "rustDeskFocusOnInputEnabled": (
                        rustdesk_focus_on_input_enabled
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

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
            prepared = self.app_bridge.prepare_rustdesk()
            if self.rustdesk_pointer_fix_enabled:
                await self._install_rustdesk_pointer_fix(restart=True)
            return prepared
        except Exception as error:
            logger.exception("Failed to prepare RustDesk App Bridge profile")
            return {"error": str(error)}

    async def install_app_bridge_artwork(
        self,
        artwork_id: str,
        app_id: int,
    ):
        if self.app_bridge is None:
            return {
                "error": "App Bridge backend is unavailable",
                "installed": 0,
                "preserved": 0,
            }
        try:
            result = await asyncio.to_thread(
                self.app_bridge.install_artwork,
                artwork_id,
                app_id,
            )
            logger.info(
                "Installed App Bridge artwork %s for non-Steam AppID %s",
                artwork_id,
                app_id,
            )
            return result
        except Exception as error:
            logger.exception(
                "Failed to install App Bridge artwork %s for AppID %s",
                artwork_id,
                app_id,
            )
            return {
                "error": str(error),
                "installed": 0,
                "preserved": 0,
            }

    async def get_mangohud_fix_status(self):
        if self.mangohud_fix is None:
            return {
                "available": False,
                "current": False,
                "error": "System Tools backend is unavailable",
                "installed": False,
                "libraryPath": "",
                "serviceState": "unknown",
            }
        try:
            return await asyncio.to_thread(self.mangohud_fix.status)
        except Exception as error:
            logger.exception("Failed to read MangoHud fix status")
            return self._mangohud_fix_error(error)

    async def install_mangohud_fix(self):
        if self.mangohud_fix is None:
            return await self.get_mangohud_fix_status()
        try:
            result = await asyncio.to_thread(self.mangohud_fix.install)
            logger.info("Installed or repaired MangoHud process FD guard")
            return result
        except Exception as error:
            logger.exception("Failed to install MangoHud process FD guard")
            return self._mangohud_fix_error(error)

    async def remove_mangohud_fix(self):
        if self.mangohud_fix is None:
            return await self.get_mangohud_fix_status()
        try:
            result = await asyncio.to_thread(self.mangohud_fix.remove)
            logger.info("Removed MangoHud process FD guard")
            return result
        except Exception as error:
            logger.exception("Failed to remove MangoHud process FD guard")
            return self._mangohud_fix_error(error)

    def _mangohud_fix_error(self, error):
        try:
            status = self.mangohud_fix.status()
        except Exception:
            status = {
                "available": False,
                "current": False,
                "installed": False,
                "libraryPath": "",
                "serviceState": "unknown",
            }
        return {
            **status,
            "error": str(error),
        }

    async def get_steamos_application_status(self):
        if self.steamos_application is None:
            return {
                "available": False,
                "current": False,
                "error": "SteamOS application backend is unavailable",
                "icon": "",
                "wrapperInstalled": False,
                "wrapperPath": "",
            }
        try:
            return self.steamos_application.status()
        except Exception as error:
            logger.exception("Failed to read SteamOS application status")
            return self._steamos_application_error(error)

    async def prepare_steamos_application(self):
        if self.steamos_application is None:
            return await self.get_steamos_application_status()
        try:
            result = await asyncio.to_thread(self.steamos_application.prepare)
            logger.info("Prepared the SteamOS Nested Desktop wrapper")
            return result
        except Exception as error:
            logger.exception("Failed to prepare the SteamOS application")
            return self._steamos_application_error(error)

    async def install_steamos_application_artwork(self, app_id: int):
        if self.steamos_application is None:
            return {
                "error": "SteamOS application backend is unavailable",
                "installed": 0,
                "preserved": 0,
            }
        try:
            result = await asyncio.to_thread(
                self.steamos_application.install_artwork,
                app_id,
            )
            logger.info(
                "Installed SteamOS artwork for non-Steam AppID %s",
                app_id,
            )
            return result
        except Exception as error:
            logger.exception(
                "Failed to install SteamOS artwork for AppID %s",
                app_id,
            )
            return {
                "error": str(error),
                "installed": 0,
                "preserved": 0,
            }

    def _steamos_application_error(self, error):
        try:
            status = self.steamos_application.status()
        except Exception:
            status = {
                "available": False,
                "current": False,
                "icon": "",
                "wrapperInstalled": False,
                "wrapperPath": "",
            }
        return {
            **status,
            "error": str(error),
        }
