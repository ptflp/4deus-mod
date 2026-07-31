"""Safe runtime control of Gamescope's composited cursor."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Callable, Mapping

from .models import PointerUpdate
from .pointer_capture import (
    CapturedPointerUpdate, GamescopePointerCapture,
)


LOGGER = logging.getLogger("4deus-nested-mouse")

GAMESCOPE_CURSOR_VISIBLE = 1
GAMESCOPE_CURSOR_HIDDEN = 0
GAMESCOPE_CURSOR_RETRY_INTERVAL = 2.0
GAMESCOPE_POINTER_GRAB_RETRY_INTERVAL = 2.0


def set_gamescope_cursor_composite(
    value: int,
    *,
    environment: Mapping[str, str] | None = None,
    timeout: float = 2.0,
) -> bool:
    """Set Gamescope's cursor compositor without invoking a shell."""
    command_environment = dict(
        os.environ if environment is None else environment
    )
    command_environment.setdefault(
        "XDG_RUNTIME_DIR",
        f"/run/user/{os.geteuid()}",
    )
    command_environment.setdefault(
        "GAMESCOPE_WAYLAND_DISPLAY",
        "gamescope-0",
    )
    try:
        result = subprocess.run(
            ("gamescopectl", "cursor_composite", str(value)),
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=command_environment,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        LOGGER.warning(
            "Unable to update the Gamescope cursor compositor: %s",
            error,
        )
        return False
    if result.returncode == 0:
        return True
    LOGGER.warning(
        "gamescopectl cursor_composite failed with code %s: %s",
        result.returncode,
        result.stderr.strip(),
    )
    return False


class GamescopeCursorCompositor:
    """Hide the host cursor while preserving crash-safe restoration."""

    def __init__(
        self,
        command: Callable[[int], bool] | None = None,
        marker_path: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        retry_interval: float = GAMESCOPE_CURSOR_RETRY_INTERVAL,
    ):
        runtime_dir = Path(
            os.environ.get(
                "XDG_RUNTIME_DIR",
                f"/run/user/{os.geteuid()}",
            )
        )
        self.command = command or set_gamescope_cursor_composite
        self.marker_path = marker_path or (
            runtime_dir / "4deus-mod-gamescope-cursor-hidden"
        )
        self.clock = clock
        self.retry_interval = retry_interval
        self.hidden = False
        self.retry_after = 0.0
        if self._marker_exists():
            self.set_hidden(False)

    def _marker_exists(self) -> bool:
        try:
            return self.marker_path.exists()
        except OSError:
            return False

    def _mark_hidden(self) -> bool:
        try:
            self.marker_path.parent.mkdir(
                mode=0o700,
                parents=True,
                exist_ok=True,
            )
            self.marker_path.write_text(
                f"{os.getpid()}\n",
                encoding="utf-8",
            )
            return True
        except OSError as error:
            LOGGER.warning(
                "Unable to create the Gamescope cursor recovery marker: %s",
                error,
            )
            return False

    def _clear_marker(self):
        try:
            self.marker_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.debug(
                "Unable to clear the Gamescope cursor recovery marker",
                exc_info=True,
            )

    def set_hidden(self, hidden: bool) -> bool:
        hidden = bool(hidden)
        marker_exists = self._marker_exists()
        if hidden == self.hidden and (hidden or not marker_exists):
            return True
        now = self.clock()
        if hidden and now < self.retry_after:
            return False
        if hidden and not self._mark_hidden():
            self.retry_after = now + self.retry_interval
            return False
        try:
            updated = bool(
                self.command(
                    GAMESCOPE_CURSOR_HIDDEN
                    if hidden
                    else GAMESCOPE_CURSOR_VISIBLE
                )
            )
        except Exception:
            LOGGER.warning(
                "Unable to update the Gamescope cursor compositor",
                exc_info=True,
            )
            updated = False
        if not updated:
            self.retry_after = now + self.retry_interval
            return False
        self.hidden = hidden
        self.retry_after = 0.0
        if hidden:
            LOGGER.info("Gamescope Proton cursor hidden")
        else:
            self._clear_marker()
            LOGGER.info("Gamescope cursor restored")
        return True

    def close(self):
        self.set_hidden(False)


class GamescopePointerInterceptor:
    """Consume the hidden Gamescope pointer while Nested Desktop owns it."""

    def __init__(
        self,
        connection_factory: Callable[[str], object] | None = None,
        clock: Callable[[], float] = time.monotonic,
        retry_interval: float = GAMESCOPE_POINTER_GRAB_RETRY_INTERVAL,
    ):
        self.connection_factory = (
            connection_factory or GamescopePointerCapture
        )
        self.clock = clock
        self.retry_interval = retry_interval
        self.connection = None
        self.display_name: str | None = None
        self.retry_after = 0.0
        self.pending_release_updates: list[PointerUpdate] = []

    def set_active(
        self,
        active: bool,
        display_name: str | None = None,
    ) -> bool:
        active = bool(active and display_name)
        if (
            active
            and self.connection is not None
            and display_name == self.display_name
        ):
            return True
        if not active:
            self.close()
            return True
        now = self.clock()
        if now < self.retry_after:
            return False
        self.close()
        connection = None
        try:
            connection = self.connection_factory(str(display_name))
            if not connection.grab_pointer():
                raise RuntimeError("pointer is already grabbed")
        except Exception as error:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            self.retry_after = now + self.retry_interval
            LOGGER.warning(
                "Unable to intercept Gamescope pointer on %s: %s",
                display_name,
                error,
            )
            return False
        self.connection = connection
        self.display_name = str(display_name)
        self.retry_after = 0.0
        LOGGER.info(
            "Gamescope master pointer redirected from %s",
            display_name,
        )
        return True

    def fileno(self) -> int:
        connection = self.connection
        if connection is None:
            return -1
        fileno = getattr(connection, "fileno", None)
        if not callable(fileno):
            return -1
        try:
            return int(fileno())
        except Exception:
            return -1

    def dispatch(self) -> tuple[CapturedPointerUpdate, ...]:
        connection = self.connection
        if connection is None:
            return ()
        dispatch = getattr(connection, "dispatch", None)
        if not callable(dispatch):
            return ()
        try:
            return tuple(dispatch())
        except Exception:
            LOGGER.warning(
                "Lost the Gamescope master pointer capture",
                exc_info=True,
            )
            self.close()
            return ()

    def take_release_updates(self) -> tuple[PointerUpdate, ...]:
        updates = tuple(self.pending_release_updates)
        self.pending_release_updates.clear()
        return updates

    def close(self):
        connection = self.connection
        display_name = self.display_name
        self.connection = None
        self.display_name = None
        if connection is None:
            return
        release_update = getattr(connection, "release_update", None)
        if callable(release_update):
            try:
                update = release_update()
                if not update.empty:
                    self.pending_release_updates.append(update)
            except Exception:
                LOGGER.debug(
                    "Unable to release captured Gamescope buttons",
                    exc_info=True,
                )
        try:
            connection.ungrab_pointer()
        except Exception:
            LOGGER.debug(
                "Unable to release the Gamescope pointer grab",
                exc_info=True,
            )
        try:
            connection.close()
        except Exception:
            LOGGER.debug(
                "Unable to close the Gamescope pointer display",
                exc_info=True,
            )
        LOGGER.info(
            "Gamescope master pointer restored on %s",
            display_name,
        )
