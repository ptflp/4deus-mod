"""Nested Desktop and RustDesk Decky endpoints."""

import asyncio
import json
import os

import decky_plugin

from ..dependencies import (
    DEFAULT_NESTED_DESKTOP_BINDINGS,
    NESTED_DESKTOP_BINDING_ACTIONS,
    NESTED_DESKTOP_BINDING_SOURCES,
    logger,
    normalize_nested_desktop_bindings,
)


class NestedDesktopEndpointsMixin:
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
