"""Nested Desktop input runtime lifecycle and coordination."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import select
import socket
import threading
import time
from typing import Callable, Mapping

from .bindings import (
    InputBindingTranslator, TrackpadTranslator, prioritize_focus_app,
)
from .constants import (
    ACTION_HIDE_KEYBOARD, DISCOVERY_INTERVAL, FOCUS_CHECK_INTERVAL,
    IDLE_INPUT_FRAME_INTERVAL, LEGACY_RUSTDESK_POINTER_SYNC_MARKER,
    RUSTDESK_FOCUS_REQUEST_COOLDOWN,
)
from .cursor import NestedDesktopCursorOverlay
from .discovery import remove_nested_wayland_alias
from .eis import EisConnection
from .models import NestedDesktopSession
from .runtime_focus import RuntimeFocusMixin
from .runtime_hid import RuntimeHidInputMixin
from .runtime_remote import RuntimeRemoteInputMixin
from .rustdesk import (
    RustDeskMouseTranslator, RustDeskRelayTranslator,
    RustDeskScrollInertia, query_rustdesk_video_connection_count,
)
from .x11 import X11Connection


LOGGER = logging.getLogger("4deus-nested-mouse")


class NestedDesktopMouseRuntime(
    RuntimeFocusMixin,
    RuntimeRemoteInputMixin,
    RuntimeHidInputMixin,
):
    def __init__(
        self,
        stop_event: threading.Event,
        proc_root: Path = Path("/proc"),
        sys_class_hidraw: Path = Path("/sys/class/hidraw"),
        dev_root: Path = Path("/dev"),
        sys_class_input: Path = Path("/sys/class/input"),
        input_dev_root: Path = Path("/dev/input"),
        mouse_enabled: bool = True,
        inertia_enabled: bool = True,
        bindings_enabled: bool = True,
        bindings: Mapping[str, object] | None = None,
        rustdesk_pointer_fix_enabled: bool = True,
        rustdesk_scroll_inertia_enabled: bool = False,
        rustdesk_focus_on_input_enabled: bool = False,
        action_callback: Callable[[str], None] | None = None,
        suspended: bool = False,
        control_fd: int | None = None,
        rustdesk_relay_path: Path | None = None,
        rustdesk_ipc_path: Path | None = None,
        rustdesk_connection_query: (
            Callable[[Path], int | None] | None
        ) = None,
        cursor_overlay_factory: (
            Callable[[NestedDesktopSession], object] | None
        ) = None,
    ):
        self.stop_event = stop_event
        self.proc_root = proc_root
        self.sys_class_hidraw = sys_class_hidraw
        self.dev_root = dev_root
        self.sys_class_input = sys_class_input
        self.input_dev_root = input_dev_root
        self.outer_x11: X11Connection | None = None
        self.inner_eis: EisConnection | None = None
        self.session: NestedDesktopSession | None = None
        self.hidraw_path: Path | None = None
        self.hidraw_fd: int | None = None
        self.rustdesk_path: Path | None = None
        self.rustdesk_fd: int | None = None
        self.rustdesk_buffer = b""
        self.rustdesk_translator = RustDeskMouseTranslator()
        self.rustdesk_keyboard_path: Path | None = None
        self.rustdesk_keyboard_fd: int | None = None
        self.rustdesk_keyboard_buffer = b""
        self.rustdesk_pointer_fix_enabled = (
            rustdesk_pointer_fix_enabled
        )
        self.rustdesk_relay_path = rustdesk_relay_path
        self.rustdesk_relay_socket: socket.socket | None = None
        self.rustdesk_relay_translator = RustDeskRelayTranslator()
        self.rustdesk_scroll_inertia = RustDeskScrollInertia(
            enabled=rustdesk_scroll_inertia_enabled,
        )
        self.rustdesk_focus_on_input_enabled = (
            rustdesk_focus_on_input_enabled
        )
        self.rustdesk_ipc_path = rustdesk_ipc_path or Path(
            f"/tmp/RustDesk-{os.geteuid()}/ipc"
        )
        self.rustdesk_connection_query = (
            rustdesk_connection_query
            or query_rustdesk_video_connection_count
        )
        self.rustdesk_video_connection_count = 0
        self.rustdesk_connection_valid_until = 0.0
        self.next_rustdesk_connection_check = 0.0
        self.wayland_alias: Path | None = None
        self.cursor_overlay_factory = (
            cursor_overlay_factory or NestedDesktopCursorOverlay
        )
        self.cursor_overlay = None
        self.cursor_overlay_active = False
        self.cursor_overlay_failed_session_pid: int | None = None
        self.translator = TrackpadTranslator(
            inertia_enabled=inertia_enabled,
        )
        self.mouse_enabled = mouse_enabled
        self.bindings_enabled = bindings_enabled
        self.binding_translator = InputBindingTranslator(
            bindings,
            pointer_actions_enabled=False,
        )
        self.action_callback = action_callback
        self.suspended = suspended
        self.remote_keyboard_dismiss_requested = False
        self.nested_desktop_focused = False
        self.next_rustdesk_focus_request = 0.0
        self.control_fd = control_fd
        self.control_buffer = b""
        self.forwarding = False
        self.remote_forwarding = False
        self.remote_scroll_forwarding = False
        self.remote_button_forwarding = False
        self.remote_relaying: bool | None = None
        self.binding_forwarding = False
        self.binding_pointer_forwarding = False
        self.next_input_frame = 0.0
        self.input_frame_interval = IDLE_INPUT_FRAME_INTERVAL
        self.focus_snapshot: tuple[
            tuple[int, ...],
            tuple[int, ...],
            tuple[int, ...],
            tuple[int, ...],
        ] | None = None
        self.next_focus_snapshot_refresh = 0.0

    def run(self):
        next_discovery = 0.0
        next_focus_check = 0.0
        try:
            self._set_remote_relaying(False)
            try:
                LEGACY_RUSTDESK_POINTER_SYNC_MARKER.unlink(
                    missing_ok=True
                )
            except OSError:
                pass
            while not self.stop_event.is_set():
                now = time.monotonic()
                if now >= next_discovery:
                    self._discover()
                    next_discovery = now + DISCOVERY_INTERVAL
                if now >= next_focus_check:
                    self._refresh_forwarding()
                    next_focus_check = now + FOCUS_CHECK_INTERVAL
                next_deadline = min(next_discovery, next_focus_check)
                timeout = max(
                    0.0,
                    min(
                        FOCUS_CHECK_INTERVAL,
                        next_deadline - time.monotonic(),
                    ),
                )
                self._read_reports(timeout)
        finally:
            self._set_cursor_overlay(False)
            self._close_cursor_overlay()
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
            self._set_remote_forwarding(False)
            self._set_remote_relaying(False)
            self._close_hidraw()
            self._close_rustdesk_joystick()
            self._close_rustdesk_keyboard()
            remove_nested_wayland_alias(self.session, self.wayland_alias)
            self.wayland_alias = None
            if self.inner_eis is not None:
                self.inner_eis.close()
            if self.outer_x11 is not None:
                self.outer_x11.close()

    def set_suspended(self, suspended: bool):
        if suspended == self.suspended:
            return
        self.suspended = suspended
        self.remote_keyboard_dismiss_requested = False
        if suspended:
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
        self.next_input_frame = 0.0
        self.input_frame_interval = IDLE_INPUT_FRAME_INTERVAL
        LOGGER.info(
            "Nested Desktop input bridge %s for the Steam keyboard",
            "paused" if suspended else "resumed",
        )

    def _request_keyboard_dismiss_for_remote_input(self):
        if (
            not self.suspended
            or self.remote_keyboard_dismiss_requested
            or self.action_callback is None
            or not self._has_active_rustdesk_connection(time.monotonic())
        ):
            return
        self.remote_keyboard_dismiss_requested = True
        try:
            self.action_callback(ACTION_HIDE_KEYBOARD)
        except Exception:
            self.remote_keyboard_dismiss_requested = False
            LOGGER.exception(
                "Failed to request Steam keyboard dismissal "
                "for RustDesk input"
            )

    def _request_focus_for_remote_input(self):
        session = self.session
        outer_x11 = self.outer_x11
        if (
            not self.rustdesk_focus_on_input_enabled
            or self.nested_desktop_focused
            or session is None
            or outer_x11 is None
        ):
            return
        now = time.monotonic()
        if (
            now < self.next_rustdesk_focus_request
            or not self._has_active_rustdesk_connection(now)
        ):
            return
        self.next_rustdesk_focus_request = (
            now + RUSTDESK_FOCUS_REQUEST_COOLDOWN
        )
        try:
            focused_app = outer_x11.cardinals(
                "GAMESCOPE_FOCUSED_APP"
            )
            focused_gfx_app = outer_x11.cardinals(
                "GAMESCOPE_FOCUSED_APP_GFX"
            )
            if (
                focused_app
                and focused_app[0] == session.app_id
                and focused_gfx_app
                and focused_gfx_app[0] == session.app_id
            ):
                self.nested_desktop_focused = True
                return
            current = outer_x11.cardinals(
                "GAMESCOPECTRL_BASELAYER_APPID"
            )
            outer_x11.set_cardinals(
                "GAMESCOPECTRL_BASELAYER_APPID",
                prioritize_focus_app(session.app_id, current),
            )
            self.focus_snapshot = None
            LOGGER.info(
                "Requested Nested Desktop focus for RustDesk input"
            )
        except Exception:
            LOGGER.exception(
                "Failed to focus Nested Desktop for RustDesk input"
            )

    def _handle_remote_input(self):
        self._request_focus_for_remote_input()
        self._request_keyboard_dismiss_for_remote_input()

    def _read_control_commands(self):
        control_fd = self.control_fd
        if control_fd is None:
            return
        try:
            chunk = os.read(control_fd, 4096)
            if not chunk:
                self.control_fd = None
                self.control_buffer = b""
                return
            self.control_buffer += chunk
            lines = self.control_buffer.split(b"\n")
            self.control_buffer = lines.pop()
            for line in lines:
                command = line.strip()
                if command == b"suspend":
                    self.set_suspended(True)
                elif command == b"resume":
                    self.set_suspended(False)
                elif command:
                    LOGGER.warning(
                        "Ignoring unknown bridge control command %r",
                        command,
                    )
        except (OSError, ValueError) as error:
            LOGGER.warning(
                "Lost the Nested Desktop bridge control channel: %s",
                error,
            )
            self.control_fd = None
            self.control_buffer = b""

    def _read_auxiliary_events(
        self,
        timeout: float,
        *,
        include_remote: bool = True,
    ):
        now = time.monotonic()
        if include_remote and self.remote_scroll_forwarding:
            timeout = self.rustdesk_scroll_inertia.timeout(now, timeout)
        control_fd = self.control_fd
        rustdesk_fd = self.rustdesk_fd if include_remote else None
        rustdesk_keyboard_fd = (
            self.rustdesk_keyboard_fd if include_remote else None
        )
        relay = (
            self.rustdesk_relay_socket
            if include_remote
            else None
        )
        descriptors = [
            descriptor
            for descriptor in (
                control_fd,
                rustdesk_fd,
                rustdesk_keyboard_fd,
                relay,
            )
            if descriptor is not None
        ]
        if not descriptors:
            self.stop_event.wait(max(0.0, timeout))
            if include_remote:
                self._tick_rustdesk_scroll_inertia()
            return
        try:
            readable, _, _ = select.select(
                descriptors,
                [],
                [],
                max(0.0, timeout),
            )
        except InterruptedError:
            return
        except (OSError, ValueError) as error:
            LOGGER.warning(
                "Lost a Nested Desktop auxiliary input: %s",
                error,
            )
            if control_fd is not None:
                self.control_fd = None
                self.control_buffer = b""
            if include_remote:
                self._close_rustdesk_joystick()
                self._close_rustdesk_keyboard()
                self._set_remote_relaying(False)
            return

        if control_fd is not None and control_fd in readable:
            self._read_control_commands()
        if (
            rustdesk_fd is not None
            and rustdesk_fd == self.rustdesk_fd
            and rustdesk_fd in readable
        ):
            self._read_rustdesk_events()
        if (
            rustdesk_keyboard_fd is not None
            and rustdesk_keyboard_fd == self.rustdesk_keyboard_fd
            and rustdesk_keyboard_fd in readable
        ):
            self._read_rustdesk_keyboard_events()
        if (
            relay is not None
            and relay is self.rustdesk_relay_socket
            and relay in readable
        ):
            self._read_rustdesk_relay_events()
        if include_remote:
            self._tick_rustdesk_scroll_inertia()

    def _tick_rustdesk_scroll_inertia(self):
        inner_eis = self.inner_eis
        if (
            not self.remote_scroll_forwarding
            or inner_eis is None
        ):
            self.rustdesk_scroll_inertia.reset()
            return
        update = self.rustdesk_scroll_inertia.tick(time.monotonic())
        if update.empty:
            return
        try:
            inner_eis.inject(update)
        except Exception as error:
            self._handle_eis_loss(error)

    def _handle_eis_loss(self, error: Exception):
        LOGGER.warning("Lost the Nested Desktop EIS input: %s", error)
        inner_eis = self.inner_eis
        if inner_eis is not None:
            inner_eis.close()
        self.inner_eis = None
        self.translator.set_active(False)
        self.binding_translator.set_active(False)
        self.forwarding = False
        self.remote_forwarding = False
        self.remote_scroll_forwarding = False
        self.remote_button_forwarding = False
        self.rustdesk_scroll_inertia.reset()
        self._set_remote_relaying(False)
        self.binding_forwarding = False
        self.binding_pointer_forwarding = False
        self._set_cursor_overlay(False)
        self.next_input_frame = 0.0
        self.input_frame_interval = IDLE_INPUT_FRAME_INTERVAL
