"""RustDesk device protocols and pointer translators."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import struct
from typing import Sequence

from .constants import (
    BTN_LEFT, BTN_MIDDLE, BTN_RIGHT, INPUT_FRAME_INTERVAL,
    JOYSTICK_AXIS_MIN, JOYSTICK_AXIS_SPAN, JOYSTICK_EVENT_AXIS,
    JOYSTICK_EVENT_BUTTON, JOYSTICK_EVENT_INIT, JOYSTICK_EVENT_SIZE,
    LINUX_ABS_X, LINUX_ABS_Y, LINUX_EV_ABS, LINUX_EV_KEY,
    LINUX_EV_REL, LINUX_EV_SYN, LINUX_INPUT_EVENT,
    LINUX_REL_HWHEEL, LINUX_REL_WHEEL, LINUX_SYN_REPORT,
    RUSTDESK_ABS_MAX_X, RUSTDESK_ABS_MAX_Y, RUSTDESK_IPC_MAX_FRAME,
    RUSTDESK_IPC_TIMEOUT, RUSTDESK_SCROLL_INERTIA_BURST_GAP,
    RUSTDESK_SCROLL_INERTIA_DECAY, RUSTDESK_SCROLL_INERTIA_DELAY,
    RUSTDESK_SCROLL_INERTIA_GAIN, RUSTDESK_SCROLL_INERTIA_MIN_EVENTS,
    RUSTDESK_SCROLL_INERTIA_RETAIN, RUSTDESK_SCROLL_INERTIA_STOP,
    RUSTDESK_SCROLL_UNIT,
)
from .models import JoystickEvent, LinuxInputEvent, PointerUpdate


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

def parse_linux_input_events(data: bytes) -> tuple[LinuxInputEvent, ...]:
    events = []
    usable = len(data) - (len(data) % LINUX_INPUT_EVENT.size)
    for offset in range(0, usable, LINUX_INPUT_EVENT.size):
        _, _, event_type, code, value = LINUX_INPUT_EVENT.unpack_from(
            data,
            offset,
        )
        events.append(
            LinuxInputEvent(
                event_type=event_type,
                code=code,
                value=value,
            )
        )
    return tuple(events)

def encode_rustdesk_ipc_frame(payload: bytes) -> bytes:
    payload_length = len(payload)
    if payload_length <= 0x3F:
        header_length = 1
    elif payload_length <= 0x3FFF:
        header_length = 2
    elif payload_length <= 0x3FFFFF:
        header_length = 3
    elif payload_length <= 0x3FFFFFFF:
        header_length = 4
    else:
        raise ValueError("RustDesk IPC frame is too large")
    encoded_length = (payload_length << 2) | (header_length - 1)
    return encoded_length.to_bytes(header_length, "little") + payload

def _receive_exact(connection: socket.socket, length: int) -> bytes:
    result = bytearray()
    while len(result) < length:
        chunk = connection.recv(length - len(result))
        if not chunk:
            raise EOFError("RustDesk IPC response was truncated")
        result.extend(chunk)
    return bytes(result)

def receive_rustdesk_ipc_frame(
    connection: socket.socket,
    maximum_length: int = RUSTDESK_IPC_MAX_FRAME,
) -> bytes:
    first = _receive_exact(connection, 1)
    header_length = (first[0] & 0x03) + 1
    header = first + _receive_exact(connection, header_length - 1)
    payload_length = int.from_bytes(header, "little") >> 2
    if payload_length > maximum_length:
        raise ValueError("RustDesk IPC response is too large")
    return _receive_exact(connection, payload_length)

def query_rustdesk_video_connection_count(
    ipc_path: Path,
    timeout: float = RUSTDESK_IPC_TIMEOUT,
) -> int | None:
    request = json.dumps(
        {"t": "VideoConnCount", "c": None},
        separators=(",", ":"),
    ).encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(ipc_path))
            client.sendall(encode_rustdesk_ipc_frame(request))
            response = json.loads(
                receive_rustdesk_ipc_frame(client).decode()
            )
    except (
        EOFError,
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
        ValueError,
    ):
        return None
    if not isinstance(response, dict):
        return None
    count = response.get("c")
    if (
        response.get("t") != "VideoConnCount"
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
    ):
        return None
    return count

class RustDeskRelayTranslator:
    def __init__(self):
        self.axes = [0, 0]
        self.axis_known = [False, False]
        self.axis_changed = False
        self.pending_buttons: dict[str, bool] = {}
        self.pending_scroll_x = 0
        self.pending_scroll_y = 0

    @staticmethod
    def _coordinate(
        value: int,
        source_maximum: int,
        start: int,
        size: int,
    ) -> float:
        normalized = max(0, min(source_maximum, value)) / source_maximum
        return float(start) + normalized * max(0, size - 1)

    def _position(
        self,
        bounds: tuple[int, int, int, int],
    ) -> PointerUpdate:
        if not all(self.axis_known):
            return PointerUpdate()
        x, y, width, height = bounds
        return PointerUpdate(
            absolute_x=self._coordinate(
                self.axes[0],
                RUSTDESK_ABS_MAX_X,
                x,
                width,
            ),
            absolute_y=self._coordinate(
                self.axes[1],
                RUSTDESK_ABS_MAX_Y,
                y,
                height,
            ),
        )

    def translate(
        self,
        events: Sequence[LinuxInputEvent],
        bounds: tuple[int, int, int, int],
    ) -> tuple[PointerUpdate, ...]:
        updates = []
        button_names = {
            BTN_LEFT: "left",
            BTN_RIGHT: "right",
            BTN_MIDDLE: "middle",
        }
        for event in events:
            if (
                event.event_type == LINUX_EV_ABS
                and event.code in (LINUX_ABS_X, LINUX_ABS_Y)
            ):
                self.axes[event.code] = event.value
                self.axis_known[event.code] = True
                self.axis_changed = True
                continue
            if (
                event.event_type == LINUX_EV_KEY
                and event.code in button_names
            ):
                self.pending_buttons[button_names[event.code]] = bool(
                    event.value
                )
                continue
            if event.event_type == LINUX_EV_REL:
                if event.code == LINUX_REL_HWHEEL:
                    self.pending_scroll_x += event.value
                elif event.code == LINUX_REL_WHEEL:
                    self.pending_scroll_y += event.value
                continue
            if (
                event.event_type != LINUX_EV_SYN
                or event.code != LINUX_SYN_REPORT
                or (
                    not self.axis_changed
                    and not self.pending_buttons
                    and not self.pending_scroll_x
                    and not self.pending_scroll_y
                )
            ):
                continue
            position = (
                self._position(bounds)
                if self.axis_changed
                else PointerUpdate()
            )
            updates.append(
                PointerUpdate(
                    absolute_x=position.absolute_x,
                    absolute_y=position.absolute_y,
                    left_button=self.pending_buttons.get("left"),
                    right_button=self.pending_buttons.get("right"),
                    middle_button=self.pending_buttons.get("middle"),
                    scroll_discrete_x=(
                        self.pending_scroll_x * RUSTDESK_SCROLL_UNIT
                    ),
                    scroll_discrete_y=(
                        -self.pending_scroll_y * RUSTDESK_SCROLL_UNIT
                    ),
                )
            )
            self.axis_changed = False
            self.pending_buttons = {}
            self.pending_scroll_x = 0
            self.pending_scroll_y = 0
        return tuple(updates)

class RustDeskScrollInertia:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_input_time: float | None = None
        self.last_direction = (0, 0)
        self.burst_events = 0
        self.armed = False
        self.next_tick = 0.0

    def reset(self):
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_input_time = None
        self.last_direction = (0, 0)
        self.burst_events = 0
        self.armed = False
        self.next_tick = 0.0

    @staticmethod
    def _direction(value: int) -> int:
        return (value > 0) - (value < 0)

    @staticmethod
    def _push_velocity(current: float, delta: int) -> float:
        if delta == 0:
            return current
        if current * delta <= 0:
            return delta * RUSTDESK_SCROLL_INERTIA_GAIN
        velocity = (
            current * RUSTDESK_SCROLL_INERTIA_RETAIN
            + delta * RUSTDESK_SCROLL_INERTIA_GAIN
        )
        maximum = RUSTDESK_SCROLL_UNIT * 2
        return max(-maximum, min(maximum, velocity))

    def observe(self, update: PointerUpdate, now: float):
        if not self.enabled:
            return
        delta_x = update.scroll_discrete_x
        delta_y = update.scroll_discrete_y
        if not delta_x and not delta_y:
            return

        direction = (
            self._direction(delta_x),
            self._direction(delta_y),
        )
        in_same_burst = bool(
            self.last_input_time is not None
            and now - self.last_input_time
            <= RUSTDESK_SCROLL_INERTIA_BURST_GAP
            and direction == self.last_direction
        )
        if in_same_burst:
            self.burst_events += 1
        else:
            self.velocity_x = 0.0
            self.velocity_y = 0.0
            self.burst_events = 1
            self.armed = False

        self.velocity_x = self._push_velocity(
            self.velocity_x,
            delta_x,
        )
        self.velocity_y = self._push_velocity(
            self.velocity_y,
            delta_y,
        )
        self.last_input_time = now
        self.last_direction = direction
        self.armed = bool(
            self.armed
            or self.burst_events >= RUSTDESK_SCROLL_INERTIA_MIN_EVENTS
        )
        self.next_tick = now + RUSTDESK_SCROLL_INERTIA_DELAY

    @property
    def active(self) -> bool:
        return bool(
            self.enabled
            and self.armed
            and (
                abs(self.velocity_x) >= RUSTDESK_SCROLL_INERTIA_STOP
                or abs(self.velocity_y) >= RUSTDESK_SCROLL_INERTIA_STOP
            )
        )

    def timeout(self, now: float, maximum: float) -> float:
        maximum = max(0.0, maximum)
        if not self.active:
            return maximum
        return min(maximum, max(0.0, self.next_tick - now))

    def tick(self, now: float) -> PointerUpdate:
        if not self.active or now < self.next_tick:
            return PointerUpdate()
        update = PointerUpdate(
            scroll_discrete_x=round(self.velocity_x),
            scroll_discrete_y=round(self.velocity_y),
        )
        self.velocity_x *= RUSTDESK_SCROLL_INERTIA_DECAY
        self.velocity_y *= RUSTDESK_SCROLL_INERTIA_DECAY
        if abs(self.velocity_x) < RUSTDESK_SCROLL_INERTIA_STOP:
            self.velocity_x = 0.0
        if abs(self.velocity_y) < RUSTDESK_SCROLL_INERTIA_STOP:
            self.velocity_y = 0.0
        if not self.velocity_x and not self.velocity_y:
            self.reset()
        else:
            self.next_tick = now + INPUT_FRAME_INTERVAL
        return update

class RustDeskMouseTranslator:
    def __init__(self):
        self.axes = [0, 0]
        self.axis_known = [False, False]
        self.buttons = [False, False, False]

    @staticmethod
    def _coordinate(value: int, start: int, size: int) -> float:
        normalized = (
            max(JOYSTICK_AXIS_MIN, min(JOYSTICK_AXIS_MIN + JOYSTICK_AXIS_SPAN, value))
            - JOYSTICK_AXIS_MIN
        ) / JOYSTICK_AXIS_SPAN
        return float(start) + normalized * max(0, size - 1)

    def position(
        self,
        bounds: tuple[int, int, int, int],
    ) -> PointerUpdate:
        if not all(self.axis_known):
            return PointerUpdate()
        x, y, width, height = bounds
        return PointerUpdate(
            absolute_x=self._coordinate(self.axes[0], x, width),
            absolute_y=self._coordinate(self.axes[1], y, height),
        )

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
            position = (
                self.position(bounds)
                if axis_changed
                else PointerUpdate()
            )
            updates.append(
                PointerUpdate(
                    absolute_x=position.absolute_x,
                    absolute_y=position.absolute_y,
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
                elif (
                    event.event_type == JOYSTICK_EVENT_BUTTON
                    and event.number < 3
                ):
                    self.buttons[event.number] = bool(event.value)
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
                pressed = bool(event.value)
                self.buttons[event.number] = pressed
                buttons[("left", "right", "middle")[event.number]] = pressed
        flush()
        return tuple(updates)
