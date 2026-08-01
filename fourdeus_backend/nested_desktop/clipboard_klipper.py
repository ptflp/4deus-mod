"""Event-driven Klipper clipboard updates for native Wayland sources."""

from __future__ import annotations

import asyncio
from collections import deque
import logging
import os
import re
import threading

from .clipboard_content import ClipboardContent, normalize_file_uris


LOGGER = logging.getLogger("4deus-nested-mouse")
KLIPPER_BUS_NAME = "org.kde.klipper"
KLIPPER_OBJECT_PATH = "/klipper"
KLIPPER_INTERFACE = "org.kde.klipper.klipper"
KWIN_BUS_NAME = "org.kde.KWin"
KWIN_OBJECT_PATH = "/KWin"
KWIN_INTERFACE = "org.kde.KWin"
CLIPBOARD_FOCUS_RELEASE_PROBE_DELAYS = (0.05, 0.15, 0.35, 0.5)


def content_from_klipper(value: str) -> ClipboardContent:
    """Interpret Klipper's textual representation without guessing mixtures."""
    if not isinstance(value, str) or not value:
        return ClipboardContent()
    payload = value.strip()
    payload = re.sub(
        r"^(?:copy|cut)(?:\r?\n|\s+(?=file:/))",
        "",
        payload,
        count=1,
        flags=re.IGNORECASE,
    )
    candidates = tuple(filter(None, (
        candidate.strip()
        for candidate in re.split(r"\s+(?=file:/)", payload)
    )))
    file_uris = normalize_file_uris(candidates)
    if file_uris and len(file_uris) == len(candidates):
        return ClipboardContent(file_uris=file_uris)
    return ClipboardContent(text=value)


class KlipperClipboardMonitor:
    """Bridge Klipper signals into a selectable, non-polling descriptor."""

    def __init__(self, bus_address: str | None = None):
        self.bus_address = bus_address
        self.read_fd, self.write_fd = os.pipe2(
            os.O_CLOEXEC | os.O_NONBLOCK
        )
        self.lock = threading.Lock()
        self.pending: deque[ClipboardContent] = deque()
        self.last_content: ClipboardContent | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop_async: asyncio.Event | None = None
        self.klipper_interface = None
        self.kwin_interface = None
        self.focus_release_task: asyncio.Task | None = None
        self.focus_release_probe_delays = (
            CLIPBOARD_FOCUS_RELEASE_PROBE_DELAYS
        )
        self.close_requested = threading.Event()
        self.thread = threading.Thread(
            target=self._thread_main,
            name="4deus-klipper-clipboard",
            daemon=True,
        )
        self.thread.start()

    def _thread_main(self):
        try:
            asyncio.run(self._listen())
        except Exception as error:
            if not self.close_requested.is_set():
                LOGGER.info("Klipper clipboard monitor is unavailable: %s", error)

    async def _listen(self):
        from dbus_next.aio import MessageBus

        bus = await MessageBus(bus_address=self.bus_address).connect()
        introspection = await bus.introspect(
            KLIPPER_BUS_NAME,
            KLIPPER_OBJECT_PATH,
        )
        proxy = bus.get_proxy_object(
            KLIPPER_BUS_NAME,
            KLIPPER_OBJECT_PATH,
            introspection,
        )
        interface = proxy.get_interface(KLIPPER_INTERFACE)
        kwin_interface = None
        try:
            kwin_introspection = await bus.introspect(
                KWIN_BUS_NAME,
                KWIN_OBJECT_PATH,
            )
            kwin_proxy = bus.get_proxy_object(
                KWIN_BUS_NAME,
                KWIN_OBJECT_PATH,
                kwin_introspection,
            )
            kwin_interface = kwin_proxy.get_interface(KWIN_INTERFACE)
        except Exception as error:
            LOGGER.info(
                "KWin clipboard focus release is unavailable: %s",
                error,
            )
        self.loop = asyncio.get_running_loop()
        self.stop_async = asyncio.Event()
        self.klipper_interface = interface
        self.kwin_interface = kwin_interface
        if self.close_requested.is_set():
            self.stop_async.set()

        def clipboard_updated():
            task = asyncio.create_task(self._read_current(interface))
            task.add_done_callback(self._log_task_failure)

        interface.on_clipboard_history_updated(clipboard_updated)
        LOGGER.info("Klipper clipboard fast path connected")
        try:
            stop_task = asyncio.create_task(self.stop_async.wait())
            disconnect_task = asyncio.create_task(bus.wait_for_disconnect())
            _done, pending = await asyncio.wait(
                (stop_task, disconnect_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        finally:
            interface.off_clipboard_history_updated(clipboard_updated)
            focus_release_task = self.focus_release_task
            if (
                focus_release_task is not None
                and not focus_release_task.done()
            ):
                try:
                    await focus_release_task
                except Exception:
                    pass
            self.focus_release_task = None
            self.klipper_interface = None
            self.kwin_interface = None
            bus.disconnect()

    async def _read_current(self, interface):
        value = await interface.call_get_clipboard_contents()
        content = content_from_klipper(str(value))
        self._publish(content)
        return content

    def _publish(self, content: ClipboardContent) -> bool:
        """Queue one genuinely new value and wake the runtime event loop."""
        if not content.available:
            return False
        with self.lock:
            if content == self.last_content:
                return False
            self.last_content = content
            self.pending.append(content)
        try:
            os.write(self.write_fd, b"\0")
        except (BlockingIOError, OSError):
            pass
        return True

    async def _release_focus_for_clipboard(self, klipper, kwin):
        was_showing_desktop = bool(
            await kwin.get_showing_desktop()
        )
        before = str(await klipper.call_get_clipboard_contents())
        changed = False
        if not was_showing_desktop:
            await kwin.call_show_desktop(True)
        try:
            for delay in self.focus_release_probe_delays:
                await asyncio.sleep(delay)
                value = str(await klipper.call_get_clipboard_contents())
                content = content_from_klipper(value)
                self._publish(content)
                if value != before:
                    changed = True
                    break
        finally:
            if not was_showing_desktop:
                await kwin.call_show_desktop(False)
        if changed:
            LOGGER.info(
                "Released Nested Desktop focus for pending clipboard data"
            )

    def _start_focus_release(self):
        if (
            self.close_requested.is_set()
            or self.klipper_interface is None
            or self.kwin_interface is None
            or (
                self.focus_release_task is not None
                and not self.focus_release_task.done()
            )
        ):
            return
        self.focus_release_task = asyncio.create_task(
            self._release_focus_for_clipboard(
                self.klipper_interface,
                self.kwin_interface,
            )
        )
        self.focus_release_task.add_done_callback(self._log_task_failure)

    def release_focus_for_clipboard(self) -> bool:
        """Briefly release the inner active window after Gamescope exits."""
        loop = self.loop
        if (
            loop is None
            or self.klipper_interface is None
            or self.kwin_interface is None
            or self.close_requested.is_set()
        ):
            return False
        loop.call_soon_threadsafe(self._start_focus_release)
        return True

    @staticmethod
    def _log_task_failure(task: asyncio.Task):
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            LOGGER.info("Klipper clipboard task failed: %s", error)

    def fileno(self) -> int:
        return self.read_fd

    def dispatch(self) -> list[ClipboardContent]:
        while True:
            try:
                if not os.read(self.read_fd, 4096):
                    break
            except BlockingIOError:
                break
            except OSError:
                return []
        with self.lock:
            if not self.pending:
                return []
            latest = self.pending[-1]
            self.pending.clear()
        return [latest]

    def close(self):
        if self.close_requested.is_set():
            return
        self.close_requested.set()
        loop = self.loop
        stop_async = self.stop_async
        if loop is not None and stop_async is not None:
            loop.call_soon_threadsafe(stop_async.set)
        self.thread.join(timeout=2.0)
        for descriptor_name in ("read_fd", "write_fd"):
            descriptor = getattr(self, descriptor_name, -1)
            setattr(self, descriptor_name, -1)
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
