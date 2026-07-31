"""Safe runtime control of Gamescope's composited cursor."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Callable, Mapping


LOGGER = logging.getLogger("4deus-nested-mouse")

GAMESCOPE_CURSOR_VISIBLE = 1
GAMESCOPE_CURSOR_HIDDEN = 0
GAMESCOPE_CURSOR_RETRY_INTERVAL = 2.0


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
