"""Clipboard-specific Nested Desktop Decky endpoints."""

import asyncio

from ..dependencies import logger


class NestedDesktopClipboardEndpointsMixin:
    async def set_nested_desktop_clipboard_enabled(
        self,
        enabled: bool,
    ):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": "Clipboard sharing enabled must be a boolean",
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                clipboard_enabled=enabled,
            )
            self.nested_desktop_clipboard_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_clipboard_enabled,
                    enabled,
                )
            logger.info(
                "Nested Desktop clipboard sharing %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception(
                "Failed to change Nested Desktop clipboard sharing"
            )
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def set_nested_desktop_clipboard_files_enabled(
        self,
        enabled: bool,
    ):
        if not isinstance(enabled, bool):
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": "Clipboard file sharing enabled must be a boolean",
            }

        try:
            await asyncio.to_thread(
                self._save_nested_desktop_mouse_settings,
                clipboard_files_enabled=enabled,
            )
            self.nested_desktop_clipboard_files_enabled = enabled
            bridge = self.nested_desktop_mouse
            if bridge is not None:
                await asyncio.to_thread(
                    bridge.set_clipboard_files_enabled,
                    enabled,
                )
            logger.info(
                "Nested Desktop clipboard file sharing %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_nested_desktop_mouse_status()
        except Exception as error:
            logger.exception(
                "Failed to change Nested Desktop clipboard file sharing"
            )
            return {
                **await self.get_nested_desktop_mouse_status(),
                "error": str(error),
            }

    async def read_nested_desktop_clipboard_text(self):
        if not self.nested_desktop_clipboard_enabled:
            return None
        bridge = self.nested_desktop_mouse
        if bridge is None:
            return None
        try:
            return await asyncio.to_thread(bridge.read_clipboard_text)
        except Exception:
            logger.exception("Failed to read the shared clipboard")
            return None
