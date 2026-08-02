"""Fail-closed handling for unsupported RustDesk Flatpak installs."""

import asyncio

from ..dependencies import logger


RUSTDESK_FLATPAK_ERROR_CODE = "rustdesk_flatpak_unsupported"
RUSTDESK_FLATPAK_ERROR = (
    "RustDesk Flatpak is unsupported; remove it and install the unpacked "
    "Arch Linux package"
)


class RustDeskFlatpakSupportMixin:
    async def _refresh_rustdesk_flatpak_status(self) -> bool:
        detected = bool(
            getattr(self, "rustdesk_flatpak_installed", False)
        )
        manager = getattr(self, "app_bridge", None)
        if manager is not None:
            try:
                detected = await asyncio.to_thread(
                    manager.rustdesk_flatpak_installed
                )
            except Exception:
                logger.exception("Failed to detect RustDesk Flatpak")

        self.rustdesk_flatpak_installed = detected
        if not detected:
            self._rustdesk_flatpak_reconciled = False
            self._rustdesk_flatpak_settings_dirty = False
            return False

        pointer_fix_enabled = self.rustdesk_pointer_fix_enabled
        scroll_inertia_enabled = self.rustdesk_scroll_inertia_enabled
        focus_on_input_enabled = self.rustdesk_focus_on_input_enabled
        settings_dirty = bool(
            getattr(self, "_rustdesk_flatpak_settings_dirty", False)
            or pointer_fix_enabled
            or scroll_inertia_enabled
            or focus_on_input_enabled
        )

        self.rustdesk_pointer_fix_enabled = False
        self.rustdesk_scroll_inertia_enabled = False
        self.rustdesk_focus_on_input_enabled = False

        if settings_dirty:
            try:
                await asyncio.to_thread(
                    self._save_nested_desktop_mouse_settings,
                    rustdesk_pointer_fix_enabled=False,
                    rustdesk_scroll_inertia_enabled=False,
                    rustdesk_focus_on_input_enabled=False,
                )
            except Exception:
                logger.exception(
                    "Failed to persist disabled RustDesk Flatpak options"
                )
            self._rustdesk_flatpak_settings_dirty = False

        bridge = self.nested_desktop_mouse
        bridge_updates = (
            (
                pointer_fix_enabled,
                "set_rustdesk_pointer_fix_enabled",
            ),
            (
                scroll_inertia_enabled,
                "set_rustdesk_scroll_inertia_enabled",
            ),
            (
                focus_on_input_enabled,
                "set_rustdesk_focus_on_input_enabled",
            ),
        )
        if bridge is not None:
            for was_enabled, method_name in bridge_updates:
                if not was_enabled:
                    continue
                try:
                    await asyncio.to_thread(
                        getattr(bridge, method_name),
                        False,
                    )
                except Exception:
                    logger.exception(
                        "Failed to disable %s for RustDesk Flatpak",
                        method_name,
                    )

        if not getattr(self, "_rustdesk_flatpak_reconciled", False):
            pointer_fix = getattr(self, "rustdesk_pointer_fix", None)
            if pointer_fix is not None:
                try:
                    await asyncio.to_thread(pointer_fix.remove)
                except Exception:
                    logger.exception(
                        "Failed to remove the unsupported RustDesk hook"
                    )
            self._rustdesk_flatpak_reconciled = True

        return True
