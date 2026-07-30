"""Data transferred between Nested Desktop subsystems."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class NestedDesktopSession:
    pid: int
    app_id: int
    display: str
    xauthority: Path
    dbus_address: str
    wayland_display: str = "wayland-0"
    software_cursor_forced: bool = False

@dataclass(frozen=True, slots=True)
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

@dataclass(frozen=True, slots=True)
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
    scroll_discrete_x: int = 0
    scroll_discrete_y: int = 0
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
            and self.scroll_discrete_x == 0
            and self.scroll_discrete_y == 0
            and not self.scroll_stop_x
            and not self.scroll_stop_y
        )

@dataclass(frozen=True, slots=True)
class JoystickEvent:
    timestamp: int
    value: int
    event_type: int
    number: int
    initial: bool = False

@dataclass(frozen=True, slots=True)
class LinuxInputEvent:
    event_type: int
    code: int
    value: int

@dataclass(frozen=True, slots=True)
class BindingUpdate:
    key_events: tuple[tuple[int, bool], ...] = ()
    pointer: PointerUpdate = PointerUpdate()
    actions: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.key_events and self.pointer.empty and not self.actions

@dataclass(frozen=True)
class CursorSnapshot:
    x: int
    y: int
    width: int
    height: int
    xhot: int
    yhot: int
    serial: int
    pixels: tuple[int, ...]
