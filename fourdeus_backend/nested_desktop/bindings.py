"""Steam Deck report parsing and configurable input bindings."""

from __future__ import annotations

import math
import struct
import sys
from typing import Mapping, Sequence

from .constants import (
    ACTION_MOUSE_LEFT, ACTION_MOUSE_MIDDLE, ACTION_MOUSE_RIGHT,
    ACTION_NONE, ACTION_SHOW_KEYBOARD, BACK_BUTTON,
    BUTTON_SOURCE_MASKS, DEFAULT_NESTED_DESKTOP_BINDINGS, EIS_KEY_CODES,
    LEFT_PAD_TOUCHED, LEFT_PAD_X_OFFSET, LEFT_STICK_PRESS_THRESHOLD,
    LEFT_STICK_RELEASE_THRESHOLD, LEFT_TRIGGER, MAX_TRACKPAD_DELTA,
    MOUSE_BINDING_ACTIONS, MOUSE_SCALE, NESTED_DESKTOP_BINDING_ACTIONS,
    NESTED_DESKTOP_BINDING_SOURCES, POINTER_INERTIA_DECAY,
    POINTER_INERTIA_START, POINTER_INERTIA_STOP, POINTER_VELOCITY_BLEND,
    REPORT_HEADER, RIGHT_PAD_PRESSED, RIGHT_PAD_PRESSURE_OFFSET,
    RIGHT_PAD_PRESS_THRESHOLD, RIGHT_PAD_RELEASE_THRESHOLD,
    RIGHT_PAD_TOUCHED, RIGHT_PAD_X_OFFSET, RIGHT_STICK_DEADZONE,
    RIGHT_STICK_MAX_SPEED, RIGHT_TRIGGER, SCROLL_EMIT_THRESHOLD,
    SCROLL_INERTIA_DECAY, SCROLL_INERTIA_START, SCROLL_INERTIA_STOP,
    SCROLL_SCALE, SCROLL_START_DEADZONE, SCROLL_VELOCITY_BLEND,
    STEAM_UI_APP_ID,
)
from .models import BindingUpdate, PointerUpdate, TrackpadState


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

def prioritize_focus_app(
    app_id: int,
    focus_control_app_ids: Sequence[int],
) -> tuple[int, ...]:
    return (
        app_id,
        *(
            candidate
            for candidate in focus_control_app_ids
            if candidate != app_id
        ),
    )

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
        pointer_actions_enabled: bool = True,
    ):
        self.bindings = normalize_nested_desktop_bindings(bindings)
        self._has_key_actions = any(
            action in EIS_KEY_CODES
            for action in self.bindings.values()
        )
        self._has_pointer_actions = any(
            action in MOUSE_BINDING_ACTIONS
            for action in self.bindings.values()
        )
        self._has_actions = any(
            action != ACTION_NONE
            for action in self.bindings.values()
        )
        self.pointer_actions_enabled = pointer_actions_enabled
        self.pointer_activation_blocked = False
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
        return self._has_key_actions

    @property
    def has_pointer_actions(self) -> bool:
        return self._has_pointer_actions

    @property
    def pointer_actions_active(self) -> bool:
        return (
            self.pointer_actions_enabled
            and self.has_pointer_actions
        )

    @property
    def has_actions(self) -> bool:
        return self._has_actions

    def set_active(self, active: bool) -> BindingUpdate:
        if active == self.active:
            return BindingUpdate()
        self.active = active
        self.needs_sync = active
        self.pointer_activation_blocked = False
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

    def set_pointer_actions_enabled(
        self,
        enabled: bool,
    ) -> PointerUpdate:
        if enabled == self.pointer_actions_enabled:
            return PointerUpdate()
        self.pointer_actions_enabled = enabled
        self.pointer_activation_blocked = enabled
        if enabled:
            return PointerUpdate()
        pointer = self._mouse_update(set())
        self.injected_mouse.clear()
        return pointer

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
            self.pointer_activation_blocked = bool(
                self.pointer_actions_enabled
                and any(
                    pressed
                    and self.bindings[source] in MOUSE_BINDING_ACTIONS
                    for source, pressed in sources.items()
                )
            )
            return BindingUpdate()
        if sources == self.last_sources:
            return BindingUpdate()

        desired_keys = {
            EIS_KEY_CODES[action]
            for source, pressed in sources.items()
            if pressed
            for action in (self.bindings[source],)
            if action in EIS_KEY_CODES
        }
        desired_mouse = (
            {
                action
                for source, pressed in sources.items()
                if pressed
                for action in (self.bindings[source],)
                if action in MOUSE_BINDING_ACTIONS
            }
            if self.pointer_actions_enabled
            else set()
        )
        if self.pointer_activation_blocked:
            if not desired_mouse:
                self.pointer_activation_blocked = False
            desired_mouse = set()
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
