"""High-level clipboard synchronization between Gamescope and Desktop."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from pathlib import Path
from typing import Callable

from .clipboard import X11ClipboardEndpoint
from .clipboard_content import (
    ClipboardContent,
    PORTAL_FILE_TRANSFER_MIME,
    PORTAL_FILES_MIME,
)
from .clipboard_klipper import KlipperClipboardMonitor
from .clipboard_portal import (
    DocumentPortalExporter,
    FileTransferPortal,
    outer_session_bus_address,
)
from .models import NestedDesktopSession


LOGGER = logging.getLogger("4deus-nested-mouse")
DEFAULT_GAMESCOPE_DISPLAYS = (":0", ":1")


@dataclass(frozen=True)
class _ClipboardSessionKey:
    pid: int
    display: str
    xauthority: Path


class NestedDesktopClipboardBridge:
    """Synchronize supported clipboard formats across both desktops."""

    def __init__(
        self,
        endpoint_factory: (
            Callable[[str, Path | None], X11ClipboardEndpoint] | None
        ) = None,
        outer_display: str | None = None,
        files_enabled: bool = True,
        outer_displays: tuple[str, ...] | None = None,
        portal_factory: Callable[[str], FileTransferPortal] | None = None,
        document_portal_factory: (
            Callable[[str], DocumentPortalExporter] | None
        ) = None,
        portal_bus_address: str | None = None,
        klipper_factory: (
            Callable[[str], KlipperClipboardMonitor] | None
        ) = None,
    ):
        self.endpoint_factory = endpoint_factory or X11ClipboardEndpoint
        configured_displays = (
            outer_displays
            if outer_displays is not None
            else (
                (outer_display,)
                if outer_display is not None
                else DEFAULT_GAMESCOPE_DISPLAYS
            )
        )
        self.outer_displays = tuple(dict.fromkeys(configured_displays))
        # Kept as a compatibility alias for callers that inspect the primary
        # Gamescope endpoint.
        self.outer_display = (
            self.outer_displays[0] if self.outer_displays else ""
        )
        self.files_enabled = files_enabled
        self.portal_factory = portal_factory
        self.file_transfer_portal: FileTransferPortal | None = None
        self.document_portal_factory = document_portal_factory
        self.document_portal_exporter: DocumentPortalExporter | None = None
        self.portal_bus_address = (
            portal_bus_address or outer_session_bus_address()
        )
        self.klipper_factory = klipper_factory
        self.klipper_monitor: KlipperClipboardMonitor | None = None
        self.session_key: _ClipboardSessionKey | None = None
        self.outer: X11ClipboardEndpoint | None = None
        self.outers: tuple[X11ClipboardEndpoint, ...] = ()
        self.outer_display_names: tuple[str, ...] = ()
        self.inner: X11ClipboardEndpoint | None = None
        self.connection_fds: tuple[int, ...] = ()
        self.latest_content: ClipboardContent | None = None
        self.latest_source_content: ClipboardContent | None = None
        self.dbus_address: str | None = None

    def set_session(self, session: NestedDesktopSession | None):
        key = (
            _ClipboardSessionKey(
                session.pid,
                session.display,
                session.xauthority,
            )
            if session is not None
            else None
        )
        if key == self.session_key and self.outers and self.inner:
            return
        self.close()
        if session is None:
            return
        opened_outers = []
        for display in self.outer_displays:
            if display == session.display:
                continue
            try:
                opened_outers.append(
                    (display, self.endpoint_factory(display, None))
                )
            except Exception as error:
                LOGGER.info(
                    "Gamescope clipboard %s is unavailable: %s",
                    display,
                    error,
                )
        if not opened_outers:
            LOGGER.warning(
                "Nested Desktop clipboard sharing is unavailable: "
                "no Gamescope clipboard could be opened"
            )
            return
        try:
            inner = self.endpoint_factory(
                session.display,
                session.xauthority,
            )
        except Exception as error:
            for _display, outer in opened_outers:
                outer.close()
            LOGGER.warning(
                "Nested Desktop clipboard sharing is unavailable: %s",
                error,
            )
            return
        self.outer_display_names = tuple(
            display for display, _outer in opened_outers
        )
        self.outers = tuple(outer for _display, outer in opened_outers)
        self.outer = self.outers[0]
        self.inner = inner
        self.dbus_address = session.dbus_address
        if self.klipper_factory is not None:
            try:
                self.klipper_monitor = self.klipper_factory(
                    session.dbus_address
                )
            except Exception as error:
                LOGGER.info(
                    "Klipper clipboard integration is unavailable: %s",
                    error,
                )
        self.connection_fds = self._connection_fds(
            tuple(filter(None, (
                *self.outers,
                inner,
                self.klipper_monitor,
            )))
        )
        self.session_key = key
        LOGGER.info(
            "Nested Desktop clipboard sharing connected: %s <-> %s",
            ", ".join(self.outer_display_names),
            session.display,
        )

    @staticmethod
    def _log_shared(
        content: ClipboardContent,
        destination: str,
    ):
        LOGGER.info(
            "Shared %s clipboard bytes (%s) with %s",
            content.byte_count,
            ", ".join(content.formats),
            destination,
        )

    def dispatch(self):
        outers = self.outers
        inner = self.inner
        if not outers or inner is None:
            return
        try:
            endpoints = [
                (outer, f"Gamescope {display}")
                for outer, display in zip(
                    outers,
                    self.outer_display_names,
                )
            ]
            endpoints.append((inner, "Nested Desktop"))
            sources = list(endpoints)
            if self.klipper_monitor is not None:
                sources.append((self.klipper_monitor, "Klipper"))
            for source, _source_name in sources:
                for content in source.dispatch():
                    shared = (
                        content
                        if self.files_enabled
                        else content.without_files()
                    )
                    shared = replace(shared, platform_file_formats=())
                    if not shared.available:
                        continue
                    if self._matches_latest(shared):
                        continue
                    source_content = shared
                    shared = self._prepare_platform_files(source, shared)
                    self.latest_source_content = source_content
                    self.latest_content = shared
                    for destination, destination_name in endpoints:
                        if destination is source:
                            continue
                        if (
                            source is self.klipper_monitor
                            and destination is inner
                        ):
                            continue
                        if destination.set_content(shared):
                            self._log_shared(shared, destination_name)
        except Exception as error:
            LOGGER.warning(
                "Lost Nested Desktop clipboard sharing: %s",
                error,
            )
            self.close()

    def _prepare_platform_files(
        self,
        source,
        content: ClipboardContent,
    ) -> ClipboardContent:
        content = replace(content, platform_file_formats=())
        if (
            source is not self.inner
            and source is not self.klipper_monitor
        ) or not content.file_uris:
            self._clear_file_transfer()
            return content
        source_uris = content.file_uris
        exporter = self.document_portal_exporter
        if exporter is None:
            if (
                self.portal_bus_address
                and self.document_portal_factory is not None
            ):
                exporter = self.document_portal_factory(
                    self.portal_bus_address
                )
                self.document_portal_exporter = exporter
        if exporter is not None:
            try:
                exported_uris = exporter.export(source_uris)
                content = replace(content, file_uris=exported_uris)
            except Exception as error:
                LOGGER.warning(
                    "Could not expose clipboard files to sandboxes: %s",
                    error,
                )
        portal = self.file_transfer_portal
        if portal is None:
            if not self.portal_bus_address or self.portal_factory is None:
                return content
            portal = self.portal_factory(self.portal_bus_address)
            self.file_transfer_portal = portal
        try:
            token = portal.replace(source_uris)
        except Exception as error:
            LOGGER.warning(
                "Could not prepare sandboxed clipboard files: %s",
                error,
            )
            portal.clear()
            return content
        if token is None:
            return content
        return replace(
            content,
            platform_file_formats=(
                (PORTAL_FILE_TRANSFER_MIME, token),
                (PORTAL_FILES_MIME, token),
            ),
        )

    def _clear_file_transfer(self):
        if self.file_transfer_portal is not None:
            self.file_transfer_portal.clear()

    def _matches_latest(self, content: ClipboardContent) -> bool:
        comparable = replace(content, platform_file_formats=())
        return any(
            replace(candidate, platform_file_formats=()) == comparable
            for candidate in (
                self.latest_content,
                self.latest_source_content,
            )
            if candidate is not None
        )

    def current_text(self) -> str | None:
        """Return the Gamescope-side text mirrored by this bridge."""
        if self.latest_content is not None:
            return self.latest_content.text
        for outer in self.outers:
            if outer.initialized:
                return outer.text
        return None

    def release_inner_focus(self) -> bool:
        """Flush lazy inner clipboard owners while Gamescope switches away."""
        monitor = self.klipper_monitor
        release = getattr(monitor, "release_focus_for_clipboard", None)
        return bool(callable(release) and release())

    def filenos(self) -> tuple[int, ...]:
        """Return live X11 sockets that can wake the runtime event loop."""
        return self.connection_fds

    @staticmethod
    def _connection_fds(
        endpoints: tuple[object, ...],
    ) -> tuple[int, ...]:
        descriptors = []
        for endpoint in endpoints:
            fileno = getattr(endpoint, "fileno", None)
            if not callable(fileno):
                continue
            descriptor = int(fileno())
            if descriptor >= 0 and descriptor not in descriptors:
                descriptors.append(descriptor)
        return tuple(descriptors)

    def close(self):
        outers = self.outers
        inner = self.inner
        self.outer = None
        self.outers = ()
        self.outer_display_names = ()
        self.inner = None
        self.connection_fds = ()
        self.session_key = None
        self.latest_content = None
        self.latest_source_content = None
        self.dbus_address = None
        portal = self.file_transfer_portal
        self.file_transfer_portal = None
        document_exporter = self.document_portal_exporter
        self.document_portal_exporter = None
        klipper_monitor = self.klipper_monitor
        self.klipper_monitor = None
        for outer in outers:
            outer.close()
        if inner is not None:
            inner.close()
        if portal is not None:
            portal.close()
        if document_exporter is not None:
            document_exporter.close()
        if klipper_monitor is not None:
            klipper_monitor.close()
