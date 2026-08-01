"""Low-level X11 definitions used by the clipboard bridge."""

from __future__ import annotations

import ctypes
import ctypes.util
from dataclasses import dataclass
import os
from pathlib import Path


X11_CURRENT_TIME = 0
X11_NONE = 0
X11_SUCCESS = 0
X11_PROP_MODE_REPLACE = 0
X11_PROP_MODE_APPEND = 2
X11_PROPERTY_NOTIFY = 28
X11_SELECTION_REQUEST = 30
X11_SELECTION_NOTIFY = 31
X11_EVENT_LONGS = 24
X11_PROPERTY_NEW_VALUE = 0
X11_PROPERTY_CHANGE_MASK = 1 << 22
XFIXES_SELECTION_NOTIFY_OFFSET = 0
XFIXES_SET_SELECTION_OWNER_NOTIFY_MASK = 1 << 0
PROPERTY_CHUNK_MAX_BYTES = 240 * 1024


@dataclass(frozen=True)
class PropertyValue:
    type_atom: int
    format: int
    bytes_value: bytes = b""
    atoms_value: tuple[int, ...] = ()


class XSelectionEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("requestor", ctypes.c_ulong),
        ("selection", ctypes.c_ulong),
        ("target", ctypes.c_ulong),
        ("property", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
    ]


class XSelectionRequestEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("owner", ctypes.c_ulong),
        ("requestor", ctypes.c_ulong),
        ("selection", ctypes.c_ulong),
        ("target", ctypes.c_ulong),
        ("property", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
    ]


class XPropertyEvent(ctypes.Structure):
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


class XFixesSelectionNotifyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("subtype", ctypes.c_int),
        ("owner", ctypes.c_ulong),
        ("selection", ctypes.c_ulong),
        ("timestamp", ctypes.c_ulong),
        ("selection_timestamp", ctypes.c_ulong),
    ]


def load_libraries() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    x11_name = ctypes.util.find_library("X11") or "libX11.so.6"
    xfixes_name = ctypes.util.find_library("Xfixes") or "libXfixes.so.3"
    x11 = ctypes.CDLL(x11_name)
    xfixes = ctypes.CDLL(xfixes_name)
    configure_libraries(x11, xfixes)
    return x11, xfixes


def configure_libraries(x11: ctypes.CDLL, xfixes: ctypes.CDLL):
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XConnectionNumber.argtypes = [ctypes.c_void_p]
    x11.XConnectionNumber.restype = ctypes.c_int
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XCreateSimpleWindow.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    x11.XCreateSimpleWindow.restype = ctypes.c_ulong
    x11.XSelectInput.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_long,
    ]
    x11.XSelectInput.restype = ctypes.c_int
    x11.XMaxRequestSize.argtypes = [ctypes.c_void_p]
    x11.XMaxRequestSize.restype = ctypes.c_long
    x11.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XDestroyWindow.restype = ctypes.c_int
    x11.XInternAtom.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XGetSelectionOwner.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    x11.XGetSelectionOwner.restype = ctypes.c_ulong
    x11.XSetSelectionOwner.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    x11.XSetSelectionOwner.restype = ctypes.c_int
    x11.XConvertSelection.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    x11.XConvertSelection.restype = ctypes.c_int
    x11.XChangeProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    x11.XChangeProperty.restype = ctypes.c_int
    x11.XGetWindowProperty.argtypes = [
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
    x11.XGetWindowProperty.restype = ctypes.c_int
    x11.XDeleteProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    x11.XDeleteProperty.restype = ctypes.c_int
    x11.XSendEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_long,
        ctypes.c_void_p,
    ]
    x11.XSendEvent.restype = ctypes.c_int
    x11.XPending.argtypes = [ctypes.c_void_p]
    x11.XPending.restype = ctypes.c_int
    x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    x11.XNextEvent.restype = ctypes.c_int
    x11.XFree.argtypes = [ctypes.c_void_p]
    x11.XFree.restype = ctypes.c_int
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XFlush.restype = ctypes.c_int
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    xfixes.XFixesQueryExtension.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
    ]
    xfixes.XFixesQueryExtension.restype = ctypes.c_int
    xfixes.XFixesSelectSelectionInput.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    xfixes.XFixesSelectSelectionInput.restype = None


def open_display(
    x11: ctypes.CDLL,
    display_name: str,
    xauthority: Path | None,
) -> int | None:
    previous_authority = os.environ.get("XAUTHORITY")
    try:
        if xauthority is None:
            os.environ.pop("XAUTHORITY", None)
        else:
            os.environ["XAUTHORITY"] = str(xauthority)
        return x11.XOpenDisplay(display_name.encode("ascii"))
    finally:
        if previous_authority is None:
            os.environ.pop("XAUTHORITY", None)
        else:
            os.environ["XAUTHORITY"] = previous_authority


def property_chunk_size(x11: ctypes.CDLL, display: int) -> int:
    request_words = int(x11.XMaxRequestSize(display))
    protocol_limit = max(4096, (request_words - 64) * 4)
    return min(PROPERTY_CHUNK_MAX_BYTES, protocol_limit)


def write_property_bytes(
    x11: ctypes.CDLL,
    display: int,
    chunk_size: int,
    requestor: int,
    property_atom: int,
    type_atom: int,
    payload: bytes,
):
    if not payload:
        x11.XChangeProperty(
            display,
            requestor,
            property_atom,
            type_atom,
            8,
            X11_PROP_MODE_REPLACE,
            None,
            0,
        )
        return
    for offset in range(0, len(payload), chunk_size):
        chunk = payload[offset:offset + chunk_size]
        buffer = ctypes.create_string_buffer(chunk)
        x11.XChangeProperty(
            display,
            requestor,
            property_atom,
            type_atom,
            8,
            X11_PROP_MODE_REPLACE if offset == 0 else X11_PROP_MODE_APPEND,
            ctypes.cast(buffer, ctypes.c_void_p),
            len(chunk),
        )
