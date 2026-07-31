"""Focus, device discovery, and forwarding state transitions."""

from __future__ import annotations

import logging
import os
import socket
import time

from .bindings import (
    decode_gamescope_display, should_forward_back_button,
    should_forward_pointer,
)
from .constants import (
    FOCUS_SNAPSHOT_FALLBACK_INTERVAL, IDLE_INPUT_FRAME_INTERVAL,
    RUSTDESK_ACTIVE_CONNECTION_CHECK_INTERVAL,
    RUSTDESK_CONNECTION_CHECK_INTERVAL, RUSTDESK_CONNECTION_STALE_GRACE,
    STEAM_UI_APP_ID,
)
from .discovery import (
    ensure_nested_wayland_alias, find_nested_desktop_session,
    find_rustdesk_joystick, find_rustdesk_keyboard,
    find_steam_deck_hidraw, remove_nested_wayland_alias,
)
from .eis import EisConnection
from .rustdesk import RustDeskMouseTranslator, RustDeskRelayTranslator
from .x11 import X11Connection


LOGGER = logging.getLogger("4deus-nested-mouse")


class RuntimeFocusMixin:
    def _discover(self):
        if self.outer_x11 is None:
            try:
                self.outer_x11 = X11Connection(":0")
                LOGGER.info("Connected to the gamescope X display")
            except Exception as error:
                LOGGER.debug("Gamescope X display is unavailable: %s", error)

        session_process_exists = bool(
            self.session is not None
            and (self.proc_root / str(self.session.pid)).exists()
        )
        discovered_session = (
            self.session
            if session_process_exists
            else find_nested_desktop_session(self.proc_root)
        )
        if discovered_session != self.session:
            self.nested_desktop_focused = False
            self._set_cursor_overlay(False)
            self._set_gamescope_pointer_intercepted(False)
            self._close_cursor_overlay()
            self.cursor_overlay_failed_session_pid = None
            self.proton_focusable_windows = ()
            self.proton_focusable_app_ids = ()
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
            self._set_touch_forwarding(False)
            self._set_remote_forwarding(False)
            self._close_rustdesk_joystick()
            self._close_rustdesk_keyboard()
            remove_nested_wayland_alias(self.session, self.wayland_alias)
            self.wayland_alias = None
            if self.inner_eis is not None:
                self.inner_eis.close()
                self.inner_eis = None
            self.session = discovered_session
            if discovered_session is not None:
                LOGGER.info(
                    "Found Nested Desktop AppID %s on %s",
                    discovered_session.app_id,
                    discovered_session.display,
                )
        if self.session is not None:
            alias = ensure_nested_wayland_alias(self.session)
            if alias is not None and alias != self.wayland_alias:
                LOGGER.info(
                    "Exposed Nested Desktop Wayland socket at %s",
                    alias,
                )
            self.wayland_alias = alias

        if self.clipboard_bridge is not None:
            self.clipboard_bridge.set_session(self.session)

        if self.session is not None and self.inner_eis is None:
            try:
                self.inner_eis = EisConnection(
                    self.session.dbus_address,
                )
                LOGGER.info("Connected to the Nested Desktop KWin EIS input")
            except Exception as error:
                LOGGER.debug("Nested Desktop input is unavailable: %s", error)

        discovered_rustdesk = None
        if (
            self.rustdesk_pointer_fix_enabled
            or self.rustdesk_focus_on_input_enabled
        ):
            discovered_rustdesk = (
                self.rustdesk_path
                if self.rustdesk_fd is not None
                else find_rustdesk_joystick(
                    self.sys_class_input,
                    self.input_dev_root,
                )
            )
        if discovered_rustdesk != self.rustdesk_path:
            self._close_rustdesk_joystick()
            self.rustdesk_path = discovered_rustdesk
        if (
            self.rustdesk_fd is None
            and self.rustdesk_path is not None
            and (
                self.rustdesk_focus_on_input_enabled
                or (
                    self.inner_eis is not None
                    and self.inner_eis.absolute_ready
                )
            )
        ):
            try:
                self.rustdesk_fd = os.open(
                    self.rustdesk_path,
                    os.O_RDONLY | os.O_NONBLOCK,
                )
                self.rustdesk_buffer = b""
                self.rustdesk_translator = RustDeskMouseTranslator()
                LOGGER.info(
                    "Reading RustDesk pointer from %s",
                    self.rustdesk_path,
                )
            except OSError as error:
                LOGGER.debug(
                    "RustDesk pointer device is unavailable: %s",
                    error,
                )

        discovered_rustdesk_keyboard = None
        if self.rustdesk_focus_on_input_enabled:
            discovered_rustdesk_keyboard = (
                self.rustdesk_keyboard_path
                if self.rustdesk_keyboard_fd is not None
                else find_rustdesk_keyboard(
                    self.sys_class_input,
                    self.input_dev_root,
                )
            )
        if discovered_rustdesk_keyboard != self.rustdesk_keyboard_path:
            self._close_rustdesk_keyboard()
            self.rustdesk_keyboard_path = discovered_rustdesk_keyboard
        if (
            self.rustdesk_keyboard_fd is None
            and self.rustdesk_keyboard_path is not None
        ):
            try:
                self.rustdesk_keyboard_fd = os.open(
                    self.rustdesk_keyboard_path,
                    os.O_RDONLY | os.O_NONBLOCK,
                )
                self.rustdesk_keyboard_buffer = b""
                LOGGER.info(
                    "Reading RustDesk keyboard from %s",
                    self.rustdesk_keyboard_path,
                )
            except OSError as error:
                LOGGER.debug(
                    "RustDesk keyboard device is unavailable: %s",
                    error,
                )

        discovered_hidraw = (
            self.hidraw_path
            if self.hidraw_fd is not None
            else find_steam_deck_hidraw(
                self.sys_class_hidraw,
                self.dev_root,
            )
        )
        if discovered_hidraw != self.hidraw_path:
            self._close_hidraw()
            self.hidraw_path = discovered_hidraw
        if self.hidraw_fd is None and self.hidraw_path is not None:
            try:
                self.hidraw_fd = os.open(
                    self.hidraw_path,
                    os.O_RDONLY | os.O_NONBLOCK,
                )
                LOGGER.info("Reading Steam Deck trackpad from %s", self.hidraw_path)
            except OSError as error:
                LOGGER.debug("Trackpad device is unavailable: %s", error)

    def _gamescope_focus_snapshot(
        self,
        now: float,
    ) -> tuple[
        tuple[int, ...],
        tuple[int, ...],
        tuple[int, ...],
        tuple[int, ...],
    ] | None:
        outer_x11 = self.outer_x11
        if outer_x11 is None:
            self.focus_snapshot = None
            return None
        drain_events = getattr(
            outer_x11,
            "drain_property_events",
            None,
        )
        changed = (
            bool(drain_events())
            if callable(drain_events)
            else True
        )
        if (
            self.focus_snapshot is not None
            and not changed
            and now < self.next_focus_snapshot_refresh
        ):
            return self.focus_snapshot
        focusable_windows = tuple(
            outer_x11.cardinals("GAMESCOPE_FOCUSABLE_WINDOWS")
        )
        snapshot = (
            tuple(outer_x11.cardinals("GAMESCOPE_FOCUSED_APP")),
            tuple(outer_x11.cardinals("GAMESCOPE_FOCUSED_APP_GFX")),
            tuple(outer_x11.cardinals("GAMESCOPE_MOUSE_FOCUS_DISPLAY")),
            self._proton_apps_for_focusable_windows(focusable_windows),
        )
        self.focus_snapshot = snapshot
        self.next_focus_snapshot_refresh = (
            now + FOCUS_SNAPSHOT_FALLBACK_INTERVAL
        )
        return snapshot

    def _proton_apps_for_focusable_windows(
        self,
        focusable_windows: tuple[int, ...],
    ) -> tuple[int, ...]:
        if focusable_windows == self.proton_focusable_windows:
            return self.proton_focusable_app_ids
        proton_app_ids = []
        seen_app_ids = set()
        session = self.session
        ignored_app_ids = {
            0,
            STEAM_UI_APP_ID,
            session.app_id if session is not None else 0,
        }
        for offset in range(0, len(focusable_windows) - 2, 3):
            app_id = focusable_windows[offset + 1]
            pid = focusable_windows[offset + 2]
            if (
                app_id in ignored_app_ids
                or app_id in seen_app_ids
                or pid <= 1
            ):
                continue
            try:
                uses_proton = self.proton_process_query(
                    pid,
                    self.proc_root,
                )
            except Exception:
                LOGGER.debug(
                    "Unable to classify AppID %s PID %s",
                    app_id,
                    pid,
                    exc_info=True,
                )
                uses_proton = False
            if uses_proton:
                proton_app_ids.append(app_id)
                seen_app_ids.add(app_id)
        self.proton_focusable_windows = focusable_windows
        self.proton_focusable_app_ids = tuple(proton_app_ids)
        return self.proton_focusable_app_ids

    def _refresh_forwarding(self):
        inner_eis = self.inner_eis
        if inner_eis is not None:
            try:
                inner_eis.dispatch()
            except Exception as error:
                self._handle_eis_loss(error)
                return
        if (
            self.outer_x11 is None
            or inner_eis is None
            or self.session is None
        ):
            self.nested_desktop_focused = False
            self._set_cursor_overlay(False)
            self._set_gamescope_pointer_intercepted(False)
            self._set_remote_forwarding(False)
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
            self._set_touch_forwarding(False)
            return
        try:
            app_id = self.session.app_id
            now = time.monotonic()
            snapshot = self._gamescope_focus_snapshot(now)
            if snapshot is None:
                return
            (
                focused_app,
                focused_gfx_app,
                mouse_focus_display,
                proton_app_ids,
            ) = snapshot
            self.nested_desktop_focused = bool(
                focused_app
                and focused_app[0] == app_id
                and focused_gfx_app
                and focused_gfx_app[0] == app_id
            )
            pointer_needs_bridge = should_forward_pointer(
                app_id,
                focused_app,
                focused_gfx_app,
                proton_app_ids,
                mouse_focus_display,
            )
            remote_pointer_targeted = should_forward_back_button(
                app_id,
                focused_app,
                focused_gfx_app,
                mouse_focus_display,
            )
            self._set_touch_forwarding(
                self.touchscreen_enabled
                and self.touchscreen_reader is not None
                and not self.suspended
                and remote_pointer_targeted
                and getattr(inner_eis, "touch_ready", False)
            )
            self._set_remote_forwarding(
                self.rustdesk_pointer_fix_enabled
                and self.rustdesk_fd is not None
                and remote_pointer_targeted
                and self._has_active_rustdesk_connection(
                    now
                )
            )
            relay_active = self._set_remote_relaying(
                self.remote_forwarding
            )
            self._set_remote_button_forwarding(
                self.remote_forwarding
                and (pointer_needs_bridge or relay_active)
            )
            if self.inner_eis is None:
                self._set_cursor_overlay(False)
                self._set_gamescope_pointer_intercepted(False)
                return
            if self.suspended or self.hidraw_fd is None:
                self._set_forwarding(False)
                self._set_binding_forwarding(False)
            else:
                binding_capabilities_ready = (
                    (
                        not self.binding_translator.has_key_actions
                        or inner_eis.keyboard_ready
                    )
                    and (
                        not (
                            self.mouse_enabled
                            and pointer_needs_bridge
                            and self.binding_translator.has_pointer_actions
                        )
                        or inner_eis.ready
                    )
                )
                self._set_binding_forwarding(
                    self.bindings_enabled
                    and self.binding_translator.has_actions
                    and binding_capabilities_ready
                    and remote_pointer_targeted
                )
                self._set_binding_pointer_forwarding(
                    self.binding_forwarding
                    and self.mouse_enabled
                    and pointer_needs_bridge
                    and self.binding_translator.has_pointer_actions
                    and inner_eis.ready
                )
                self._set_forwarding(
                    self.mouse_enabled
                    and inner_eis.ready
                    and pointer_needs_bridge
                )
            gamescope_pointer_relay_requested = bool(
                self.gamescope_pointer_relay_enabled
                and self.gamescope_pointer_interceptor is not None
                and inner_eis.ready
            )
            self._set_cursor_overlay(
                not self.suspended
                and pointer_needs_bridge
                and (
                    self.forwarding
                    or self.binding_pointer_forwarding
                    or self.remote_forwarding
                    or gamescope_pointer_relay_requested
                )
            )
            self._set_gamescope_pointer_intercepted(
                not self.suspended
                and pointer_needs_bridge
                and gamescope_pointer_relay_requested
                and (
                    self.cursor_overlay_active
                    or self.session.software_cursor_forced
                ),
                decode_gamescope_display(mouse_focus_display),
            )
        except Exception as error:
            self._handle_eis_loss(error)

    def _has_active_rustdesk_connection(self, now: float) -> bool:
        if now >= self.next_rustdesk_connection_check:
            interval = (
                RUSTDESK_ACTIVE_CONNECTION_CHECK_INTERVAL
                if self.rustdesk_video_connection_count > 0
                else RUSTDESK_CONNECTION_CHECK_INTERVAL
            )
            self.next_rustdesk_connection_check = (
                now + interval
            )
            count = self.rustdesk_connection_query(
                self.rustdesk_ipc_path
            )
            if count is not None:
                previous = self.rustdesk_video_connection_count
                self.rustdesk_video_connection_count = count
                interval = (
                    RUSTDESK_ACTIVE_CONNECTION_CHECK_INTERVAL
                    if count > 0
                    else RUSTDESK_CONNECTION_CHECK_INTERVAL
                )
                self.next_rustdesk_connection_check = now + interval
                self.rustdesk_connection_valid_until = (
                    now
                    + interval
                    + RUSTDESK_CONNECTION_STALE_GRACE
                )
                if count != previous:
                    LOGGER.info(
                        "RustDesk active video connections: %s",
                        count,
                    )
            elif now >= self.rustdesk_connection_valid_until:
                self.rustdesk_video_connection_count = 0
                self.next_rustdesk_connection_check = (
                    now + RUSTDESK_CONNECTION_CHECK_INTERVAL
                )
        return self.rustdesk_video_connection_count > 0

    def _set_forwarding(self, active: bool):
        if active == self.forwarding:
            return
        inner_eis = self.inner_eis
        try:
            if active:
                active = bool(
                    inner_eis is not None
                    and inner_eis.set_emulating(True)
                )
            update = self.translator.set_active(active)
            if inner_eis is not None:
                inner_eis.inject(update)
                if not active and not (
                    self.binding_pointer_forwarding
                    or self.remote_scroll_forwarding
                    or self.gamescope_pointer_forwarding
                ):
                    inner_eis.set_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
        if active != self.forwarding:
            self.next_input_frame = 0.0
            self.input_frame_interval = IDLE_INPUT_FRAME_INTERVAL
        if active == self.forwarding:
            return
        self.forwarding = active
        if active:
            LOGGER.info("Nested Desktop trackpad forwarding enabled")
        else:
            LOGGER.info("Nested Desktop trackpad forwarding disabled")

    def _set_binding_forwarding(self, active: bool):
        if active == self.binding_forwarding:
            return
        inner_eis = self.inner_eis
        try:
            if not active:
                self._set_binding_pointer_forwarding(False)
            if active:
                active = bool(inner_eis is not None)
                if (
                    active
                    and self.binding_translator.has_key_actions
                ):
                    active = bool(inner_eis.set_keyboard_emulating(True))
            update = self.binding_translator.set_active(active)
            if inner_eis is not None:
                self._inject_binding_update(update)
                if not active:
                    if self.binding_translator.has_key_actions:
                        inner_eis.set_keyboard_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
        if active != self.binding_forwarding:
            self.next_input_frame = 0.0
            self.input_frame_interval = IDLE_INPUT_FRAME_INTERVAL
        if active == self.binding_forwarding:
            return
        self.binding_forwarding = active
        if active:
            LOGGER.info("Nested Desktop configurable bindings enabled")
        else:
            LOGGER.info("Nested Desktop configurable bindings disabled")

    def _set_touch_forwarding(self, active: bool):
        if active == self.touch_forwarding:
            return
        if not active:
            self.touchscreen_inertia.reset()
        inner_eis = self.inner_eis
        try:
            if active:
                active = bool(
                    inner_eis is not None
                    and inner_eis.set_touch_emulating(True)
                )
            elif inner_eis is not None:
                inner_eis.set_touch_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
        if active == self.touch_forwarding:
            return
        self.touch_forwarding = active
        LOGGER.info(
            "Nested Desktop touchscreen forwarding %s",
            "enabled" if active else "disabled",
        )

    def _set_binding_pointer_forwarding(self, active: bool):
        active = bool(
            active
            and self.binding_forwarding
            and self.binding_translator.has_pointer_actions
        )
        if active == self.binding_pointer_forwarding:
            return
        inner_eis = self.inner_eis
        try:
            if active:
                active = bool(
                    inner_eis is not None
                    and inner_eis.set_emulating(True)
                )
            update = (
                self.binding_translator
                .set_pointer_actions_enabled(active)
            )
            if inner_eis is not None:
                inner_eis.inject(update)
                if (
                    not active
                    and not self.forwarding
                    and not self.remote_scroll_forwarding
                    and not self.gamescope_pointer_forwarding
                ):
                    inner_eis.set_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
        if active != self.binding_pointer_forwarding:
            self.next_input_frame = 0.0
        if active == self.binding_pointer_forwarding:
            return
        self.binding_pointer_forwarding = active
        LOGGER.info(
            "Nested Desktop mouse bindings %s",
            "enabled" if active else "disabled",
        )

    def _set_remote_forwarding(self, active: bool):
        if not active:
            self.rustdesk_scroll_inertia.reset()
            self._set_remote_button_forwarding(False)
            self._set_remote_relaying(False)
        if active == self.remote_forwarding:
            inner_eis = self.inner_eis
            if (
                active
                and inner_eis is not None
                and inner_eis.absolute_ready
                and inner_eis.absolute_emulating
                and inner_eis.ready
                and inner_eis.emulating
                and self.remote_scroll_forwarding
            ):
                return
            if not active and (
                inner_eis is None
                or (
                    not inner_eis.absolute_emulating
                    and not self.remote_scroll_forwarding
                )
            ):
                return
        inner_eis = self.inner_eis
        try:
            if active:
                bounds = (
                    inner_eis.absolute_bounds()
                    if inner_eis is not None
                    else None
                )
                active = bool(
                    inner_eis is not None
                    and bounds is not None
                    and inner_eis.set_absolute_emulating(True)
                )
                self.remote_scroll_forwarding = bool(
                    active
                    and inner_eis is not None
                    and inner_eis.set_emulating(True)
                )
                if active and bounds is not None:
                    inner_eis.inject_absolute(
                        self.rustdesk_translator.position(bounds)
                    )
            elif inner_eis is not None:
                inner_eis.set_absolute_emulating(False)
                self.remote_scroll_forwarding = False
                if not (
                    self.forwarding
                    or self.binding_pointer_forwarding
                    or self.gamescope_pointer_forwarding
                ):
                    inner_eis.set_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
            self.remote_scroll_forwarding = False
        self.remote_forwarding = active
        if not active:
            self._set_remote_relaying(False)
        if active:
            LOGGER.info("RustDesk Nested Desktop pointer bridge enabled")
        else:
            LOGGER.info("RustDesk Nested Desktop pointer bridge disabled")

    def _set_remote_button_forwarding(self, active: bool):
        active = bool(active and self.remote_forwarding)
        if active == self.remote_button_forwarding:
            return
        self.remote_button_forwarding = active
        LOGGER.info(
            "RustDesk Nested Desktop button bridge %s",
            "enabled" if active else "disabled",
        )

    def _set_remote_relaying(self, active: bool) -> bool:
        active = bool(active and self.remote_forwarding)
        relay_path = self.rustdesk_relay_path
        relay_socket = self.rustdesk_relay_socket
        if (
            active
            and self.remote_relaying
            and relay_socket is not None
        ):
            return True
        if not active:
            if (
                self.remote_relaying is False
                and relay_socket is None
            ):
                return False
            if relay_socket is not None:
                relay_socket.close()
            self.rustdesk_relay_socket = None
            self.rustdesk_relay_translator = RustDeskRelayTranslator()
            if relay_path is not None:
                try:
                    relay_path.unlink(missing_ok=True)
                except OSError as error:
                    LOGGER.warning(
                        "Unable to remove the RustDesk pointer relay %s: %s",
                        relay_path,
                        error,
                    )
            was_active = bool(self.remote_relaying)
            self.remote_relaying = False
            if was_active:
                LOGGER.info("RustDesk pointer relay disabled")
            return False
        if relay_path is None:
            self.remote_relaying = False
            return False

        relay: socket.socket | None = None
        try:
            relay_path.unlink(missing_ok=True)
            relay = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            relay.setblocking(False)
            relay.bind(str(relay_path))
            os.chmod(relay_path, 0o600)
        except OSError as error:
            if relay is not None:
                relay.close()
            try:
                relay_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.remote_relaying = False
            LOGGER.warning(
                "Unable to enable the RustDesk pointer relay %s: %s",
                relay_path,
                error,
            )
            return False
        self.rustdesk_relay_socket = relay
        self.rustdesk_relay_translator = RustDeskRelayTranslator()
        self.remote_relaying = True
        LOGGER.info("RustDesk pointer relay enabled")
        return True
