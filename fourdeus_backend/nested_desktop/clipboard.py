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
    PLATFORM_FILE_MIME_TYPES,
    normalize_content,
    parse_file_uri_list,
)
from .clipboard_owner import X11ClipboardOwnerMixin
from .clipboard_x11 import (
    PropertyValue as _PropertyValue,
    X11_CURRENT_TIME,
    X11_EVENT_LONGS,
    X11_NONE,
    X11_PROPERTY_CHANGE_MASK,
    X11_PROPERTY_NEW_VALUE,
    X11_PROPERTY_NOTIFY,
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
)
LOGGER = logging.getLogger("4deus-nested-mouse")
CLIPBOARD_REQUEST_TIMEOUT = 5.0
CLIPBOARD_OWNER_HANDOFF_TIMEOUT = 0.1
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
CLIPBOARD_PLATFORM_FILE_MIME_TYPES = PLATFORM_FILE_MIME_TYPES
class X11ClipboardEndpoint(X11ClipboardOwnerMixin):
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
        self.connection_fd = int(
            self.x11.XConnectionNumber(self.display)
        )
        try:
            self.root = self.x11.XDefaultRootWindow(self.display)
            self.window = self._create_window()
            if not self.window:
                raise RuntimeError(
                    f"Cannot create clipboard window on {display_name}"
                )
            self.owner_window = self.window
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
            self.kde_uri_list = self._atom("application/x-kde4-urilist")
            self.kde_cut_selection = self._atom(
                "application/x-kde-cutselection"
            )
            self.file_targets = {
                self.uri_list,
                self.gnome_copied_files,
                self.kde_uri_list,
            }
            self.preferred_file_targets = (
                self.uri_list,
                self.kde_uri_list,
                self.gnome_copied_files,
            )
            self.platform_file_atoms = {
                mime: self._atom(mime)
                for mime in CLIPBOARD_PLATFORM_FILE_MIME_TYPES
            }
            self.platform_file_mimes_by_atom = {
                atom: mime for mime, atom in self.platform_file_atoms.items()
            }
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
    def _create_window(self) -> int:
        return int(self.x11.XCreateSimpleWindow(
            self.display,
            self.root,
            -10,
            -10,
            1,
            1,
            0,
            0,
            0,
        ))

    def _rotate_request_window(self):
        new_window = self._create_window()
        if not new_window:
            raise RuntimeError(f"Cannot rotate clipboard window on {self.display_name}")
        self.x11.XSelectInput(
            self.display,
            new_window,
            X11_PROPERTY_CHANGE_MASK,
        )
        previous_window = self.window
        self.window = new_window
        if self.owner_window == previous_window:
            self.owner_window = new_window
        if previous_window:
            self.x11.XDestroyWindow(self.display, previous_window)
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
        if owner == self.owner_window:
            return
        if self.request_pending:
            self.request_again = True
            self.discard_pending = True
            self.request_deadline = min(
                self.request_deadline,
                self.clock() + CLIPBOARD_OWNER_HANDOFF_TIMEOUT,
            )
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
        if (
            target in self.file_targets
            or target in self.platform_file_mimes_by_atom
        ):
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
        for mime in CLIPBOARD_PLATFORM_FILE_MIME_TYPES:
            platform_target = self.platform_file_atoms.get(mime)
            if (
                platform_target is not None
                and platform_target in offered_targets
            ):
                selected.append(platform_target)
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
            target in self.platform_file_mimes_by_atom
            and value is not None
            and value.format == 8
        ):
            self.pending_content.platform_file_formats[
                self.platform_file_mimes_by_atom[target]
            ] = value.bytes_value
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
                    and notification.owner != self.owner_window
                ):
                    self._request_current()

        if (
            self.request_pending
            and self.clock() >= self.request_deadline
        ):
            if self.request_again:
                updates.extend(self._complete_request())
            else:
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
        return normalize_content(
            content,
            image_mimes=self.image_atoms,
            max_bytes=self.max_bytes,
            max_text_bytes=self.max_text_bytes,
            max_file_list_bytes=CLIPBOARD_FILE_LIST_MAX_BYTES,
            platform_file_mimes=CLIPBOARD_PLATFORM_FILE_MIME_TYPES,
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
        new_owner = self._create_window()
        if not new_owner:
            return False
        self.x11.XSetSelectionOwner(
            self.display,
            self.selection,
            new_owner,
            X11_CURRENT_TIME,
        )
        self.x11.XFlush(self.display)
        owns_selection = self.x11.XGetSelectionOwner(
            self.display,
            self.selection,
        ) == new_owner
        if not owns_selection:
            self.x11.XDestroyWindow(self.display, new_owner)
            return False
        previous_owner = self.owner_window
        self.owner_window = new_owner
        if previous_owner and previous_owner != self.window:
            self.x11.XDestroyWindow(self.display, previous_owner)
        return True

    def set_text(self, text: str) -> bool:
        return self.set_content(ClipboardContent(text=text))

    def fileno(self) -> int:
        """Return the X11 socket used for event-driven clipboard wakeups."""
        return int(getattr(self, "connection_fd", -1))

    def close(self):
        display = getattr(self, "display", None)
        if not display:
            return
        self.display = None
        self.connection_fd = -1
        window = getattr(self, "window", None)
        owner_window = getattr(self, "owner_window", None)
        self.owner_window = None
        if owner_window and owner_window != window:
            self.x11.XDestroyWindow(display, owner_window)
        if window:
            self.window = None
            self.x11.XDestroyWindow(display, window)
        self.x11.XCloseDisplay(display)
