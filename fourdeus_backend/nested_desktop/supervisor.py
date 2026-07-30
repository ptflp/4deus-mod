"""Supervises the unprivileged Nested Desktop input worker."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import pwd
import select
import shutil
import subprocess
import threading
from typing import Callable, Mapping

from .bindings import normalize_nested_desktop_bindings
from .constants import ACTION_HIDE_KEYBOARD, ACTION_SHOW_KEYBOARD


class NestedDesktopMouseSupervisor:
    def __init__(
        self,
        plugin_root: str | Path,
        logger: logging.Logger,
        mouse_enabled: bool = True,
        inertia_enabled: bool = True,
        bindings_enabled: bool = True,
        bindings: Mapping[str, object] | None = None,
        rustdesk_pointer_fix_enabled: bool = True,
        rustdesk_scroll_inertia_enabled: bool = False,
        rustdesk_focus_on_input_enabled: bool = False,
        run_as_user: str | None = None,
        action_callback: Callable[[str], None] | None = None,
    ):
        self.plugin_root = Path(plugin_root)
        self.logger = logger
        self.mouse_enabled = mouse_enabled
        self.inertia_enabled = inertia_enabled
        self.bindings_enabled = bindings_enabled
        self.bindings = normalize_nested_desktop_bindings(bindings)
        self.rustdesk_pointer_fix_enabled = rustdesk_pointer_fix_enabled
        self.rustdesk_scroll_inertia_enabled = (
            rustdesk_scroll_inertia_enabled
        )
        self.rustdesk_focus_on_input_enabled = (
            rustdesk_focus_on_input_enabled
        )
        self.run_as_user = run_as_user
        self.action_callback = action_callback
        self.suspended = False
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen | None = None
        self.process_lock = threading.Lock()

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._supervise,
            name="4deus-nested-mouse-supervisor",
            daemon=True,
        )
        self.thread.start()

    def running(self) -> bool:
        thread = self.thread
        with self.process_lock:
            process = self.process
        return bool(
            thread is not None
            and thread.is_alive()
            and process is not None
            and process.poll() is None
        )

    def stop(self):
        self.stop_event.set()
        with self.process_lock:
            process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
        thread = self.thread
        if thread is not None:
            thread.join(timeout=3)
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=1)
        self.thread = None

    def set_inertia_enabled(self, enabled: bool):
        if enabled == self.inertia_enabled:
            return
        self._restart_with(lambda: setattr(self, "inertia_enabled", enabled))

    def set_mouse_enabled(self, enabled: bool):
        if enabled == self.mouse_enabled:
            return
        self._restart_with(lambda: setattr(self, "mouse_enabled", enabled))

    def set_rustdesk_pointer_fix_enabled(self, enabled: bool):
        if enabled == self.rustdesk_pointer_fix_enabled:
            return
        self._restart_with(
            lambda: setattr(
                self,
                "rustdesk_pointer_fix_enabled",
                enabled,
            )
        )

    def set_rustdesk_scroll_inertia_enabled(self, enabled: bool):
        if enabled == self.rustdesk_scroll_inertia_enabled:
            return
        self._restart_with(
            lambda: setattr(
                self,
                "rustdesk_scroll_inertia_enabled",
                enabled,
            )
        )

    def set_rustdesk_focus_on_input_enabled(self, enabled: bool):
        if enabled == self.rustdesk_focus_on_input_enabled:
            return
        self._restart_with(
            lambda: setattr(
                self,
                "rustdesk_focus_on_input_enabled",
                enabled,
            )
        )

    def set_bindings(
        self,
        enabled: bool,
        bindings: Mapping[str, object],
    ):
        normalized = normalize_nested_desktop_bindings(bindings)
        if (
            enabled == self.bindings_enabled
            and normalized == self.bindings
        ):
            return

        def apply():
            self.bindings_enabled = enabled
            self.bindings = normalized

        self._restart_with(apply)

    def set_suspended(self, suspended: bool):
        if not isinstance(suspended, bool):
            raise TypeError("Suspended must be a boolean")
        with self.process_lock:
            if suspended == self.suspended:
                return
            self.suspended = suspended
            process = self.process
            if process is not None and process.poll() is None:
                self._write_control(process, suspended)

    def _write_control(
        self,
        process: subprocess.Popen,
        suspended: bool,
    ):
        stream = process.stdin
        if stream is None:
            return
        try:
            stream.write(b"suspend\n" if suspended else b"resume\n")
            stream.flush()
        except (BrokenPipeError, OSError, ValueError):
            if process.poll() is None:
                self.logger.warning(
                    "Failed to update Nested Desktop bridge suspension"
                )

    def _restart_with(self, apply: Callable[[], None]):
        was_started = bool(
            self.thread is not None and self.thread.is_alive()
        )
        if was_started:
            self.stop()
        apply()
        if (
            self.mouse_enabled
            or self.bindings_enabled
            or self.rustdesk_pointer_fix_enabled
            or self.rustdesk_focus_on_input_enabled
        ):
            self.start()

    def _dispatch_action(self, action: str):
        if action not in {
            ACTION_HIDE_KEYBOARD,
            ACTION_SHOW_KEYBOARD,
        }:
            self.logger.warning(
                "Ignoring unknown Nested Desktop worker action %s",
                action,
            )
            return
        callback = self.action_callback
        if callback is None:
            return
        try:
            callback(action)
        except Exception:
            self.logger.exception(
                "Failed to dispatch Nested Desktop worker action %s",
                action,
            )

    def _supervise(self):
        worker_path = self.plugin_root / "nested_desktop_mouse.py"
        python_executable = shutil.which("python3") or "/usr/bin/python3"
        while not self.stop_event.is_set():
            try:
                with self.process_lock:
                    launch_suspended = self.suspended
                command = [
                    python_executable,
                    str(worker_path),
                    "--worker",
                ]
                worker_user = None
                worker_group = None
                worker_groups = None
                environment = {
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                }
                if self.run_as_user and os.geteuid() == 0:
                    account = pwd.getpwnam(self.run_as_user)
                    worker_user = account.pw_uid
                    worker_group = account.pw_gid
                    worker_groups = os.getgrouplist(
                        self.run_as_user,
                        account.pw_gid,
                    )
                    environment.update(
                        {
                            "HOME": account.pw_dir,
                            "LOGNAME": account.pw_name,
                            "USER": account.pw_name,
                            "XDG_RUNTIME_DIR": (
                                f"/run/user/{account.pw_uid}"
                            ),
                        }
                    )
                if not self.inertia_enabled:
                    command.append("--no-inertia")
                if not self.mouse_enabled:
                    command.append("--no-mouse-bridge")
                if not self.bindings_enabled:
                    command.append("--no-bindings")
                if not self.rustdesk_pointer_fix_enabled:
                    command.append("--no-rustdesk-pointer-fix")
                if self.rustdesk_scroll_inertia_enabled:
                    command.append("--rustdesk-scroll-inertia")
                if self.rustdesk_focus_on_input_enabled:
                    command.append("--rustdesk-focus-on-input")
                if launch_suspended:
                    command.append("--suspended")
                command.extend(
                    (
                        "--bindings-json",
                        json.dumps(
                            self.bindings,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                )
                process = subprocess.Popen(
                    command,
                    cwd=self.plugin_root,
                    env=environment,
                    close_fds=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    user=worker_user,
                    group=worker_group,
                    extra_groups=worker_groups,
                )
            except Exception:
                self.logger.exception(
                    "Failed to start the Nested Desktop mouse bridge"
                )
                if self.stop_event.wait(2):
                    return
                continue

            with self.process_lock:
                self.process = process
                if self.suspended != launch_suspended:
                    self._write_control(process, self.suspended)
            self.logger.info("Started the Nested Desktop mouse bridge")
            action_buffer = b""
            while process.poll() is None and not self.stop_event.is_set():
                output = process.stdout
                if output is None:
                    self.stop_event.wait(0.5)
                    continue
                readable, _, _ = select.select([output], [], [], 0.5)
                if not readable:
                    continue
                chunk = os.read(output.fileno(), 4096)
                if not chunk:
                    continue
                action_buffer += chunk
                lines = action_buffer.split(b"\n")
                action_buffer = lines.pop()
                for line in lines:
                    action = line.decode("utf-8", errors="replace").strip()
                    if action:
                        self._dispatch_action(action)
            if self.stop_event.is_set():
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stdin is not None:
                    process.stdin.close()
                break
            if process.stdout is not None:
                process.stdout.close()
            if process.stdin is not None:
                process.stdin.close()
            self.logger.warning(
                "Nested Desktop mouse bridge exited with code %s; restarting",
                process.returncode,
            )
            if self.stop_event.wait(2):
                break

        with self.process_lock:
            self.process = None
