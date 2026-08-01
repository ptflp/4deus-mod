"""X11 clipboard ownership and selection response handling."""

from __future__ import annotations

import ctypes

from .clipboard_content import (
    encode_file_uri_list,
    encode_gnome_copied_files,
)
from .clipboard_x11 import (
    X11_NONE,
    X11_PROP_MODE_REPLACE,
    X11_SELECTION_NOTIFY,
    XSelectionEvent as _XSelectionEvent,
    XSelectionRequestEvent as _XSelectionRequestEvent,
    write_property_bytes,
)


class X11ClipboardOwnerMixin:
    """Serve clipboard payloads owned by an endpoint."""

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

    def _available_targets(self, content) -> set[int]:
        available_targets = {self.targets}
        if content.text is not None:
            available_targets.update(self.supported_text_targets)
        if (
            content.image is not None
            and content.image_mime in self.image_atoms
        ):
            available_targets.add(self.image_atoms[content.image_mime])
        if content.file_uris:
            available_targets.update(self.file_targets)
            available_targets.add(self.kde_cut_selection)
        available_targets.update(
            self.platform_file_atoms[mime]
            for mime, _payload in content.platform_file_formats
            if mime in self.platform_file_atoms
        )
        return available_targets

    def _file_payload(self, content, target: int) -> bytes | None:
        if content.file_uris:
            if target in (self.uri_list, self.kde_uri_list):
                return encode_file_uri_list(content.file_uris)
            if target == self.gnome_copied_files:
                return encode_gnome_copied_files(content.file_uris)
            if target == self.kde_cut_selection:
                return b"0"
        mime = self.platform_file_mimes_by_atom.get(target)
        if mime is None:
            return None
        return dict(content.platform_file_formats).get(mime)

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
                available_targets = self._available_targets(content)
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
            else:
                payload = self._file_payload(content, request.target)
                if payload is not None:
                    self._write_property_bytes(
                        request.requestor,
                        property_atom,
                        request.target,
                        payload,
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
