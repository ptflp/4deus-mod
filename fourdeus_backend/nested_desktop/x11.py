"""Minimal X11 property access for gamescope focus state."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
from pathlib import Path
from typing import Sequence

from .constants import (
    GAMESCOPE_FOCUS_EVENT_PROPERTIES, X11_EVENT_LONGS,
    X11_PROPERTY_CHANGE_MASK, X11_PROPERTY_NOTIFY,
)


class _XPropertyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("atom", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("state", ctypes.c_int),
    ]

class X11Connection:
    GRAB_SUCCESS = 0
    GRAB_MODE_ASYNC = 1
    CURRENT_TIME = 0

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
        self.focus_property_atoms = {
            atom
            for property_name in GAMESCOPE_FOCUS_EVENT_PROPERTIES
            for atom in (
                self.x11.XInternAtom(
                    self.display,
                    property_name.encode("ascii"),
                    1,
                ),
            )
            if atom != 0
        }
        self.x11.XSelectInput(
            self.display,
            self.root,
            X11_PROPERTY_CHANGE_MASK,
        )
        self.x11.XFlush(self.display)

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
        self.x11.XChangeProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
        ]
        self.x11.XChangeProperty.restype = ctypes.c_int
        self.x11.XSelectInput.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_long,
        ]
        self.x11.XSelectInput.restype = ctypes.c_int
        self.x11.XGrabPointer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self.x11.XGrabPointer.restype = ctypes.c_int
        self.x11.XUngrabPointer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self.x11.XUngrabPointer.restype = ctypes.c_int
        self.x11.XPending.argtypes = [ctypes.c_void_p]
        self.x11.XPending.restype = ctypes.c_int
        self.x11.XNextEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.x11.XNextEvent.restype = ctypes.c_int
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

    def set_cardinals(
        self,
        property_name: str,
        values: Sequence[int],
    ):
        atom = self.x11.XInternAtom(
            self.display,
            property_name.encode("ascii"),
            0,
        )
        cardinal_atom = self.x11.XInternAtom(
            self.display,
            b"CARDINAL",
            0,
        )
        if atom == 0 or cardinal_atom == 0:
            raise RuntimeError(
                f"Cannot create X11 property {property_name}"
            )
        payload = (ctypes.c_ulong * len(values))(
            *(int(value) & 0xFFFFFFFF for value in values)
        )
        self.x11.XChangeProperty(
            self.display,
            self.root,
            atom,
            cardinal_atom,
            32,
            0,
            ctypes.cast(
                payload,
                ctypes.POINTER(ctypes.c_ubyte),
            ),
            len(values),
        )
        self.x11.XFlush(self.display)

    def drain_property_events(self) -> bool:
        event = (ctypes.c_long * X11_EVENT_LONGS)()
        changed = False
        while self.x11.XPending(self.display) > 0:
            self.x11.XNextEvent(
                self.display,
                ctypes.byref(event),
            )
            property_event = ctypes.cast(
                ctypes.byref(event),
                ctypes.POINTER(_XPropertyEvent),
            ).contents
            changed = bool(
                changed
                or (
                    property_event.type == X11_PROPERTY_NOTIFY
                    and property_event.atom in self.focus_property_atoms
                )
            )
        return changed

    def grab_pointer(self) -> bool:
        """Exclusively consume pointer delivery without blocking keyboard."""
        status = self.x11.XGrabPointer(
            self.display,
            self.root,
            0,
            0,
            self.GRAB_MODE_ASYNC,
            self.GRAB_MODE_ASYNC,
            0,
            0,
            self.CURRENT_TIME,
        )
        self.x11.XFlush(self.display)
        return status == self.GRAB_SUCCESS

    def ungrab_pointer(self):
        self.x11.XUngrabPointer(
            self.display,
            self.CURRENT_TIME,
        )
        self.x11.XFlush(self.display)

    def close(self):
        display = getattr(self, "display", None)
        if display:
            self.display = None
            self.x11.XCloseDisplay(display)
