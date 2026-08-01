"""Capture Gamescope pointer input without detaching XInput devices."""

from __future__ import annotations

import ctypes
import ctypes.util
from dataclasses import dataclass
import math
import time
from typing import Callable, Mapping

from .models import PointerUpdate


XI_ALL_DEVICES = 0
XI_MASTER_POINTER = 1
XI_BUTTON_PRESS = 4
XI_BUTTON_RELEASE = 5
XI_RAW_BUTTON_PRESS = 15
XI_RAW_BUTTON_RELEASE = 16
XI_RAW_MOTION = 17
XI_GRAB_MODE_ASYNC = 1
XI_GRAB_SUCCESS = 0
XI_EVENT_MASK_BYTES = 4
XI_SCROLL_V120 = 120
GENERIC_EVENT = 35
CURRENT_TIME = 0


class _XIEventMask(ctypes.Structure):
    _fields_ = [
        ("deviceid", ctypes.c_int),
        ("mask_len", ctypes.c_int),
        ("mask", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class _XIDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("deviceid", ctypes.c_int),
        ("name", ctypes.c_char_p),
        ("use", ctypes.c_int),
        ("attachment", ctypes.c_int),
        ("enabled", ctypes.c_int),
        ("num_classes", ctypes.c_int),
        ("classes", ctypes.c_void_p),
    ]


class _XIValuatorState(ctypes.Structure):
    _fields_ = [
        ("mask_len", ctypes.c_int),
        ("mask", ctypes.POINTER(ctypes.c_ubyte)),
        ("values", ctypes.POINTER(ctypes.c_double)),
    ]


class _XGenericEventCookie(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("extension", ctypes.c_int),
        ("evtype", ctypes.c_int),
        ("cookie", ctypes.c_uint),
        ("data", ctypes.c_void_p),
    ]


class _XIRawEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("extension", ctypes.c_int),
        ("evtype", ctypes.c_int),
        ("time", ctypes.c_ulong),
        ("deviceid", ctypes.c_int),
        ("sourceid", ctypes.c_int),
        ("detail", ctypes.c_int),
        ("flags", ctypes.c_int),
        ("valuators", _XIValuatorState),
        ("raw_values", ctypes.POINTER(ctypes.c_double)),
    ]


@dataclass(frozen=True, slots=True)
class CapturedPointerUpdate:
    received_at: float
    update: PointerUpdate


class GamescopePointerTranslator:
    """Translate XI2 raw pointer axes into the bridge's input model."""

    def __init__(self):
        self.motion_fraction_x = 0.0
        self.motion_fraction_y = 0.0
        self.scroll_fraction_x = 0.0
        self.scroll_fraction_y = 0.0
        self.pressed_buttons: set[int] = set()

    @staticmethod
    def _emit_integer(value: float) -> tuple[int, float]:
        emitted = math.trunc(value)
        return emitted, value - emitted

    def motion(self, axes: Mapping[int, float]) -> PointerUpdate:
        self.motion_fraction_x += float(axes.get(0, 0.0))
        self.motion_fraction_y += float(axes.get(1, 0.0))
        dx, self.motion_fraction_x = self._emit_integer(
            self.motion_fraction_x
        )
        dy, self.motion_fraction_y = self._emit_integer(
            self.motion_fraction_y
        )

        self.scroll_fraction_x += (
            float(axes.get(2, 0.0)) * XI_SCROLL_V120
        )
        self.scroll_fraction_y += (
            float(axes.get(3, 0.0)) * XI_SCROLL_V120
        )
        scroll_x, self.scroll_fraction_x = self._emit_integer(
            self.scroll_fraction_x
        )
        scroll_y, self.scroll_fraction_y = self._emit_integer(
            self.scroll_fraction_y
        )
        return PointerUpdate(
            dx=dx,
            dy=dy,
            scroll_discrete_x=scroll_x,
            scroll_discrete_y=scroll_y,
        )

    def button(self, detail: int, pressed: bool) -> PointerUpdate:
        # XI2 buttons 4-7 are legacy wheel aliases. Smooth and discrete
        # scrolling already arrives through valuator axes 2 and 3.
        field = {
            1: "left_button",
            2: "middle_button",
            3: "right_button",
        }.get(detail)
        if field is None:
            return PointerUpdate()
        if pressed:
            self.pressed_buttons.add(detail)
        else:
            self.pressed_buttons.discard(detail)
        return PointerUpdate(**{field: pressed})

    def release(self) -> PointerUpdate:
        update = PointerUpdate(
            left_button=False if 1 in self.pressed_buttons else None,
            middle_button=False if 2 in self.pressed_buttons else None,
            right_button=False if 3 in self.pressed_buttons else None,
        )
        self.pressed_buttons.clear()
        self.motion_fraction_x = 0.0
        self.motion_fraction_y = 0.0
        self.scroll_fraction_x = 0.0
        self.scroll_fraction_y = 0.0
        return update


class GamescopePointerCapture:
    """Actively grab the XI2 master pointer and expose its raw events."""

    def __init__(
        self,
        display_name: str,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.display_name = display_name
        self.clock = clock
        self.x11 = ctypes.CDLL(
            ctypes.util.find_library("X11") or "libX11.so.6"
        )
        self.xi = ctypes.CDLL(
            ctypes.util.find_library("Xi") or "libXi.so.6"
        )
        self._configure_libraries()
        self.display = self.x11.XOpenDisplay(display_name.encode("ascii"))
        if not self.display:
            raise RuntimeError(f"Cannot open X display {display_name}")
        self.root = self.x11.XDefaultRootWindow(self.display)
        self.master_pointer_id: int | None = None
        self.grabbed = False
        self.translator = GamescopePointerTranslator()

    def _configure_libraries(self):
        pointer = ctypes.c_void_p
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = pointer
        self.x11.XDefaultRootWindow.argtypes = [pointer]
        self.x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x11.XDefaultScreen.argtypes = [pointer]
        self.x11.XDefaultScreen.restype = ctypes.c_int
        self.x11.XDisplayWidth.argtypes = [pointer, ctypes.c_int]
        self.x11.XDisplayWidth.restype = ctypes.c_int
        self.x11.XDisplayHeight.argtypes = [pointer, ctypes.c_int]
        self.x11.XDisplayHeight.restype = ctypes.c_int
        self.x11.XQueryPointer.argtypes = [
            pointer,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint),
        ]
        self.x11.XQueryPointer.restype = ctypes.c_int
        self.x11.XConnectionNumber.argtypes = [pointer]
        self.x11.XConnectionNumber.restype = ctypes.c_int
        self.x11.XPending.argtypes = [pointer]
        self.x11.XPending.restype = ctypes.c_int
        self.x11.XNextEvent.argtypes = [pointer, pointer]
        self.x11.XNextEvent.restype = ctypes.c_int
        self.x11.XGetEventData.argtypes = [
            pointer,
            ctypes.POINTER(_XGenericEventCookie),
        ]
        self.x11.XGetEventData.restype = ctypes.c_int
        self.x11.XFreeEventData.argtypes = [
            pointer,
            ctypes.POINTER(_XGenericEventCookie),
        ]
        self.x11.XFlush.argtypes = [pointer]
        self.x11.XFlush.restype = ctypes.c_int
        self.x11.XCloseDisplay.argtypes = [pointer]
        self.x11.XCloseDisplay.restype = ctypes.c_int

        self.xi.XIQueryVersion.argtypes = [
            pointer,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.xi.XIQueryVersion.restype = ctypes.c_int
        self.xi.XIQueryDevice.argtypes = [
            pointer,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        self.xi.XIQueryDevice.restype = ctypes.POINTER(_XIDeviceInfo)
        self.xi.XIFreeDeviceInfo.argtypes = [
            ctypes.POINTER(_XIDeviceInfo)
        ]
        self.xi.XIGrabDevice.argtypes = [
            pointer,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(_XIEventMask),
        ]
        self.xi.XIGrabDevice.restype = ctypes.c_int
        self.xi.XIUngrabDevice.argtypes = [
            pointer,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        self.xi.XIUngrabDevice.restype = ctypes.c_int

    @staticmethod
    def _event_mask(device_id: int) -> tuple[_XIEventMask, object]:
        bits = (ctypes.c_ubyte * XI_EVENT_MASK_BYTES)()
        for event_type in (
            XI_RAW_BUTTON_PRESS,
            XI_RAW_BUTTON_RELEASE,
            XI_RAW_MOTION,
        ):
            bits[event_type >> 3] |= 1 << (event_type & 7)
        return _XIEventMask(device_id, len(bits), bits), bits

    def _find_master_pointer(self) -> int | None:
        count = ctypes.c_int()
        devices = self.xi.XIQueryDevice(
            self.display,
            XI_ALL_DEVICES,
            ctypes.byref(count),
        )
        if not devices:
            return None
        try:
            for index in range(count.value):
                device = devices[index]
                if device.enabled and device.use == XI_MASTER_POINTER:
                    return int(device.deviceid)
        finally:
            self.xi.XIFreeDeviceInfo(devices)
        return None

    def grab_pointer(self) -> bool:
        if self.grabbed:
            return True
        major = ctypes.c_int(2)
        minor = ctypes.c_int(0)
        if self.xi.XIQueryVersion(
            self.display,
            ctypes.byref(major),
            ctypes.byref(minor),
        ) != 0:
            return False
        device_id = self._find_master_pointer()
        if device_id is None:
            return False
        mask, _bits = self._event_mask(device_id)
        status = self.xi.XIGrabDevice(
            self.display,
            device_id,
            self.root,
            CURRENT_TIME,
            0,
            XI_GRAB_MODE_ASYNC,
            XI_GRAB_MODE_ASYNC,
            0,
            ctypes.byref(mask),
        )
        self.x11.XFlush(self.display)
        if status != XI_GRAB_SUCCESS:
            return False
        self.master_pointer_id = device_id
        self.grabbed = True
        return True

    def fileno(self) -> int:
        if not self.display:
            return -1
        return int(self.x11.XConnectionNumber(self.display))

    def pointer_snapshot(self) -> tuple[int, int, int, int] | None:
        """Return the root pointer position and display dimensions."""
        if not self.display:
            return None
        root = ctypes.c_ulong()
        child = ctypes.c_ulong()
        root_x = ctypes.c_int()
        root_y = ctypes.c_int()
        window_x = ctypes.c_int()
        window_y = ctypes.c_int()
        buttons = ctypes.c_uint()
        if not self.x11.XQueryPointer(
            self.display,
            self.root,
            ctypes.byref(root),
            ctypes.byref(child),
            ctypes.byref(root_x),
            ctypes.byref(root_y),
            ctypes.byref(window_x),
            ctypes.byref(window_y),
            ctypes.byref(buttons),
        ):
            return None
        screen = self.x11.XDefaultScreen(self.display)
        width = int(self.x11.XDisplayWidth(self.display, screen))
        height = int(self.x11.XDisplayHeight(self.display, screen))
        if width <= 0 or height <= 0:
            return None
        return root_x.value, root_y.value, width, height

    @staticmethod
    def _valuator_values(event: _XIRawEvent) -> dict[int, float]:
        state = event.valuators
        if (
            state.mask_len <= 0
            or not state.mask
            or not state.values
        ):
            return {}
        values: dict[int, float] = {}
        value_index = 0
        for axis in range(state.mask_len * 8):
            if not state.mask[axis >> 3] & (1 << (axis & 7)):
                continue
            values[axis] = float(state.values[value_index])
            value_index += 1
        return values

    def dispatch(self) -> tuple[CapturedPointerUpdate, ...]:
        if not self.display or not self.grabbed:
            return ()
        updates = []
        event_buffer = (ctypes.c_long * 24)()
        while self.x11.XPending(self.display) > 0:
            self.x11.XNextEvent(
                self.display,
                ctypes.byref(event_buffer),
            )
            cookie = ctypes.cast(
                ctypes.byref(event_buffer),
                ctypes.POINTER(_XGenericEventCookie),
            )
            if (
                cookie.contents.type != GENERIC_EVENT
                or not self.x11.XGetEventData(self.display, cookie)
            ):
                continue
            try:
                if not cookie.contents.data:
                    continue
                raw = ctypes.cast(
                    cookie.contents.data,
                    ctypes.POINTER(_XIRawEvent),
                ).contents
                if raw.evtype == XI_RAW_MOTION:
                    update = self.translator.motion(
                        self._valuator_values(raw)
                    )
                elif raw.evtype in (
                    XI_RAW_BUTTON_PRESS,
                    XI_RAW_BUTTON_RELEASE,
                ):
                    update = self.translator.button(
                        raw.detail,
                        raw.evtype == XI_RAW_BUTTON_PRESS,
                    )
                else:
                    continue
                if not update.empty:
                    updates.append(
                        CapturedPointerUpdate(self.clock(), update)
                    )
            finally:
                self.x11.XFreeEventData(self.display, cookie)
        return tuple(updates)

    def release_update(self) -> PointerUpdate:
        return self.translator.release()

    def ungrab_pointer(self):
        if not self.display or not self.grabbed:
            return
        device_id = self.master_pointer_id
        self.grabbed = False
        self.master_pointer_id = None
        if device_id is not None:
            self.xi.XIUngrabDevice(
                self.display,
                device_id,
                CURRENT_TIME,
            )
        self.x11.XFlush(self.display)

    def close(self):
        display = getattr(self, "display", None)
        if not display:
            return
        self.ungrab_pointer()
        self.display = None
        self.x11.XCloseDisplay(display)
