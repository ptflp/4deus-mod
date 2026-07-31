"""Event-driven text, image, and file clipboard sharing."""

from __future__ import annotations

import ctypes
from collections import deque
import logging
from pathlib import Path
import time
from typing import Callable, Iterable

from .clipboard_content import (
    ClipboardContent,
    PendingClipboardContent as _PendingClipboardContent,
    encode_file_uri_list,
    encode_gnome_copied_files,
    normalize_file_uris,
    parse_file_uri_list,
)
from .clipboard_x11 import (
    PropertyValue as _PropertyValue,
    X11_CURRENT_TIME,
    X11_EVENT_LONGS,
    X11_NONE,
    X11_PROPERTY_CHANGE_MASK,
    X11_PROPERTY_NEW_VALUE,
    X11_PROPERTY_NOTIFY,
    X11_PROP_MODE_REPLACE,
    X11_SELECTION_NOTIFY,
    X11_SELECTION_REQUEST,
    X11_SUCCESS,
    XFixesSelectionNotifyEvent as _XFixesSelectionNotifyEvent,
    XPropertyEvent as _XPropertyEvent,
    XSelectionEvent as _XSelectionEvent,
    XSelectionRequestEvent as _XSelectionRequestEvent,
    XFIXES_SELECTION_NOTIFY_OFFSET,
    XFIXES_SET_SELECTION_OWNER_NOTIFY_MASK,
    load_libraries,
    open_display,
    property_chunk_size,
    write_property_bytes,
)


LOGGER = logging.getLogger("4deus-nested-mouse")

CLIPBOARD_REQUEST_TIMEOUT = 5.0
CLIPBOARD_TEXT_MAX_BYTES = 4 * 1024 * 1024
CLIPBOARD_MAX_BYTES = 64 * 1024 * 1024
CLIPBOARD_TARGETS_MAX_BYTES = 64 * 1024
CLIPBOARD_FILE_LIST_MAX_BYTES = 1024 * 1024
CLIPBOARD_IMAGE_MIME_TYPES = (
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/bmp",
)


class X11ClipboardEndpoint:
    """Own, serve, and observe one X11 clipboard selection."""

    def __init__(
        self,
        display_name: str,
        xauthority: Path | None = None,
        *,
        selection_name: str = "CLIPBOARD",
        max_bytes: int = CLIPBOARD_MAX_BYTES,
        max_text_bytes: int = CLIPBOARD_TEXT_MAX_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.display_name = display_name
        self.max_bytes = max_bytes
        self.max_text_bytes = min(max_text_bytes, max_bytes)
        self.clock = clock
        self.content = ClipboardContent()
        self.text: str | None = None
        self.initialized = False
        self.request_pending = False
        self.request_again = False
        self.discard_pending = False
        self.request_deadline = 0.0
        self.pending_target: int | None = None
        self.pending_targets: deque[int] = deque()
        self.pending_content = _PendingClipboardContent()
        self.incremental_buffer: bytearray | None = None
        self.incremental_discard = False

        self.x11, self.xfixes = load_libraries()
        self.display = open_display(self.x11, display_name, xauthority)
        if not self.display:
            raise RuntimeError(f"Cannot open X display {display_name}")
        try:
            self.root = self.x11.XDefaultRootWindow(self.display)
            self.window = self.x11.XCreateSimpleWindow(
                self.display,
                self.root,
                -10,
                -10,
                1,
                1,
                0,
                0,
                0,
            )
            if not self.window:
                raise RuntimeError(
                    f"Cannot create clipboard window on {display_name}"
                )
            self.selection = self._atom(selection_name)
            self.targets = self._atom("TARGETS")
            self.atom_type = self._atom("ATOM")
            self.utf8 = self._atom("UTF8_STRING")
            self.text_target = self._atom("TEXT")
            self.string = self._atom("STRING")
            self.incr = self._atom("INCR")
            self.text_plain = self._atom("text/plain")
            self.text_plain_utf8 = self._atom(
                "text/plain;charset=utf-8"
            )
            self.uri_list = self._atom("text/uri-list")
            self.gnome_copied_files = self._atom(
                "x-special/gnome-copied-files"
            )
            self.kde_cut_selection = self._atom(
                "application/x-kde-cutselection"
            )
            self.file_targets = {
                self.uri_list,
                self.gnome_copied_files,
            }
            self.preferred_file_targets = (
                self.uri_list,
                self.gnome_copied_files,
            )
            self.image_atoms = {
                mime: self._atom(mime)
                for mime in CLIPBOARD_IMAGE_MIME_TYPES
            }
            self.image_mimes_by_atom = {
                atom: mime for mime, atom in self.image_atoms.items()
            }
            self.property = self._atom("_4DEUS_CLIPBOARD_DATA")
            self.supported_text_targets = {
                self.utf8,
                self.text_target,
                self.string,
                self.text_plain,
                self.text_plain_utf8,
            }
            self.preferred_text_targets = (
                self.utf8,
                self.text_plain_utf8,
                self.text_plain,
                self.text_target,
                self.string,
            )
            self.property_chunk_bytes = property_chunk_size(
                self.x11,
                self.display,
            )
            self.x11.XSelectInput(
                self.display,
                self.window,
                X11_PROPERTY_CHANGE_MASK,
            )
            event_base = ctypes.c_int()
            error_base = ctypes.c_int()
            if not self.xfixes.XFixesQueryExtension(
                self.display,
                ctypes.byref(event_base),
                ctypes.byref(error_base),
            ):
                raise RuntimeError(
                    f"XFixes is unavailable on {display_name}"
                )
            self.xfixes_event = event_base.value
            self.xfixes.XFixesSelectSelectionInput(
                self.display,
                self.root,
                self.selection,
                XFIXES_SET_SELECTION_OWNER_NOTIFY_MASK,
            )
            self.x11.XFlush(self.display)
            self._request_current()
        except Exception:
            self.close()
            raise

    def _atom(self, name: str) -> int:
        atom = self.x11.XInternAtom(
            self.display,
            name.encode("ascii"),
            0,
        )
        if atom == 0:
            raise RuntimeError(
                f"Cannot create X11 atom {name} on {self.display_name}"
            )
        return int(atom)

    def _request_current(self):
        owner = self.x11.XGetSelectionOwner(
            self.display,
            self.selection,
        )
        if owner == X11_NONE:
            self.initialized = True
            self.request_pending = False
            self.request_again = False
            self.discard_pending = False
            self.pending_target = None
            self.pending_targets.clear()
            self.pending_content = _PendingClipboardContent()
            self.incremental_buffer = None
            self.incremental_discard = False
            self.content = ClipboardContent()
            self.text = None
            return
        if owner == self.window:
            return
        if self.request_pending:
            self.request_again = True
            self.discard_pending = True
            return
        self.request_pending = True
        self.pending_targets.clear()
        self.pending_content = _PendingClipboardContent()
        self.incremental_buffer = None
        self.incremental_discard = False
        self._request_target(self.targets)

    def _request_target(self, target: int):
        self.x11.XDeleteProperty(
            self.display,
            self.window,
            self.property,
        )
        self.x11.XConvertSelection(
            self.display,
            self.selection,
            target,
            self.property,
            self.window,
            X11_CURRENT_TIME,
        )
        self.pending_target = target
        self.request_deadline = self.clock() + CLIPBOARD_REQUEST_TIMEOUT
        self.x11.XFlush(self.display)

    def _target_limit(self, target: int | None) -> int:
        if target == self.targets:
            return CLIPBOARD_TARGETS_MAX_BYTES
        if target in self.file_targets:
            return CLIPBOARD_FILE_LIST_MAX_BYTES
        if target in self.image_mimes_by_atom:
            return self.max_bytes
        return self.max_text_bytes

    def _read_property(
        self,
        property_atom: int,
        max_bytes: int,
    ) -> _PropertyValue | None:
        if property_atom == X11_NONE:
            return None
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        item_count = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        value = ctypes.POINTER(ctypes.c_ubyte)()
        status = self.x11.XGetWindowProperty(
            self.display,
            self.window,
            property_atom,
            0,
            max(1, (max_bytes + 3) // 4),
            1,
            0,
            ctypes.byref(actual_type),
            ctypes.byref(actual_format),
            ctypes.byref(item_count),
            ctypes.byref(bytes_after),
            ctypes.byref(value),
        )
        if status != X11_SUCCESS:
            return None
        try:
            if bytes_after.value != 0:
                self.x11.XDeleteProperty(
                    self.display,
                    self.window,
                    property_atom,
                )
                self.x11.XFlush(self.display)
                return None
            value_format = int(actual_format.value)
            item_count_value = int(item_count.value)
            if value_format == 8:
                if item_count_value > max_bytes:
                    return None
                payload = (
                    ctypes.string_at(value, item_count_value)
                    if value
                    else b""
                )
                return _PropertyValue(
                    type_atom=int(actual_type.value),
                    format=value_format,
                    bytes_value=payload,
                )
            if value_format == 32:
                if item_count_value * 4 > max_bytes:
                    return None
                atoms = (
                    tuple(
                        int(item)
                        for item in ctypes.cast(
                            value,
                            ctypes.POINTER(ctypes.c_ulong),
                        )[:item_count_value]
                    )
                    if value
                    else ()
                )
                return _PropertyValue(
                    type_atom=int(actual_type.value),
                    format=value_format,
                    atoms_value=atoms,
                )
            return None
        finally:
            if value:
                self.x11.XFree(value)

    def _supported_targets(self, offered: Iterable[int]) -> deque[int]:
        offered_targets = set(offered)
        selected: deque[int] = deque()
        for file_target in self.preferred_file_targets:
            if file_target in offered_targets:
                selected.append(file_target)
                break
        for mime in CLIPBOARD_IMAGE_MIME_TYPES:
            image_target = self.image_atoms[mime]
            if image_target in offered_targets:
                selected.append(image_target)
                break
        for text_target in self.preferred_text_targets:
            if text_target in offered_targets:
                selected.append(text_target)
                break
        return selected

    def _consume_target(
        self,
        target: int,
        value: _PropertyValue | None,
    ) -> list[ClipboardContent]:
        if target == self.targets:
            if value is None:
                self.pending_targets = deque((self.utf8,))
            elif value.format == 32:
                self.pending_targets = self._supported_targets(
                    value.atoms_value
                )
        elif (
            target in self.file_targets
            and value is not None
            and value.format == 8
        ):
            self.pending_content.file_uris = parse_file_uri_list(
                value.bytes_value
            )
        elif (
            target in self.image_mimes_by_atom
            and value is not None
            and value.format == 8
        ):
            self.pending_content.image_mime = (
                self.image_mimes_by_atom[target]
            )
            self.pending_content.image = value.bytes_value
        elif (
            target in self.supported_text_targets
            and value is not None
            and value.format == 8
        ):
            encoding = "latin-1" if target == self.string else "utf-8"
            self.pending_content.text = value.bytes_value.rstrip(
                b"\0"
            ).decode(encoding, errors="replace")

        if self.pending_targets:
            self._request_target(self.pending_targets.popleft())
            return []
        return self._complete_request()

    def _complete_request(self) -> list[ClipboardContent]:
        self.request_pending = False
        self.request_deadline = 0.0
        self.pending_target = None
        self.pending_targets.clear()
        self.incremental_buffer = None
        self.incremental_discard = False
        content = self.pending_content.freeze()
        self.pending_content = _PendingClipboardContent()
        updates: list[ClipboardContent] = []
        if self.discard_pending:
            self.discard_pending = False
        elif not self.initialized:
            self.initialized = True
            self.content = content
            self.text = content.text
        else:
            changed = content != self.content
            self.content = content
            self.text = content.text
            if changed and content.available:
                updates.append(content)
        request_again = self.request_again
        self.request_again = False
        if request_again:
            self._request_current()
        return updates

    def _begin_incremental_receive(self):
        self.incremental_buffer = bytearray()
        self.incremental_discard = False
        self.request_deadline = self.clock() + CLIPBOARD_REQUEST_TIMEOUT
        self.x11.XFlush(self.display)

    def _handle_incremental_property(
        self,
        notification: _XPropertyEvent,
    ) -> list[ClipboardContent]:
        target = self.pending_target
        if (
            self.incremental_buffer is None
            or target is None
            or notification.window != self.window
            or notification.atom != self.property
            or notification.state != X11_PROPERTY_NEW_VALUE
        ):
            return []
        value = self._read_property(
            self.property,
            self._target_limit(target),
        )
        self.x11.XFlush(self.display)
        if value is None or value.format != 8:
            self.incremental_discard = True
            self.request_deadline = self.clock() + CLIPBOARD_REQUEST_TIMEOUT
            return []
        chunk = value.bytes_value
        if not chunk:
            payload = None
            if not self.incremental_discard:
                payload = _PropertyValue(
                    type_atom=value.type_atom,
                    format=8,
                    bytes_value=bytes(self.incremental_buffer),
                )
            self.incremental_buffer = None
            self.incremental_discard = False
            return self._consume_target(target, payload)
        if (
            not self.incremental_discard
            and len(self.incremental_buffer) + len(chunk)
            <= self._target_limit(target)
        ):
            self.incremental_buffer.extend(chunk)
        else:
            self.incremental_discard = True
            self.incremental_buffer.clear()
        self.request_deadline = self.clock() + CLIPBOARD_REQUEST_TIMEOUT
        return []

    def _handle_selection_notify(
        self,
        notification: _XSelectionEvent,
    ) -> list[ClipboardContent]:
        target = self.pending_target
        if (
            not self.request_pending
            or target is None
            or notification.requestor != self.window
            or notification.selection != self.selection
        ):
            return []
        value = self._read_property(
            notification.property,
            self._target_limit(target),
        )
        if value is not None and value.type_atom == self.incr:
            self._begin_incremental_receive()
            return []
        return self._consume_target(target, value)

    def _write_property_bytes(
        self,
        requestor: int,
        property_atom: int,
        type_atom: int,
        payload: bytes,
    ):
        write_property_bytes(
            self.x11,
            self.display,
            self.property_chunk_bytes,
            requestor,
            property_atom,
            type_atom,
            payload,
        )

    def _respond_to_request(self, request: _XSelectionRequestEvent):
        response = _XSelectionEvent()
        response.type = X11_SELECTION_NOTIFY
        response.display = self.display
        response.requestor = request.requestor
        response.selection = request.selection
        response.target = request.target
        response.property = X11_NONE
        response.time = request.time
        property_atom = request.property or request.target
        content = self.content

        if request.selection == self.selection and content.available:
            if request.target == self.targets:
                available_targets = {self.targets}
                if content.text is not None:
                    available_targets.update(self.supported_text_targets)
                if (
                    content.image is not None
                    and content.image_mime in self.image_atoms
                ):
                    available_targets.add(
                        self.image_atoms[content.image_mime]
                    )
                if content.file_uris:
                    available_targets.update(self.file_targets)
                    available_targets.add(self.kde_cut_selection)
                targets = (ctypes.c_ulong * len(available_targets))(
                    *sorted(available_targets)
                )
                self.x11.XChangeProperty(
                    self.display,
                    request.requestor,
                    property_atom,
                    self.atom_type,
                    32,
                    X11_PROP_MODE_REPLACE,
                    ctypes.cast(targets, ctypes.c_void_p),
                    len(targets),
                )
                response.property = property_atom
            elif content.file_uris and request.target == self.uri_list:
                self._write_property_bytes(
                    request.requestor,
                    property_atom,
                    request.target,
                    encode_file_uri_list(content.file_uris),
                )
                response.property = property_atom
            elif (
                content.file_uris
                and request.target == self.gnome_copied_files
            ):
                self._write_property_bytes(
                    request.requestor,
                    property_atom,
                    request.target,
                    encode_gnome_copied_files(content.file_uris),
                )
                response.property = property_atom
            elif (
                content.file_uris
                and request.target == self.kde_cut_selection
            ):
                self._write_property_bytes(
                    request.requestor,
                    property_atom,
                    request.target,
                    b"0",
                )
                response.property = property_atom
            elif (
                content.image is not None
                and content.image_mime in self.image_atoms
                and request.target == self.image_atoms[content.image_mime]
            ):
                self._write_property_bytes(
                    request.requestor,
                    property_atom,
                    request.target,
                    content.image,
                )
                response.property = property_atom
            elif (
                content.text is not None
                and request.target in self.supported_text_targets
            ):
                if request.target == self.string:
                    payload = content.text.encode(
                        "latin-1",
                        errors="replace",
                    )
                else:
                    payload = content.text.encode("utf-8")
                self._write_property_bytes(
                    request.requestor,
                    property_atom,
                    request.target,
                    payload,
                )
                response.property = property_atom

        self.x11.XSendEvent(
            self.display,
            request.requestor,
            0,
            0,
            ctypes.byref(response),
        )
        self.x11.XFlush(self.display)

    def dispatch(self) -> list[ClipboardContent]:
        updates: list[ClipboardContent] = []
        event = (ctypes.c_long * X11_EVENT_LONGS)()
        while self.display and self.x11.XPending(self.display) > 0:
            self.x11.XNextEvent(
                self.display,
                ctypes.byref(event),
            )
            event_type = ctypes.cast(
                ctypes.byref(event),
                ctypes.POINTER(ctypes.c_int),
            ).contents.value
            if event_type == X11_SELECTION_REQUEST:
                request = ctypes.cast(
                    ctypes.byref(event),
                    ctypes.POINTER(_XSelectionRequestEvent),
                ).contents
                self._respond_to_request(request)
            elif event_type == X11_SELECTION_NOTIFY:
                notification = ctypes.cast(
                    ctypes.byref(event),
                    ctypes.POINTER(_XSelectionEvent),
                ).contents
                updates.extend(
                    self._handle_selection_notify(notification)
                )
            elif event_type == X11_PROPERTY_NOTIFY:
                notification = ctypes.cast(
                    ctypes.byref(event),
                    ctypes.POINTER(_XPropertyEvent),
                ).contents
                updates.extend(
                    self._handle_incremental_property(notification)
                )
            elif event_type == (
                self.xfixes_event + XFIXES_SELECTION_NOTIFY_OFFSET
            ):
                notification = ctypes.cast(
                    ctypes.byref(event),
                    ctypes.POINTER(_XFixesSelectionNotifyEvent),
                ).contents
                if (
                    notification.selection == self.selection
                    and notification.owner != self.window
                ):
                    self._request_current()

        if (
            self.request_pending
            and self.clock() >= self.request_deadline
        ):
            target = self.pending_target
            self.incremental_buffer = None
            self.incremental_discard = False
            if target is not None:
                updates.extend(self._consume_target(target, None))
        return updates

    def _normalize_content(
        self,
        content: ClipboardContent,
    ) -> ClipboardContent:
        text = content.text if isinstance(content.text, str) else None
        if (
            text is not None
            and len(text.encode("utf-8")) > self.max_text_bytes
        ):
            LOGGER.warning(
                "Clipboard text exceeds the %s-byte sharing limit",
                self.max_text_bytes,
            )
            text = None
        image = content.image if isinstance(content.image, bytes) else None
        image_mime = (
            content.image_mime
            if content.image_mime in self.image_atoms
            else None
        )
        if image is not None and len(image) > self.max_bytes:
            LOGGER.warning(
                "Clipboard image exceeds the %s-byte sharing limit",
                self.max_bytes,
            )
            image = None
        if not image or image_mime is None:
            image = None
            image_mime = None
        file_uris = normalize_file_uris(content.file_uris)
        if (
            file_uris
            and len(encode_file_uri_list(file_uris))
            > CLIPBOARD_FILE_LIST_MAX_BYTES
        ):
            LOGGER.warning(
                "Clipboard file list exceeds the %s-byte sharing limit",
                CLIPBOARD_FILE_LIST_MAX_BYTES,
            )
            file_uris = ()
        return ClipboardContent(
            text=text,
            image_mime=image_mime,
            image=image,
            file_uris=file_uris,
        )

    def set_content(self, content: ClipboardContent) -> bool:
        normalized = self._normalize_content(content)
        if not normalized.available:
            return False
        if self.request_pending:
            self.discard_pending = True
        self.content = normalized
        self.text = normalized.text
        self.initialized = True
        self.x11.XSetSelectionOwner(
            self.display,
            self.selection,
            self.window,
            X11_CURRENT_TIME,
        )
        self.x11.XFlush(self.display)
        return self.x11.XGetSelectionOwner(
            self.display,
            self.selection,
        ) == self.window

    def set_text(self, text: str) -> bool:
        return self.set_content(ClipboardContent(text=text))

    def close(self):
        display = getattr(self, "display", None)
        if not display:
            return
        self.display = None
        window = getattr(self, "window", None)
        if window:
            self.window = None
            self.x11.XDestroyWindow(display, window)
        self.x11.XCloseDisplay(display)
