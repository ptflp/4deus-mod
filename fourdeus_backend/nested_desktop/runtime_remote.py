"""RustDesk and binding event ingestion for the runtime."""

from __future__ import annotations

import logging
import os
import time

from .constants import (
    JOYSTICK_EVENT_AXIS, JOYSTICK_EVENT_BUTTON, JOYSTICK_EVENT_SIZE,
    LINUX_EV_KEY, LINUX_EV_SYN, LINUX_INPUT_EVENT,
)
from .models import BindingUpdate, PointerUpdate
from .rustdesk import parse_joystick_events, parse_linux_input_events


LOGGER = logging.getLogger("4deus-nested-mouse")


class RuntimeRemoteInputMixin:
    def _inject_binding_update(self, update: BindingUpdate):
        inner_eis = self.inner_eis
        if inner_eis is not None:
            inner_eis.inject(update.pointer)
            self._apply_cursor_overlay(update.pointer)
            for key_code, pressed in update.key_events:
                inner_eis.inject_key(key_code, pressed)
        callback = self.action_callback
        if callback is not None:
            for action in update.actions:
                try:
                    callback(action)
                except Exception:
                    LOGGER.exception(
                        "Failed to dispatch Nested Desktop action %s",
                        action,
                    )

    def _read_rustdesk_events(self):
        fd = self.rustdesk_fd
        inner_eis = self.inner_eis
        if fd is None:
            return
        try:
            chunks = []
            while True:
                try:
                    chunk = os.read(fd, 4096)
                except BlockingIOError:
                    break
                if not chunk:
                    self._close_rustdesk_joystick()
                    return
                chunks.append(chunk)
            if not chunks:
                return
            self.rustdesk_buffer += b"".join(chunks)
            usable = len(self.rustdesk_buffer) - (
                len(self.rustdesk_buffer) % JOYSTICK_EVENT_SIZE
            )
            if not usable:
                return
            events = parse_joystick_events(self.rustdesk_buffer[:usable])
            self.rustdesk_buffer = self.rustdesk_buffer[usable:]
            if any(
                not event.initial
                and event.event_type in (
                    JOYSTICK_EVENT_AXIS,
                    JOYSTICK_EVENT_BUTTON,
                )
                for event in events
            ):
                self._handle_remote_input()
            forwarding = self.remote_forwarding and inner_eis is not None
            bounds = inner_eis.absolute_bounds() if forwarding else None
            if forwarding and bounds is None:
                self._set_remote_forwarding(False)
                forwarding = False
            if bounds is None:
                bounds = (0, 0, 1, 1)
            updates = self.rustdesk_translator.translate(events, bounds)
            if not forwarding or inner_eis is None:
                return
            for update in updates:
                if not self.remote_button_forwarding:
                    update = PointerUpdate(
                        absolute_x=update.absolute_x,
                        absolute_y=update.absolute_y,
                    )
                if not update.empty:
                    inner_eis.inject_absolute(update)
                    self._apply_cursor_overlay(update)
        except (OSError, ValueError) as error:
            LOGGER.warning("Lost the RustDesk pointer device: %s", error)
            self._close_rustdesk_joystick()
        except Exception as error:
            self._handle_eis_loss(error)

    def _read_rustdesk_keyboard_events(self):
        fd = self.rustdesk_keyboard_fd
        if fd is None:
            return
        try:
            chunks = []
            while True:
                try:
                    chunk = os.read(fd, 4096)
                except BlockingIOError:
                    break
                if not chunk:
                    self._close_rustdesk_keyboard()
                    return
                chunks.append(chunk)
            if not chunks:
                return
            self.rustdesk_keyboard_buffer += b"".join(chunks)
            usable = len(self.rustdesk_keyboard_buffer) - (
                len(self.rustdesk_keyboard_buffer)
                % LINUX_INPUT_EVENT.size
            )
            if not usable:
                return
            events = parse_linux_input_events(
                self.rustdesk_keyboard_buffer[:usable]
            )
            self.rustdesk_keyboard_buffer = (
                self.rustdesk_keyboard_buffer[usable:]
            )
            if any(
                event.event_type == LINUX_EV_KEY
                and event.value != 0
                for event in events
            ):
                self._handle_remote_input()
        except OSError as error:
            LOGGER.warning(
                "Lost the RustDesk keyboard device: %s",
                error,
            )
            self._close_rustdesk_keyboard()

    def _read_rustdesk_relay_events(self):
        relay = self.rustdesk_relay_socket
        inner_eis = self.inner_eis
        if relay is None:
            return
        try:
            forwarding = (
                bool(self.remote_relaying)
                and self.remote_forwarding
                and inner_eis is not None
            )
            bounds = inner_eis.absolute_bounds() if forwarding else None
            if forwarding and bounds is None:
                self._set_remote_forwarding(False)
                return
            if bounds is None:
                bounds = (0, 0, 1, 1)
            while True:
                try:
                    data = relay.recv(4096)
                except BlockingIOError:
                    break
                if not data:
                    continue
                events = parse_linux_input_events(data)
                if any(
                    event.event_type != LINUX_EV_SYN
                    for event in events
                ):
                    self._handle_remote_input()
                updates = self.rustdesk_relay_translator.translate(
                    events,
                    bounds,
                )
                if not forwarding or inner_eis is None:
                    continue
                for update in updates:
                    absolute_update = PointerUpdate(
                        absolute_x=update.absolute_x,
                        absolute_y=update.absolute_y,
                        left_button=update.left_button,
                        right_button=update.right_button,
                        middle_button=update.middle_button,
                    )
                    if not absolute_update.empty:
                        inner_eis.inject_absolute(absolute_update)
                        self._apply_cursor_overlay(absolute_update)
                    scroll_update = PointerUpdate(
                        scroll_x=update.scroll_x,
                        scroll_y=update.scroll_y,
                        scroll_discrete_x=update.scroll_discrete_x,
                        scroll_discrete_y=update.scroll_discrete_y,
                        scroll_stop_x=update.scroll_stop_x,
                        scroll_stop_y=update.scroll_stop_y,
                    )
                    if (
                        self.remote_scroll_forwarding
                        and not scroll_update.empty
                    ):
                        inner_eis.inject(scroll_update)
                        self.rustdesk_scroll_inertia.observe(
                            scroll_update,
                            time.monotonic(),
                        )
        except OSError as error:
            LOGGER.warning("Lost the RustDesk pointer relay: %s", error)
            self._set_remote_relaying(False)
        except Exception as error:
            self._handle_eis_loss(error)
