"""Decky plugin lifecycle and system-key orchestration."""

import asyncio
import os
from pathlib import Path
import pwd

import decky_plugin

from .dependencies import (
    AppBridgeManager,
    DEFAULT_NESTED_DESKTOP_BINDINGS,
    MangoHudFixManager,
    NestedDesktopMouseSupervisor,
    PLUGIN_ROOT,
    RustDeskPointerFixManager,
    SteamOsApplicationManager,
    TrackpadMetricsMonitor,
    logger,
    reconcile_steam_deck_controller_authorization,
)
from .endpoints.controller import ControllerEndpointsMixin
from .endpoints.developer import DeveloperEndpointsMixin
from .endpoints.nested_desktop import NestedDesktopEndpointsMixin
from .endpoints.system_tools import SystemToolsEndpointsMixin
from .keyboard import (
    KEY_CODES,
    KEY_LEFTALT,
    KEY_LEFTCTRL,
    KEY_LEFTMETA,
    KEY_LEFTSHIFT,
    VirtualKeyboard,
)


class Plugin(
    DeveloperEndpointsMixin,
    ControllerEndpointsMixin,
    NestedDesktopEndpointsMixin,
    SystemToolsEndpointsMixin,
):
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
        (
            self.controller_module_enabled,
            self.trackpad_auto_recovery_enabled,
        ) = self._load_controller_settings()
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
            self.nested_desktop_module_enabled,
            self.nested_desktop_mouse_enabled,
            self.nested_desktop_gamescope_pointer_relay_enabled,
            self.nested_desktop_mouse_inertia_enabled,
            self.nested_desktop_bindings_enabled,
            self.nested_desktop_bindings,
            self.nested_desktop_clipboard_enabled,
            self.nested_desktop_clipboard_files_enabled,
            self.rustdesk_pointer_fix_enabled,
            self.rustdesk_scroll_inertia_enabled,
            self.rustdesk_focus_on_input_enabled,
            self.nested_desktop_touch_enabled,
            self.nested_desktop_touch_inertia_enabled,
            self.nested_desktop_touch_inertia_config,
        ) = self._load_nested_desktop_mouse_settings()
        self.event_loop = None
        self.nested_desktop_mouse = (
            NestedDesktopMouseSupervisor(
                plugin_root=PLUGIN_ROOT,
                logger=logger,
                module_enabled=self.nested_desktop_module_enabled,
                mouse_enabled=self.nested_desktop_mouse_enabled,
                gamescope_pointer_relay_enabled=(
                    self.nested_desktop_gamescope_pointer_relay_enabled
                ),
                inertia_enabled=(
                    self.nested_desktop_mouse_inertia_enabled
                ),
                bindings_enabled=self.nested_desktop_bindings_enabled,
                bindings=self.nested_desktop_bindings,
                clipboard_enabled=(
                    self.nested_desktop_clipboard_enabled
                ),
                clipboard_files_enabled=(
                    self.nested_desktop_clipboard_files_enabled
                ),
                touchscreen_enabled=self.nested_desktop_touch_enabled,
                touchscreen_inertia_enabled=(
                    self.nested_desktop_touch_inertia_enabled
                ),
                touchscreen_inertia_config=(
                    self.nested_desktop_touch_inertia_config
                ),
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
        if (
            self.nested_desktop_module_enabled
            and self.rustdesk_pointer_fix_enabled
        ):
            await self._stage_rustdesk_pointer_fix()
        if self.app_bridge is not None:
            try:
                refreshed = await asyncio.to_thread(
                    self.app_bridge.refresh_installed_runner
                )
                if refreshed:
                    logger.info("Refreshed the installed App Bridge runner")
            except Exception:
                logger.exception("Failed to refresh the App Bridge runner")
        if self.nested_desktop_module_enabled:
            await self._refresh_installed_steamos_wrapper()
        self._sync_trackpad_metrics()
        if (
            self.nested_desktop_mouse is not None
            and self.nested_desktop_module_enabled
            and (
                self.nested_desktop_mouse_enabled
                or self.nested_desktop_gamescope_pointer_relay_enabled
                or self.nested_desktop_clipboard_enabled
                or self.nested_desktop_touch_enabled
                or self.nested_desktop_bindings_enabled
                or self.rustdesk_pointer_fix_enabled
                or self.rustdesk_focus_on_input_enabled
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
