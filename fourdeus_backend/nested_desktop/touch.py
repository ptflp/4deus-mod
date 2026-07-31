"""Steam Deck multitouch parsing for Nested Desktop forwarding."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import math
import os
import struct
from typing import Mapping

from .constants import (
    LINUX_ABS_MT_POSITION_X,
    LINUX_ABS_MT_POSITION_Y,
    LINUX_ABS_MT_SLOT,
    LINUX_ABS_MT_TRACKING_ID,
    LINUX_EV_ABS,
    LINUX_EV_SYN,
    LINUX_INPUT_EVENT,
    LINUX_SYN_REPORT,
    TOUCH_DISPLAY_HEIGHT,
    TOUCH_DISPLAY_WIDTH,
    TOUCH_INERTIA_DEFAULT_DURATION_MS,
    TOUCH_INERTIA_DEFAULT_MIN_DISTANCE,
    TOUCH_INERTIA_DEFAULT_START_SPEED,
    TOUCH_INERTIA_FRAME_INTERVAL,
    TOUCH_INERTIA_MAX_DISTANCE,
    TOUCH_INERTIA_MAX_DURATION_MS,
    TOUCH_INERTIA_MAX_RELEASE_GAP,
    TOUCH_INERTIA_MAX_SPEED,
    TOUCH_INERTIA_MAX_START_SPEED,
    TOUCH_INERTIA_MIN_ALIGNMENT,
    TOUCH_INERTIA_MIN_DISTANCE,
    TOUCH_INERTIA_MIN_EFFICIENCY,
    TOUCH_INERTIA_MIN_DURATION_MS,
    TOUCH_INERTIA_MIN_START_SPEED,
    TOUCH_INERTIA_STOP_SPEED,
    TOUCH_INERTIA_VELOCITY_BLEND,
)
from .models import LinuxInputEvent, TouchFrame, TouchUpdate


_INPUT_ABSINFO = struct.Struct("=iiiiii")
_IOC_READ = 2
_IOC_DIRSHIFT = 30
_IOC_SIZESHIFT = 16
_IOC_TYPESHIFT = 8


def _axis_bounds(fd: int, code: int) -> tuple[int, int]:
    request = (
        (_IOC_READ << _IOC_DIRSHIFT)
        | (_INPUT_ABSINFO.size << _IOC_SIZESHIFT)
        | (ord("E") << _IOC_TYPESHIFT)
        | (0x40 + code)
    )
    payload = bytearray(_INPUT_ABSINFO.size)
    fcntl.ioctl(fd, request, payload, True)
    _, minimum, maximum, _, _, _ = _INPUT_ABSINFO.unpack(payload)
    if maximum <= minimum:
        raise ValueError(
            f"Invalid touchscreen axis {code}: {minimum}..{maximum}"
        )
    return minimum, maximum


def parse_linux_input_events(
    data: bytes,
) -> tuple[LinuxInputEvent, ...]:
    usable = len(data) - (len(data) % LINUX_INPUT_EVENT.size)
    return tuple(
        LinuxInputEvent(
            event_type=event_type,
            code=code,
            value=value,
            timestamp=seconds + microseconds / 1_000_000,
        )
        for offset in range(0, usable, LINUX_INPUT_EVENT.size)
        for seconds, microseconds, event_type, code, value in (
            LINUX_INPUT_EVENT.unpack_from(data, offset),
        )
    )


@dataclass(slots=True)
class _TouchSlot:
    tracking_id: int | None = None
    x: int | None = None
    y: int | None = None
    pending_down: bool = False
    pending_up: int | None = None
    moved: bool = False


class TouchscreenParser:
    """Coalesces type-B multitouch events into display-normalized frames."""

    def __init__(
        self,
        x_bounds: tuple[int, int],
        y_bounds: tuple[int, int],
    ):
        self.x_min, self.x_max = x_bounds
        self.y_min, self.y_max = y_bounds
        self.current_slot = 0
        self.slots: dict[int, _TouchSlot] = {}

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _position(self, slot: _TouchSlot) -> tuple[float, float]:
        raw_x = self._clamp(
            ((slot.x or 0) - self.x_min) / (self.x_max - self.x_min)
        )
        raw_y = self._clamp(
            ((slot.y or 0) - self.y_min) / (self.y_max - self.y_min)
        )
        # The panel reports portrait coordinates. SteamOS rotates them
        # clockwise into the 1280x800 landscape display.
        return raw_y, 1.0 - raw_x

    def feed(
        self,
        event: LinuxInputEvent,
    ) -> tuple[TouchUpdate, ...] | None:
        if event.event_type == LINUX_EV_ABS:
            self._feed_absolute(event.code, event.value)
            return None
        if (
            event.event_type == LINUX_EV_SYN
            and event.code == LINUX_SYN_REPORT
        ):
            return self._flush()
        return None

    def _feed_absolute(self, code: int, value: int):
        if code == LINUX_ABS_MT_SLOT:
            if value >= 0:
                self.current_slot = value
            return
        slot = self.slots.setdefault(self.current_slot, _TouchSlot())
        if code == LINUX_ABS_MT_TRACKING_ID:
            if value < 0:
                if slot.tracking_id is not None:
                    slot.pending_up = slot.tracking_id
                slot.tracking_id = None
                slot.pending_down = False
                slot.moved = False
            else:
                if (
                    slot.tracking_id is not None
                    and slot.tracking_id != value
                ):
                    slot.pending_up = slot.tracking_id
                slot.tracking_id = value
                slot.pending_down = True
                slot.moved = False
            return
        if code == LINUX_ABS_MT_POSITION_X:
            slot.x = value
            slot.moved = slot.tracking_id is not None
        elif code == LINUX_ABS_MT_POSITION_Y:
            slot.y = value
            slot.moved = slot.tracking_id is not None

    def _flush(self) -> tuple[TouchUpdate, ...]:
        updates: list[TouchUpdate] = []
        for slot_number in sorted(self.slots):
            slot = self.slots[slot_number]
            if slot.pending_up is not None:
                updates.append(TouchUpdate(slot.pending_up, "up"))
                slot.pending_up = None
            if (
                slot.tracking_id is not None
                and slot.x is not None
                and slot.y is not None
            ):
                phase = (
                    "down"
                    if slot.pending_down
                    else "motion" if slot.moved else None
                )
                if phase is not None:
                    x, y = self._position(slot)
                    updates.append(
                        TouchUpdate(slot.tracking_id, phase, x, y)
                    )
                    slot.pending_down = False
            slot.moved = False
        return tuple(updates)


class TouchscreenReader:
    def __init__(
        self,
        fd: int,
        x_bounds: tuple[int, int] | None = None,
        y_bounds: tuple[int, int] | None = None,
    ):
        self.fd = fd
        self.buffer = b""
        self.parser = TouchscreenParser(
            x_bounds or _axis_bounds(fd, LINUX_ABS_MT_POSITION_X),
            y_bounds or _axis_bounds(fd, LINUX_ABS_MT_POSITION_Y),
        )

    def read_frames(self) -> tuple[TouchFrame, ...]:
        while True:
            try:
                chunk = os.read(self.fd, LINUX_INPUT_EVENT.size * 128)
            except BlockingIOError:
                break
            if not chunk:
                raise EOFError("Touchscreen device closed")
            self.buffer += chunk
        usable = len(self.buffer) - (
            len(self.buffer) % LINUX_INPUT_EVENT.size
        )
        data, self.buffer = self.buffer[:usable], self.buffer[usable:]
        frames = []
        for event in parse_linux_input_events(data):
            frame = self.parser.feed(event)
            if frame:
                frames.append(
                    TouchFrame(event.timestamp or 0.0, frame)
                )
        return tuple(frames)

    def close(self):
        if self.fd < 0:
            return
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = -1


@dataclass(slots=True)
class _TouchGesture:
    contact_id: int
    start_x: float
    start_y: float
    last_x: float
    last_y: float
    start_time: float
    last_motion_time: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    path_distance: float = 0.0
    motion_samples: int = 0


@dataclass(frozen=True, slots=True)
class TouchscreenInertiaConfig:
    duration_ms: int = TOUCH_INERTIA_DEFAULT_DURATION_MS
    start_speed: int = TOUCH_INERTIA_DEFAULT_START_SPEED
    min_distance: int = TOUCH_INERTIA_DEFAULT_MIN_DISTANCE

    @staticmethod
    def _bounded_int(
        value: object,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        if isinstance(value, bool):
            return default
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return max(minimum, min(maximum, round(number)))

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object] | None,
    ) -> TouchscreenInertiaConfig:
        if not isinstance(values, Mapping):
            values = {}
        return cls(
            duration_ms=cls._bounded_int(
                values.get("durationMs"),
                TOUCH_INERTIA_DEFAULT_DURATION_MS,
                TOUCH_INERTIA_MIN_DURATION_MS,
                TOUCH_INERTIA_MAX_DURATION_MS,
            ),
            start_speed=cls._bounded_int(
                values.get("startSpeed"),
                TOUCH_INERTIA_DEFAULT_START_SPEED,
                TOUCH_INERTIA_MIN_START_SPEED,
                TOUCH_INERTIA_MAX_START_SPEED,
            ),
            min_distance=cls._bounded_int(
                values.get("minDistance"),
                TOUCH_INERTIA_DEFAULT_MIN_DISTANCE,
                TOUCH_INERTIA_MIN_DISTANCE,
                TOUCH_INERTIA_MAX_DISTANCE,
            ),
        )

    @classmethod
    def from_user_values(
        cls,
        duration_ms: object,
        start_speed: object,
        min_distance: object,
    ) -> TouchscreenInertiaConfig:
        values = (
            (
                "duration",
                duration_ms,
                TOUCH_INERTIA_MIN_DURATION_MS,
                TOUCH_INERTIA_MAX_DURATION_MS,
            ),
            (
                "start speed",
                start_speed,
                TOUCH_INERTIA_MIN_START_SPEED,
                TOUCH_INERTIA_MAX_START_SPEED,
            ),
            (
                "minimum distance",
                min_distance,
                TOUCH_INERTIA_MIN_DISTANCE,
                TOUCH_INERTIA_MAX_DISTANCE,
            ),
        )
        normalized = []
        for label, value, minimum, maximum in values:
            if isinstance(value, bool):
                raise ValueError(f"Touch inertia {label} must be numeric")
            try:
                number = float(value)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Touch inertia {label} must be numeric"
                ) from error
            if (
                not math.isfinite(number)
                or number < minimum
                or number > maximum
            ):
                raise ValueError(
                    f"Touch inertia {label} must be between "
                    f"{minimum} and {maximum}"
                )
            normalized.append(round(number))
        return cls(*normalized)

    def as_dict(self) -> dict[str, int]:
        return {
            "durationMs": self.duration_ms,
            "startSpeed": self.start_speed,
            "minDistance": self.min_distance,
        }

    @property
    def decay(self) -> float:
        frame_count = max(
            1.0,
            self.duration_ms
            / 1_000
            / TOUCH_INERTIA_FRAME_INTERVAL,
        )
        return (
            TOUCH_INERTIA_STOP_SPEED / TOUCH_INERTIA_MAX_SPEED
        ) ** (1.0 / frame_count)

    @property
    def start_speed_per_frame(self) -> float:
        return self.start_speed * TOUCH_INERTIA_FRAME_INTERVAL

    @property
    def min_displacement(self) -> float:
        return self.min_distance * 0.78


class TouchscreenInertia:
    """Extends only a deliberate, fast, single-contact swipe."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        config: TouchscreenInertiaConfig | None = None,
    ):
        config = config or TouchscreenInertiaConfig()
        self.enabled = enabled
        self.config = config
        self.decay = config.decay
        self.start_speed = config.start_speed_per_frame
        self.contacts: dict[int, tuple[float, float]] = {}
        self.gesture: _TouchGesture | None = None
        self.contact_id: int | None = None
        self.position_x = 0.0
        self.position_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_tick = 0.0
        self.next_tick = 0.0
        self.ending = False

    @property
    def active(self) -> bool:
        return self.contact_id is not None

    def reset(self):
        self.contacts.clear()
        self.gesture = None
        self._reset_inertia()

    def _reset_inertia(self):
        self.contact_id = None
        self.position_x = 0.0
        self.position_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_tick = 0.0
        self.next_tick = 0.0
        self.ending = False

    def cancel(self) -> tuple[TouchUpdate, ...]:
        contact_id = self.contact_id
        self._reset_inertia()
        return (
            (TouchUpdate(contact_id, "up"),)
            if contact_id is not None
            else ()
        )

    @staticmethod
    def _pixel_vector(
        x: float,
        y: float,
    ) -> tuple[float, float]:
        return x * TOUCH_DISPLAY_WIDTH, y * TOUCH_DISPLAY_HEIGHT

    @staticmethod
    def _clamp_speed(
        velocity_x: float,
        velocity_y: float,
    ) -> tuple[float, float]:
        pixel_x, pixel_y = TouchscreenInertia._pixel_vector(
            velocity_x,
            velocity_y,
        )
        speed = math.hypot(pixel_x, pixel_y)
        if speed <= TOUCH_INERTIA_MAX_SPEED:
            return velocity_x, velocity_y
        scale = TOUCH_INERTIA_MAX_SPEED / speed
        return velocity_x * scale, velocity_y * scale

    @staticmethod
    def _frame_time(frame: TouchFrame, now: float) -> float:
        return frame.timestamp if frame.timestamp > 0 else now

    def _begin_gesture(self, update: TouchUpdate, timestamp: float):
        if update.x is None or update.y is None:
            self.gesture = None
            return
        self.gesture = _TouchGesture(
            contact_id=update.contact_id,
            start_x=update.x,
            start_y=update.y,
            last_x=update.x,
            last_y=update.y,
            start_time=timestamp,
            last_motion_time=timestamp,
        )

    def _observe_motion(self, update: TouchUpdate, timestamp: float):
        gesture = self.gesture
        if (
            gesture is None
            or gesture.contact_id != update.contact_id
            or update.x is None
            or update.y is None
        ):
            return
        delta_x = update.x - gesture.last_x
        delta_y = update.y - gesture.last_y
        gesture.last_x = update.x
        gesture.last_y = update.y
        pixel_x, pixel_y = self._pixel_vector(delta_x, delta_y)
        distance = math.hypot(pixel_x, pixel_y)
        if distance <= 0:
            return
        elapsed = timestamp - gesture.last_motion_time
        gesture.last_motion_time = timestamp
        gesture.path_distance += distance
        gesture.motion_samples += 1
        if elapsed <= 0:
            elapsed = TOUCH_INERTIA_FRAME_INTERVAL
        if elapsed > TOUCH_INERTIA_MAX_RELEASE_GAP:
            gesture.velocity_x = 0.0
            gesture.velocity_y = 0.0
            return
        scale = TOUCH_INERTIA_FRAME_INTERVAL / elapsed
        instant_x, instant_y = self._clamp_speed(
            delta_x * scale,
            delta_y * scale,
        )
        retained = 1.0 - TOUCH_INERTIA_VELOCITY_BLEND
        gesture.velocity_x = (
            gesture.velocity_x * retained
            + instant_x * TOUCH_INERTIA_VELOCITY_BLEND
        )
        gesture.velocity_y = (
            gesture.velocity_y * retained
            + instant_y * TOUCH_INERTIA_VELOCITY_BLEND
        )

    def _eligible(self, gesture: _TouchGesture, timestamp: float) -> bool:
        if (
            not self.enabled
            or gesture.motion_samples < 2
            or timestamp - gesture.last_motion_time
            > TOUCH_INERTIA_MAX_RELEASE_GAP
        ):
            return False
        displacement_x = gesture.last_x - gesture.start_x
        displacement_y = gesture.last_y - gesture.start_y
        pixel_displacement = self._pixel_vector(
            displacement_x,
            displacement_y,
        )
        displacement = math.hypot(*pixel_displacement)
        pixel_velocity = self._pixel_vector(
            gesture.velocity_x,
            gesture.velocity_y,
        )
        speed = math.hypot(*pixel_velocity)
        if (
            gesture.path_distance < self.config.min_distance
            or displacement < self.config.min_displacement
            or speed < self.start_speed
        ):
            return False
        efficiency = displacement / max(gesture.path_distance, 1.0)
        alignment = (
            (
                pixel_displacement[0] * pixel_velocity[0]
                + pixel_displacement[1] * pixel_velocity[1]
            )
            / (displacement * speed)
        )
        return (
            efficiency >= TOUCH_INERTIA_MIN_EFFICIENCY
            and alignment >= TOUCH_INERTIA_MIN_ALIGNMENT
        )

    def _start_inertia(self, gesture: _TouchGesture, now: float):
        self.contact_id = gesture.contact_id
        self.position_x = gesture.last_x
        self.position_y = gesture.last_y
        self.velocity_x, self.velocity_y = self._clamp_speed(
            gesture.velocity_x,
            gesture.velocity_y,
        )
        self.last_tick = now
        self.next_tick = now + TOUCH_INERTIA_FRAME_INTERVAL
        self.ending = False

    def process(
        self,
        frame: TouchFrame,
        now: float,
    ) -> tuple[tuple[TouchUpdate, ...], ...]:
        output: list[tuple[TouchUpdate, ...]] = []
        has_down = any(
            update.phase == "down" for update in frame.updates
        )
        if has_down and self.active:
            cancelled = self.cancel()
            if cancelled:
                output.append(cancelled)

        timestamp = self._frame_time(frame, now)
        forwarded = []
        for update in frame.updates:
            if update.phase == "down":
                if update.x is None or update.y is None:
                    forwarded.append(update)
                    continue
                was_empty = not self.contacts
                self.contacts[update.contact_id] = (update.x, update.y)
                if (
                    was_empty
                    and len(self.contacts) == 1
                    and self.enabled
                ):
                    self._begin_gesture(update, timestamp)
                elif len(self.contacts) > 1:
                    self.gesture = None
                forwarded.append(update)
                continue

            if update.phase == "motion":
                if update.x is not None and update.y is not None:
                    self.contacts[update.contact_id] = (
                        update.x,
                        update.y,
                    )
                    self._observe_motion(update, timestamp)
                forwarded.append(update)
                continue

            if update.phase == "up":
                gesture = self.gesture
                self.contacts.pop(update.contact_id, None)
                eligible = bool(
                    not has_down
                    and not self.contacts
                    and gesture is not None
                    and gesture.contact_id == update.contact_id
                    and self._eligible(gesture, timestamp)
                )
                self.gesture = None
                if eligible and gesture is not None:
                    self._start_inertia(gesture, now)
                    continue
                forwarded.append(update)
                continue

            forwarded.append(update)

        if forwarded:
            output.append(tuple(forwarded))
        return tuple(output)

    def timeout(self, now: float, maximum: float) -> float:
        maximum = max(0.0, maximum)
        if not self.active:
            return maximum
        return min(maximum, max(0.0, self.next_tick - now))

    def tick(self, now: float) -> tuple[TouchUpdate, ...]:
        contact_id = self.contact_id
        if contact_id is None or now < self.next_tick:
            return ()
        if self.ending:
            self._reset_inertia()
            return (TouchUpdate(contact_id, "up"),)

        elapsed = max(
            TOUCH_INERTIA_FRAME_INTERVAL,
            min(0.05, now - self.last_tick),
        )
        frame_scale = elapsed / TOUCH_INERTIA_FRAME_INTERVAL
        next_x = max(
            0.0,
            min(1.0, self.position_x + self.velocity_x * frame_scale),
        )
        next_y = max(
            0.0,
            min(1.0, self.position_y + self.velocity_y * frame_scale),
        )
        moved = next_x != self.position_x or next_y != self.position_y
        self.position_x = next_x
        self.position_y = next_y
        if not moved:
            self._reset_inertia()
            return (TouchUpdate(contact_id, "up"),)
        self.last_tick = now
        decay = self.decay ** frame_scale
        self.velocity_x *= decay
        self.velocity_y *= decay
        speed = math.hypot(
            *self._pixel_vector(self.velocity_x, self.velocity_y)
        )
        self.ending = speed < TOUCH_INERTIA_STOP_SPEED
        self.next_tick = now + TOUCH_INERTIA_FRAME_INTERVAL
        return (
            TouchUpdate(
                contact_id,
                "motion",
                self.position_x,
                self.position_y,
            ),
        )
