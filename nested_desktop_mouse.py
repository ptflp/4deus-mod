from __future__ import annotations

import argparse
import ctypes
import ctypes.util
from dataclasses import dataclass
import json
import logging
import math
import os
from pathlib import Path
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time
from typing import Callable, Mapping, Sequence


LOGGER = logging.getLogger("4deus-nested-mouse")

STEAM_DECK_HID_ID = "0003:000028DE:00001205"
STEAM_UI_APP_ID = 769
REPORT_HEADER = b"\x01\x00\x09"
RIGHT_TRIGGER = 0x00000001
LEFT_TRIGGER = 0x00000002
BACK_BUTTON = 0x00000020
LEFT_PAD_PRESSED = 0x00020000
RIGHT_PAD_PRESSED = 0x00040000
LEFT_PAD_TOUCHED = 0x00080000
RIGHT_PAD_TOUCHED = 0x00100000
LEFT_PAD_X_OFFSET = 16
LEFT_PAD_Y_OFFSET = 18
RIGHT_PAD_X_OFFSET = 20
RIGHT_PAD_Y_OFFSET = 22
RIGHT_PAD_PRESSURE_OFFSET = 58
RIGHT_PAD_PRESS_THRESHOLD = 2_000
RIGHT_PAD_RELEASE_THRESHOLD = 1_000
MAX_TRACKPAD_DELTA = 12_000
MOUSE_SCALE = 0.008
SCROLL_SCALE = 0.007
SCROLL_START_DEADZONE = 320
SCROLL_EMIT_THRESHOLD = 48
POINTER_VELOCITY_BLEND = 0.55
POINTER_INERTIA_DECAY = 0.90
POINTER_INERTIA_START = 4.0
POINTER_INERTIA_STOP = 0.15
SCROLL_VELOCITY_BLEND = 0.55
SCROLL_INERTIA_DECAY = 0.90
SCROLL_INERTIA_START = 1.2
SCROLL_INERTIA_STOP = 0.01
RIGHT_STICK_DEADZONE = 8_000
RIGHT_STICK_MAX_SPEED = 18.0
INPUT_FRAME_INTERVAL = 1 / 60
FOCUS_CHECK_INTERVAL = 0.25
DISCOVERY_INTERVAL = 5.0
KEYBOARD_DEVICE_GRACE = 0.5
RUSTDESK_MOUSE_NAME = "mouce-library-fake-mouse"
JOYSTICK_EVENT_SIZE = 8
JOYSTICK_EVENT_BUTTON = 0x01
JOYSTICK_EVENT_AXIS = 0x02
JOYSTICK_EVENT_INIT = 0x80
JOYSTICK_AXIS_MIN = -32_767
JOYSTICK_AXIS_SPAN = 65_534

EI_DEVICE_CAP_POINTER = 1 << 0
EI_DEVICE_CAP_POINTER_ABSOLUTE = 1 << 1
EI_DEVICE_CAP_KEYBOARD = 1 << 2
EI_DEVICE_CAP_SCROLL = 1 << 4
EI_DEVICE_CAP_BUTTON = 1 << 5
EI_EVENT_DISCONNECT = 2
EI_EVENT_SEAT_ADDED = 3
EI_EVENT_DEVICE_ADDED = 5
EI_EVENT_DEVICE_REMOVED = 6
EI_EVENT_DEVICE_PAUSED = 7
EI_EVENT_DEVICE_RESUMED = 8
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112
KEYBOARD_PORTAL_CAPABILITY = 1
POINTER_PORTAL_CAPABILITY = 2
LEFT_STICK_PRESS_THRESHOLD = 16_000
LEFT_STICK_RELEASE_THRESHOLD = 12_000

ACTION_NONE = "none"
ACTION_SHOW_KEYBOARD = "SHOW_KEYBOARD"
ACTION_MOUSE_LEFT = "MOUSE_LEFT"
ACTION_MOUSE_RIGHT = "MOUSE_RIGHT"
ACTION_MOUSE_MIDDLE = "MOUSE_MIDDLE"

EIS_KEY_CODES = {
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
    "KEY_LEFTCTRL": 29,
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
    "KEY_LEFTALT": 56,
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
}

NESTED_DESKTOP_BINDING_SOURCES = (
    "a",
    "b",
    "x",
    "y",
    "dpadUp",
    "dpadRight",
    "dpadLeft",
    "dpadDown",
    "leftStickUp",
    "leftStickRight",
    "leftStickLeft",
    "leftStickDown",
    "view",
    "menu",
    "l1",
    "r1",
    "l2",
    "r2",
    "l3",
    "r3",
    "l4",
    "r4",
    "l5",
    "r5",
    "leftPadClick",
    "rightPadClick",
)

DEFAULT_NESTED_DESKTOP_BINDINGS = {
    "a": "KEY_ENTER",
    "b": "KEY_ESC",
    "x": ACTION_SHOW_KEYBOARD,
    "y": "KEY_SPACE",
    "dpadUp": "KEY_UP",
    "dpadRight": "KEY_RIGHT",
    "dpadLeft": "KEY_LEFT",
    "dpadDown": "KEY_DOWN",
    "leftStickUp": "KEY_UP",
    "leftStickRight": "KEY_RIGHT",
    "leftStickLeft": "KEY_LEFT",
    "leftStickDown": "KEY_DOWN",
    "view": "KEY_ESC",
    "menu": "KEY_TAB",
    "l1": "KEY_LEFTCTRL",
    "r1": "KEY_LEFTALT",
    "l2": ACTION_MOUSE_RIGHT,
    "r2": ACTION_MOUSE_LEFT,
    "l3": ACTION_NONE,
    "r3": ACTION_MOUSE_LEFT,
    "l4": "KEY_LEFTSHIFT",
    "r4": "KEY_PAGEUP",
    "l5": "KEY_LEFTMETA",
    "r5": "KEY_PAGEDOWN",
    "leftPadClick": ACTION_MOUSE_MIDDLE,
    "rightPadClick": ACTION_MOUSE_LEFT,
}

NESTED_DESKTOP_BINDING_ACTIONS = frozenset(
    (
        ACTION_NONE,
        ACTION_SHOW_KEYBOARD,
        ACTION_MOUSE_LEFT,
        ACTION_MOUSE_RIGHT,
        ACTION_MOUSE_MIDDLE,
        *EIS_KEY_CODES,
    )
)

BUTTON_SOURCE_MASKS = {
    "r2": 1 << 0,
    "l2": 1 << 1,
    "r1": 1 << 2,
    "l1": 1 << 3,
    "y": 1 << 4,
    "b": 1 << 5,
    "x": 1 << 6,
    "a": 1 << 7,
    "dpadUp": 1 << 8,
    "dpadRight": 1 << 9,
    "dpadLeft": 1 << 10,
    "dpadDown": 1 << 11,
    "view": 1 << 12,
    "menu": 1 << 14,
    "l5": 1 << 15,
    "r5": 1 << 16,
    "leftPadClick": 1 << 17,
    "rightPadClick": 1 << 18,
    "l3": 1 << 22,
    "r3": 1 << 26,
    "l4": 1 << 41,
    "r4": 1 << 42,
}


@dataclass(frozen=True)
class NestedDesktopSession:
    pid: int
    app_id: int
    display: str
    xauthority: Path
    dbus_address: str
    wayland_display: str = "wayland-0"


@dataclass(frozen=True)
class TrackpadState:
    back_pressed: bool
    left_touched: bool
    right_touched: bool
    right_pressed: bool
    right_pressure: int
    left_trigger: bool
    right_trigger: bool
    left_x: int
    left_y: int
    right_x: int
    right_y: int
    buttons: int = 0
    left_stick_x: int = 0
    left_stick_y: int = 0
    right_stick_x: int = 0
    right_stick_y: int = 0


@dataclass(frozen=True)
class PointerUpdate:
    dx: int = 0
    dy: int = 0
    absolute_x: float | None = None
    absolute_y: float | None = None
    left_button: bool | None = None
    right_button: bool | None = None
    middle_button: bool | None = None
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    scroll_stop_x: bool = False
    scroll_stop_y: bool = False

    @property
    def empty(self) -> bool:
        return (
            self.dx == 0
            and self.dy == 0
            and self.absolute_x is None
            and self.absolute_y is None
            and self.left_button is None
            and self.right_button is None
            and self.middle_button is None
            and self.scroll_x == 0
            and self.scroll_y == 0
            and not self.scroll_stop_x
            and not self.scroll_stop_y
        )


@dataclass(frozen=True)
class JoystickEvent:
    timestamp: int
    value: int
    event_type: int
    number: int
    initial: bool = False


def parse_joystick_events(data: bytes) -> tuple[JoystickEvent, ...]:
    events = []
    usable = len(data) - (len(data) % JOYSTICK_EVENT_SIZE)
    for offset in range(0, usable, JOYSTICK_EVENT_SIZE):
        timestamp, value, raw_type, number = struct.unpack_from(
            "<IhBB",
            data,
            offset,
        )
        events.append(
            JoystickEvent(
                timestamp=timestamp,
                value=value,
                event_type=raw_type & ~JOYSTICK_EVENT_INIT,
                number=number,
                initial=bool(raw_type & JOYSTICK_EVENT_INIT),
            )
        )
    return tuple(events)


class RustDeskMouseTranslator:
    def __init__(self):
        self.axes = [0, 0]
        self.axis_known = [False, False]

    @staticmethod
    def _coordinate(value: int, start: int, size: int) -> float:
        normalized = (
            max(JOYSTICK_AXIS_MIN, min(JOYSTICK_AXIS_MIN + JOYSTICK_AXIS_SPAN, value))
            - JOYSTICK_AXIS_MIN
        ) / JOYSTICK_AXIS_SPAN
        return float(start) + normalized * max(0, size - 1)

    def translate(
        self,
        events: Sequence[JoystickEvent],
        bounds: tuple[int, int, int, int],
    ) -> tuple[PointerUpdate, ...]:
        updates: list[PointerUpdate] = []
        frame_time: int | None = None
        axis_changed = False
        buttons: dict[str, bool] = {}

        def flush():
            nonlocal axis_changed, buttons
            if not axis_changed and not buttons:
                return
            x, y, width, height = bounds
            absolute = (
                axis_changed
                and self.axis_known[0]
                and self.axis_known[1]
            )
            updates.append(
                PointerUpdate(
                    absolute_x=(
                        self._coordinate(self.axes[0], x, width)
                        if absolute
                        else None
                    ),
                    absolute_y=(
                        self._coordinate(self.axes[1], y, height)
                        if absolute
                        else None
                    ),
                    left_button=buttons.get("left"),
                    right_button=buttons.get("right"),
                    middle_button=buttons.get("middle"),
                )
            )
            axis_changed = False
            buttons = {}

        for event in events:
            if event.initial:
                if (
                    event.event_type == JOYSTICK_EVENT_AXIS
                    and event.number < 2
                ):
                    self.axes[event.number] = event.value
                    self.axis_known[event.number] = True
                continue
            if frame_time is None:
                frame_time = event.timestamp
            elif event.timestamp != frame_time:
                flush()
                frame_time = event.timestamp
            if (
                event.event_type == JOYSTICK_EVENT_AXIS
                and event.number < 2
            ):
                self.axes[event.number] = event.value
                self.axis_known[event.number] = True
                axis_changed = True
            elif (
                event.event_type == JOYSTICK_EVENT_BUTTON
                and event.number < 3
            ):
                buttons[("left", "right", "middle")[event.number]] = bool(
                    event.value
                )
        flush()
        return tuple(updates)


def parse_trackpad_report(report: bytes) -> TrackpadState | None:
    if (
        len(report) < RIGHT_PAD_PRESSURE_OFFSET + 2
        or report[:3] != REPORT_HEADER
    ):
        return None
    buttons = int.from_bytes(report[8:16], "little")
    controls = buttons & 0xFFFFFFFF
    left_x, left_y = struct.unpack_from("<hh", report, LEFT_PAD_X_OFFSET)
    right_x, right_y = struct.unpack_from("<hh", report, RIGHT_PAD_X_OFFSET)
    left_stick_x, left_stick_y = struct.unpack_from("<hh", report, 48)
    right_stick_x, right_stick_y = struct.unpack_from("<hh", report, 52)
    right_pressure = struct.unpack_from(
        "<H",
        report,
        RIGHT_PAD_PRESSURE_OFFSET,
    )[0]
    return TrackpadState(
        back_pressed=bool(controls & BACK_BUTTON),
        left_touched=bool(controls & LEFT_PAD_TOUCHED),
        right_touched=bool(controls & RIGHT_PAD_TOUCHED),
        right_pressed=bool(controls & RIGHT_PAD_PRESSED),
        right_pressure=right_pressure,
        left_trigger=bool(controls & LEFT_TRIGGER),
        right_trigger=bool(controls & RIGHT_TRIGGER),
        left_x=left_x,
        left_y=left_y,
        right_x=right_x,
        right_y=right_y,
        buttons=buttons,
        left_stick_x=left_stick_x,
        left_stick_y=left_stick_y,
        right_stick_x=right_stick_x,
        right_stick_y=right_stick_y,
    )


def decode_gamescope_display(values: Sequence[int]) -> str:
    raw = bytearray()
    for value in values:
        raw.extend(int(value).to_bytes(4, sys.byteorder, signed=False))
    return bytes(raw).split(b"\0", 1)[0].decode("ascii", errors="ignore")


def should_forward_pointer(
    session_app_id: int,
    focused_app: Sequence[int],
    focused_gfx_app: Sequence[int],
    focusable_apps: Sequence[int],
    mouse_focus_display: Sequence[int],
) -> bool:
    if not should_forward_back_button(
        session_app_id,
        focused_app,
        focused_gfx_app,
        mouse_focus_display,
    ):
        return False
    ignored = {0, STEAM_UI_APP_ID, session_app_id}
    return any(app_id not in ignored for app_id in focusable_apps)


def should_forward_back_button(
    session_app_id: int,
    focused_app: Sequence[int],
    focused_gfx_app: Sequence[int],
    mouse_focus_display: Sequence[int],
) -> bool:
    if not focused_app or focused_app[0] != session_app_id:
        return False
    if not focused_gfx_app or focused_gfx_app[0] != session_app_id:
        return False
    if decode_gamescope_display(mouse_focus_display) in ("", ":0"):
        return False
    return True


@dataclass(frozen=True)
class BindingUpdate:
    key_events: tuple[tuple[int, bool], ...] = ()
    pointer: PointerUpdate = PointerUpdate()
    actions: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.key_events and self.pointer.empty and not self.actions


def normalize_nested_desktop_bindings(
    bindings: Mapping[str, object] | None,
) -> dict[str, str]:
    normalized = dict(DEFAULT_NESTED_DESKTOP_BINDINGS)
    if not isinstance(bindings, Mapping):
        return normalized
    for source in NESTED_DESKTOP_BINDING_SOURCES:
        action = bindings.get(source)
        if isinstance(action, str) and action in NESTED_DESKTOP_BINDING_ACTIONS:
            normalized[source] = action
    return normalized


class InputBindingTranslator:
    def __init__(
        self,
        bindings: Mapping[str, object] | None = None,
    ):
        self.bindings = normalize_nested_desktop_bindings(bindings)
        self.active = False
        self.last_sources = {
            source: False for source in NESTED_DESKTOP_BINDING_SOURCES
        }
        self.injected_keys: set[int] = set()
        self.injected_mouse: set[str] = set()
        self.right_pressure_pressed = False
        self.needs_sync = False

    @property
    def has_key_actions(self) -> bool:
        return any(action in EIS_KEY_CODES for action in self.bindings.values())

    @property
    def has_pointer_actions(self) -> bool:
        return any(
            action in (
                ACTION_MOUSE_LEFT,
                ACTION_MOUSE_RIGHT,
                ACTION_MOUSE_MIDDLE,
            )
            for action in self.bindings.values()
        )

    @property
    def has_actions(self) -> bool:
        return any(
            action != ACTION_NONE for action in self.bindings.values()
        )

    def set_active(self, active: bool) -> BindingUpdate:
        if active == self.active:
            return BindingUpdate()
        self.active = active
        self.needs_sync = active
        if active:
            return BindingUpdate()
        key_events = tuple(
            (key_code, False) for key_code in sorted(self.injected_keys)
        )
        pointer = self._mouse_update(set())
        self.injected_keys.clear()
        self.injected_mouse.clear()
        self.right_pressure_pressed = False
        self.last_sources = {
            source: False for source in NESTED_DESKTOP_BINDING_SOURCES
        }
        return BindingUpdate(key_events=key_events, pointer=pointer)

    def _stick_pressed(
        self,
        value: int,
        positive: bool,
        was_pressed: bool,
    ) -> bool:
        threshold = (
            LEFT_STICK_RELEASE_THRESHOLD
            if was_pressed
            else LEFT_STICK_PRESS_THRESHOLD
        )
        return value >= threshold if positive else value <= -threshold

    def _source_states(self, state: TrackpadState) -> dict[str, bool]:
        states = {
            source: bool(state.buttons & mask)
            for source, mask in BUTTON_SOURCE_MASKS.items()
        }
        if (
            not state.right_touched
            or state.right_pressure <= RIGHT_PAD_RELEASE_THRESHOLD
        ):
            self.right_pressure_pressed = False
        elif state.right_pressure >= RIGHT_PAD_PRESS_THRESHOLD:
            self.right_pressure_pressed = True
        states["rightPadClick"] = bool(
            states["rightPadClick"] or self.right_pressure_pressed
        )
        stick_values = {
            "leftStickUp": (state.left_stick_y, True),
            "leftStickRight": (state.left_stick_x, True),
            "leftStickLeft": (state.left_stick_x, False),
            "leftStickDown": (state.left_stick_y, False),
        }
        for source, (value, positive) in stick_values.items():
            states[source] = self._stick_pressed(
                value,
                positive,
                self.last_sources[source],
            )
        return {
            source: states.get(source, False)
            for source in NESTED_DESKTOP_BINDING_SOURCES
        }

    def _mouse_update(self, desired: set[str]) -> PointerUpdate:
        values: dict[str, bool | None] = {
            ACTION_MOUSE_LEFT: None,
            ACTION_MOUSE_RIGHT: None,
            ACTION_MOUSE_MIDDLE: None,
        }
        for action in values:
            was_pressed = action in self.injected_mouse
            is_pressed = action in desired
            if was_pressed != is_pressed:
                values[action] = is_pressed
        return PointerUpdate(
            left_button=values[ACTION_MOUSE_LEFT],
            right_button=values[ACTION_MOUSE_RIGHT],
            middle_button=values[ACTION_MOUSE_MIDDLE],
        )

    def translate(self, state: TrackpadState) -> BindingUpdate:
        sources = self._source_states(state)
        if not self.active:
            self.last_sources = sources
            return BindingUpdate()
        if self.needs_sync:
            self.needs_sync = False
            self.last_sources = sources
            return BindingUpdate()

        desired_keys = {
            EIS_KEY_CODES[action]
            for source, pressed in sources.items()
            if pressed
            for action in (self.bindings[source],)
            if action in EIS_KEY_CODES
        }
        desired_mouse = {
            action
            for source, pressed in sources.items()
            if pressed
            for action in (self.bindings[source],)
            if action in (
                ACTION_MOUSE_LEFT,
                ACTION_MOUSE_RIGHT,
                ACTION_MOUSE_MIDDLE,
            )
        }
        key_events = tuple(
            (key_code, False)
            for key_code in sorted(self.injected_keys - desired_keys)
        ) + tuple(
            (key_code, True)
            for key_code in sorted(desired_keys - self.injected_keys)
        )
        actions = tuple(
            ACTION_SHOW_KEYBOARD
            for source, pressed in sources.items()
            if (
                pressed
                and not self.last_sources[source]
                and self.bindings[source] == ACTION_SHOW_KEYBOARD
            )
        )
        pointer = self._mouse_update(desired_mouse)
        self.last_sources = sources
        self.injected_keys = desired_keys
        self.injected_mouse = desired_mouse
        return BindingUpdate(
            key_events=key_events,
            pointer=pointer,
            actions=actions,
        )


class TrackpadTranslator:
    def __init__(
        self,
        scale: float = MOUSE_SCALE,
        scroll_scale: float = SCROLL_SCALE,
        scroll_start_deadzone: int = SCROLL_START_DEADZONE,
        scroll_emit_threshold: int = SCROLL_EMIT_THRESHOLD,
        inertia_enabled: bool = True,
    ):
        self.scale = scale
        self.scroll_scale = scroll_scale
        self.scroll_start_deadzone = scroll_start_deadzone
        self.scroll_emit_threshold = scroll_emit_threshold
        self.inertia_enabled = inertia_enabled
        self.active = False
        self.previous_right_position: tuple[int, int] | None = None
        self.previous_left_position: tuple[int, int] | None = None
        self.fraction_x = 0.0
        self.fraction_y = 0.0
        self.stick_fraction_x = 0.0
        self.stick_fraction_y = 0.0
        self.stick_active = False
        self.pointer_velocity_x = 0.0
        self.pointer_velocity_y = 0.0
        self.pointer_inertia = False
        self.scroll_velocity_y = 0.0
        self.scroll_inertia = False
        self.scroll_pending_y = 0
        self.scroll_active = False
        self.scrolling = False

    def set_active(self, active: bool) -> PointerUpdate:
        if active == self.active:
            return PointerUpdate()

        was_scrolling = self.scrolling
        self.active = active
        self.previous_right_position = None
        self.previous_left_position = None
        self.fraction_x = 0.0
        self.fraction_y = 0.0
        self.stick_fraction_x = 0.0
        self.stick_fraction_y = 0.0
        self.stick_active = False
        self.pointer_velocity_x = 0.0
        self.pointer_velocity_y = 0.0
        self.pointer_inertia = False
        self.scroll_velocity_y = 0.0
        self.scroll_inertia = False
        self.scroll_pending_y = 0
        self.scroll_active = False
        update = PointerUpdate(
            scroll_stop_y=not active and was_scrolling,
        )
        if not active:
            self.scrolling = False
        return update

    def _emit_pointer(self, move_x: float, move_y: float) -> tuple[int, int]:
        self.fraction_x += move_x
        self.fraction_y += move_y
        dx = math.trunc(self.fraction_x)
        dy = math.trunc(self.fraction_y)
        self.fraction_x -= dx
        self.fraction_y -= dy
        return dx, dy

    def _translate_pointer(self, state: TrackpadState) -> tuple[int, int]:
        if state.right_touched:
            self.pointer_inertia = False
            if self.previous_right_position is None:
                self.previous_right_position = (state.right_x, state.right_y)
                self.pointer_velocity_x = 0.0
                self.pointer_velocity_y = 0.0
                return 0, 0

            raw_dx = state.right_x - self.previous_right_position[0]
            raw_dy = state.right_y - self.previous_right_position[1]
            self.previous_right_position = (state.right_x, state.right_y)
            if (
                abs(raw_dx) > MAX_TRACKPAD_DELTA
                or abs(raw_dy) > MAX_TRACKPAD_DELTA
            ):
                self.pointer_velocity_x = 0.0
                self.pointer_velocity_y = 0.0
                return 0, 0

            move_x = raw_dx * self.scale
            move_y = -raw_dy * self.scale
            retained = 1.0 - POINTER_VELOCITY_BLEND
            self.pointer_velocity_x = (
                self.pointer_velocity_x * retained
                + move_x * POINTER_VELOCITY_BLEND
            )
            self.pointer_velocity_y = (
                self.pointer_velocity_y * retained
                + move_y * POINTER_VELOCITY_BLEND
            )
            return self._emit_pointer(move_x, move_y)

        just_released = self.previous_right_position is not None
        self.previous_right_position = None
        if just_released:
            speed = math.hypot(
                self.pointer_velocity_x,
                self.pointer_velocity_y,
            )
            self.pointer_inertia = (
                self.inertia_enabled
                and speed >= POINTER_INERTIA_START
            )
            if not self.pointer_inertia:
                self.pointer_velocity_x = 0.0
                self.pointer_velocity_y = 0.0

        if not self.pointer_inertia:
            return 0, 0

        result = self._emit_pointer(
            self.pointer_velocity_x,
            self.pointer_velocity_y,
        )
        self.pointer_velocity_x *= POINTER_INERTIA_DECAY
        self.pointer_velocity_y *= POINTER_INERTIA_DECAY
        if math.hypot(
            self.pointer_velocity_x,
            self.pointer_velocity_y,
        ) < POINTER_INERTIA_STOP:
            self.pointer_velocity_x = 0.0
            self.pointer_velocity_y = 0.0
            self.pointer_inertia = False
        return result

    def _stick_axis_motion(self, value: int) -> float:
        magnitude = abs(value)
        if magnitude <= RIGHT_STICK_DEADZONE:
            return 0.0
        normalized = min(
            1.0,
            (magnitude - RIGHT_STICK_DEADZONE)
            / (32_767 - RIGHT_STICK_DEADZONE),
        )
        motion = RIGHT_STICK_MAX_SPEED * normalized * normalized
        return math.copysign(motion, value)

    def _translate_stick_pointer(
        self,
        state: TrackpadState,
    ) -> tuple[int, int]:
        move_x = self._stick_axis_motion(state.right_stick_x)
        move_y = -self._stick_axis_motion(state.right_stick_y)
        self.stick_active = bool(move_x or move_y)
        if not self.stick_active:
            self.stick_fraction_x = 0.0
            self.stick_fraction_y = 0.0
            return 0, 0
        self.stick_fraction_x += move_x
        self.stick_fraction_y += move_y
        dx = math.trunc(self.stick_fraction_x)
        dy = math.trunc(self.stick_fraction_y)
        self.stick_fraction_x -= dx
        self.stick_fraction_y -= dy
        return dx, dy

    def _translate_scroll(self, state: TrackpadState) -> tuple[float, bool]:
        if state.left_touched:
            if self.previous_left_position is None:
                stop = self.scrolling
                self.previous_left_position = (state.left_x, state.left_y)
                self.scroll_velocity_y = 0.0
                self.scroll_inertia = False
                self.scroll_pending_y = 0
                self.scroll_active = False
                self.scrolling = False
                return 0.0, stop

            raw_dy = state.left_y - self.previous_left_position[1]
            self.previous_left_position = (state.left_x, state.left_y)
            if abs(raw_dy) > MAX_TRACKPAD_DELTA:
                self.scroll_velocity_y = 0.0
                self.scroll_pending_y = 0
                return 0.0, False

            self.scroll_pending_y += raw_dy
            if not self.scroll_active:
                if abs(self.scroll_pending_y) < self.scroll_start_deadzone:
                    self.scroll_velocity_y *= 1.0 - SCROLL_VELOCITY_BLEND
                    return 0.0, False
                direction = 1 if self.scroll_pending_y > 0 else -1
                self.scroll_pending_y -= (
                    direction * self.scroll_start_deadzone
                )
                self.scroll_active = True

            if abs(self.scroll_pending_y) < self.scroll_emit_threshold:
                self.scroll_velocity_y *= 1.0 - SCROLL_VELOCITY_BLEND
                return 0.0, False

            scroll_y = -self.scroll_pending_y * self.scroll_scale
            self.scroll_pending_y = 0
            self.scroll_velocity_y = (
                self.scroll_velocity_y * (1.0 - SCROLL_VELOCITY_BLEND)
                + scroll_y * SCROLL_VELOCITY_BLEND
            )
            if scroll_y:
                self.scrolling = True
            return scroll_y, False

        just_released = self.previous_left_position is not None
        self.previous_left_position = None
        self.scroll_pending_y = 0
        self.scroll_active = False
        if just_released:
            self.scroll_inertia = (
                self.inertia_enabled
                and abs(self.scroll_velocity_y) >= SCROLL_INERTIA_START
            )
            if not self.scroll_inertia:
                self.scroll_velocity_y = 0.0

        if self.scroll_inertia:
            if abs(self.scroll_velocity_y) >= SCROLL_INERTIA_STOP:
                scroll_y = self.scroll_velocity_y
                self.scroll_velocity_y *= SCROLL_INERTIA_DECAY
                self.scrolling = True
                return scroll_y, False
            self.scroll_velocity_y = 0.0
            self.scroll_inertia = False

        if self.scrolling:
            self.scrolling = False
            return 0.0, True
        return 0.0, False

    def translate(self, state: TrackpadState) -> PointerUpdate:
        if not self.active:
            self.previous_right_position = None
            self.previous_left_position = None
            return PointerUpdate()

        dx, dy = self._translate_pointer(state)
        stick_dx, stick_dy = self._translate_stick_pointer(state)
        scroll_y, scroll_stop_y = self._translate_scroll(state)

        return PointerUpdate(
            dx=dx + stick_dx,
            dy=dy + stick_dy,
            scroll_y=scroll_y,
            scroll_stop_y=scroll_stop_y,
        )

    @property
    def needs_idle_tick(self) -> bool:
        return bool(
            self.previous_right_position is not None
            or self.previous_left_position is not None
            or self.pointer_inertia
            or self.scroll_inertia
            or self.stick_active
            or self.scrolling
        )


def _read_cmdline(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return []
    return [
        part.decode("utf-8", errors="replace")
        for part in raw.split(b"\0")
        if part
    ]


def _read_environ(path: Path) -> dict[str, str]:
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return {}
    variables = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        variables[key.decode("utf-8", errors="replace")] = value.decode(
            "utf-8",
            errors="replace",
        )
    return variables


def _read_parent_pid(process_directory: Path) -> int | None:
    try:
        lines = (process_directory / "status").read_text(
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None
    for line in lines.splitlines():
        if line.startswith("PPid:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def _option_value(arguments: Sequence[str], name: str) -> str | None:
    for index, argument in enumerate(arguments):
        if argument == name and index + 1 < len(arguments):
            return arguments[index + 1]
        prefix = f"{name}="
        if argument.startswith(prefix):
            return argument[len(prefix) :]
    return None


def _find_steam_app_id(
    pid: int,
    proc_root: Path,
    maximum_depth: int = 24,
) -> int | None:
    current_pid = pid
    for _ in range(maximum_depth):
        process_directory = proc_root / str(current_pid)
        for argument in _read_cmdline(process_directory / "cmdline"):
            match = re.fullmatch(r"AppId=(\d+)", argument)
            if match:
                return int(match.group(1))
        parent_pid = _read_parent_pid(process_directory)
        if parent_pid is None or parent_pid <= 1 or parent_pid == current_pid:
            return None
        current_pid = parent_pid
    return None


def find_nested_desktop_session(
    proc_root: Path = Path("/proc"),
) -> NestedDesktopSession | None:
    try:
        process_directories = list(proc_root.iterdir())
    except OSError:
        return None

    for process_directory in process_directories:
        if not process_directory.name.isdigit():
            continue
        arguments = _read_cmdline(process_directory / "cmdline")
        if not arguments:
            continue
        executable = Path(arguments[0]).name
        if executable != "kwin_wayland":
            continue
        display = _option_value(arguments, "--xwayland-display")
        xauthority = _option_value(arguments, "--xwayland-xauthority")
        wayland_display = _option_value(arguments, "--socket") or "wayland-0"
        if (
            not display
            or not xauthority
            or "nested-desktop." not in xauthority
        ):
            continue
        try:
            pid = int(process_directory.name)
        except ValueError:
            continue
        app_id = _find_steam_app_id(pid, proc_root)
        authority_path = Path(xauthority)
        if app_id is None or not authority_path.is_file():
            continue
        runtime_directory = authority_path.parent
        dbus_address = _find_nested_dbus_address(
            process_directories,
            runtime_directory,
        )
        if dbus_address is None:
            continue
        return NestedDesktopSession(
            pid=pid,
            app_id=app_id,
            display=display,
            xauthority=authority_path,
            dbus_address=dbus_address,
            wayland_display=wayland_display,
        )
    return None


def _find_nested_dbus_address(
    process_directories: Sequence[Path],
    runtime_directory: Path,
) -> str | None:
    expected_runtime = str(runtime_directory)
    fallback = None
    for process_directory in process_directories:
        if not process_directory.name.isdigit():
            continue
        environment = _read_environ(process_directory / "environ")
        if environment.get("XDG_RUNTIME_DIR") != expected_runtime:
            continue
        address = environment.get("DBUS_SESSION_BUS_ADDRESS")
        if not address:
            continue
        if "guid=" in address:
            return address
        executable = _read_cmdline(process_directory / "cmdline")
        if executable and Path(executable[0]).name not in (
            "dbus-run-session",
            "dbus-daemon",
        ):
            fallback = address
    return fallback


def find_steam_deck_hidraw(
    sys_class_hidraw: Path = Path("/sys/class/hidraw"),
    dev_root: Path = Path("/dev"),
) -> Path | None:
    try:
        candidates = sorted(sys_class_hidraw.glob("hidraw*"))
    except OSError:
        return None

    for candidate in candidates:
        try:
            uevent = (candidate / "device/uevent").read_text(
                encoding="utf-8",
                errors="replace",
            )
            descriptor = (candidate / "device/report_descriptor").read_bytes()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if f"HID_ID={STEAM_DECK_HID_ID}" not in uevent:
            continue
        if not descriptor.startswith(b"\x06\xff\xff"):
            continue
        return dev_root / candidate.name
    return None


def find_rustdesk_joystick(
    sys_class_input: Path = Path("/sys/class/input"),
    dev_root: Path = Path("/dev/input"),
) -> Path | None:
    try:
        candidates = sorted(sys_class_input.glob("js*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            name = (candidate / "device/name").read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if name == RUSTDESK_MOUSE_NAME:
            return dev_root / candidate.name
    return None


def _wayland_alias_paths(
    session: NestedDesktopSession,
) -> tuple[Path, Path]:
    runtime_directory = session.xauthority.parent
    return (
        runtime_directory.parent / session.wayland_display,
        runtime_directory / session.wayland_display,
    )


def _resolved_link(path: Path) -> Path | None:
    try:
        target = Path(os.readlink(path))
    except OSError:
        return None
    if not target.is_absolute():
        target = path.parent / target
    return target.resolve(strict=False)


def _is_nested_wayland_target(path: Path, runtime_root: Path) -> bool:
    try:
        relative = path.relative_to(runtime_root)
    except ValueError:
        return False
    return bool(
        len(relative.parts) == 2
        and relative.parts[0].startswith("nested-desktop.")
        and relative.parts[1].startswith("wayland-")
    )


def ensure_nested_wayland_alias(
    session: NestedDesktopSession,
) -> Path | None:
    alias, target = _wayland_alias_paths(session)
    if not target.exists():
        return None
    if alias.is_symlink():
        current = _resolved_link(alias)
        if current == target.resolve(strict=False):
            return alias
        if current is None or not _is_nested_wayland_target(
            current,
            alias.parent,
        ):
            return None
    elif os.path.lexists(alias):
        return None

    temporary = alias.with_name(
        f".{alias.name}.4deus-{os.getpid()}-{time.monotonic_ns()}"
    )
    try:
        os.symlink(target, temporary)
        os.replace(temporary, alias)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        return None
    return alias


def remove_nested_wayland_alias(
    session: NestedDesktopSession | None,
    alias: Path | None,
):
    if session is None or alias is None or not alias.is_symlink():
        return
    _, target = _wayland_alias_paths(session)
    if _resolved_link(alias) != target.resolve(strict=False):
        return
    try:
        alias.unlink()
    except OSError:
        pass


class X11Connection:
    def __init__(
        self,
        display_name: str,
        xauthority: Path | None = None,
    ):
        x11_name = ctypes.util.find_library("X11") or "libX11.so.6"
        self.x11 = ctypes.CDLL(x11_name)
        self._configure_x11()
        self.display = self._open_display(display_name, xauthority)
        if not self.display:
            raise RuntimeError(f"Cannot open X display {display_name}")
        self.root = self.x11.XDefaultRootWindow(self.display)
        self.atoms: dict[str, int] = {}

    def _configure_x11(self):
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x11.XInternAtom.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        self.x11.XInternAtom.restype = ctypes.c_ulong
        self.x11.XGetWindowProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_long,
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        self.x11.XGetWindowProperty.restype = ctypes.c_int
        self.x11.XFree.argtypes = [ctypes.c_void_p]
        self.x11.XFree.restype = ctypes.c_int
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.x11.XFlush.restype = ctypes.c_int
        self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.x11.XCloseDisplay.restype = ctypes.c_int

    def _open_display(
        self,
        display_name: str,
        xauthority: Path | None,
    ) -> int | None:
        previous_authority = os.environ.get("XAUTHORITY")
        try:
            if xauthority is None:
                os.environ.pop("XAUTHORITY", None)
            else:
                os.environ["XAUTHORITY"] = str(xauthority)
            return self.x11.XOpenDisplay(display_name.encode("ascii"))
        finally:
            if previous_authority is None:
                os.environ.pop("XAUTHORITY", None)
            else:
                os.environ["XAUTHORITY"] = previous_authority

    def cardinals(self, property_name: str) -> list[int]:
        atom = self.atoms.get(property_name)
        if atom is None:
            atom = self.x11.XInternAtom(
                self.display,
                property_name.encode("ascii"),
                1,
            )
            self.atoms[property_name] = atom
        if atom == 0:
            return []

        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        item_count = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        value = ctypes.POINTER(ctypes.c_ubyte)()
        status = self.x11.XGetWindowProperty(
            self.display,
            self.root,
            atom,
            0,
            4096,
            0,
            0,
            ctypes.byref(actual_type),
            ctypes.byref(actual_format),
            ctypes.byref(item_count),
            ctypes.byref(bytes_after),
            ctypes.byref(value),
        )
        if status != 0 or not value:
            return []
        try:
            if actual_format.value != 32:
                return []
            cardinals = ctypes.cast(
                value,
                ctypes.POINTER(ctypes.c_ulong),
            )
            return [
                int(cardinals[index]) & 0xFFFFFFFF
                for index in range(item_count.value)
            ]
        finally:
            self.x11.XFree(value)

    def close(self):
        display = getattr(self, "display", None)
        if display:
            self.display = None
            self.x11.XCloseDisplay(display)


class EisConnection:
    def __init__(self, dbus_address: str):
        import dbus

        self.dbus = dbus
        self.bus = None
        self.remote = None
        self.cookie = None
        self.ei = None
        self.pointer_device = None
        self.absolute_pointer_device = None
        self.keyboard_device = None
        self.ready = False
        self.absolute_ready = False
        self.keyboard_ready = False
        self.emulating = False
        self.absolute_emulating = False
        self.keyboard_emulating = False
        self.sequence = 0
        self.lib = ctypes.CDLL(
            ctypes.util.find_library("ei") or "libei.so.1"
        )
        self._configure_libei()

        backend_fd = None
        try:
            self.bus = dbus.bus.BusConnection(dbus_address)
            remote_object = self.bus.get_object(
                "org.kde.KWin",
                "/org/kde/KWin/EIS/RemoteDesktop",
            )
            self.remote = dbus.Interface(
                remote_object,
                "org.kde.KWin.EIS.RemoteDesktop",
            )
            fd_object, cookie = self.remote.connectToEIS(
                dbus.Int32(
                    KEYBOARD_PORTAL_CAPABILITY
                    | POINTER_PORTAL_CAPABILITY
                )
            )
            backend_fd = fd_object.take()
            self.cookie = int(cookie)

            self.ei = self.lib.ei_new_sender(None)
            if not self.ei:
                raise RuntimeError("Cannot create a libei sender")
            self.lib.ei_configure_name(
                self.ei,
                b"4deus Mod Nested Desktop input",
            )
            result = self.lib.ei_setup_backend_fd(self.ei, backend_fd)
            if result != 0:
                os.close(backend_fd)
                backend_fd = None
                raise RuntimeError(f"Cannot connect libei backend: {result}")
            backend_fd = None
            self._wait_until_ready()
        except Exception:
            if backend_fd is not None:
                os.close(backend_fd)
            self.close()
            raise

    def _configure_libei(self):
        pointer = ctypes.c_void_p
        self.lib.ei_new_sender.argtypes = [pointer]
        self.lib.ei_new_sender.restype = pointer
        self.lib.ei_configure_name.argtypes = [pointer, ctypes.c_char_p]
        self.lib.ei_setup_backend_fd.argtypes = [pointer, ctypes.c_int]
        self.lib.ei_setup_backend_fd.restype = ctypes.c_int
        self.lib.ei_get_fd.argtypes = [pointer]
        self.lib.ei_get_fd.restype = ctypes.c_int
        self.lib.ei_dispatch.argtypes = [pointer]
        self.lib.ei_dispatch.restype = ctypes.c_int
        self.lib.ei_get_event.argtypes = [pointer]
        self.lib.ei_get_event.restype = pointer
        self.lib.ei_event_get_type.argtypes = [pointer]
        self.lib.ei_event_get_type.restype = ctypes.c_int
        self.lib.ei_event_get_seat.argtypes = [pointer]
        self.lib.ei_event_get_seat.restype = pointer
        self.lib.ei_event_get_device.argtypes = [pointer]
        self.lib.ei_event_get_device.restype = pointer
        self.lib.ei_event_unref.argtypes = [pointer]
        self.lib.ei_event_unref.restype = pointer
        self.lib.ei_seat_bind_capabilities.argtypes = [pointer]
        self.lib.ei_device_has_capability.argtypes = [
            pointer,
            ctypes.c_int,
        ]
        self.lib.ei_device_has_capability.restype = ctypes.c_int
        self.lib.ei_device_ref.argtypes = [pointer]
        self.lib.ei_device_ref.restype = pointer
        self.lib.ei_device_unref.argtypes = [pointer]
        self.lib.ei_device_unref.restype = pointer
        self.lib.ei_device_start_emulating.argtypes = [
            pointer,
            ctypes.c_uint32,
        ]
        self.lib.ei_device_stop_emulating.argtypes = [pointer]
        self.lib.ei_device_pointer_motion.argtypes = [
            pointer,
            ctypes.c_double,
            ctypes.c_double,
        ]
        self.lib.ei_device_pointer_motion_absolute.argtypes = [
            pointer,
            ctypes.c_double,
            ctypes.c_double,
        ]
        self.lib.ei_device_button_button.argtypes = [
            pointer,
            ctypes.c_uint32,
            ctypes.c_bool,
        ]
        self.lib.ei_device_keyboard_key.argtypes = [
            pointer,
            ctypes.c_uint32,
            ctypes.c_bool,
        ]
        self.lib.ei_device_scroll_delta.argtypes = [
            pointer,
            ctypes.c_double,
            ctypes.c_double,
        ]
        self.lib.ei_device_scroll_stop.argtypes = [
            pointer,
            ctypes.c_bool,
            ctypes.c_bool,
        ]
        self.lib.ei_device_frame.argtypes = [
            pointer,
            ctypes.c_uint64,
        ]
        self.lib.ei_device_get_region.argtypes = [
            pointer,
            ctypes.c_size_t,
        ]
        self.lib.ei_device_get_region.restype = pointer
        self.lib.ei_region_get_x.argtypes = [pointer]
        self.lib.ei_region_get_x.restype = ctypes.c_uint32
        self.lib.ei_region_get_y.argtypes = [pointer]
        self.lib.ei_region_get_y.restype = ctypes.c_uint32
        self.lib.ei_region_get_width.argtypes = [pointer]
        self.lib.ei_region_get_width.restype = ctypes.c_uint32
        self.lib.ei_region_get_height.argtypes = [pointer]
        self.lib.ei_region_get_height.restype = ctypes.c_uint32
        self.lib.ei_now.argtypes = [pointer]
        self.lib.ei_now.restype = ctypes.c_uint64
        self.lib.ei_unref.argtypes = [pointer]
        self.lib.ei_unref.restype = pointer

    def _wait_until_ready(self):
        deadline = time.monotonic() + 3
        pointer_ready_since = None
        while time.monotonic() < deadline:
            self.dispatch()
            if self.ready and self.keyboard_ready:
                return
            if self.ready:
                now = time.monotonic()
                if pointer_ready_since is None:
                    pointer_ready_since = now
                elif now - pointer_ready_since >= KEYBOARD_DEVICE_GRACE:
                    LOGGER.warning(
                        "KWin did not provide an EIS keyboard device; "
                        "pointer forwarding remains available"
                    )
                    return
            select.select([self.lib.ei_get_fd(self.ei)], [], [], 0.1)
        if self.ready:
            LOGGER.warning(
                "KWin did not provide an EIS keyboard device; "
                "pointer forwarding remains available"
            )
            return
        raise RuntimeError("KWin did not provide an EIS pointer device")

    def dispatch(self):
        if self.ei is None:
            return
        result = self.lib.ei_dispatch(self.ei)
        if result < 0:
            raise RuntimeError(f"libei dispatch failed: {result}")
        while True:
            event = self.lib.ei_get_event(self.ei)
            if not event:
                return
            try:
                self._handle_event(event)
            finally:
                self.lib.ei_event_unref(event)

    def _handle_event(self, event):
        event_type = self.lib.ei_event_get_type(event)
        if event_type == EI_EVENT_DISCONNECT:
            raise RuntimeError("KWin disconnected the EIS pointer")
        if event_type == EI_EVENT_SEAT_ADDED:
            self.lib.ei_seat_bind_capabilities(
                self.lib.ei_event_get_seat(event),
                ctypes.c_int(EI_DEVICE_CAP_POINTER),
                ctypes.c_int(EI_DEVICE_CAP_POINTER_ABSOLUTE),
                ctypes.c_int(EI_DEVICE_CAP_KEYBOARD),
                ctypes.c_int(EI_DEVICE_CAP_SCROLL),
                ctypes.c_int(EI_DEVICE_CAP_BUTTON),
                ctypes.c_void_p(),
            )
            return
        if event_type == EI_EVENT_DEVICE_ADDED:
            candidate = self.lib.ei_event_get_device(event)
            if (
                self.pointer_device is None
                and self.lib.ei_device_has_capability(
                    candidate,
                    EI_DEVICE_CAP_POINTER,
                )
                and self.lib.ei_device_has_capability(
                    candidate,
                    EI_DEVICE_CAP_BUTTON,
                )
                and self.lib.ei_device_has_capability(
                    candidate,
                    EI_DEVICE_CAP_SCROLL,
                )
            ):
                self.pointer_device = self.lib.ei_device_ref(candidate)
            if (
                self.absolute_pointer_device is None
                and self.lib.ei_device_has_capability(
                    candidate,
                    EI_DEVICE_CAP_POINTER_ABSOLUTE,
                )
                and self.lib.ei_device_has_capability(
                    candidate,
                    EI_DEVICE_CAP_BUTTON,
                )
            ):
                self.absolute_pointer_device = self.lib.ei_device_ref(
                    candidate
                )
            if (
                self.keyboard_device is None
                and self.lib.ei_device_has_capability(
                    candidate,
                    EI_DEVICE_CAP_KEYBOARD,
                )
            ):
                self.keyboard_device = self.lib.ei_device_ref(candidate)
            return
        event_device = self.lib.ei_event_get_device(event)
        if event_type == EI_EVENT_DEVICE_RESUMED:
            if event_device == self.pointer_device:
                self.ready = True
            if event_device == self.absolute_pointer_device:
                self.absolute_ready = True
            if event_device == self.keyboard_device:
                self.keyboard_ready = True
        elif event_type == EI_EVENT_DEVICE_PAUSED:
            if event_device == self.pointer_device:
                self.ready = False
                self.emulating = False
            if event_device == self.absolute_pointer_device:
                self.absolute_ready = False
                self.absolute_emulating = False
            if event_device == self.keyboard_device:
                self.keyboard_ready = False
                self.keyboard_emulating = False
        elif event_type == EI_EVENT_DEVICE_REMOVED:
            if event_device == self.pointer_device:
                self.ready = False
                self.emulating = False
                self.pointer_device = self.lib.ei_device_unref(
                    self.pointer_device
                )
            if event_device == self.absolute_pointer_device:
                self.absolute_ready = False
                self.absolute_emulating = False
                self.absolute_pointer_device = self.lib.ei_device_unref(
                    self.absolute_pointer_device
                )
            if event_device == self.keyboard_device:
                self.keyboard_ready = False
                self.keyboard_emulating = False
                self.keyboard_device = self.lib.ei_device_unref(
                    self.keyboard_device
                )

    def set_emulating(self, active: bool) -> bool:
        self.dispatch()
        if active == self.emulating:
            return self.ready
        if active:
            if not self.ready or self.pointer_device is None:
                return False
            if not self._device_emulating_elsewhere(
                self.pointer_device,
                "pointer",
            ):
                self._start_emulating(self.pointer_device)
            self.emulating = True
        elif self.pointer_device is not None:
            self.emulating = False
            if not self._device_emulating_elsewhere(
                self.pointer_device,
                "pointer",
            ):
                self.lib.ei_device_stop_emulating(self.pointer_device)
        self.lib.ei_dispatch(self.ei)
        return self.ready

    def set_absolute_emulating(self, active: bool) -> bool:
        self.dispatch()
        if active == self.absolute_emulating:
            return self.absolute_ready
        device = self.absolute_pointer_device
        if active:
            if not self.absolute_ready or device is None:
                return False
            if not self._device_emulating_elsewhere(device, "absolute"):
                self._start_emulating(device)
            self.absolute_emulating = True
        elif device is not None:
            self.absolute_emulating = False
            if not self._device_emulating_elsewhere(device, "absolute"):
                self.lib.ei_device_stop_emulating(device)
        self.lib.ei_dispatch(self.ei)
        return self.absolute_ready

    def set_keyboard_emulating(self, active: bool) -> bool:
        self.dispatch()
        if active == self.keyboard_emulating:
            return self.keyboard_ready
        if active:
            if not self.keyboard_ready or self.keyboard_device is None:
                return False
            if not self._device_emulating_elsewhere(
                self.keyboard_device,
                "keyboard",
            ):
                self._start_emulating(self.keyboard_device)
            self.keyboard_emulating = True
        elif self.keyboard_device is not None:
            self.keyboard_emulating = False
            if not self._device_emulating_elsewhere(
                self.keyboard_device,
                "keyboard",
            ):
                self.lib.ei_device_stop_emulating(self.keyboard_device)
        self.lib.ei_dispatch(self.ei)
        return self.keyboard_ready

    def _device_emulating_elsewhere(self, device, owner: str) -> bool:
        return any(
            active and candidate == device
            for candidate, active, candidate_owner in (
                (self.pointer_device, self.emulating, "pointer"),
                (
                    self.absolute_pointer_device,
                    self.absolute_emulating,
                    "absolute",
                ),
                (self.keyboard_device, self.keyboard_emulating, "keyboard"),
            )
            if candidate_owner != owner
        )

    def _start_emulating(self, device):
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        if self.sequence == 0:
            self.sequence = 1
        self.lib.ei_device_start_emulating(device, self.sequence)

    def inject(self, update: PointerUpdate):
        if (
            update.empty
            or not self.ready
            or not self.emulating
            or self.pointer_device is None
        ):
            return
        if update.dx or update.dy:
            self.lib.ei_device_pointer_motion(
                self.pointer_device,
                float(update.dx),
                float(update.dy),
            )
        if update.scroll_x or update.scroll_y:
            self.lib.ei_device_scroll_delta(
                self.pointer_device,
                update.scroll_x,
                update.scroll_y,
            )
        if update.scroll_stop_x or update.scroll_stop_y:
            self.lib.ei_device_scroll_stop(
                self.pointer_device,
                update.scroll_stop_x,
                update.scroll_stop_y,
            )
        if update.left_button is not None:
            self.lib.ei_device_button_button(
                self.pointer_device,
                BTN_LEFT,
                update.left_button,
            )
        if update.right_button is not None:
            self.lib.ei_device_button_button(
                self.pointer_device,
                BTN_RIGHT,
                update.right_button,
            )
        if update.middle_button is not None:
            self.lib.ei_device_button_button(
                self.pointer_device,
                BTN_MIDDLE,
                update.middle_button,
            )
        self.lib.ei_device_frame(
            self.pointer_device,
            self.lib.ei_now(self.ei),
        )
        self.lib.ei_dispatch(self.ei)

    def absolute_bounds(self) -> tuple[int, int, int, int] | None:
        device = self.absolute_pointer_device
        if device is None:
            return None
        region = self.lib.ei_device_get_region(device, 0)
        if not region:
            return None
        return (
            int(self.lib.ei_region_get_x(region)),
            int(self.lib.ei_region_get_y(region)),
            int(self.lib.ei_region_get_width(region)),
            int(self.lib.ei_region_get_height(region)),
        )

    def inject_absolute(self, update: PointerUpdate):
        device = self.absolute_pointer_device
        if (
            update.empty
            or not self.absolute_ready
            or not self.absolute_emulating
            or device is None
        ):
            return
        if (
            update.absolute_x is not None
            and update.absolute_y is not None
        ):
            self.lib.ei_device_pointer_motion_absolute(
                device,
                update.absolute_x,
                update.absolute_y,
            )
        if update.left_button is not None:
            self.lib.ei_device_button_button(
                device,
                BTN_LEFT,
                update.left_button,
            )
        if update.right_button is not None:
            self.lib.ei_device_button_button(
                device,
                BTN_RIGHT,
                update.right_button,
            )
        if update.middle_button is not None:
            self.lib.ei_device_button_button(
                device,
                BTN_MIDDLE,
                update.middle_button,
            )
        self.lib.ei_device_frame(device, self.lib.ei_now(self.ei))
        self.lib.ei_dispatch(self.ei)

    def inject_key(self, key_code: int, pressed: bool):
        if (
            not self.keyboard_ready
            or not self.keyboard_emulating
            or self.keyboard_device is None
        ):
            return
        self.lib.ei_device_keyboard_key(
            self.keyboard_device,
            key_code,
            pressed,
        )
        self.lib.ei_device_frame(
            self.keyboard_device,
            self.lib.ei_now(self.ei),
        )
        self.lib.ei_dispatch(self.ei)

    def close(self):
        if self.ei is not None:
            try:
                active_devices = {
                    device
                    for device, active in (
                        (self.pointer_device, self.emulating),
                        (
                            self.absolute_pointer_device,
                            self.absolute_emulating,
                        ),
                        (self.keyboard_device, self.keyboard_emulating),
                    )
                    if device is not None and active
                }
                for device in active_devices:
                    self.lib.ei_device_stop_emulating(device)
                if active_devices:
                    self.lib.ei_dispatch(self.ei)
            except Exception:
                pass
            if self.pointer_device is not None:
                self.pointer_device = self.lib.ei_device_unref(
                    self.pointer_device
                )
            if self.absolute_pointer_device is not None:
                self.absolute_pointer_device = self.lib.ei_device_unref(
                    self.absolute_pointer_device
                )
            if self.keyboard_device is not None:
                self.keyboard_device = self.lib.ei_device_unref(
                    self.keyboard_device
                )
            self.ei = self.lib.ei_unref(self.ei)
        self.ready = False
        self.absolute_ready = False
        self.keyboard_ready = False
        self.emulating = False
        self.absolute_emulating = False
        self.keyboard_emulating = False
        if self.remote is not None and self.cookie is not None:
            try:
                self.remote.disconnect(self.dbus.Int32(self.cookie))
            except Exception:
                pass
        self.remote = None
        self.cookie = None
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
        self.bus = None


class NestedDesktopMouseRuntime:
    def __init__(
        self,
        stop_event: threading.Event,
        proc_root: Path = Path("/proc"),
        sys_class_hidraw: Path = Path("/sys/class/hidraw"),
        dev_root: Path = Path("/dev"),
        sys_class_input: Path = Path("/sys/class/input"),
        input_dev_root: Path = Path("/dev/input"),
        inertia_enabled: bool = True,
        bindings_enabled: bool = True,
        bindings: Mapping[str, object] | None = None,
        action_callback: Callable[[str], None] | None = None,
        suspended: bool = False,
        control_fd: int | None = None,
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
        self.wayland_alias: Path | None = None
        self.translator = TrackpadTranslator(
            inertia_enabled=inertia_enabled,
        )
        self.bindings_enabled = bindings_enabled
        self.binding_translator = InputBindingTranslator(bindings)
        self.action_callback = action_callback
        self.suspended = suspended
        self.control_fd = control_fd
        self.control_buffer = b""
        self.forwarding = False
        self.remote_forwarding = False
        self.binding_forwarding = False
        self.next_input_frame = 0.0

    def run(self):
        next_discovery = 0.0
        next_focus_check = 0.0
        try:
            while not self.stop_event.is_set():
                self._read_control_commands()
                now = time.monotonic()
                if now >= next_discovery:
                    self._discover()
                    next_discovery = now + DISCOVERY_INTERVAL
                if now >= next_focus_check:
                    self._refresh_forwarding()
                    next_focus_check = now + FOCUS_CHECK_INTERVAL
                self._read_reports(0.04)
        finally:
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
            self._set_remote_forwarding(False)
            self._close_hidraw()
            self._close_rustdesk_joystick()
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
        if suspended:
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
        self.next_input_frame = 0.0
        LOGGER.info(
            "Nested Desktop input bridge %s for the Steam keyboard",
            "paused" if suspended else "resumed",
        )

    def _read_control_commands(self):
        control_fd = self.control_fd
        if control_fd is None:
            return
        try:
            readable, _, _ = select.select([control_fd], [], [], 0)
            if not readable:
                return
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
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
            self._set_remote_forwarding(False)
            self._close_rustdesk_joystick()
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

        if self.session is not None and self.inner_eis is None:
            try:
                self.inner_eis = EisConnection(
                    self.session.dbus_address,
                )
                LOGGER.info("Connected to the Nested Desktop KWin EIS input")
            except Exception as error:
                LOGGER.debug("Nested Desktop input is unavailable: %s", error)

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
            and self.inner_eis is not None
            and self.inner_eis.absolute_ready
        ):
            try:
                self.rustdesk_fd = os.open(
                    self.rustdesk_path,
                    os.O_RDONLY | os.O_NONBLOCK,
                )
                self.rustdesk_buffer = b""
                self.rustdesk_translator = RustDeskMouseTranslator()
                self._set_remote_forwarding(True)
                LOGGER.info(
                    "Bridging RustDesk pointer from %s into Nested Desktop",
                    self.rustdesk_path,
                )
            except OSError as error:
                LOGGER.debug(
                    "RustDesk pointer device is unavailable: %s",
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

    def _refresh_forwarding(self):
        inner_eis = self.inner_eis
        if inner_eis is not None:
            try:
                inner_eis.dispatch()
            except Exception as error:
                self._handle_eis_loss(error)
                return
            self._set_remote_forwarding(self.rustdesk_fd is not None)
        if (
            self.suspended
            or self.outer_x11 is None
            or inner_eis is None
            or self.session is None
            or self.hidraw_fd is None
        ):
            self._set_forwarding(False)
            self._set_binding_forwarding(False)
            return
        try:
            app_id = self.session.app_id
            focused_app = self.outer_x11.cardinals(
                "GAMESCOPE_FOCUSED_APP"
            )
            focused_gfx_app = self.outer_x11.cardinals(
                "GAMESCOPE_FOCUSED_APP_GFX"
            )
            mouse_focus_display = self.outer_x11.cardinals(
                "GAMESCOPE_MOUSE_FOCUS_DISPLAY"
            )
            focusable_apps = self.outer_x11.cardinals(
                "GAMESCOPE_FOCUSABLE_APPS"
            )
            binding_capabilities_ready = (
                (
                    not self.binding_translator.has_key_actions
                    or inner_eis.keyboard_ready
                )
                and (
                    not self.binding_translator.has_pointer_actions
                    or inner_eis.ready
                )
            )
            self._set_binding_forwarding(
                self.bindings_enabled
                and self.binding_translator.has_actions
                and binding_capabilities_ready
                and should_forward_back_button(
                    app_id,
                    focused_app,
                    focused_gfx_app,
                    mouse_focus_display,
                )
            )
            self._set_forwarding(
                inner_eis.ready
                and should_forward_pointer(
                    app_id,
                    focused_app,
                    focused_gfx_app,
                    focusable_apps,
                    mouse_focus_display,
                )
            )
        except Exception as error:
            self._handle_eis_loss(error)

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
                    self.binding_forwarding
                    and self.binding_translator.has_pointer_actions
                ):
                    inner_eis.set_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
        if active != self.forwarding:
            self.next_input_frame = 0.0
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
            if active:
                active = bool(inner_eis is not None)
                if (
                    active
                    and self.binding_translator.has_pointer_actions
                ):
                    active = bool(inner_eis.set_emulating(True))
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
                    if (
                        self.binding_translator.has_pointer_actions
                        and not self.forwarding
                    ):
                        inner_eis.set_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
        if active != self.binding_forwarding:
            self.next_input_frame = 0.0
        if active == self.binding_forwarding:
            return
        self.binding_forwarding = active
        if active:
            LOGGER.info("Nested Desktop configurable bindings enabled")
        else:
            LOGGER.info("Nested Desktop configurable bindings disabled")

    def _set_remote_forwarding(self, active: bool):
        if active == self.remote_forwarding:
            inner_eis = self.inner_eis
            if (
                active
                and inner_eis is not None
                and inner_eis.absolute_ready
                and inner_eis.absolute_emulating
            ):
                return
            if not active and (
                inner_eis is None
                or not inner_eis.absolute_emulating
            ):
                return
        inner_eis = self.inner_eis
        try:
            if active:
                active = bool(
                    inner_eis is not None
                    and inner_eis.absolute_bounds() is not None
                    and inner_eis.set_absolute_emulating(True)
                )
            elif inner_eis is not None:
                inner_eis.set_absolute_emulating(False)
        except Exception as error:
            self._handle_eis_loss(error)
            active = False
        self.remote_forwarding = active
        if active:
            LOGGER.info("RustDesk Nested Desktop pointer bridge enabled")
        else:
            LOGGER.info("RustDesk Nested Desktop pointer bridge disabled")

    def _inject_binding_update(self, update: BindingUpdate):
        inner_eis = self.inner_eis
        if inner_eis is not None:
            inner_eis.inject(update.pointer)
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
        self.binding_forwarding = False
        self.next_input_frame = 0.0

    def _read_rustdesk_events(self):
        fd = self.rustdesk_fd
        inner_eis = self.inner_eis
        if (
            fd is None
            or inner_eis is None
            or not self.remote_forwarding
        ):
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
            bounds = inner_eis.absolute_bounds()
            if bounds is None:
                self._set_remote_forwarding(False)
                return
            for update in self.rustdesk_translator.translate(events, bounds):
                inner_eis.inject_absolute(update)
        except (OSError, ValueError) as error:
            LOGGER.warning("Lost the RustDesk pointer device: %s", error)
            self._close_rustdesk_joystick()
        except Exception as error:
            self._handle_eis_loss(error)

    def _read_reports(self, timeout: float):
        if self.rustdesk_fd is not None and self.remote_forwarding:
            try:
                readable, _, _ = select.select(
                    [self.rustdesk_fd],
                    [],
                    [],
                    0,
                )
                if readable:
                    self._read_rustdesk_events()
            except (OSError, ValueError) as error:
                LOGGER.warning(
                    "Lost the RustDesk pointer device: %s",
                    error,
                )
                self._close_rustdesk_joystick()
        if self.hidraw_fd is None:
            self._wait_for_rustdesk(timeout)
            return
        if not self.forwarding and not self.binding_forwarding:
            self._wait_for_rustdesk(timeout)
            return

        now = time.monotonic()
        if now < self.next_input_frame:
            self.stop_event.wait(
                min(timeout, self.next_input_frame - now)
            )
            return
        self.next_input_frame = now + INPUT_FRAME_INTERVAL

        try:
            readable, _, _ = select.select(
                [self.hidraw_fd],
                [],
                [],
                0,
            )
            if not readable:
                return
            latest_report: bytes | None = None
            while True:
                try:
                    report = os.read(self.hidraw_fd, 64)
                except BlockingIOError:
                    break
                if not report:
                    self._close_hidraw()
                    return
                if len(report) >= 24 and report[:3] == REPORT_HEADER:
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
            if (
                not state.left_touched
                and not state.right_touched
                and abs(state.right_stick_x) <= RIGHT_STICK_DEADZONE
                and abs(state.right_stick_y) <= RIGHT_STICK_DEADZONE
                and not self.translator.needs_idle_tick
                and binding_update.empty
            ):
                return
            update = (
                self.translator.translate(state)
                if self.forwarding
                else PointerUpdate()
            )
            if self.inner_eis is not None:
                try:
                    self.inner_eis.inject(update)
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

    def _wait_for_rustdesk(self, timeout: float):
        if self.rustdesk_fd is None or not self.remote_forwarding:
            self.stop_event.wait(timeout)
            return
        try:
            readable, _, _ = select.select(
                [self.rustdesk_fd],
                [],
                [],
                timeout,
            )
            if readable:
                self._read_rustdesk_events()
        except (OSError, ValueError) as error:
            LOGGER.warning("Lost the RustDesk pointer device: %s", error)
            self._close_rustdesk_joystick()

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


class NestedDesktopMouseSupervisor:
    def __init__(
        self,
        plugin_root: str | Path,
        logger: logging.Logger,
        inertia_enabled: bool = True,
        bindings_enabled: bool = True,
        bindings: Mapping[str, object] | None = None,
        action_callback: Callable[[str], None] | None = None,
    ):
        self.plugin_root = Path(plugin_root)
        self.logger = logger
        self.inertia_enabled = inertia_enabled
        self.bindings_enabled = bindings_enabled
        self.bindings = normalize_nested_desktop_bindings(bindings)
        self.action_callback = action_callback
        self.suspended = False
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen | None = None
        self.process_lock = threading.Lock()

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._supervise,
            name="4deus-nested-mouse-supervisor",
            daemon=True,
        )
        self.thread.start()

    def running(self) -> bool:
        thread = self.thread
        with self.process_lock:
            process = self.process
        return bool(
            thread is not None
            and thread.is_alive()
            and process is not None
            and process.poll() is None
        )

    def stop(self):
        self.stop_event.set()
        with self.process_lock:
            process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
        thread = self.thread
        if thread is not None:
            thread.join(timeout=3)
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=1)
        self.thread = None

    def set_inertia_enabled(self, enabled: bool):
        if enabled == self.inertia_enabled:
            return
        self._restart_with(lambda: setattr(self, "inertia_enabled", enabled))

    def set_bindings(
        self,
        enabled: bool,
        bindings: Mapping[str, object],
    ):
        normalized = normalize_nested_desktop_bindings(bindings)
        if (
            enabled == self.bindings_enabled
            and normalized == self.bindings
        ):
            return

        def apply():
            self.bindings_enabled = enabled
            self.bindings = normalized

        self._restart_with(apply)

    def set_suspended(self, suspended: bool):
        if not isinstance(suspended, bool):
            raise TypeError("Suspended must be a boolean")
        with self.process_lock:
            if suspended == self.suspended:
                return
            self.suspended = suspended
            process = self.process
            if process is not None and process.poll() is None:
                self._write_control(process, suspended)

    def _write_control(
        self,
        process: subprocess.Popen,
        suspended: bool,
    ):
        stream = process.stdin
        if stream is None:
            return
        try:
            stream.write(b"suspend\n" if suspended else b"resume\n")
            stream.flush()
        except (BrokenPipeError, OSError, ValueError):
            if process.poll() is None:
                self.logger.warning(
                    "Failed to update Nested Desktop bridge suspension"
                )

    def _restart_with(self, apply: Callable[[], None]):
        was_started = bool(
            self.thread is not None and self.thread.is_alive()
        )
        if was_started:
            self.stop()
        apply()
        if was_started:
            self.start()

    def _dispatch_action(self, action: str):
        if action != ACTION_SHOW_KEYBOARD:
            self.logger.warning(
                "Ignoring unknown Nested Desktop worker action %s",
                action,
            )
            return
        callback = self.action_callback
        if callback is None:
            return
        try:
            callback(action)
        except Exception:
            self.logger.exception(
                "Failed to dispatch Nested Desktop worker action %s",
                action,
            )

    def _supervise(self):
        worker_path = self.plugin_root / Path(__file__).name
        python_executable = shutil.which("python3") or "/usr/bin/python3"
        while not self.stop_event.is_set():
            try:
                with self.process_lock:
                    launch_suspended = self.suspended
                command = [
                    python_executable,
                    str(worker_path),
                    "--worker",
                ]
                if not self.inertia_enabled:
                    command.append("--no-inertia")
                if not self.bindings_enabled:
                    command.append("--no-bindings")
                if launch_suspended:
                    command.append("--suspended")
                command.extend(
                    (
                        "--bindings-json",
                        json.dumps(
                            self.bindings,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                )
                process = subprocess.Popen(
                    command,
                    cwd=self.plugin_root,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    close_fds=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                )
            except Exception:
                self.logger.exception(
                    "Failed to start the Nested Desktop mouse bridge"
                )
                if self.stop_event.wait(2):
                    return
                continue

            with self.process_lock:
                self.process = process
                if self.suspended != launch_suspended:
                    self._write_control(process, self.suspended)
            self.logger.info("Started the Nested Desktop mouse bridge")
            action_buffer = b""
            while process.poll() is None and not self.stop_event.is_set():
                output = process.stdout
                if output is None:
                    self.stop_event.wait(0.5)
                    continue
                readable, _, _ = select.select([output], [], [], 0.5)
                if not readable:
                    continue
                chunk = os.read(output.fileno(), 4096)
                if not chunk:
                    continue
                action_buffer += chunk
                lines = action_buffer.split(b"\n")
                action_buffer = lines.pop()
                for line in lines:
                    action = line.decode("utf-8", errors="replace").strip()
                    if action:
                        self._dispatch_action(action)
            if self.stop_event.is_set():
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stdin is not None:
                    process.stdin.close()
                break
            if process.stdout is not None:
                process.stdout.close()
            if process.stdin is not None:
                process.stdin.close()
            self.logger.warning(
                "Nested Desktop mouse bridge exited with code %s; restarting",
                process.returncode,
            )
            if self.stop_event.wait(2):
                break

        with self.process_lock:
            self.process = None


def _configure_parent_death_signal():
    try:
        libc_name = ctypes.util.find_library("c") or "libc.so.6"
        libc = ctypes.CDLL(libc_name)
        libc.prctl.argtypes = [
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        libc.prctl.restype = ctypes.c_int
        libc.prctl(1, signal.SIGTERM, 0, 0, 0)
    except Exception:
        LOGGER.debug("Unable to configure the parent-death signal")


def run_worker(
    inertia_enabled: bool = True,
    bindings_enabled: bool = True,
    bindings: Mapping[str, object] | None = None,
    suspended: bool = False,
    control_fd: int | None = None,
) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _configure_parent_death_signal()
    stop_event = threading.Event()

    def stop_worker(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    runtime = NestedDesktopMouseRuntime(
        stop_event,
        inertia_enabled=inertia_enabled,
        bindings_enabled=bindings_enabled,
        bindings=bindings,
        action_callback=lambda action: print(action, flush=True),
        suspended=suspended,
        control_fd=control_fd,
    )
    runtime.run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--no-inertia", action="store_true")
    parser.add_argument("--no-bindings", action="store_true")
    parser.add_argument("--suspended", action="store_true")
    parser.add_argument("--bindings-json", default="{}")
    arguments = parser.parse_args()
    if not arguments.worker:
        parser.error("--worker is required")
    try:
        bindings = json.loads(arguments.bindings_json)
    except json.JSONDecodeError as error:
        parser.error(f"invalid --bindings-json: {error}")
    if not isinstance(bindings, dict):
        parser.error("--bindings-json must contain an object")
    return run_worker(
        inertia_enabled=not arguments.no_inertia,
        bindings_enabled=not arguments.no_bindings,
        bindings=bindings,
        suspended=arguments.suspended,
        control_fd=sys.stdin.fileno(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
