"""Decky plugin lifecycle and system-key orchestration."""

import asyncio
from collections import deque
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


KEYBOARD_SETTLE_SECONDS = 0.03
SYSTEM_KEY_REQUEST_CACHE_SIZE = 128


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
        self.app_bridge = (
            AppBridgeManager(
                home=user_home,
                plugin_root=PLUGIN_ROOT,
            )
            if AppBridgeManager is not None
            else None
        )
        self.rustdesk_flatpak_installed = bool(
            self.app_bridge
            and self.app_bridge.rustdesk_flatpak_installed()
        )
        self._rustdesk_flatpak_reconciled = False
        self._rustdesk_flatpak_settings_dirty = False
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
        if self.rustdesk_flatpak_installed:
            self._rustdesk_flatpak_settings_dirty = any(
                (
                    self.rustdesk_pointer_fix_enabled,
                    self.rustdesk_scroll_inertia_enabled,
                    self.rustdesk_focus_on_input_enabled,
                )
            )
            self.rustdesk_pointer_fix_enabled = False
            self.rustdesk_scroll_inertia_enabled = False
            self.rustdesk_focus_on_input_enabled = False
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
        self.completed_system_key_requests = set()
        self.completed_system_key_request_order = deque()
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
        await self._refresh_rustdesk_flatpak_status()
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
            await self._prepare_system_keyboard(self.keyboard)
            logger.info("Created 4deus Mod uinput keyboard")
        except Exception:
            if self.keyboard is not None:
                try:
                    self.keyboard.close()
                except Exception:
                    logger.exception(
                        "Failed to close the incomplete uinput keyboard"
                    )
                self.keyboard = None
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
        async with self.input_lock:
            keyboard = self.keyboard
            self.keyboard = None
            if keyboard is not None:
                for key_code in tuple(self.held_key_codes):
                    try:
                        keyboard.write_key(key_code, 0)
                    except Exception:
                        logger.exception(
                            "Failed to release a held key during unload"
                        )
                        break
                self.held_key_codes.clear()
                keyboard.close()
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
        request_id: str | None = None,
    ):
        key_code = KEY_CODES.get(key_name)
        if key_code is None:
            logger.error("Cannot send system key: %s", key_name)
            return False

        async with self.input_lock:
            normalized_request_id = self._normalize_system_key_request_id(
                request_id
            )
            if (
                normalized_request_id is not None
                and normalized_request_id
                in self.completed_system_key_requests
            ):
                return True
            for attempt in range(2):
                keyboard = self.keyboard
                if keyboard is None:
                    if attempt or not await self._recreate_system_keyboard(
                        None
                    ):
                        logger.error("Cannot send system key: %s", key_name)
                        return False
                    continue
                try:
                    cleanup_failed = await self._send_system_key_once(
                        keyboard,
                        key_code,
                        with_control=with_control,
                        with_alt=with_alt,
                        with_shift=with_shift,
                        with_meta=with_meta,
                    )
                    self._remember_system_key_request(normalized_request_id)
                    if cleanup_failed:
                        logger.warning(
                            "Recreating virtual keyboard after a key-release "
                            "failure"
                        )
                        await self._recreate_system_keyboard(keyboard)
                    return True
                except Exception:
                    logger.exception(
                        "Failed to send system key: %s (attempt %s)",
                        key_name,
                        attempt + 1,
                    )
                    if attempt or not await self._recreate_system_keyboard(
                        keyboard
                    ):
                        return False
            return False

    async def set_system_key_state(self, key_name: str, pressed: bool):
        key_code = KEY_CODES.get(key_name)
        if key_code is None:
            logger.error("Cannot set system key state: %s", key_name)
            return False

        async with self.input_lock:
            for attempt in range(2):
                keyboard = self.keyboard
                if keyboard is None:
                    if attempt or not await self._recreate_system_keyboard(
                        None
                    ):
                        logger.error(
                            "Cannot set system key state: %s", key_name
                        )
                        return False
                    continue
                try:
                    await self._prepare_system_keyboard(keyboard)
                    if pressed and key_code not in self.held_key_codes:
                        keyboard.write_key(key_code, 1)
                        self.held_key_codes.add(key_code)
                    elif not pressed and key_code in self.held_key_codes:
                        keyboard.write_key(key_code, 0)
                        self.held_key_codes.remove(key_code)
                    return True
                except Exception:
                    logger.exception(
                        "Failed to set system key state: %s=%s (attempt %s)",
                        key_name,
                        pressed,
                        attempt + 1,
                    )
                    if attempt or not await self._recreate_system_keyboard(
                        keyboard
                    ):
                        return False
            return False

    async def _prepare_system_keyboard(self, keyboard):
        prepare = getattr(keyboard, "prepare", None)
        if callable(prepare) and prepare():
            await asyncio.sleep(KEYBOARD_SETTLE_SECONDS)

    async def _send_system_key_once(
        self,
        keyboard,
        key_code: int,
        *,
        with_control: bool,
        with_alt: bool,
        with_shift: bool,
        with_meta: bool,
    ) -> bool:
        await self._prepare_system_keyboard(keyboard)
        chord_modifiers = [
            (with_control, KEY_LEFTCTRL),
            (with_alt, KEY_LEFTALT),
            (with_shift, KEY_LEFTSHIFT),
            (with_meta, KEY_LEFTMETA),
        ]
        pressed_modifiers = []
        target_was_held = key_code in self.held_key_codes
        cleanup_failed = False
        try:
            for enabled, modifier in chord_modifiers:
                if enabled and modifier not in self.held_key_codes:
                    keyboard.write_key(modifier, 1)
                    pressed_modifiers.append(modifier)
            keyboard.write_key(key_code, 1)
            await asyncio.sleep(KEYBOARD_SETTLE_SECONDS)
        finally:
            try:
                if not target_was_held:
                    keyboard.write_key(key_code, 0)
                for modifier in reversed(pressed_modifiers):
                    keyboard.write_key(modifier, 0)
            except Exception:
                cleanup_failed = True
                logger.exception("Failed to release virtual keyboard keys")
        return cleanup_failed

    async def _recreate_system_keyboard(self, failed_keyboard) -> bool:
        if failed_keyboard is not None:
            try:
                failed_keyboard.close()
            except Exception:
                logger.exception("Failed to close the broken virtual keyboard")
        self.keyboard = None
        try:
            self.keyboard = VirtualKeyboard()
            await self._prepare_system_keyboard(self.keyboard)
            for key_code in sorted(self.held_key_codes):
                self.keyboard.write_key(key_code, 1)
            logger.warning("Recreated the 4deus Mod uinput keyboard")
            return True
        except Exception:
            logger.exception("Failed to recreate the 4deus Mod uinput keyboard")
            if self.keyboard is not None:
                try:
                    self.keyboard.close()
                except Exception:
                    logger.exception(
                        "Failed to close the replacement virtual keyboard"
                    )
                self.keyboard = None
            return False

    @staticmethod
    def _normalize_system_key_request_id(request_id) -> str | None:
        if not isinstance(request_id, str):
            return None
        request_id = request_id.strip()
        if not request_id or len(request_id) > 128:
            return None
        return request_id

    def _remember_system_key_request(self, request_id: str | None):
        if (
            request_id is None
            or request_id in self.completed_system_key_requests
        ):
            return
        self.completed_system_key_requests.add(request_id)
        self.completed_system_key_request_order.append(request_id)
        while (
            len(self.completed_system_key_request_order)
            > SYSTEM_KEY_REQUEST_CACHE_SIZE
        ):
            expired = self.completed_system_key_request_order.popleft()
            self.completed_system_key_requests.discard(expired)

    async def log_keyboard_diagnostics(self, payload: str):
        if not isinstance(payload, str):
            return False
        logger.info("Keyboard diagnostics: %s", payload[:4000])
        return True
