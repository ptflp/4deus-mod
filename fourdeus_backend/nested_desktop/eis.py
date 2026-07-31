"""KWin EIS/libei input injection connection."""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
import select
import time

from .constants import (
    BTN_LEFT, BTN_MIDDLE, BTN_RIGHT, EI_DEVICE_CAP_BUTTON,
    EI_DEVICE_CAP_KEYBOARD, EI_DEVICE_CAP_POINTER,
    EI_DEVICE_CAP_POINTER_ABSOLUTE, EI_DEVICE_CAP_SCROLL,
    EI_DEVICE_CAP_TOUCH,
    EI_EVENT_DEVICE_ADDED, EI_EVENT_DEVICE_PAUSED,
    EI_EVENT_DEVICE_REMOVED, EI_EVENT_DEVICE_RESUMED,
    EI_EVENT_DISCONNECT, EI_EVENT_SEAT_ADDED, KEYBOARD_DEVICE_GRACE,
    KEYBOARD_PORTAL_CAPABILITY, POINTER_PORTAL_CAPABILITY,
    TOUCH_PORTAL_CAPABILITY,
)
from .models import PointerUpdate, TouchUpdate


LOGGER = logging.getLogger("4deus-nested-mouse")


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
        self.touch_device = None
        self.ready = False
        self.absolute_ready = False
        self.keyboard_ready = False
        self.touch_ready = False
        self.emulating = False
        self.absolute_emulating = False
        self.keyboard_emulating = False
        self.touch_emulating = False
        self.active_touches = {}
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
                    | TOUCH_PORTAL_CAPABILITY
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
        self.lib.ei_device_touch_new.argtypes = [pointer]
        self.lib.ei_device_touch_new.restype = pointer
        self.lib.ei_touch_down.argtypes = [
            pointer,
            ctypes.c_double,
            ctypes.c_double,
        ]
        self.lib.ei_touch_motion.argtypes = [
            pointer,
            ctypes.c_double,
            ctypes.c_double,
        ]
        self.lib.ei_touch_up.argtypes = [pointer]
        self.lib.ei_touch_unref.argtypes = [pointer]
        self.lib.ei_touch_unref.restype = pointer
        self.lib.ei_device_scroll_delta.argtypes = [
            pointer,
            ctypes.c_double,
            ctypes.c_double,
        ]
        self.lib.ei_device_scroll_discrete.argtypes = [
            pointer,
            ctypes.c_int32,
            ctypes.c_int32,
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
                ctypes.c_int(EI_DEVICE_CAP_TOUCH),
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
            if (
                self.touch_device is None
                and self.lib.ei_device_has_capability(
                    candidate,
                    EI_DEVICE_CAP_TOUCH,
                )
            ):
                self.touch_device = self.lib.ei_device_ref(candidate)
            return
        event_device = self.lib.ei_event_get_device(event)
        if event_type == EI_EVENT_DEVICE_RESUMED:
            if event_device == self.pointer_device:
                self.ready = True
            if event_device == self.absolute_pointer_device:
                self.absolute_ready = True
            if event_device == self.keyboard_device:
                self.keyboard_ready = True
            if event_device == self.touch_device:
                self.touch_ready = True
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
            if event_device == self.touch_device:
                self.touch_ready = False
                self.touch_emulating = False
                self._release_active_touches(send_up=False)
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
            if event_device == self.touch_device:
                self.touch_ready = False
                self.touch_emulating = False
                self._release_active_touches(send_up=False)
                self.touch_device = self.lib.ei_device_unref(
                    self.touch_device
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

    def set_touch_emulating(self, active: bool) -> bool:
        self.dispatch()
        if active == self.touch_emulating:
            return self.touch_ready
        device = self.touch_device
        if active:
            if not self.touch_ready or device is None:
                return False
            if not self._device_emulating_elsewhere(device, "touch"):
                self._start_emulating(device)
            self.touch_emulating = True
        elif device is not None:
            self._release_active_touches(send_up=True)
            self.touch_emulating = False
            if not self._device_emulating_elsewhere(device, "touch"):
                self.lib.ei_device_stop_emulating(device)
        self.lib.ei_dispatch(self.ei)
        return self.touch_ready

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
                (self.touch_device, self.touch_emulating, "touch"),
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
        if update.scroll_discrete_x or update.scroll_discrete_y:
            self.lib.ei_device_scroll_discrete(
                self.pointer_device,
                update.scroll_discrete_x,
                update.scroll_discrete_y,
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

    def _device_bounds(
        self,
        device,
    ) -> tuple[int, int, int, int] | None:
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

    def absolute_bounds(self) -> tuple[int, int, int, int] | None:
        return self._device_bounds(self.absolute_pointer_device)

    def touch_bounds(self) -> tuple[int, int, int, int] | None:
        return self._device_bounds(self.touch_device)

    @staticmethod
    def _touch_coordinate(
        normalized: float,
        start: int,
        size: int,
    ) -> float:
        value = max(0.0, min(1.0, normalized))
        return float(start) + value * max(0, size - 1)

    def inject_touch(self, updates: tuple[TouchUpdate, ...]):
        device = self.touch_device
        bounds = self.touch_bounds()
        if (
            not updates
            or not self.touch_ready
            or not self.touch_emulating
            or device is None
            or bounds is None
        ):
            return
        origin_x, origin_y, width, height = bounds
        emitted = False
        for update in updates:
            touch = self.active_touches.get(update.contact_id)
            if (
                update.phase == "down"
                and update.x is not None
                and update.y is not None
            ):
                if touch is not None:
                    continue
                touch = self.lib.ei_device_touch_new(device)
                if not touch:
                    continue
                self.lib.ei_touch_down(
                    touch,
                    self._touch_coordinate(update.x, origin_x, width),
                    self._touch_coordinate(update.y, origin_y, height),
                )
                self.active_touches[update.contact_id] = touch
                emitted = True
            elif (
                update.phase == "motion"
                and touch is not None
                and update.x is not None
                and update.y is not None
            ):
                self.lib.ei_touch_motion(
                    touch,
                    self._touch_coordinate(update.x, origin_x, width),
                    self._touch_coordinate(update.y, origin_y, height),
                )
                emitted = True
            elif update.phase == "up" and touch is not None:
                self.lib.ei_touch_up(touch)
                self.lib.ei_touch_unref(touch)
                self.active_touches.pop(update.contact_id, None)
                emitted = True
        if emitted:
            self.lib.ei_device_frame(device, self.lib.ei_now(self.ei))
            self.lib.ei_dispatch(self.ei)

    def _release_active_touches(self, *, send_up: bool):
        device = self.touch_device
        touches = tuple(self.active_touches.values())
        self.active_touches.clear()
        for touch in touches:
            if send_up:
                self.lib.ei_touch_up(touch)
            self.lib.ei_touch_unref(touch)
        if send_up and touches and device is not None and self.ei is not None:
            self.lib.ei_device_frame(device, self.lib.ei_now(self.ei))

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
                self._release_active_touches(
                    send_up=(
                        self.touch_ready
                        and self.touch_emulating
                    )
                )
                active_devices = {
                    device
                    for device, active in (
                        (self.pointer_device, self.emulating),
                        (
                            self.absolute_pointer_device,
                            self.absolute_emulating,
                        ),
                        (self.keyboard_device, self.keyboard_emulating),
                        (self.touch_device, self.touch_emulating),
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
            if self.touch_device is not None:
                self.touch_device = self.lib.ei_device_unref(
                    self.touch_device
                )
            self.ei = self.lib.ei_unref(self.ei)
        self.ready = False
        self.absolute_ready = False
        self.keyboard_ready = False
        self.touch_ready = False
        self.emulating = False
        self.absolute_emulating = False
        self.keyboard_emulating = False
        self.touch_emulating = False
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
