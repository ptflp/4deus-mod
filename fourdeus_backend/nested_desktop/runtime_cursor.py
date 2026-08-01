"""Software cursor and Gamescope pointer ownership transitions."""

from __future__ import annotations

import logging
import time

from .constants import (
    GAMESCOPE_POINTER_HID_SUPPRESSION_GRACE,
    GAMESCOPE_POINTER_RELAY_DELAY,
)
from .models import PointerUpdate


LOGGER = logging.getLogger("4deus-nested-mouse")


class RuntimeCursorMixin:
    @staticmethod
    def _map_pointer_position(
        source: tuple[int, int, int, int],
        target: tuple[int, int, int, int],
    ) -> PointerUpdate | None:
        source_x, source_y, source_width, source_height = source
        target_x, target_y, target_width, target_height = target
        if min(
            source_width,
            source_height,
            target_width,
            target_height,
        ) <= 0:
            return None
        source_x = max(0, min(source_width - 1, source_x))
        source_y = max(0, min(source_height - 1, source_y))
        normalized_x = source_x / max(1, source_width - 1)
        normalized_y = source_y / max(1, source_height - 1)
        return PointerUpdate(
            absolute_x=(
                float(target_x)
                + normalized_x * max(0, target_width - 1)
            ),
            absolute_y=(
                float(target_y)
                + normalized_y * max(0, target_height - 1)
            ),
        )

    def _pointer_emulation_has_owner(self) -> bool:
        return bool(
            self.forwarding
            or self.binding_pointer_forwarding
            or self.remote_scroll_forwarding
            or self.gamescope_pointer_forwarding
        )

    def _set_cursor_overlay(self, active: bool):
        session = self.session
        active = bool(
            active
            and session is not None
            and not session.software_cursor_forced
        )
        overlay = self.cursor_overlay
        if (
            active
            and session is not None
            and self.cursor_overlay_failed_session_pid == session.pid
        ):
            active = False
        if not active:
            self._set_gamescope_cursor_hidden(False)
        try:
            if active and overlay is None and session is not None:
                overlay = self.cursor_overlay_factory(session)
                self.cursor_overlay = overlay
            if active:
                overlay.show()
            elif overlay is not None:
                overlay.hide()
        except Exception as error:
            LOGGER.warning(
                "Nested Desktop cursor overlay is unavailable: %s",
                error,
            )
            if session is not None:
                self.cursor_overlay_failed_session_pid = session.pid
            self._close_cursor_overlay()
            active = False
        if active:
            self._set_gamescope_cursor_hidden(True)
        if active == self.cursor_overlay_active:
            return
        self.cursor_overlay_active = active
        LOGGER.info(
            "Nested Desktop cursor overlay %s",
            "enabled" if active else "disabled",
        )

    def _apply_cursor_overlay(self, update: PointerUpdate):
        overlay = self.cursor_overlay
        if not self.cursor_overlay_active or overlay is None:
            return
        try:
            overlay.apply(update)
        except Exception as error:
            LOGGER.warning(
                "Lost the Nested Desktop cursor overlay: %s",
                error,
            )
            if self.session is not None:
                self.cursor_overlay_failed_session_pid = self.session.pid
            self._close_cursor_overlay()

    def _close_cursor_overlay(self):
        self._set_gamescope_cursor_hidden(False)
        overlay = self.cursor_overlay
        self.cursor_overlay = None
        self.cursor_overlay_active = False
        if overlay is None:
            return
        try:
            overlay.close()
        except Exception:
            LOGGER.debug(
                "Failed to close the Nested Desktop cursor overlay",
                exc_info=True,
            )

    def _set_gamescope_cursor_hidden(self, hidden: bool):
        compositor = self.gamescope_cursor_compositor
        if compositor is None:
            return
        try:
            compositor.set_hidden(hidden)
        except Exception:
            LOGGER.warning(
                "Unable to update the Gamescope cursor compositor",
                exc_info=True,
            )

    def _set_gamescope_pointer_intercepted(
        self,
        active: bool,
        display_name: str | None = None,
    ):
        interceptor = self.gamescope_pointer_interceptor
        inner_eis = self.inner_eis
        active = bool(
            active
            and self.gamescope_pointer_relay_enabled
            and interceptor is not None
            and inner_eis is not None
            and inner_eis.ready
            and display_name
        )
        if (
            active
            and self.gamescope_pointer_forwarding
            and interceptor.display_name == display_name
            and interceptor.fileno() >= 0
            and getattr(inner_eis, "emulating", True)
        ):
            return
        emulation_requested = False
        try:
            if active:
                emulation_requested = True
                active = bool(
                    inner_eis.set_emulating(True)
                    and interceptor.set_active(True, display_name)
                )
            elif interceptor is not None:
                interceptor.set_active(False)
        except Exception as error:
            LOGGER.warning(
                "Unable to update Gamescope pointer interception: %s",
                error,
            )
            active = False
            if interceptor is not None:
                try:
                    interceptor.set_active(False)
                except Exception:
                    LOGGER.debug(
                        "Unable to release Gamescope pointer interception",
                        exc_info=True,
                    )

        was_active = self.gamescope_pointer_forwarding
        self.gamescope_pointer_forwarding = active
        if active:
            if not was_active:
                LOGGER.info("Gamescope pointer relay enabled")
            return

        self.gamescope_pointer_updates.clear()
        self.gamescope_pointer_hid_suppression_until = 0.0
        if interceptor is not None:
            self._inject_gamescope_release_updates(
                interceptor.take_release_updates()
            )
        if (
            inner_eis is not None
            and (was_active or emulation_requested)
            and not self._pointer_emulation_has_owner()
        ):
            try:
                inner_eis.set_emulating(False)
            except Exception as error:
                self._handle_eis_loss(error)
                return
        if was_active:
            LOGGER.info("Gamescope pointer relay disabled")

    def _sync_gamescope_pointer_position(
        self,
        display_name: str | None,
    ) -> bool:
        """Rebase the inner pointer after returning from another app."""
        interceptor = self.gamescope_pointer_interceptor
        inner_eis = self.inner_eis
        if (
            interceptor is None
            or inner_eis is None
            or not display_name
        ):
            return False
        # A Proton application may retain the XI2 grab briefly after losing
        # focus. Reading XQueryPointer does not require that grab, so use a
        # short-lived X11 connection when the regular relay could not start.
        source = interceptor.pointer_snapshot(display_name)
        target = inner_eis.absolute_bounds()
        if source is None or target is None:
            return False
        update = self._map_pointer_position(source, target)
        if update is None:
            return False
        was_absolute_emulating = bool(inner_eis.absolute_emulating)
        started_absolute_emulation = False
        if not was_absolute_emulating:
            if not inner_eis.set_absolute_emulating(True):
                return False
            started_absolute_emulation = True
        try:
            inner_eis.inject_absolute(update)
            self._apply_cursor_overlay(update)
        finally:
            if started_absolute_emulation:
                inner_eis.set_absolute_emulating(False)
        LOGGER.info(
            "Nested Desktop pointer synchronized from %dx%d (%d, %d) "
            "to %.1f, %.1f",
            source[2],
            source[3],
            source[0],
            source[1],
            update.absolute_x,
            update.absolute_y,
        )
        return True

    def _inject_gamescope_release_updates(self, updates):
        inner_eis = self.inner_eis
        if inner_eis is None:
            return
        try:
            for update in updates:
                inner_eis.inject(update)
                self._apply_cursor_overlay(update)
        except Exception as error:
            self._handle_eis_loss(error)

    def _gamescope_pointer_fileno(self) -> int | None:
        if not self.gamescope_pointer_forwarding:
            return None
        interceptor = self.gamescope_pointer_interceptor
        if interceptor is None:
            return None
        descriptor = interceptor.fileno()
        return descriptor if descriptor >= 0 else None

    def _read_gamescope_pointer_events(self):
        interceptor = self.gamescope_pointer_interceptor
        if interceptor is None or not self.gamescope_pointer_forwarding:
            return
        updates = interceptor.dispatch()
        self.gamescope_pointer_updates.extend(updates)
        if (
            updates
            and self.hidraw_fd is not None
            and (self.forwarding or self.binding_pointer_forwarding)
        ):
            # Bypass the regular 60 Hz HID throttle once so the physical
            # report can suppress its matching Gamescope event before the
            # short relay delay expires.
            self.next_input_frame = 0.0
        if interceptor.fileno() < 0:
            self._set_gamescope_pointer_intercepted(False)

    def _gamescope_pointer_timeout(
        self,
        now: float,
        timeout: float,
    ) -> float:
        if not self.gamescope_pointer_updates:
            return timeout
        due_at = (
            self.gamescope_pointer_updates[0].received_at
            + GAMESCOPE_POINTER_RELAY_DELAY
        )
        return min(timeout, max(0.0, due_at - now))

    def _flush_gamescope_pointer_updates(self):
        if not self.gamescope_pointer_forwarding:
            self.gamescope_pointer_updates.clear()
            return
        now = time.monotonic()
        due_before = now - GAMESCOPE_POINTER_RELAY_DELAY
        inner_eis = self.inner_eis
        if inner_eis is None:
            self.gamescope_pointer_updates.clear()
            return
        try:
            while self.gamescope_pointer_updates:
                captured = self.gamescope_pointer_updates[0]
                if captured.received_at > due_before:
                    break
                self.gamescope_pointer_updates.popleft()
                if (
                    captured.received_at
                    <= self.gamescope_pointer_hid_suppression_until
                ):
                    continue
                inner_eis.inject(captured.update)
                self._apply_cursor_overlay(captured.update)
        except Exception as error:
            self._handle_eis_loss(error)

    def _mark_gamescope_pointer_hid_activity(self, now: float):
        if not self.gamescope_pointer_forwarding:
            return
        self.gamescope_pointer_hid_suppression_until = max(
            self.gamescope_pointer_hid_suppression_until,
            now + GAMESCOPE_POINTER_HID_SUPPRESSION_GRACE,
        )
