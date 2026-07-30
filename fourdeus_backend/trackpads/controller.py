"""Steam Deck HID discovery and controller reset operations."""

from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
from typing import Callable

from .constants import STEAM_DECK_HID_ID


LOGGER = logging.getLogger("4deus-trackpad-metrics")
_CONTROLLER_USB_LOCK = threading.RLock()


def find_steam_deck_hidraw(
    sys_class_hidraw: Path = Path("/sys/class/hidraw"),
    dev_root: Path = Path("/dev"),
) -> Path | None:
    try:
        candidates = sorted(sys_class_hidraw.glob("hidraw*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            uevent = (candidate / "device/uevent").read_text(
                encoding="utf-8",
                errors="replace",
            )
            descriptor = (
                candidate / "device/report_descriptor"
            ).read_bytes()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if f"HID_ID={STEAM_DECK_HID_ID}" not in uevent:
            continue
        if not descriptor.startswith(b"\x06\xff\xff"):
            continue
        return dev_root / candidate.name
    return None

def find_steam_deck_usb_device(
    sys_bus_usb_devices: Path = Path("/sys/bus/usb/devices"),
) -> Path | None:
    try:
        candidates = sorted(sys_bus_usb_devices.glob("*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            vendor = (candidate / "idVendor").read_text(
                encoding="utf-8",
            ).strip().lower()
            product = (candidate / "idProduct").read_text(
                encoding="utf-8",
            ).strip().lower()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if (
            vendor == "28de"
            and product == "1205"
            and (candidate / "authorized").exists()
        ):
            return candidate
    return None

def reconcile_steam_deck_controller_authorization(
    *,
    sys_bus_usb_devices: Path = Path("/sys/bus/usb/devices"),
    usb_device_finder: Callable[[], Path | None] | None = None,
) -> bool:
    with _CONTROLLER_USB_LOCK:
        usb_device = (
            usb_device_finder()
            if usb_device_finder is not None
            else find_steam_deck_usb_device(sys_bus_usb_devices)
        )
        if usb_device is None:
            return False
        authorized_path = usb_device / "authorized"
        if authorized_path.read_text(encoding="utf-8").strip() == "1":
            return False
        authorized_path.write_text("1", encoding="utf-8")
        LOGGER.warning(
            "Restored Steam Deck built-in controller USB authorization at %s",
            usb_device,
        )
        return True

def reinitialize_steam_deck_trackpad_driver(
    device_path: Path | None = None,
    *,
    sys_class_hidraw: Path = Path("/sys/class/hidraw"),
    device_finder: Callable[[], Path | None] = find_steam_deck_hidraw,
    settle_seconds: float = 0.25,
    timeout_seconds: float = 3.0,
) -> Path:
    path = device_path or device_finder()
    if path is None:
        raise RuntimeError("Steam Deck trackpad device was not found")
    raw_device_link = sys_class_hidraw / path.name / "device"
    try:
        raw_device = raw_device_link.resolve(strict=True)
    except (FileNotFoundError, OSError) as error:
        raise RuntimeError(
            f"Unable to resolve the trackpad HID device {path}"
        ) from error

    physical_device = None
    for candidate in raw_device.parent.glob("0003:28DE:1205.*"):
        try:
            uevent = (candidate / "uevent").read_text(
                encoding="utf-8",
                errors="replace",
            )
            driver = (candidate / "driver").resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        unique_id = next(
            (
                line.partition("=")[2]
                for line in uevent.splitlines()
                if line.startswith("HID_UNIQ=")
            ),
            "",
        )
        if (
            f"HID_ID={STEAM_DECK_HID_ID}" in uevent
            and unique_id
            and driver.name == "hid-steam"
        ):
            physical_device = candidate
            break
    if physical_device is None:
        raise RuntimeError(
            "Steam Deck physical controller HID was not found"
        )

    device_id = physical_device.name
    driver_directory = (physical_device / "driver").resolve(strict=True)
    unbind_path = driver_directory / "unbind"
    bind_path = driver_directory / "bind"
    unbound = False
    try:
        unbind_path.write_text(device_id, encoding="utf-8")
        unbound = True
        time.sleep(max(0.05, float(settle_seconds)))
        bind_error = None
        for _attempt in range(3):
            try:
                bind_path.write_text(device_id, encoding="utf-8")
                bind_error = None
                break
            except OSError as error:
                bind_error = error
                time.sleep(0.2)
        if bind_error is not None:
            raise bind_error
        unbound = False
    finally:
        if unbound:
            try:
                bind_path.write_text(device_id, encoding="utf-8")
            except OSError:
                LOGGER.exception(
                    "Failed to restore the Steam Deck HID driver binding"
                )

    deadline = time.monotonic() + max(0.25, float(timeout_seconds))
    while time.monotonic() < deadline:
        recovered_path = device_finder()
        if recovered_path is not None:
            return recovered_path
        time.sleep(0.1)
    raise RuntimeError(
        "Steam Deck trackpad HID did not return after reinitialization"
    )

def power_cycle_steam_deck_controller(
    device_path: Path | None = None,
    *,
    sys_class_hidraw: Path = Path("/sys/class/hidraw"),
    sys_bus_usb_devices: Path = Path("/sys/bus/usb/devices"),
    device_finder: Callable[[], Path | None] = find_steam_deck_hidraw,
    usb_device_finder: Callable[[], Path | None] | None = None,
    disabled_seconds: float = 0.75,
    timeout_seconds: float = 6.0,
) -> Path:
    path = device_path or device_finder()
    usb_device = None
    if path is not None:
        try:
            raw_device = (
                sys_class_hidraw / path.name / "device"
            ).resolve(strict=True)
        except (FileNotFoundError, OSError):
            raw_device = None
        if raw_device is not None:
            for candidate in (raw_device, *raw_device.parents):
                try:
                    vendor = (candidate / "idVendor").read_text(
                        encoding="utf-8"
                    ).strip().lower()
                    product = (candidate / "idProduct").read_text(
                        encoding="utf-8"
                    ).strip().lower()
                except (FileNotFoundError, OSError):
                    continue
                if vendor == "28de" and product == "1205":
                    usb_device = candidate
                    break
    if usb_device is None:
        usb_device = (
            usb_device_finder()
            if usb_device_finder is not None
            else find_steam_deck_usb_device(sys_bus_usb_devices)
        )
    if usb_device is None:
        raise RuntimeError(
            "Steam Deck built-in controller USB device was not found"
        )

    authorized_path = usb_device / "authorized"
    with _CONTROLLER_USB_LOCK:
        disabled = False
        try:
            authorized_path.write_text("0", encoding="utf-8")
            disabled = True
            time.sleep(max(0.25, float(disabled_seconds)))
        finally:
            if disabled:
                enable_error = None
                for _attempt in range(5):
                    try:
                        authorized_path.write_text("1", encoding="utf-8")
                        enable_error = None
                        disabled = False
                        break
                    except OSError as error:
                        enable_error = error
                        time.sleep(0.2)
                if enable_error is not None:
                    raise RuntimeError(
                        "Failed to re-enable the Steam Deck controller"
                    ) from enable_error

        deadline = time.monotonic() + max(1.0, float(timeout_seconds))
        while time.monotonic() < deadline:
            recovered_path = device_finder()
            if recovered_path is not None:
                return recovered_path
            time.sleep(0.1)
    raise RuntimeError(
        "Steam Deck controller did not return after the USB power cycle"
    )
