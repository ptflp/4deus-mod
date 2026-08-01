import asyncio
from collections import deque
import os
import threading
import unittest

from fourdeus_backend.nested_desktop.clipboard_content import ClipboardContent
from fourdeus_backend.nested_desktop.clipboard_klipper import (
    KlipperClipboardMonitor,
    content_from_klipper,
)


class KlipperClipboardMonitorTests(unittest.TestCase):
    def test_recognizes_complete_file_uri_lists(self):
        self.assertEqual(
            content_from_klipper(
                "file:///tmp/one%20file.pdf\nfile:///tmp/two.zip"
            ),
            ClipboardContent(file_uris=(
                "file:///tmp/one%20file.pdf",
                "file:///tmp/two.zip",
            )),
        )
        self.assertEqual(
            content_from_klipper(
                "file:///tmp/one.zip file:/tmp/two.pdf"
            ),
            ClipboardContent(file_uris=(
                "file:///tmp/one.zip",
                "file:///tmp/two.pdf",
            )),
        )

    def test_mixed_or_regular_values_remain_text(self):
        value = "file:///tmp/one.pdf\nnot a file URI"
        self.assertEqual(
            content_from_klipper(value),
            ClipboardContent(text=value),
        )
        self.assertEqual(
            content_from_klipper("ordinary text"),
            ClipboardContent(text="ordinary text"),
        )

    def test_dispatch_coalesces_bursts_to_the_latest_value(self):
        monitor = KlipperClipboardMonitor.__new__(KlipperClipboardMonitor)
        monitor.read_fd, monitor.write_fd = os.pipe2(
            os.O_CLOEXEC | os.O_NONBLOCK
        )
        monitor.lock = threading.Lock()
        monitor.pending = deque((
            ClipboardContent(text="old"),
            ClipboardContent(text="new"),
        ))
        os.write(monitor.write_fd, b"\0\0")
        try:
            self.assertEqual(
                monitor.dispatch(),
                [ClipboardContent(text="new")],
            )
            self.assertEqual(monitor.dispatch(), [])
        finally:
            os.close(monitor.read_fd)
            os.close(monitor.write_fd)

    def test_focus_release_flushes_lazy_clipboard_and_restores_windows(self):
        class Klipper:
            def __init__(self):
                self.values = deque((
                    "old clipboard",
                    "file:///tmp/new.pdf",
                ))

            async def call_get_clipboard_contents(self):
                if len(self.values) > 1:
                    return self.values.popleft()
                return self.values[0]

        class KWin:
            def __init__(self):
                self.show_desktop = []

            async def get_showing_desktop(self):
                return False

            async def call_show_desktop(self, showing):
                self.show_desktop.append(showing)

        monitor = KlipperClipboardMonitor.__new__(KlipperClipboardMonitor)
        monitor.read_fd, monitor.write_fd = os.pipe2(
            os.O_CLOEXEC | os.O_NONBLOCK
        )
        monitor.lock = threading.Lock()
        monitor.pending = deque()
        monitor.last_content = ClipboardContent(text="old clipboard")
        monitor.focus_release_probe_delays = (0,)
        kwin = KWin()
        try:
            asyncio.run(monitor._release_focus_for_clipboard(
                Klipper(),
                kwin,
            ))

            self.assertEqual(kwin.show_desktop, [True, False])
            self.assertEqual(monitor.dispatch(), [ClipboardContent(
                file_uris=("file:///tmp/new.pdf",),
            )])
        finally:
            os.close(monitor.read_fd)
            os.close(monitor.write_fd)


if __name__ == "__main__":
    unittest.main()
