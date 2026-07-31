"""Physical touchscreen input handling for the Nested Desktop runtime."""

from __future__ import annotations

import logging
import time


LOGGER = logging.getLogger("4deus-nested-mouse")


class RuntimeTouchInputMixin:
    def _read_touchscreen_events(self):
        reader = self.touchscreen_reader
        if reader is None:
            return
        try:
            frames = reader.read_frames()
        except (EOFError, OSError, ValueError) as error:
            LOGGER.warning("Lost the Steam Deck touchscreen: %s", error)
            self._set_touch_forwarding(False)
            self._close_touchscreen()
            return
        if (
            frames
            and self.outer_x11 is not None
            and self.session is not None
        ):
            # Touches are infrequent, so refresh focus synchronously to avoid
            # forwarding the first tap after Steam opens an overlay.
            self.focus_snapshot = None
            self._refresh_forwarding()
        if not self.touch_forwarding:
            self.touchscreen_inertia.reset()
            return
        inner_eis = self.inner_eis
        if inner_eis is None:
            return
        try:
            now = time.monotonic()
            for frame in frames:
                for output in self.touchscreen_inertia.process(frame, now):
                    inner_eis.inject_touch(output)
        except Exception as error:
            self._handle_eis_loss(error)

    def _tick_touchscreen_inertia(self):
        inner_eis = self.inner_eis
        if not self.touch_forwarding or inner_eis is None:
            self.touchscreen_inertia.reset()
            return
        frame = self.touchscreen_inertia.tick(time.monotonic())
        if not frame:
            return
        try:
            inner_eis.inject_touch(frame)
        except Exception as error:
            self._handle_eis_loss(error)

    def _close_touchscreen(self):
        self.touchscreen_inertia.reset()
        reader = self.touchscreen_reader
        self.touchscreen_reader = None
        if reader is None:
            return
        reader.close()
