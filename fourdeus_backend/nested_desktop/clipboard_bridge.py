"""High-level clipboard synchronization between Gamescope and Desktop."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable

from .clipboard import X11ClipboardEndpoint
from .clipboard_content import ClipboardContent
from .models import NestedDesktopSession


LOGGER = logging.getLogger("4deus-nested-mouse")


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
        outer_display: str = ":0",
        files_enabled: bool = True,
    ):
        self.endpoint_factory = endpoint_factory or X11ClipboardEndpoint
        self.outer_display = outer_display
        self.files_enabled = files_enabled
        self.session_key: _ClipboardSessionKey | None = None
        self.outer: X11ClipboardEndpoint | None = None
        self.inner: X11ClipboardEndpoint | None = None

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
        if key == self.session_key and self.outer and self.inner:
            return
        self.close()
        if session is None:
            return
        try:
            outer = self.endpoint_factory(self.outer_display, None)
            try:
                inner = self.endpoint_factory(
                    session.display,
                    session.xauthority,
                )
            except Exception:
                outer.close()
                raise
        except Exception as error:
            LOGGER.warning(
                "Nested Desktop clipboard sharing is unavailable: %s",
                error,
            )
            return
        self.outer = outer
        self.inner = inner
        self.session_key = key
        LOGGER.info("Nested Desktop clipboard sharing connected")

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
        outer = self.outer
        inner = self.inner
        if outer is None or inner is None:
            return
        try:
            outer_updates = outer.dispatch()
            inner_updates = inner.dispatch()
            for content in outer_updates:
                shared = (
                    content if self.files_enabled else content.without_files()
                )
                if shared.available and inner.set_content(shared):
                    self._log_shared(shared, "Nested Desktop")
            for content in inner_updates:
                shared = (
                    content if self.files_enabled else content.without_files()
                )
                if shared.available and outer.set_content(shared):
                    self._log_shared(shared, "Gamescope")
        except Exception as error:
            LOGGER.warning(
                "Lost Nested Desktop clipboard sharing: %s",
                error,
            )
            self.close()

    def current_text(self) -> str | None:
        """Return the Gamescope-side text mirrored by this bridge."""
        outer = self.outer
        if outer is None or not outer.initialized:
            return None
        return outer.text

    def close(self):
        outer = self.outer
        inner = self.inner
        self.outer = None
        self.inner = None
        self.session_key = None
        if outer is not None:
            outer.close()
        if inner is not None:
            inner.close()
