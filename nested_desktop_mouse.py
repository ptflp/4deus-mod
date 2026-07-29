from __future__ import annotations

import argparse
import ctypes
import ctypes.util
from dataclasses import dataclass
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
from typing import Sequence


LOGGER = logging.getLogger("4deus-nested-mouse")

STEAM_DECK_HID_ID = "0003:000028DE:00001205"
STEAM_UI_APP_ID = 769
REPORT_HEADER = b"\x01\x00\x09"
RIGHT_TRIGGER = 0x00000001
LEFT_TRIGGER = 0x00000002
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
POINTER_INERTIA_START = 0.8
POINTER_INERTIA_STOP = 0.15
SCROLL_VELOCITY_BLEND = 0.55
SCROLL_INERTIA_DECAY = 0.90
SCROLL_INERTIA_START = 0.35
SCROLL_INERTIA_STOP = 0.01
INPUT_FRAME_INTERVAL = 1 / 60
FOCUS_CHECK_INTERVAL = 0.25
DISCOVERY_INTERVAL = 5.0

EI_DEVICE_CAP_POINTER = 1 << 0
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
POINTER_PORTAL_CAPABILITY = 2


@dataclass(frozen=True)
class NestedDesktopSession:
    pid: int
    app_id: int
    display: str
    xauthority: Path
    dbus_address: str


@dataclass(frozen=True)
class TrackpadState:
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


@dataclass(frozen=True)
class PointerUpdate:
    dx: int = 0
    dy: int = 0
    left_button: bool | None = None
    right_button: bool | None = None
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    scroll_stop_x: bool = False
    scroll_stop_y: bool = False

    @property
    def empty(self) -> bool:
        return (
            self.dx == 0
            and self.dy == 0
            and self.left_button is None
            and self.right_button is None
            and self.scroll_x == 0
            and self.scroll_y == 0
            and not self.scroll_stop_x
            and not self.scroll_stop_y
        )


def parse_trackpad_report(report: bytes) -> TrackpadState | None:
    if (
        len(report) < RIGHT_PAD_PRESSURE_OFFSET + 2
        or report[:3] != REPORT_HEADER
    ):
        return None
    controls = int.from_bytes(report[8:12], "little")
    left_x, left_y = struct.unpack_from("<hh", report, LEFT_PAD_X_OFFSET)
    right_x, right_y = struct.unpack_from("<hh", report, RIGHT_PAD_X_OFFSET)
    right_pressure = struct.unpack_from(
        "<H",
        report,
        RIGHT_PAD_PRESSURE_OFFSET,
    )[0]
    return TrackpadState(
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
    if not focused_app or focused_app[0] != session_app_id:
        return False
    if not focused_gfx_app or focused_gfx_app[0] != session_app_id:
        return False
    if decode_gamescope_display(mouse_focus_display) in ("", ":0"):
        return False
    ignored = {0, STEAM_UI_APP_ID, session_app_id}
    return any(app_id not in ignored for app_id in focusable_apps)


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
        self.pointer_velocity_x = 0.0
        self.pointer_velocity_y = 0.0
        self.pointer_inertia = False
        self.scroll_velocity_y = 0.0
        self.scroll_inertia = False
        self.scroll_pending_y = 0
        self.scroll_active = False
        self.last_left_trigger = False
        self.last_left_click = False
        self.right_pressure_pressed = False
        self.injected_left_button = False
        self.injected_right_button = False
        self.scrolling = False
        self.needs_button_sync = True

    def set_active(self, active: bool) -> PointerUpdate:
        if active == self.active:
            return PointerUpdate()

        was_scrolling = self.scrolling
        self.active = active
        self.previous_right_position = None
        self.previous_left_position = None
        self.fraction_x = 0.0
        self.fraction_y = 0.0
        self.pointer_velocity_x = 0.0
        self.pointer_velocity_y = 0.0
        self.pointer_inertia = False
        self.scroll_velocity_y = 0.0
        self.scroll_inertia = False
        self.scroll_pending_y = 0
        self.scroll_active = False
        self.needs_button_sync = True
        update = PointerUpdate(
            left_button=(
                False if not active and self.injected_left_button else None
            ),
            right_button=(
                False if not active and self.injected_right_button else None
            ),
            scroll_stop_y=not active and was_scrolling,
        )
        if not active:
            self.injected_left_button = False
            self.injected_right_button = False
            self.right_pressure_pressed = False
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

    def _pressure_click(self, state: TrackpadState) -> bool:
        if (
            not state.right_touched
            or state.right_pressure <= RIGHT_PAD_RELEASE_THRESHOLD
        ):
            self.right_pressure_pressed = False
        elif state.right_pressure >= RIGHT_PAD_PRESS_THRESHOLD:
            self.right_pressure_pressed = True
        return self.right_pressure_pressed

    def translate(self, state: TrackpadState) -> PointerUpdate:
        pressure_click = self._pressure_click(state)
        left_click = (
            state.right_trigger
            or state.right_pressed
            or pressure_click
        )
        if not self.active:
            self.previous_right_position = None
            self.previous_left_position = None
            self.last_left_trigger = state.left_trigger
            self.last_left_click = left_click
            return PointerUpdate()

        left_button: bool | None = None
        right_button: bool | None = None
        if self.needs_button_sync:
            self.last_left_trigger = state.left_trigger
            self.last_left_click = left_click
            self.needs_button_sync = False
        else:
            if left_click != self.last_left_click:
                self.last_left_click = left_click
                if left_click:
                    self.injected_left_button = True
                    left_button = True
                elif self.injected_left_button:
                    self.injected_left_button = False
                    left_button = False
            if state.left_trigger != self.last_left_trigger:
                self.last_left_trigger = state.left_trigger
                if state.left_trigger:
                    self.injected_right_button = True
                    right_button = True
                elif self.injected_right_button:
                    self.injected_right_button = False
                    right_button = False

        dx, dy = self._translate_pointer(state)
        scroll_y, scroll_stop_y = self._translate_scroll(state)

        return PointerUpdate(
            dx=dx,
            dy=dy,
            left_button=left_button,
            right_button=right_button,
            scroll_y=scroll_y,
            scroll_stop_y=scroll_stop_y,
        )

    @property
    def needs_idle_tick(self) -> bool:
        return bool(
            self.needs_button_sync
            or self.previous_right_position is not None
            or self.previous_left_position is not None
            or self.pointer_inertia
            or self.scroll_inertia
            or self.last_left_trigger
            or self.last_left_click
            or self.right_pressure_pressed
            or self.injected_left_button
            or self.injected_right_button
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
        self.ready = False
        self.emulating = False
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
                dbus.Int32(POINTER_PORTAL_CAPABILITY)
            )
            backend_fd = fd_object.take()
            self.cookie = int(cookie)

            self.ei = self.lib.ei_new_sender(None)
            if not self.ei:
                raise RuntimeError("Cannot create a libei sender")
            self.lib.ei_configure_name(
                self.ei,
                b"4deus Mod Nested Desktop pointer",
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
        self.lib.ei_device_button_button.argtypes = [
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
        self.lib.ei_now.argtypes = [pointer]
        self.lib.ei_now.restype = ctypes.c_uint64
        self.lib.ei_unref.argtypes = [pointer]
        self.lib.ei_unref.restype = pointer

    def _wait_until_ready(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.dispatch()
            if self.ready:
                return
            select.select([self.lib.ei_get_fd(self.ei)], [], [], 0.1)
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
            return
        event_device = self.lib.ei_event_get_device(event)
        if event_device != self.pointer_device:
            return
        if event_type == EI_EVENT_DEVICE_RESUMED:
            self.ready = True
        elif event_type == EI_EVENT_DEVICE_PAUSED:
            self.ready = False
            self.emulating = False
        elif event_type == EI_EVENT_DEVICE_REMOVED:
            self.ready = False
            self.emulating = False
            self.pointer_device = self.lib.ei_device_unref(
                self.pointer_device
            )

    def set_emulating(self, active: bool) -> bool:
        self.dispatch()
        if active == self.emulating:
            return self.ready
        if active:
            if not self.ready or self.pointer_device is None:
                return False
            self.sequence = (self.sequence + 1) & 0xFFFFFFFF
            if self.sequence == 0:
                self.sequence = 1
            self.lib.ei_device_start_emulating(
                self.pointer_device,
                self.sequence,
            )
            self.emulating = True
        elif self.pointer_device is not None:
            self.lib.ei_device_stop_emulating(self.pointer_device)
            self.emulating = False
        self.lib.ei_dispatch(self.ei)
        return self.ready

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
        self.lib.ei_device_frame(
            self.pointer_device,
            self.lib.ei_now(self.ei),
        )
        self.lib.ei_dispatch(self.ei)

    def close(self):
        if self.ei is not None:
            try:
                if self.emulating and self.pointer_device is not None:
                    self.lib.ei_device_stop_emulating(self.pointer_device)
                    self.lib.ei_dispatch(self.ei)
            except Exception:
                pass
            if self.pointer_device is not None:
                self.pointer_device = self.lib.ei_device_unref(
                    self.pointer_device
                )
            self.ei = self.lib.ei_unref(self.ei)
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
        inertia_enabled: bool = True,
    ):
        self.stop_event = stop_event
        self.proc_root = proc_root
        self.sys_class_hidraw = sys_class_hidraw
        self.dev_root = dev_root
        self.outer_x11: X11Connection | None = None
        self.inner_eis: EisConnection | None = None
        self.session: NestedDesktopSession | None = None
        self.hidraw_path: Path | None = None
        self.hidraw_fd: int | None = None
        self.translator = TrackpadTranslator(
            inertia_enabled=inertia_enabled,
        )
        self.forwarding = False
        self.next_input_frame = 0.0

    def run(self):
        next_discovery = 0.0
        next_focus_check = 0.0
        try:
            while not self.stop_event.is_set():
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
            self._close_hidraw()
            if self.inner_eis is not None:
                self.inner_eis.close()
            if self.outer_x11 is not None:
                self.outer_x11.close()

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

        if self.session is not None and self.inner_eis is None:
            try:
                self.inner_eis = EisConnection(
                    self.session.dbus_address,
                )
                LOGGER.info("Connected to the Nested Desktop KWin EIS input")
            except Exception as error:
                LOGGER.debug("Nested Desktop input is unavailable: %s", error)

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
        if (
            self.outer_x11 is None
            or self.inner_eis is None
            or self.session is None
            or self.hidraw_fd is None
        ):
            self._set_forwarding(False)
            return
        try:
            self.inner_eis.dispatch()
            if not self.inner_eis.ready:
                self._set_forwarding(False)
                return

            app_id = self.session.app_id
            focused_app = self.outer_x11.cardinals(
                "GAMESCOPE_FOCUSED_APP"
            )
            if not focused_app or focused_app[0] != app_id:
                self._set_forwarding(False)
                return
            focused_gfx_app = self.outer_x11.cardinals(
                "GAMESCOPE_FOCUSED_APP_GFX"
            )
            if not focused_gfx_app or focused_gfx_app[0] != app_id:
                self._set_forwarding(False)
                return
            mouse_focus_display = self.outer_x11.cardinals(
                "GAMESCOPE_MOUSE_FOCUS_DISPLAY"
            )
            if decode_gamescope_display(mouse_focus_display) in ("", ":0"):
                self._set_forwarding(False)
                return
            focusable_apps = self.outer_x11.cardinals(
                "GAMESCOPE_FOCUSABLE_APPS"
            )
            ignored = {0, STEAM_UI_APP_ID, app_id}
            self._set_forwarding(
                any(value not in ignored for value in focusable_apps)
            )
        except Exception as error:
            LOGGER.warning("Lost the Nested Desktop EIS input: %s", error)
            self.inner_eis.close()
            self.inner_eis = None
            self._set_forwarding(False)

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
                if not active:
                    inner_eis.set_emulating(False)
        except Exception as error:
            LOGGER.warning("Lost the Nested Desktop EIS input: %s", error)
            if inner_eis is not None:
                inner_eis.close()
            self.inner_eis = None
            active = False
            self.translator.set_active(False)
        if active != self.forwarding:
            self.next_input_frame = 0.0
        if active == self.forwarding:
            return
        self.forwarding = active
        if active:
            LOGGER.info("Nested Desktop trackpad forwarding enabled")
        else:
            LOGGER.info("Nested Desktop trackpad forwarding disabled")

    def _read_reports(self, timeout: float):
        if self.hidraw_fd is None:
            self.stop_event.wait(timeout)
            return
        if not self.forwarding:
            self.stop_event.wait(timeout)
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
            if (
                not state.left_touched
                and not state.right_touched
                and not state.left_trigger
                and not state.right_trigger
                and not state.right_pressed
                and state.right_pressure <= RIGHT_PAD_RELEASE_THRESHOLD
                and not self.translator.needs_idle_tick
            ):
                return
            update = self.translator.translate(state)
            if self.inner_eis is not None:
                try:
                    self.inner_eis.inject(update)
                except Exception as error:
                    LOGGER.warning(
                        "Lost the Nested Desktop EIS input: %s",
                        error,
                    )
                    self.inner_eis.close()
                    self.inner_eis = None
                    self.translator.set_active(False)
                    self.forwarding = False
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


class NestedDesktopMouseSupervisor:
    def __init__(
        self,
        plugin_root: str | Path,
        logger: logging.Logger,
        inertia_enabled: bool = True,
    ):
        self.plugin_root = Path(plugin_root)
        self.logger = logger
        self.inertia_enabled = inertia_enabled
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
        was_started = bool(
            self.thread is not None and self.thread.is_alive()
        )
        if was_started:
            self.stop()
        self.inertia_enabled = enabled
        if was_started:
            self.start()

    def _supervise(self):
        worker_path = self.plugin_root / Path(__file__).name
        python_executable = shutil.which("python3") or "/usr/bin/python3"
        while not self.stop_event.is_set():
            try:
                command = [
                    python_executable,
                    str(worker_path),
                    "--worker",
                ]
                if not self.inertia_enabled:
                    command.append("--no-inertia")
                process = subprocess.Popen(
                    command,
                    cwd=self.plugin_root,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    close_fds=True,
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
            self.logger.info("Started the Nested Desktop mouse bridge")
            while process.poll() is None and not self.stop_event.wait(0.5):
                pass
            if self.stop_event.is_set():
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                break
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


def run_worker(inertia_enabled: bool = True) -> int:
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
    )
    runtime.run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--no-inertia", action="store_true")
    arguments = parser.parse_args()
    if not arguments.worker:
        parser.error("--worker is required")
    return run_worker(inertia_enabled=not arguments.no_inertia)


if __name__ == "__main__":
    raise SystemExit(main())
