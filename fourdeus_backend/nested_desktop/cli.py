"""Command-line worker bootstrap used by the supervisor."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import logging
import signal
import sys
import threading
from typing import Mapping

from .constants import (
    RUSTDESK_POINTER_RELAY_SOCKET,
    TOUCH_INERTIA_DEFAULT_DURATION_MS,
    TOUCH_INERTIA_DEFAULT_MIN_DISTANCE,
    TOUCH_INERTIA_DEFAULT_START_SPEED,
)
from .clipboard_bridge import NestedDesktopClipboardBridge
from .clipboard_klipper import KlipperClipboardMonitor
from .clipboard_portal import DocumentPortalExporter, FileTransferPortal
from .gamescope import (
    GamescopeCursorCompositor, GamescopePointerInterceptor,
)
from .runtime import NestedDesktopMouseRuntime
from .touch import TouchscreenInertiaConfig


LOGGER = logging.getLogger("4deus-nested-mouse")


def _configure_parent_death_signal():
    try:
        libc_name = ctypes.util.find_library("c") or "libc.so.6"
        libc = ctypes.CDLL(libc_name)
        libc.prctl.argtypes = [
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        libc.prctl.restype = ctypes.c_int
        libc.prctl(1, signal.SIGTERM, 0, 0, 0)
    except Exception:
        LOGGER.debug("Unable to configure the parent-death signal")


def run_worker(
    mouse_enabled: bool = True,
    gamescope_pointer_relay_enabled: bool = True,
    inertia_enabled: bool = True,
    bindings_enabled: bool = True,
    bindings: Mapping[str, object] | None = None,
    touchscreen_enabled: bool = True,
    touchscreen_fd: int | None = None,
    touchscreen_inertia_enabled: bool = True,
    touchscreen_inertia_config: (
        TouchscreenInertiaConfig | None
    ) = None,
    rustdesk_pointer_fix_enabled: bool = True,
    rustdesk_scroll_inertia_enabled: bool = False,
    rustdesk_focus_on_input_enabled: bool = False,
    clipboard_enabled: bool = False,
    clipboard_files_enabled: bool = True,
    suspended: bool = False,
    control_fd: int | None = None,
) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _configure_parent_death_signal()
    stop_event = threading.Event()

    def stop_worker(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    runtime = NestedDesktopMouseRuntime(
        stop_event,
        mouse_enabled=mouse_enabled,
        gamescope_pointer_relay_enabled=(
            gamescope_pointer_relay_enabled
        ),
        inertia_enabled=inertia_enabled,
        bindings_enabled=bindings_enabled,
        bindings=bindings,
        touchscreen_enabled=touchscreen_enabled,
        touchscreen_fd=touchscreen_fd,
        touchscreen_inertia_enabled=touchscreen_inertia_enabled,
        touchscreen_inertia_config=touchscreen_inertia_config,
        rustdesk_pointer_fix_enabled=rustdesk_pointer_fix_enabled,
        rustdesk_scroll_inertia_enabled=(
            rustdesk_scroll_inertia_enabled
        ),
        rustdesk_focus_on_input_enabled=(
            rustdesk_focus_on_input_enabled
        ),
        action_callback=lambda action: print(action, flush=True),
        suspended=suspended,
        control_fd=control_fd,
        rustdesk_relay_path=(
            RUSTDESK_POINTER_RELAY_SOCKET
            if rustdesk_pointer_fix_enabled
            else None
        ),
        gamescope_cursor_compositor=GamescopeCursorCompositor(),
        gamescope_pointer_interceptor=GamescopePointerInterceptor(),
        clipboard_bridge=(
            NestedDesktopClipboardBridge(
                files_enabled=clipboard_files_enabled,
                klipper_factory=KlipperClipboardMonitor,
                portal_factory=FileTransferPortal,
                document_portal_factory=DocumentPortalExporter,
            )
            if clipboard_enabled
            else None
        ),
    )
    runtime.run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--no-mouse-bridge", action="store_true")
    parser.add_argument(
        "--no-gamescope-pointer-relay",
        action="store_true",
    )
    parser.add_argument("--no-inertia", action="store_true")
    parser.add_argument("--no-bindings", action="store_true")
    parser.add_argument("--no-touchscreen", action="store_true")
    parser.add_argument("--touchscreen-fd", type=int, default=-1)
    parser.add_argument("--no-touchscreen-inertia", action="store_true")
    parser.add_argument(
        "--touchscreen-inertia-duration-ms",
        type=int,
        default=TOUCH_INERTIA_DEFAULT_DURATION_MS,
    )
    parser.add_argument(
        "--touchscreen-inertia-start-speed",
        type=int,
        default=TOUCH_INERTIA_DEFAULT_START_SPEED,
    )
    parser.add_argument(
        "--touchscreen-inertia-min-distance",
        type=int,
        default=TOUCH_INERTIA_DEFAULT_MIN_DISTANCE,
    )
    parser.add_argument("--no-rustdesk-pointer-fix", action="store_true")
    parser.add_argument("--rustdesk-scroll-inertia", action="store_true")
    parser.add_argument(
        "--rustdesk-focus-on-input",
        action="store_true",
    )
    parser.add_argument("--clipboard-sharing", action="store_true")
    parser.add_argument("--no-clipboard-files", action="store_true")
    parser.add_argument("--suspended", action="store_true")
    parser.add_argument("--bindings-json", default="{}")
    arguments = parser.parse_args()
    if not arguments.worker:
        parser.error("--worker is required")
    try:
        bindings = json.loads(arguments.bindings_json)
    except json.JSONDecodeError as error:
        parser.error(f"invalid --bindings-json: {error}")
    if not isinstance(bindings, dict):
        parser.error("--bindings-json must contain an object")
    return run_worker(
        mouse_enabled=not arguments.no_mouse_bridge,
        gamescope_pointer_relay_enabled=(
            not arguments.no_gamescope_pointer_relay
        ),
        inertia_enabled=not arguments.no_inertia,
        bindings_enabled=not arguments.no_bindings,
        bindings=bindings,
        touchscreen_enabled=not arguments.no_touchscreen,
        touchscreen_fd=(
            arguments.touchscreen_fd
            if arguments.touchscreen_fd >= 0
            else None
        ),
        touchscreen_inertia_enabled=(
            not arguments.no_touchscreen_inertia
        ),
        touchscreen_inertia_config=(
            TouchscreenInertiaConfig.from_mapping(
                {
                    "durationMs": (
                        arguments.touchscreen_inertia_duration_ms
                    ),
                    "startSpeed": (
                        arguments.touchscreen_inertia_start_speed
                    ),
                    "minDistance": (
                        arguments.touchscreen_inertia_min_distance
                    ),
                }
            )
        ),
        rustdesk_pointer_fix_enabled=(
            not arguments.no_rustdesk_pointer_fix
        ),
        rustdesk_scroll_inertia_enabled=(
            arguments.rustdesk_scroll_inertia
        ),
        rustdesk_focus_on_input_enabled=(
            arguments.rustdesk_focus_on_input
        ),
        clipboard_enabled=arguments.clipboard_sharing,
        clipboard_files_enabled=not arguments.no_clipboard_files,
        suspended=arguments.suspended,
        control_fd=sys.stdin.fileno(),
    )
