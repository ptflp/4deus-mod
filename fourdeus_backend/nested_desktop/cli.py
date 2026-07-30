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

from .constants import RUSTDESK_POINTER_RELAY_SOCKET
from .runtime import NestedDesktopMouseRuntime


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
    inertia_enabled: bool = True,
    bindings_enabled: bool = True,
    bindings: Mapping[str, object] | None = None,
    rustdesk_pointer_fix_enabled: bool = True,
    rustdesk_scroll_inertia_enabled: bool = False,
    rustdesk_focus_on_input_enabled: bool = False,
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
        inertia_enabled=inertia_enabled,
        bindings_enabled=bindings_enabled,
        bindings=bindings,
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
    )
    runtime.run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--no-mouse-bridge", action="store_true")
    parser.add_argument("--no-inertia", action="store_true")
    parser.add_argument("--no-bindings", action="store_true")
    parser.add_argument("--no-rustdesk-pointer-fix", action="store_true")
    parser.add_argument("--rustdesk-scroll-inertia", action="store_true")
    parser.add_argument(
        "--rustdesk-focus-on-input",
        action="store_true",
    )
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
        inertia_enabled=not arguments.no_inertia,
        bindings_enabled=not arguments.no_bindings,
        bindings=bindings,
        rustdesk_pointer_fix_enabled=(
            not arguments.no_rustdesk_pointer_fix
        ),
        rustdesk_scroll_inertia_enabled=(
            arguments.rustdesk_scroll_inertia
        ),
        rustdesk_focus_on_input_enabled=(
            arguments.rustdesk_focus_on_input
        ),
        suspended=arguments.suspended,
        control_fd=sys.stdin.fileno(),
    )
