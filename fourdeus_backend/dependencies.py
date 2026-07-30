"""Optional backend integrations loaded by the Decky plugin."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

import decky_plugin


logger = decky_plugin.logger
logger.setLevel(logging.INFO)

PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)


def _missing(component: str, consequence: str) -> None:
    logger.exception(
        "%s is unavailable; %s",
        component,
        consequence,
    )


try:
    from app_bridge import AppBridgeManager
except Exception:
    AppBridgeManager = None
    _missing("App Bridge", "keyboard features will remain active")

try:
    from mangoapp_hotfix import MangoHudFixManager
except Exception:
    MangoHudFixManager = None
    _missing("MangoHud System Tool", "other features will remain active")

try:
    from rustdesk_pointer_fix import RustDeskPointerFixManager
except Exception:
    RustDeskPointerFixManager = None
    _missing("RustDesk pointer fix", "other features will remain active")

try:
    from steamos_application import SteamOsApplicationManager
except Exception:
    SteamOsApplicationManager = None
    _missing(
        "SteamOS application System Tool",
        "other features will remain active",
    )

try:
    from trackpad_metrics import (
        TrackpadMetricsMonitor,
        power_cycle_steam_deck_controller,
        reconcile_steam_deck_controller_authorization,
        reinitialize_steam_deck_trackpad_driver,
    )
except Exception:
    TrackpadMetricsMonitor = None
    power_cycle_steam_deck_controller = None
    reconcile_steam_deck_controller_authorization = None
    reinitialize_steam_deck_trackpad_driver = None
    _missing(
        "Trackpad metrics",
        "other features will remain active",
    )

try:
    from nested_desktop_mouse import (
        DEFAULT_NESTED_DESKTOP_BINDINGS,
        NESTED_DESKTOP_BINDING_ACTIONS,
        NESTED_DESKTOP_BINDING_SOURCES,
        NestedDesktopMouseSupervisor,
        normalize_nested_desktop_bindings,
    )
except Exception:
    NestedDesktopMouseSupervisor = None
    DEFAULT_NESTED_DESKTOP_BINDINGS = {}
    NESTED_DESKTOP_BINDING_ACTIONS = frozenset()
    NESTED_DESKTOP_BINDING_SOURCES = ()

    def normalize_nested_desktop_bindings(_bindings):
        return {}

    _missing(
        "Nested Desktop mouse bridge",
        "other features will remain active",
    )


__all__ = [
    "AppBridgeManager",
    "DEFAULT_NESTED_DESKTOP_BINDINGS",
    "MangoHudFixManager",
    "NESTED_DESKTOP_BINDING_ACTIONS",
    "NESTED_DESKTOP_BINDING_SOURCES",
    "NestedDesktopMouseSupervisor",
    "PLUGIN_ROOT",
    "RustDeskPointerFixManager",
    "SteamOsApplicationManager",
    "TrackpadMetricsMonitor",
    "logger",
    "normalize_nested_desktop_bindings",
    "power_cycle_steam_deck_controller",
    "reconcile_steam_deck_controller_authorization",
    "reinitialize_steam_deck_trackpad_driver",
]
