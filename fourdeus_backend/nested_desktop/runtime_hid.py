"""Steam Deck HID report loop and descriptor lifecycle."""

from __future__ import annotations

import logging
import os
import time

from .bindings import parse_trackpad_report
from .constants import (
    IDLE_INPUT_FRAME_INTERVAL, INPUT_FRAME_INTERVAL, REPORT_HEADER,
    RIGHT_STICK_DEADZONE,
)
from .models import BindingUpdate, PointerUpdate
from .rustdesk import RustDeskMouseTranslator


LOGGER = logging.getLogger("4deus-nested-mouse")


class RuntimeHidInputMixin:
    def _read_reports(self, timeout: float):
        if self.hidraw_fd is None:
            self._read_auxiliary_events(timeout)
            return
        if not self.forwarding and not self.binding_forwarding:
            self._read_auxiliary_events(timeout)
            return

        now = time.monotonic()
        if now < self.next_input_frame:
            self._read_auxiliary_events(
                min(timeout, self.next_input_frame - now),
                include_remote=False,
            )
            return
        self._read_auxiliary_events(0)
        if not self.forwarding and not self.binding_forwarding:
            return
        frame_started = time.monotonic()
        self.next_input_frame = (
            frame_started + self.input_frame_interval
        )

        try:
            latest_report: bytes | None = None
            while True:
                try:
                    report = os.read(self.hidraw_fd, 64)
                except BlockingIOError:
                    break
                if not report:
                    self._close_hidraw()
                    return
                if len(report) >= 24 and report.startswith(REPORT_HEADER):
                    latest_report = report
            if latest_report is None:
                return
            state = parse_trackpad_report(latest_report)
            if state is None:
                return
            binding_update = (
                self.binding_translator.translate(state)
                if self.binding_forwarding
                else BindingUpdate()
            )
            input_active = bool(
                state.left_touched
                or state.right_touched
                or abs(state.right_stick_x) > RIGHT_STICK_DEADZONE
                or abs(state.right_stick_y) > RIGHT_STICK_DEADZONE
                or self.translator.needs_idle_tick
                or not binding_update.empty
            )
            next_interval = (
                INPUT_FRAME_INTERVAL
                if input_active
                else IDLE_INPUT_FRAME_INTERVAL
            )
            if next_interval < self.input_frame_interval:
                self.next_input_frame = min(
                    self.next_input_frame,
                    frame_started + next_interval,
                )
            self.input_frame_interval = next_interval
            if not input_active:
                return
            update = (
                self.translator.translate(state)
                if self.forwarding
                else PointerUpdate()
            )
            if (
                (
                    self.forwarding
                    and (
                        state.left_touched
                        or state.right_touched
                        or not update.empty
                    )
                )
                or (
                    self.binding_pointer_forwarding
                    and not binding_update.pointer.empty
                )
            ):
                self._mark_gamescope_pointer_hid_activity(frame_started)
            if self.inner_eis is not None:
                try:
                    self.inner_eis.inject(update)
                    self._apply_cursor_overlay(update)
                    self._inject_binding_update(binding_update)
                except Exception as error:
                    self._handle_eis_loss(error)
                    return
        except (OSError, ValueError) as error:
            LOGGER.warning("Lost the Steam Deck trackpad device: %s", error)
            self._close_hidraw()

    def _close_hidraw(self):
        if self.hidraw_fd is not None:
            try:
                os.close(self.hidraw_fd)
            except OSError:
                pass
        self.hidraw_fd = None
        self.hidraw_path = None

    def _close_rustdesk_joystick(self):
        self._set_remote_forwarding(False)
        if self.rustdesk_fd is not None:
            try:
                os.close(self.rustdesk_fd)
            except OSError:
                pass
        self.rustdesk_fd = None
        self.rustdesk_path = None
        self.rustdesk_buffer = b""
        self.rustdesk_translator = RustDeskMouseTranslator()
        self.rustdesk_video_connection_count = 0
        self.rustdesk_connection_valid_until = 0.0
        self.next_rustdesk_connection_check = 0.0

    def _close_rustdesk_keyboard(self):
        if self.rustdesk_keyboard_fd is not None:
            try:
                os.close(self.rustdesk_keyboard_fd)
            except OSError:
                pass
        self.rustdesk_keyboard_fd = None
        self.rustdesk_keyboard_path = None
        self.rustdesk_keyboard_buffer = b""
