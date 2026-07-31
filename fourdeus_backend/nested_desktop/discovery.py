"""Nested Desktop process, HID, and Wayland discovery."""

from __future__ import annotations

import os
from pathlib import Path
import re
import time
from typing import Sequence

from .constants import (
    RUSTDESK_KEYBOARD_NAME, RUSTDESK_MOUSE_NAME, STEAM_DECK_HID_ID,
    STEAM_DECK_TOUCHSCREEN_NAMES,
)
from .models import NestedDesktopSession


def _read_cmdline(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return []
    return [
        part.decode("utf-8", errors="replace")
        for part in raw.split(b"\0")
        if part
    ]

def _read_environ(path: Path) -> dict[str, str]:
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return {}
    variables = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        variables[key.decode("utf-8", errors="replace")] = value.decode(
            "utf-8",
            errors="replace",
        )
    return variables

def _read_parent_pid(process_directory: Path) -> int | None:
    try:
        lines = (process_directory / "status").read_text(
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None
    for line in lines.splitlines():
        if line.startswith("PPid:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None

def _option_value(arguments: Sequence[str], name: str) -> str | None:
    for index, argument in enumerate(arguments):
        if argument == name and index + 1 < len(arguments):
            return arguments[index + 1]
        prefix = f"{name}="
        if argument.startswith(prefix):
            return argument[len(prefix) :]
    return None

def _find_steam_app_id(
    pid: int,
    proc_root: Path,
    maximum_depth: int = 24,
) -> int | None:
    current_pid = pid
    for _ in range(maximum_depth):
        process_directory = proc_root / str(current_pid)
        for argument in _read_cmdline(process_directory / "cmdline"):
            match = re.fullmatch(r"AppId=(\d+)", argument)
            if match:
                return int(match.group(1))
        parent_pid = _read_parent_pid(process_directory)
        if parent_pid is None or parent_pid <= 1 or parent_pid == current_pid:
            return None
        current_pid = parent_pid
    return None

def _find_inherited_environment_value(
    pid: int,
    key: str,
    proc_root: Path,
    maximum_depth: int = 24,
) -> str | None:
    current_pid = pid
    for _ in range(maximum_depth):
        process_directory = proc_root / str(current_pid)
        value = _read_environ(
            process_directory / "environ"
        ).get(key)
        if value is not None:
            return value
        parent_pid = _read_parent_pid(process_directory)
        if (
            parent_pid is None
            or parent_pid <= 1
            or parent_pid == current_pid
        ):
            return None
        current_pid = parent_pid
    return None

def find_nested_desktop_session(
    proc_root: Path = Path("/proc"),
) -> NestedDesktopSession | None:
    try:
        process_directories = list(proc_root.iterdir())
    except OSError:
        return None

    for process_directory in process_directories:
        if not process_directory.name.isdigit():
            continue
        arguments = _read_cmdline(process_directory / "cmdline")
        if not arguments:
            continue
        executable = Path(arguments[0]).name
        if executable != "kwin_wayland":
            continue
        display = _option_value(arguments, "--xwayland-display")
        xauthority = _option_value(arguments, "--xwayland-xauthority")
        wayland_display = _option_value(arguments, "--socket") or "wayland-0"
        if (
            not display
            or not xauthority
            or "nested-desktop." not in xauthority
        ):
            continue
        try:
            pid = int(process_directory.name)
        except ValueError:
            continue
        app_id = _find_steam_app_id(pid, proc_root)
        authority_path = Path(xauthority)
        if app_id is None or not authority_path.is_file():
            continue
        runtime_directory = authority_path.parent
        dbus_address = _find_nested_dbus_address(
            process_directories,
            runtime_directory,
        )
        if dbus_address is None:
            continue
        return NestedDesktopSession(
            pid=pid,
            app_id=app_id,
            display=display,
            xauthority=authority_path,
            dbus_address=dbus_address,
            wayland_display=wayland_display,
            software_cursor_forced=(
                _find_inherited_environment_value(
                    pid,
                    "KWIN_FORCE_SW_CURSOR",
                    proc_root,
                )
                == "1"
            ),
        )
    return None

def _find_nested_dbus_address(
    process_directories: Sequence[Path],
    runtime_directory: Path,
) -> str | None:
    expected_runtime = str(runtime_directory)
    fallback = None
    for process_directory in process_directories:
        if not process_directory.name.isdigit():
            continue
        environment = _read_environ(process_directory / "environ")
        if environment.get("XDG_RUNTIME_DIR") != expected_runtime:
            continue
        address = environment.get("DBUS_SESSION_BUS_ADDRESS")
        if not address:
            continue
        if "guid=" in address:
            return address
        executable = _read_cmdline(process_directory / "cmdline")
        if executable and Path(executable[0]).name not in (
            "dbus-run-session",
            "dbus-daemon",
        ):
            fallback = address
    return fallback

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
            descriptor = (candidate / "device/report_descriptor").read_bytes()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if f"HID_ID={STEAM_DECK_HID_ID}" not in uevent:
            continue
        if not descriptor.startswith(b"\x06\xff\xff"):
            continue
        return dev_root / candidate.name
    return None


def find_steam_deck_touchscreen(
    sys_class_input: Path = Path("/sys/class/input"),
    dev_root: Path = Path("/dev/input"),
) -> Path | None:
    try:
        candidates = sorted(sys_class_input.glob("event*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            name = (candidate / "device/name").read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if name in STEAM_DECK_TOUCHSCREEN_NAMES:
            return dev_root / candidate.name
    return None


def find_rustdesk_joystick(
    sys_class_input: Path = Path("/sys/class/input"),
    dev_root: Path = Path("/dev/input"),
) -> Path | None:
    try:
        candidates = sorted(sys_class_input.glob("js*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            name = (candidate / "device/name").read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if name == RUSTDESK_MOUSE_NAME:
            return dev_root / candidate.name
    return None

def find_rustdesk_keyboard(
    sys_class_input: Path = Path("/sys/class/input"),
    dev_root: Path = Path("/dev/input"),
) -> Path | None:
    try:
        candidates = sorted(sys_class_input.glob("event*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            name = (candidate / "device/name").read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if name == RUSTDESK_KEYBOARD_NAME:
            return dev_root / candidate.name
    return None

def _wayland_alias_paths(
    session: NestedDesktopSession,
) -> tuple[Path, Path]:
    runtime_directory = session.xauthority.parent
    return (
        runtime_directory.parent / session.wayland_display,
        runtime_directory / session.wayland_display,
    )

def _resolved_link(path: Path) -> Path | None:
    try:
        target = Path(os.readlink(path))
    except OSError:
        return None
    if not target.is_absolute():
        target = path.parent / target
    return target.resolve(strict=False)

def _is_nested_wayland_target(path: Path, runtime_root: Path) -> bool:
    try:
        relative = path.relative_to(runtime_root)
    except ValueError:
        return False
    return bool(
        len(relative.parts) == 2
        and relative.parts[0].startswith("nested-desktop.")
        and relative.parts[1].startswith("wayland-")
    )

def ensure_nested_wayland_alias(
    session: NestedDesktopSession,
) -> Path | None:
    alias, target = _wayland_alias_paths(session)
    if not target.exists():
        return None
    if alias.is_symlink():
        current = _resolved_link(alias)
        if current == target.resolve(strict=False):
            return alias
        if current is None or not _is_nested_wayland_target(
            current,
            alias.parent,
        ):
            return None
    elif os.path.lexists(alias):
        return None

    temporary = alias.with_name(
        f".{alias.name}.4deus-{os.getpid()}-{time.monotonic_ns()}"
    )
    try:
        os.symlink(target, temporary)
        os.replace(temporary, alias)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        return None
    return alias

def remove_nested_wayland_alias(
    session: NestedDesktopSession | None,
    alias: Path | None,
):
    if session is None or alias is None or not alias.is_symlink():
        return
    _, target = _wayland_alias_paths(session)
    if _resolved_link(alias) != target.resolve(strict=False):
        return
    try:
        alias.unlink()
    except OSError:
        pass
