from pathlib import Path
import base64
from collections import deque
import json
import os
import socket
import struct
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from nested_desktop_mouse import (
    BACK_BUTTON,
    ACTION_HIDE_KEYBOARD,
    ACTION_MOUSE_LEFT,
    ACTION_MOUSE_MIDDLE,
    ACTION_MOUSE_RIGHT,
    ACTION_SHOW_KEYBOARD,
    BindingUpdate,
    BUTTON_SOURCE_MASKS,
    CapturedPointerUpdate,
    ClipboardContent,
    CursorSnapshot,
    DEFAULT_NESTED_DESKTOP_BINDINGS,
    EIS_KEY_CODES,
    GamescopeCursorCompositor,
    GamescopePointerInterceptor,
    GamescopePointerTranslator,
    GAMESCOPE_POINTER_RELAY_DELAY,
    IDLE_INPUT_FRAME_INTERVAL,
    INPUT_FRAME_INTERVAL,
    InputBindingTranslator,
    LEFT_PAD_TOUCHED,
    LEFT_TRIGGER,
    JoystickEvent,
    LinuxInputEvent,
    NestedDesktopCursorOverlay,
    NestedDesktopClipboardBridge,
    NestedDesktopSession,
    PointerUpdate,
    RIGHT_PAD_TOUCHED,
    RIGHT_PAD_PRESSED,
    RIGHT_TRIGGER,
    TrackpadState,
    TrackpadTranslator,
    X11ClipboardEndpoint,
    NestedDesktopMouseRuntime,
    NestedDesktopMouseSupervisor,
    RustDeskMouseTranslator,
    RustDeskRelayTranslator,
    RustDeskScrollInertia,
    STEAM_UI_APP_ID,
    cursor_alpha_mask,
    decode_gamescope_display,
    encode_rustdesk_ipc_frame,
    ensure_nested_wayland_alias,
    find_nested_desktop_session,
    find_rustdesk_keyboard,
    find_rustdesk_joystick,
    find_steam_deck_hidraw,
    outlined_cursor_snapshot,
    parse_joystick_events,
    parse_trackpad_report,
    prioritize_focus_app,
    process_uses_proton,
    query_rustdesk_video_connection_count,
    receive_rustdesk_ipc_frame,
    remove_nested_wayland_alias,
    scaled_cursor_snapshot,
    should_forward_back_button,
    should_forward_pointer,
)
from fourdeus_backend.nested_desktop.clipboard_content import (
    encode_file_uri_list,
    encode_gnome_copied_files,
    parse_file_uri_list,
)


class NestedDesktopSupervisorTests(unittest.TestCase):
    def test_module_gate_keeps_child_settings_without_starting_worker(self):
        supervisor = NestedDesktopMouseSupervisor(
            plugin_root=Path("/tmp/4deus-test"),
            logger=MagicMock(),
            module_enabled=False,
        )
        supervisor.start = MagicMock()

        supervisor.set_mouse_enabled(False)

        self.assertFalse(supervisor.mouse_enabled)
        supervisor.start.assert_not_called()

        supervisor.set_module_enabled(True)

        self.assertTrue(supervisor.module_enabled)
        supervisor.start.assert_called_once_with()

    def test_clipboard_alone_starts_the_worker(self):
        supervisor = NestedDesktopMouseSupervisor(
            plugin_root=Path("/tmp/4deus-test"),
            logger=MagicMock(),
            mouse_enabled=False,
            bindings_enabled=False,
            touchscreen_enabled=False,
            rustdesk_pointer_fix_enabled=False,
            rustdesk_focus_on_input_enabled=False,
            clipboard_enabled=False,
        )
        supervisor.start = MagicMock()

        supervisor.set_clipboard_enabled(True)

        self.assertTrue(supervisor.clipboard_enabled)
        supervisor.start.assert_called_once_with()

    def test_decodes_clipboard_response_without_logging_its_text(self):
        supervisor = NestedDesktopMouseSupervisor(
            plugin_root=Path("/tmp/4deus-test"),
            logger=MagicMock(),
            clipboard_enabled=True,
        )
        with supervisor.clipboard_condition:
            supervisor.pending_clipboard_requests.add(7)

        encoded = base64.b64encode("общий".encode("utf-8")).decode("ascii")
        supervisor._handle_worker_output(
            f"clipboard-text:7:1:{encoded}"
        )

        self.assertEqual(supervisor.clipboard_responses[7], "общий")


class NestedDesktopClipboardTests(unittest.TestCase):
    def test_owner_handoff_caps_only_the_stale_request_deadline(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.display = 1
        endpoint.selection = 2
        endpoint.owner_window = 10
        endpoint.request_pending = True
        endpoint.request_again = False
        endpoint.discard_pending = False
        endpoint.request_deadline = 50.0
        endpoint.clock = MagicMock(return_value=20.0)
        endpoint.x11 = MagicMock()
        endpoint.x11.XGetSelectionOwner.return_value = 99

        endpoint._request_current()

        self.assertTrue(endpoint.request_again)
        self.assertTrue(endpoint.discard_pending)
        self.assertAlmostEqual(endpoint.request_deadline, 20.1)

    def test_new_content_rotates_the_x11_selection_owner(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.display = 1
        endpoint.selection = 2
        endpoint.window = 10
        endpoint.owner_window = 11
        endpoint.request_pending = False
        endpoint.x11 = MagicMock()
        endpoint._create_window = MagicMock(return_value=12)
        copied = ClipboardContent(text="new clipboard sequence")
        endpoint._normalize_content = MagicMock(return_value=copied)
        endpoint.x11.XGetSelectionOwner.return_value = 12

        self.assertTrue(endpoint.set_content(copied))

        endpoint.x11.XSetSelectionOwner.assert_called_once_with(
            1,
            2,
            12,
            0,
        )
        endpoint.x11.XDestroyWindow.assert_called_once_with(1, 11)
        self.assertEqual(endpoint.owner_window, 12)
        self.assertEqual(endpoint.content, copied)

    def test_rotated_owner_is_not_mistaken_for_an_external_copy(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.display = 1
        endpoint.selection = 2
        endpoint.window = 10
        endpoint.owner_window = 12
        endpoint.x11 = MagicMock()
        endpoint.x11.XGetSelectionOwner.return_value = 12

        endpoint._request_current()

        endpoint.x11.XConvertSelection.assert_not_called()

    def test_endpoint_exposes_its_x11_connection_descriptor(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.display = 3
        endpoint.connection_fd = 17

        self.assertEqual(endpoint.fileno(), 17)

        endpoint.connection_fd = -1
        self.assertEqual(endpoint.fileno(), -1)

    def test_prefers_png_and_utf8_when_an_owner_offers_both(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.image_atoms = {
            "image/png": 20,
            "image/jpeg": 21,
            "image/webp": 22,
            "image/bmp": 23,
        }
        endpoint.preferred_file_targets = (30, 31)
        endpoint.preferred_text_targets = (10, 11)
        endpoint.platform_file_atoms = {
            "application/vnd.portal.filetransfer": 40,
            "application/vnd.portal.files": 41,
        }

        selected = endpoint._supported_targets((11, 21, 10, 20))

        self.assertEqual(list(selected), [20, 10])

    def test_prefers_file_image_and_text_without_reading_file_bytes(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.image_atoms = {
            "image/png": 20,
            "image/jpeg": 21,
            "image/webp": 22,
            "image/bmp": 23,
        }
        endpoint.preferred_file_targets = (30, 31)
        endpoint.preferred_text_targets = (10, 11)
        endpoint.platform_file_atoms = {
            "application/vnd.portal.filetransfer": 40,
            "application/vnd.portal.files": 41,
        }

        selected = endpoint._supported_targets((11, 30, 20, 10))

        self.assertEqual(list(selected), [30, 20, 10])

    def test_file_uri_lists_accept_only_local_copyable_paths(self):
        parsed = parse_file_uri_list(
            b"cut\n"
            b"# copied by a file manager\r\n"
            b"file:///tmp/one%20file\r\n"
            b"file://localhost/tmp/two\r\n"
            b"https://example.com/not-local\r\n"
            b"file://remote-host/tmp/not-local\r\n"
        )

        self.assertEqual(
            parsed,
            ("file:///tmp/one%20file", "file:///tmp/two"),
        )
        self.assertEqual(
            encode_file_uri_list(parsed),
            b"file:///tmp/one%20file\r\nfile:///tmp/two\r\n",
        )
        self.assertEqual(
            encode_gnome_copied_files(parsed),
            b"copy\nfile:///tmp/one%20file\nfile:///tmp/two\n",
        )

    def test_serves_file_manager_cut_state_as_copy_only(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.display = 1
        endpoint.selection = 2
        endpoint.targets = 3
        endpoint.uri_list = 4
        endpoint.gnome_copied_files = 5
        endpoint.kde_uri_list = 10
        endpoint.kde_cut_selection = 6
        endpoint.file_targets = {4, 5}
        endpoint.platform_file_atoms = {}
        endpoint.platform_file_mimes_by_atom = {}
        endpoint.supported_text_targets = set()
        endpoint.image_atoms = {}
        endpoint.x11 = MagicMock()
        endpoint.content = ClipboardContent(
            file_uris=("file:///tmp/copied",),
        )
        endpoint._write_property_bytes = MagicMock()
        request = SimpleNamespace(
            requestor=7,
            selection=2,
            target=6,
            property=8,
            time=9,
        )

        endpoint._respond_to_request(request)

        endpoint._write_property_bytes.assert_called_once_with(
            7,
            8,
            6,
            b"0",
        )

    def test_large_image_limit_does_not_discard_valid_text(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.max_text_bytes = 16
        endpoint.max_bytes = 8
        endpoint.image_atoms = {"image/png": 20}

        with self.assertLogs("4deus-nested-mouse", level="WARNING"):
            normalized = endpoint._normalize_content(
                ClipboardContent(
                    text="kept",
                    image_mime="image/png",
                    image=b"123456789",
                )
            )

        self.assertEqual(normalized, ClipboardContent(text="kept"))

    def test_normalization_keeps_only_bounded_platform_file_formats(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.max_text_bytes = 16
        endpoint.max_bytes = 64
        endpoint.image_atoms = {}

        normalized = endpoint._normalize_content(ClipboardContent(
            platform_file_formats=(
                ("application/vnd.portal.filetransfer", b"token"),
                ("application/x-unsafe", b"ignored"),
            ),
        ))

        self.assertEqual(
            normalized.platform_file_formats,
            (("application/vnd.portal.filetransfer", b"token"),),
        )

    def test_platform_file_formats_are_removed_with_file_sharing(self):
        content = ClipboardContent(
            text="kept",
            file_uris=("file:///tmp/copied",),
            platform_file_formats=((
                "application/vnd.portal.filetransfer",
                b"token",
            ),),
        )

        self.assertEqual(content.without_files(), ClipboardContent(text="kept"))

    def test_serves_large_payload_in_x11_safe_property_chunks(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.x11 = MagicMock()
        endpoint.display = 1
        endpoint.property_chunk_bytes = 4

        endpoint._write_property_bytes(2, 3, 4, b"abcdefghij")

        calls = endpoint.x11.XChangeProperty.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual([call.args[5] for call in calls], [0, 2, 2])
        self.assertEqual([call.args[7] for call in calls], [4, 4, 2])

    def test_receives_incremental_image_chunks_before_publishing(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.pending_target = 20
        endpoint.window = 1
        endpoint.property = 2
        endpoint.incremental_buffer = bytearray()
        endpoint.incremental_discard = False
        endpoint.max_bytes = 64
        endpoint.max_text_bytes = 16
        endpoint.targets = 5
        endpoint.file_targets = set()
        endpoint.image_mimes_by_atom = {20: "image/png"}
        endpoint.platform_file_mimes_by_atom = {}
        endpoint.clock = MagicMock(return_value=1.0)
        endpoint.x11 = MagicMock()
        endpoint.display = 3
        endpoint._read_property = MagicMock(side_effect=(
            SimpleNamespace(format=8, type_atom=20, bytes_value=b"PNG-"),
            SimpleNamespace(format=8, type_atom=20, bytes_value=b""),
        ))
        endpoint._consume_target = MagicMock(return_value=[])
        notification = SimpleNamespace(
            window=1,
            atom=2,
            state=0,
        )

        endpoint._handle_incremental_property(notification)
        endpoint._handle_incremental_property(notification)

        endpoint._consume_target.assert_called_once()
        target, value = endpoint._consume_target.call_args.args
        self.assertEqual(target, 20)
        self.assertEqual(value.bytes_value, b"PNG-")

    def test_preserves_portal_file_transfer_for_sandboxed_apps(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.targets = 1
        endpoint.file_targets = {2}
        endpoint.platform_file_mimes_by_atom = {
            3: "application/vnd.portal.filetransfer",
        }
        endpoint.image_mimes_by_atom = {}
        endpoint.supported_text_targets = set()
        endpoint.pending_content = MagicMock()
        endpoint.pending_content.platform_file_formats = {}
        endpoint.pending_targets = deque()
        endpoint._complete_request = MagicMock(return_value=[])

        endpoint._consume_target(
            3,
            SimpleNamespace(format=8, bytes_value=b"portal-token"),
        )

        self.assertEqual(
            endpoint.pending_content.platform_file_formats,
            {"application/vnd.portal.filetransfer": b"portal-token"},
        )

    def test_serves_portal_file_transfer_token_unchanged(self):
        endpoint = X11ClipboardEndpoint.__new__(X11ClipboardEndpoint)
        endpoint.display = 1
        endpoint.selection = 2
        endpoint.targets = 3
        endpoint.uri_list = 4
        endpoint.kde_uri_list = 5
        endpoint.gnome_copied_files = 6
        endpoint.kde_cut_selection = 7
        endpoint.file_targets = {4, 5, 6}
        endpoint.platform_file_atoms = {
            "application/vnd.portal.filetransfer": 8,
        }
        endpoint.platform_file_mimes_by_atom = {
            8: "application/vnd.portal.filetransfer",
        }
        endpoint.supported_text_targets = set()
        endpoint.image_atoms = {}
        endpoint.x11 = MagicMock()
        endpoint.content = ClipboardContent(
            file_uris=("file:///tmp/copied",),
            platform_file_formats=((
                "application/vnd.portal.filetransfer",
                b"portal-token",
            ),),
        )
        endpoint._write_property_bytes = MagicMock()
        request = SimpleNamespace(
            requestor=9,
            selection=2,
            target=8,
            property=10,
            time=11,
        )

        endpoint._respond_to_request(request)

        endpoint._write_property_bytes.assert_called_once_with(
            9,
            10,
            8,
            b"portal-token",
        )

    def test_forwards_new_text_in_both_directions(self):
        endpoints = []

        class Endpoint:
            def __init__(self, display_name, xauthority):
                self.display_name = display_name
                self.xauthority = xauthority
                self.updates = []
                self.received = []
                self.closed = 0
                self.initialized = True
                self.text = None
                endpoints.append(self)

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                self.text = value.text
                return True

            def close(self):
                self.closed += 1

        bridge = NestedDesktopClipboardBridge(
            endpoint_factory=Endpoint,
            outer_display=":0",
        )
        session = NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )

        bridge.set_session(session)
        endpoints[0].updates.append(ClipboardContent(text="outer"))
        bridge.dispatch()
        endpoints[1].updates.append(ClipboardContent(text="inner"))
        bridge.dispatch()

        self.assertEqual(
            endpoints[0].received,
            [ClipboardContent(text="inner")],
        )
        self.assertEqual(
            endpoints[1].received,
            [ClipboardContent(text="outer")],
        )
        self.assertEqual(bridge.current_text(), "inner")
        bridge.close()
        self.assertEqual([endpoint.closed for endpoint in endpoints], [1, 1])

    def test_file_sharing_can_be_disabled_without_blocking_text(self):
        endpoints = []

        class Endpoint:
            def __init__(self, _display_name, _xauthority):
                self.updates = []
                self.received = []
                self.initialized = True
                self.text = None
                endpoints.append(self)

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                return True

            def close(self):
                pass

        bridge = NestedDesktopClipboardBridge(
            endpoint_factory=Endpoint,
            outer_display=":0",
            files_enabled=False,
        )
        bridge.set_session(NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        ))
        endpoints[0].updates.append(ClipboardContent(
            text="still shared",
            file_uris=("file:///tmp/not-shared",),
        ))

        bridge.dispatch()

        self.assertEqual(
            endpoints[1].received,
            [ClipboardContent(text="still shared")],
        )
        bridge.close()

    def test_inner_files_receive_a_bridge_owned_portal_token(self):
        endpoints = []

        class Endpoint:
            def __init__(self, _display_name, _xauthority):
                self.updates = []
                self.received = []
                self.initialized = True
                self.text = None
                endpoints.append(self)

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                return True

            def close(self):
                pass

        portal = MagicMock()
        portal.replace.return_value = b"bridge-token"
        bridge = NestedDesktopClipboardBridge(
            endpoint_factory=Endpoint,
            outer_display=":0",
            portal_factory=lambda _address: portal,
        )
        bridge.set_session(NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        ))
        endpoints[1].updates.append(ClipboardContent(
            file_uris=("file:///tmp/copied.pdf",),
            platform_file_formats=((
                "application/vnd.portal.filetransfer",
                b"dolphin-token",
            ),),
        ))

        bridge.dispatch()

        portal.replace.assert_called_once_with(("file:///tmp/copied.pdf",))
        self.assertEqual(
            endpoints[0].received,
            [ClipboardContent(
                file_uris=("file:///tmp/copied.pdf",),
                platform_file_formats=(
                    (
                        "application/vnd.portal.filetransfer",
                        b"bridge-token",
                    ),
                    (
                        "application/vnd.portal.files",
                        b"bridge-token",
                    ),
                ),
            )],
        )
        bridge.close()
        portal.close.assert_called_once_with()

    def test_klipper_files_bypass_inner_x11_without_stealing_its_owner(self):
        endpoints = []

        class Endpoint:
            def __init__(self, _display_name, _xauthority):
                self.updates = []
                self.received = []
                self.initialized = True
                self.text = None
                endpoints.append(self)

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                return True

            def fileno(self):
                return -1

            def close(self):
                pass

        monitor = MagicMock()
        monitor.fileno.return_value = -1
        monitor.dispatch.return_value = [ClipboardContent(
            file_uris=("file:///tmp/copied.pdf",),
        )]
        portal = MagicMock()
        portal.replace.return_value = b"bridge-token"
        bridge = NestedDesktopClipboardBridge(
            endpoint_factory=Endpoint,
            outer_display=":0",
            portal_factory=lambda _address: portal,
            klipper_factory=lambda _address: monitor,
        )
        bridge.set_session(NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        ))

        bridge.dispatch()

        self.assertEqual(len(endpoints[0].received), 1)
        self.assertEqual(endpoints[1].received, [])
        self.assertEqual(
            endpoints[0].received[0].platform_file_formats,
            (
                ("application/vnd.portal.filetransfer", b"bridge-token"),
                ("application/vnd.portal.files", b"bridge-token"),
            ),
        )
        bridge.close()
        monitor.close.assert_called_once_with()

    def test_inner_files_use_document_portal_uris_for_outer_sandboxes(self):
        endpoints = []

        class Endpoint:
            def __init__(self, _display_name, _xauthority):
                self.updates = []
                self.received = []
                self.initialized = True
                self.text = None
                endpoints.append(self)

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                return True

            def close(self):
                pass

        exporter = MagicMock()
        exporter.export.return_value = (
            "file:///run/user/1000/doc/abc/copied.pdf",
        )
        portal = MagicMock()
        portal.replace.return_value = b"bridge-token"
        bridge = NestedDesktopClipboardBridge(
            endpoint_factory=Endpoint,
            outer_display=":0",
            portal_factory=lambda _address: portal,
            document_portal_factory=lambda _address: exporter,
        )
        bridge.set_session(NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        ))
        source_uris = ("file:///tmp/copied.pdf",)
        endpoints[1].updates.append(ClipboardContent(file_uris=source_uris))

        bridge.dispatch()

        exporter.export.assert_called_once_with(source_uris)
        portal.replace.assert_called_once_with(source_uris)
        self.assertEqual(
            endpoints[0].received[0].file_uris,
            ("file:///run/user/1000/doc/abc/copied.pdf",),
        )
        bridge.close()
        exporter.close.assert_called_once_with()

    def test_forwards_an_image_and_its_text_representation_together(self):
        endpoints = []

        class Endpoint:
            def __init__(self, _display_name, _xauthority):
                self.updates = []
                self.received = []
                self.initialized = True
                self.text = None
                endpoints.append(self)

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                self.text = value.text
                return True

            @staticmethod
            def close():
                return None

        bridge = NestedDesktopClipboardBridge(
            endpoint_factory=Endpoint,
            outer_display=":0",
        )
        bridge.set_session(
            NestedDesktopSession(
                pid=1,
                app_id=2,
                display=":2",
                xauthority=Path("/tmp/xauth"),
                dbus_address="unix:path=/tmp/dbus",
            )
        )
        copied = ClipboardContent(
            text="https://example.test/image.png",
            image_mime="image/png",
            image=b"\x89PNG\r\n\x1a\nimage-data",
        )

        endpoints[0].updates.append(copied)
        bridge.dispatch()

        self.assertEqual(endpoints[1].received, [copied])
        self.assertEqual(
            endpoints[1].received[0].formats,
            ("text/plain", "image/png"),
        )
        self.assertEqual(
            endpoints[1].received[0].byte_count,
            len(copied.text.encode("utf-8")) + len(copied.image),
        )

    def test_synchronizes_both_gamescope_xwayland_clipboards(self):
        endpoints = {}

        class Endpoint:
            def __init__(self, display_name, _xauthority):
                self.display_name = display_name
                self.updates = []
                self.received = []
                self.initialized = True
                self.text = None
                self.closed = False
                endpoints[display_name] = self

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                self.text = value.text
                return True

            def close(self):
                self.closed = True

        bridge = NestedDesktopClipboardBridge(endpoint_factory=Endpoint)
        bridge.set_session(
            NestedDesktopSession(
                pid=1,
                app_id=2,
                display=":2",
                xauthority=Path("/tmp/xauth"),
                dbus_address="unix:path=/tmp/dbus",
            )
        )
        copied = ClipboardContent(
            text="copied in Chrome",
            image_mime="image/png",
            image=b"png-image",
        )

        endpoints[":1"].updates.append(copied)
        bridge.dispatch()

        self.assertEqual(endpoints[":0"].received, [copied])
        self.assertEqual(endpoints[":2"].received, [copied])
        self.assertEqual(bridge.current_text(), "copied in Chrome")

        nested_text = ClipboardContent(text="copied in desktop")
        endpoints[":2"].updates.append(nested_text)
        bridge.dispatch()

        self.assertEqual(endpoints[":0"].received[-1], nested_text)
        self.assertEqual(endpoints[":1"].received[-1], nested_text)
        bridge.close()
        self.assertTrue(all(endpoint.closed for endpoint in endpoints.values()))

    def test_optional_gamescope_clipboard_may_be_unavailable(self):
        endpoints = {}

        class Endpoint:
            def __init__(self, display_name, _xauthority):
                if display_name == ":1":
                    raise RuntimeError("display is not running")
                self.updates = []
                self.received = []
                self.initialized = True
                self.text = None
                endpoints[display_name] = self

            def dispatch(self):
                updates = list(self.updates)
                self.updates.clear()
                return updates

            def set_content(self, value):
                self.received.append(value)
                return True

            @staticmethod
            def close():
                return None

        bridge = NestedDesktopClipboardBridge(endpoint_factory=Endpoint)
        bridge.set_session(
            NestedDesktopSession(
                pid=1,
                app_id=2,
                display=":2",
                xauthority=Path("/tmp/xauth"),
                dbus_address="unix:path=/tmp/dbus",
            )
        )
        copied = ClipboardContent(text="fallback")
        endpoints[":0"].updates.append(copied)

        bridge.dispatch()

        self.assertEqual(endpoints[":2"].received, [copied])
        bridge.close()

    def test_bridge_exposes_every_live_clipboard_descriptor(self):
        endpoints = []

        class Endpoint:
            def __init__(self, _display_name, _xauthority):
                self.descriptor = 20 + len(endpoints)
                endpoints.append(self)

            def fileno(self):
                return self.descriptor

            @staticmethod
            def close():
                return None

        bridge = NestedDesktopClipboardBridge(endpoint_factory=Endpoint)
        bridge.set_session(
            NestedDesktopSession(
                pid=1,
                app_id=2,
                display=":2",
                xauthority=Path("/tmp/xauth"),
                dbus_address="unix:path=/tmp/dbus",
            )
        )

        self.assertEqual(bridge.filenos(), (20, 21, 22))
        bridge.close()


def trackpad_state(
    *,
    back_pressed: bool = False,
    left_touched: bool = False,
    right_touched: bool = False,
    right_pressed: bool = False,
    right_pressure: int = 0,
    left_trigger: bool = False,
    right_trigger: bool = False,
    left_x: int = 0,
    left_y: int = 0,
    right_x: int = 0,
    right_y: int = 0,
    buttons: int = 0,
    left_stick_x: int = 0,
    left_stick_y: int = 0,
    right_stick_x: int = 0,
    right_stick_y: int = 0,
) -> TrackpadState:
    return TrackpadState(
        back_pressed=back_pressed,
        left_touched=left_touched,
        right_touched=right_touched,
        right_pressed=right_pressed,
        right_pressure=right_pressure,
        left_trigger=left_trigger,
        right_trigger=right_trigger,
        left_x=left_x,
        left_y=left_y,
        right_x=right_x,
        right_y=right_y,
        buttons=buttons,
        left_stick_x=left_stick_x,
        left_stick_y=left_stick_y,
        right_stick_x=right_stick_x,
        right_stick_y=right_stick_y,
    )


def packed_display(value: str) -> list[int]:
    encoded = value.encode("ascii") + b"\0"
    encoded += b"\0" * ((4 - len(encoded) % 4) % 4)
    return [
        int.from_bytes(encoded[index : index + 4], "little")
        for index in range(0, len(encoded), 4)
    ]


class TrackpadReportTests(unittest.TestCase):
    def test_parses_pads_triggers_and_signed_coordinates(self):
        report = bytearray(64)
        report[:3] = b"\x01\x00\x09"
        controls = (
            BACK_BUTTON
            | LEFT_PAD_TOUCHED
            | RIGHT_PAD_TOUCHED
            | RIGHT_PAD_PRESSED
            | LEFT_TRIGGER
            | RIGHT_TRIGGER
        )
        report[8:12] = controls.to_bytes(4, "little")
        struct.pack_into("<hh", report, 16, 4321, -8765)
        struct.pack_into("<hh", report, 20, -1234, 5678)
        struct.pack_into("<hh", report, 48, 12_345, -23_456)
        struct.pack_into("<hh", report, 52, -9_876, 16_543)
        struct.pack_into("<H", report, 58, 3456)

        state = parse_trackpad_report(bytes(report))

        self.assertEqual(
            state,
            trackpad_state(
                back_pressed=True,
                left_touched=True,
                right_touched=True,
                right_pressed=True,
                right_pressure=3456,
                left_trigger=True,
                right_trigger=True,
                left_x=4321,
                left_y=-8765,
                right_x=-1234,
                right_y=5678,
                buttons=controls,
                left_stick_x=12_345,
                left_stick_y=-23_456,
                right_stick_x=-9_876,
                right_stick_y=16_543,
            ),
        )

    def test_ignores_other_hid_reports(self):
        self.assertIsNone(parse_trackpad_report(b"\0" * 64))
        self.assertIsNone(parse_trackpad_report(b"\x01\x00\x09"))
        self.assertIsNone(
            parse_trackpad_report(b"\x01\x00\x09" + b"\0" * 56)
        )


class RustDeskMouseTranslatorTests(unittest.TestCase):
    def test_coalesces_axes_from_one_joystick_frame(self):
        translator = RustDeskMouseTranslator()
        initial = (
            JoystickEvent(1, -32_767, 2, 0, True),
            JoystickEvent(1, -32_767, 2, 1, True),
        )
        self.assertEqual(
            translator.translate(initial, (0, 0, 1280, 800)),
            (),
        )

        updates = translator.translate(
            (
                JoystickEvent(2, 32_767, 2, 0),
                JoystickEvent(2, 32_767, 2, 1),
            ),
            (0, 0, 1280, 800),
        )

        self.assertEqual(
            updates,
            (PointerUpdate(absolute_x=1279.0, absolute_y=799.0),),
        )

    def test_preserves_button_transitions(self):
        translator = RustDeskMouseTranslator()

        updates = translator.translate(
            (
                JoystickEvent(1, 0, 2, 0, True),
                JoystickEvent(1, 0, 2, 1, True),
                JoystickEvent(2, 1, 1, 0),
                JoystickEvent(3, 0, 1, 0),
            ),
            (0, 0, 1280, 800),
        )

        self.assertEqual(
            updates,
            (
                PointerUpdate(left_button=True),
                PointerUpdate(left_button=False),
            ),
        )

    def test_parses_complete_joystick_records_only(self):
        record = struct.pack("<IhBB", 42, -123, 0x82, 1)

        self.assertEqual(
            parse_joystick_events(record + b"\xff"),
            (JoystickEvent(42, -123, 2, 1, True),),
        )

    def test_relay_coalesces_native_absolute_motion_and_buttons(self):
        translator = RustDeskRelayTranslator()

        updates = translator.translate(
            (
                LinuxInputEvent(3, 0, 1280),
                LinuxInputEvent(3, 1, 800),
                LinuxInputEvent(0, 0, 0),
                LinuxInputEvent(1, 0x110, 1),
                LinuxInputEvent(0, 0, 0),
            ),
            (0, 0, 1280, 800),
        )

        self.assertEqual(
            updates,
            (
                PointerUpdate(absolute_x=1279.0, absolute_y=799.0),
                PointerUpdate(left_button=True),
            ),
        )

    def test_relay_keeps_an_incomplete_frame_for_the_next_datagram(self):
        translator = RustDeskRelayTranslator()

        self.assertEqual(
            translator.translate(
                (LinuxInputEvent(1, 0x111, 1),),
                (0, 0, 1280, 800),
            ),
            (),
        )
        self.assertEqual(
            translator.translate(
                (LinuxInputEvent(0, 0, 0),),
                (0, 0, 1280, 800),
            ),
            (PointerUpdate(right_button=True),),
        )

    def test_relay_forwards_wheel_and_middle_button_frames(self):
        translator = RustDeskRelayTranslator()

        updates = translator.translate(
            (
                LinuxInputEvent(2, 8, 1),
                LinuxInputEvent(2, 6, -1),
                LinuxInputEvent(0, 0, 0),
                LinuxInputEvent(1, 0x112, 1),
                LinuxInputEvent(0, 0, 0),
                LinuxInputEvent(1, 0x112, 0),
                LinuxInputEvent(0, 0, 0),
            ),
            (0, 0, 1280, 800),
        )

        self.assertEqual(
            updates,
            (
                PointerUpdate(
                    scroll_discrete_x=-90,
                    scroll_discrete_y=-90,
                ),
                PointerUpdate(middle_button=True),
                PointerUpdate(middle_button=False),
            ),
        )


class RustDeskScrollInertiaTests(unittest.TestCase):
    def test_disabled_inertia_has_no_pending_work(self):
        inertia = RustDeskScrollInertia()

        inertia.observe(PointerUpdate(scroll_discrete_y=90), 1.0)

        self.assertFalse(inertia.active)
        self.assertEqual(inertia.timeout(1.0, 0.25), 0.25)
        self.assertEqual(inertia.tick(2.0), PointerUpdate())

    def test_single_wheel_click_does_not_start_inertia(self):
        inertia = RustDeskScrollInertia(enabled=True)

        inertia.observe(PointerUpdate(scroll_discrete_y=90), 1.0)

        self.assertFalse(inertia.active)
        self.assertEqual(inertia.tick(2.0), PointerUpdate())

    def test_fast_wheel_burst_decays_after_a_short_delay(self):
        inertia = RustDeskScrollInertia(enabled=True)
        for now in (1.0, 1.02, 1.04):
            inertia.observe(PointerUpdate(scroll_discrete_y=90), now)

        self.assertTrue(inertia.active)
        self.assertAlmostEqual(inertia.timeout(1.04, 0.25), 0.05)
        self.assertEqual(inertia.tick(1.089), PointerUpdate())
        self.assertEqual(
            inertia.tick(1.09),
            PointerUpdate(scroll_discrete_y=60),
        )
        self.assertEqual(
            inertia.tick(1.107),
            PointerUpdate(scroll_discrete_y=49),
        )

    def test_direction_change_starts_a_new_burst(self):
        inertia = RustDeskScrollInertia(enabled=True)
        for now in (1.0, 1.02, 1.04):
            inertia.observe(PointerUpdate(scroll_discrete_y=90), now)

        inertia.observe(PointerUpdate(scroll_discrete_y=-90), 1.05)

        self.assertFalse(inertia.active)
        self.assertEqual(inertia.tick(2.0), PointerUpdate())


class InputBindingTranslatorTests(unittest.TestCase):
    def test_maps_a_fresh_b_press_to_escape_state(self):
        translator = InputBindingTranslator()
        translator.set_active(True)

        self.assertEqual(translator.translate(trackpad_state()), BindingUpdate())
        self.assertEqual(
            translator.translate(trackpad_state(buttons=BACK_BUTTON)),
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_ESC"], True),)),
        )
        self.assertEqual(
            translator.translate(trackpad_state()),
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_ESC"], False),)),
        )

    def test_does_not_press_escape_when_b_was_already_held(self):
        translator = InputBindingTranslator()
        held = trackpad_state(buttons=BACK_BUTTON)
        translator.translate(held)
        translator.set_active(True)

        self.assertEqual(translator.translate(held), BindingUpdate())
        self.assertEqual(translator.translate(trackpad_state()), BindingUpdate())
        self.assertEqual(
            translator.translate(held),
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_ESC"], True),)),
        )

    def test_releases_escape_when_forwarding_stops(self):
        translator = InputBindingTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())
        translator.translate(trackpad_state(buttons=BACK_BUTTON))

        self.assertEqual(
            translator.set_active(False),
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_ESC"], False),)),
        )
        self.assertFalse(translator.injected_keys)

    def test_shared_escape_stays_held_until_b_and_view_are_released(self):
        translator = InputBindingTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())
        b_and_view = BACK_BUTTON | BUTTON_SOURCE_MASKS["view"]

        pressed = translator.translate(trackpad_state(buttons=b_and_view))
        b_released = translator.translate(
            trackpad_state(buttons=BUTTON_SOURCE_MASKS["view"])
        )
        released = translator.translate(trackpad_state())

        self.assertEqual(
            pressed,
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_ESC"], True),)),
        )
        self.assertEqual(b_released, BindingUpdate())
        self.assertEqual(
            released,
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_ESC"], False),)),
        )

    def test_none_removes_an_individual_binding(self):
        translator = InputBindingTranslator({"b": "none"})
        translator.set_active(True)
        translator.translate(trackpad_state())

        self.assertEqual(
            translator.translate(trackpad_state(buttons=BACK_BUTTON)),
            BindingUpdate(),
        )

    def test_x_requests_the_steam_keyboard_on_press_only(self):
        translator = InputBindingTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())
        x_pressed = trackpad_state(buttons=BUTTON_SOURCE_MASKS["x"])

        self.assertEqual(
            translator.translate(x_pressed),
            BindingUpdate(actions=(ACTION_SHOW_KEYBOARD,)),
        )
        self.assertEqual(translator.translate(x_pressed), BindingUpdate())
        self.assertEqual(translator.translate(trackpad_state()), BindingUpdate())

    def test_default_mouse_sources_are_aggregated(self):
        translator = InputBindingTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())
        r2_and_pad = (
            BUTTON_SOURCE_MASKS["r2"]
            | BUTTON_SOURCE_MASKS["rightPadClick"]
        )

        pressed = translator.translate(
            trackpad_state(buttons=r2_and_pad, right_pressed=True)
        )
        pad_released = translator.translate(
            trackpad_state(buttons=BUTTON_SOURCE_MASKS["r2"])
        )
        released = translator.translate(trackpad_state())

        self.assertEqual(
            pressed,
            BindingUpdate(pointer=PointerUpdate(left_button=True)),
        )
        self.assertEqual(pad_released, BindingUpdate())
        self.assertEqual(
            released,
            BindingUpdate(pointer=PointerUpdate(left_button=False)),
        )

    def test_pointer_bindings_can_follow_focus_without_stopping_hotkeys(self):
        translator = InputBindingTranslator(
            pointer_actions_enabled=False,
        )
        translator.set_active(True)
        translator.translate(trackpad_state())
        r2_pressed = trackpad_state(
            buttons=BUTTON_SOURCE_MASKS["r2"]
        )

        self.assertEqual(
            translator.translate(r2_pressed),
            BindingUpdate(),
        )
        self.assertEqual(
            translator.set_pointer_actions_enabled(True),
            PointerUpdate(),
        )
        self.assertEqual(
            translator.translate(r2_pressed),
            BindingUpdate(),
        )
        self.assertEqual(
            translator.translate(trackpad_state()),
            BindingUpdate(),
        )
        self.assertEqual(
            translator.translate(r2_pressed),
            BindingUpdate(pointer=PointerUpdate(left_button=True)),
        )
        self.assertEqual(
            translator.set_pointer_actions_enabled(False),
            PointerUpdate(left_button=False),
        )
        self.assertTrue(translator.active)

    def test_pointer_defaults_cover_both_triggers_and_left_pad_click(self):
        translator = InputBindingTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())
        buttons = (
            BUTTON_SOURCE_MASKS["l2"]
            | BUTTON_SOURCE_MASKS["r2"]
            | BUTTON_SOURCE_MASKS["leftPadClick"]
        )

        update = translator.translate(trackpad_state(buttons=buttons))

        self.assertEqual(
            update,
            BindingUpdate(
                pointer=PointerUpdate(
                    left_button=True,
                    right_button=True,
                    middle_button=True,
                )
            ),
        )

    def test_right_pad_pressure_uses_hysteresis(self):
        translator = InputBindingTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())

        pressed = translator.translate(
            trackpad_state(right_touched=True, right_pressure=2_100)
        )
        held = translator.translate(
            trackpad_state(right_touched=True, right_pressure=1_500)
        )
        released = translator.translate(
            trackpad_state(right_touched=True, right_pressure=900)
        )

        self.assertEqual(
            pressed,
            BindingUpdate(pointer=PointerUpdate(left_button=True)),
        )
        self.assertEqual(held, BindingUpdate())
        self.assertEqual(
            released,
            BindingUpdate(pointer=PointerUpdate(left_button=False)),
        )

    def test_left_stick_directions_have_press_and_release_hysteresis(self):
        translator = InputBindingTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())

        pressed = translator.translate(trackpad_state(left_stick_y=17_000))
        held = translator.translate(trackpad_state(left_stick_y=13_000))
        released = translator.translate(trackpad_state(left_stick_y=11_000))

        self.assertEqual(
            pressed,
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_UP"], True),)),
        )
        self.assertEqual(held, BindingUpdate())
        self.assertEqual(
            released,
            BindingUpdate(key_events=((EIS_KEY_CODES["KEY_UP"], False),)),
        )

    def test_steam_defaults_include_keyboard_mouse_and_navigation(self):
        self.assertEqual(DEFAULT_NESTED_DESKTOP_BINDINGS["a"], "KEY_ENTER")
        self.assertEqual(DEFAULT_NESTED_DESKTOP_BINDINGS["b"], "KEY_ESC")
        self.assertEqual(
            DEFAULT_NESTED_DESKTOP_BINDINGS["x"],
            ACTION_SHOW_KEYBOARD,
        )
        self.assertEqual(
            DEFAULT_NESTED_DESKTOP_BINDINGS["l2"],
            ACTION_MOUSE_RIGHT,
        )
        self.assertEqual(
            DEFAULT_NESTED_DESKTOP_BINDINGS["r2"],
            ACTION_MOUSE_LEFT,
        )
        self.assertEqual(
            DEFAULT_NESTED_DESKTOP_BINDINGS["leftPadClick"],
            ACTION_MOUSE_MIDDLE,
        )


class TrackpadTranslatorTests(unittest.TestCase):
    def test_default_bridge_scroll_uses_tuned_scale_and_deadzone(self):
        translator = TrackpadTranslator()
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=0)
        )

        inside_deadzone = translator.translate(
            trackpad_state(left_touched=True, left_y=479)
        )
        scrolled = translator.translate(
            trackpad_state(left_touched=True, left_y=1_000)
        )

        self.assertEqual(inside_deadzone, PointerUpdate())
        self.assertAlmostEqual(scrolled.scroll_y, -2.6)

    def test_only_translates_motion_while_active(self):
        translator = TrackpadTranslator(scale=0.1)
        first = trackpad_state(
            right_touched=True,
            right_x=100,
            right_y=100,
        )
        second = trackpad_state(
            right_touched=True,
            right_x=130,
            right_y=80,
        )

        self.assertEqual(translator.translate(first), PointerUpdate())
        translator.set_active(True)
        self.assertEqual(translator.translate(first), PointerUpdate())
        self.assertEqual(
            translator.translate(second),
            PointerUpdate(dx=3, dy=2),
        )

        translator.set_active(False)
        self.assertEqual(translator.translate(second), PointerUpdate())

    def test_drops_wraparound_jump_and_resumes_from_new_position(self):
        translator = TrackpadTranslator(scale=1)
        translator.set_active(True)
        translator.translate(
            trackpad_state(right_touched=True, right_x=30_000)
        )

        jump = translator.translate(
            trackpad_state(right_touched=True, right_x=-30_000)
        )
        resumed = translator.translate(
            trackpad_state(right_touched=True, right_x=-29_990)
        )

        self.assertEqual(jump, PointerUpdate())
        self.assertEqual(resumed, PointerUpdate(dx=10))

    def test_right_stick_moves_the_pointer_with_a_deadzone(self):
        translator = TrackpadTranslator()
        translator.set_active(True)

        deadzone = translator.translate(
            trackpad_state(right_stick_x=7_000)
        )
        moved = translator.translate(
            trackpad_state(right_stick_x=32_767, right_stick_y=32_767)
        )
        stopped = translator.translate(trackpad_state())

        self.assertEqual(deadzone, PointerUpdate())
        self.assertEqual(moved, PointerUpdate(dx=18, dy=-18))
        self.assertEqual(stopped, PointerUpdate())
        self.assertFalse(translator.stick_active)

    def test_pointer_continues_with_inertia_after_a_flick(self):
        translator = TrackpadTranslator(scale=0.1)
        translator.set_active(True)
        translator.translate(
            trackpad_state(right_touched=True, right_x=0)
        )
        moved = translator.translate(
            trackpad_state(right_touched=True, right_x=100)
        )

        first_inertia = translator.translate(trackpad_state())
        second_inertia = translator.translate(trackpad_state())

        self.assertEqual(moved, PointerUpdate(dx=10))
        self.assertEqual(first_inertia, PointerUpdate(dx=5))
        self.assertEqual(second_inertia, PointerUpdate(dx=5))

    def test_slow_pointer_motion_stops_immediately_on_release(self):
        translator = TrackpadTranslator(scale=0.1)
        translator.set_active(True)
        for position in (0, 20, 40, 60, 80):
            translator.translate(
                trackpad_state(
                    right_touched=True,
                    right_x=position,
                )
            )

        released = translator.translate(trackpad_state())

        self.assertEqual(released, PointerUpdate())
        self.assertFalse(translator.pointer_inertia)

    def test_pointer_inertia_decays_and_retouch_stops_it(self):
        translator = TrackpadTranslator(scale=0.1)
        translator.set_active(True)
        translator.translate(
            trackpad_state(right_touched=True, right_x=0)
        )
        translator.translate(
            trackpad_state(right_touched=True, right_x=100)
        )
        translator.translate(trackpad_state())

        caught = translator.translate(
            trackpad_state(right_touched=True, right_x=100)
        )
        released_again = translator.translate(trackpad_state())

        self.assertEqual(caught, PointerUpdate())
        self.assertEqual(released_again, PointerUpdate())

    def test_pointer_inertia_eventually_stops(self):
        translator = TrackpadTranslator(scale=0.1)
        translator.set_active(True)
        translator.translate(
            trackpad_state(right_touched=True, right_x=0)
        )
        translator.translate(
            trackpad_state(right_touched=True, right_x=100)
        )
        updates = [
            translator.translate(trackpad_state())
            for _ in range(80)
        ]

        self.assertTrue(any(update.dx for update in updates))
        self.assertFalse(translator.pointer_inertia)
        self.assertEqual(updates[-1], PointerUpdate())

    def test_pointer_stops_on_release_when_inertia_is_disabled(self):
        translator = TrackpadTranslator(
            scale=0.1,
            inertia_enabled=False,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(right_touched=True, right_x=0)
        )
        translator.translate(
            trackpad_state(right_touched=True, right_x=100)
        )

        released = translator.translate(trackpad_state())

        self.assertEqual(released, PointerUpdate())
        self.assertFalse(translator.pointer_inertia)

    def test_left_pad_scroll_continues_with_inertia_then_stops(self):
        translator = TrackpadTranslator(
            scroll_scale=0.1,
            scroll_start_deadzone=0,
            scroll_emit_threshold=0,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=100)
        )

        scrolled = translator.translate(
            trackpad_state(left_touched=True, left_y=140)
        )
        first_inertia = translator.translate(trackpad_state())
        updates = [
            translator.translate(trackpad_state())
            for _ in range(80)
        ]

        self.assertEqual(scrolled, PointerUpdate(scroll_y=-4))
        self.assertAlmostEqual(first_inertia.scroll_y, -2.2)
        self.assertTrue(any(update.scroll_y for update in updates))
        self.assertTrue(any(update.scroll_stop_y for update in updates))
        self.assertFalse(translator.scroll_inertia)

    def test_default_small_scroll_does_not_start_inertia(self):
        translator = TrackpadTranslator()
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=0)
        )
        translator.translate(
            trackpad_state(left_touched=True, left_y=1_000)
        )

        stopped = translator.translate(trackpad_state())

        self.assertEqual(stopped, PointerUpdate(scroll_stop_y=True))
        self.assertFalse(translator.scroll_inertia)

    def test_slow_left_pad_scroll_stops_without_inertia(self):
        translator = TrackpadTranslator(
            scroll_scale=0.1,
            scroll_start_deadzone=0,
            scroll_emit_threshold=0,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=100)
        )
        translator.translate(
            trackpad_state(left_touched=True, left_y=105)
        )

        stopped = translator.translate(trackpad_state())

        self.assertEqual(stopped, PointerUpdate(scroll_stop_y=True))

    def test_sustained_slow_scroll_stops_without_inertia(self):
        translator = TrackpadTranslator(
            scroll_scale=0.1,
            scroll_start_deadzone=0,
            scroll_emit_threshold=0,
        )
        translator.set_active(True)
        for position in (100, 110, 120, 130, 140):
            translator.translate(
                trackpad_state(
                    left_touched=True,
                    left_y=position,
                )
            )

        stopped = translator.translate(trackpad_state())

        self.assertEqual(stopped, PointerUpdate(scroll_stop_y=True))
        self.assertFalse(translator.scroll_inertia)

    def test_scroll_stops_on_release_when_inertia_is_disabled(self):
        translator = TrackpadTranslator(
            scroll_scale=0.1,
            scroll_start_deadzone=0,
            scroll_emit_threshold=0,
            inertia_enabled=False,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=100)
        )
        translator.translate(
            trackpad_state(left_touched=True, left_y=130)
        )

        stopped = translator.translate(trackpad_state())

        self.assertEqual(stopped, PointerUpdate(scroll_stop_y=True))
        self.assertFalse(translator.scroll_inertia)

    def test_idle_frames_can_be_skipped_immediately(self):
        translator = TrackpadTranslator()
        translator.set_active(True)

        self.assertFalse(translator.needs_idle_tick)
        translator.translate(trackpad_state())

        self.assertFalse(translator.needs_idle_tick)

    def test_touching_left_pad_stops_active_scroll_inertia(self):
        translator = TrackpadTranslator(
            scroll_scale=0.1,
            scroll_start_deadzone=0,
            scroll_emit_threshold=0,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=100)
        )
        translator.translate(
            trackpad_state(left_touched=True, left_y=140)
        )
        translator.translate(trackpad_state())

        caught = translator.translate(
            trackpad_state(left_touched=True, left_y=140)
        )

        self.assertEqual(caught, PointerUpdate(scroll_stop_y=True))
        self.assertFalse(translator.scroll_inertia)

    def test_scroll_ignores_micro_movements_until_deadzone_is_crossed(self):
        translator = TrackpadTranslator(
            scroll_scale=0.01,
            scroll_start_deadzone=100,
            scroll_emit_threshold=20,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=0)
        )

        first = translator.translate(
            trackpad_state(left_touched=True, left_y=40)
        )
        second = translator.translate(
            trackpad_state(left_touched=True, left_y=80)
        )
        crossed = translator.translate(
            trackpad_state(left_touched=True, left_y=105)
        )
        emitted = translator.translate(
            trackpad_state(left_touched=True, left_y=125)
        )

        self.assertEqual(first, PointerUpdate())
        self.assertEqual(second, PointerUpdate())
        self.assertEqual(crossed, PointerUpdate())
        self.assertEqual(emitted, PointerUpdate(scroll_y=-0.25))

    def test_scroll_accumulates_small_movements_after_activation(self):
        translator = TrackpadTranslator(
            scroll_scale=0.01,
            scroll_start_deadzone=100,
            scroll_emit_threshold=20,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=0)
        )
        activated = translator.translate(
            trackpad_state(left_touched=True, left_y=150)
        )

        first_micro = translator.translate(
            trackpad_state(left_touched=True, left_y=160)
        )
        second_micro = translator.translate(
            trackpad_state(left_touched=True, left_y=170)
        )

        self.assertEqual(activated, PointerUpdate(scroll_y=-0.5))
        self.assertEqual(first_micro, PointerUpdate())
        self.assertEqual(second_micro, PointerUpdate(scroll_y=-0.2))

    def test_micro_scroll_gesture_does_not_start_or_emit_stop(self):
        translator = TrackpadTranslator(
            scroll_scale=0.01,
            scroll_start_deadzone=100,
            scroll_emit_threshold=20,
        )
        translator.set_active(True)
        translator.translate(
            trackpad_state(left_touched=True, left_y=0)
        )
        moved = translator.translate(
            trackpad_state(left_touched=True, left_y=50)
        )
        released = translator.translate(trackpad_state())

        self.assertEqual(moved, PointerUpdate())
        self.assertEqual(released, PointerUpdate())


class GamescopeFocusTests(unittest.TestCase):
    def test_gamescope_pointer_translator_keeps_fractional_motion(self):
        translator = GamescopePointerTranslator()

        first = translator.motion({0: 0.4, 1: -0.6})
        second = translator.motion({0: 0.7, 1: -0.6})
        scroll = translator.motion({2: 0.5, 3: -1.0})

        self.assertEqual(first, PointerUpdate())
        self.assertEqual(second, PointerUpdate(dx=1, dy=-1))
        self.assertEqual(
            scroll,
            PointerUpdate(
                scroll_discrete_x=60,
                scroll_discrete_y=-120,
            ),
        )

    def test_gamescope_pointer_translator_releases_held_buttons(self):
        translator = GamescopePointerTranslator()

        self.assertEqual(
            translator.button(1, True),
            PointerUpdate(left_button=True),
        )
        self.assertEqual(
            translator.button(3, True),
            PointerUpdate(right_button=True),
        )
        self.assertEqual(
            translator.release(),
            PointerUpdate(left_button=False, right_button=False),
        )

    def test_gamescope_pointer_interceptor_grabs_only_on_transitions(self):
        connections = []

        class Connection:
            def __init__(self, display_name):
                self.display_name = display_name
                self.grabs = 0
                self.ungrabs = 0
                self.closed = 0
                self.updates = (
                    CapturedPointerUpdate(
                        1.0,
                        PointerUpdate(left_button=True),
                    ),
                )
                connections.append(self)

            def grab_pointer(self):
                self.grabs += 1
                return True

            def ungrab_pointer(self):
                self.ungrabs += 1

            @staticmethod
            def fileno():
                return 7

            def dispatch(self):
                updates = self.updates
                self.updates = ()
                return updates

            @staticmethod
            def release_update():
                return PointerUpdate(left_button=False)

            def close(self):
                self.closed += 1

        interceptor = GamescopePointerInterceptor(
            connection_factory=Connection,
        )

        self.assertTrue(interceptor.set_active(True, ":1"))
        self.assertTrue(interceptor.set_active(True, ":1"))
        self.assertEqual(interceptor.fileno(), 7)
        self.assertEqual(
            interceptor.dispatch(),
            (
                CapturedPointerUpdate(
                    1.0,
                    PointerUpdate(left_button=True),
                ),
            ),
        )
        self.assertTrue(interceptor.set_active(False))

        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0].display_name, ":1")
        self.assertEqual(connections[0].grabs, 1)
        self.assertEqual(connections[0].ungrabs, 1)
        self.assertEqual(connections[0].closed, 1)
        self.assertEqual(
            interceptor.take_release_updates(),
            (PointerUpdate(left_button=False),),
        )

    def test_gamescope_pointer_relay_delays_and_forwards_external_input(self):
        class Interceptor:
            display_name = None

            def __init__(self):
                self.active = False
                self.updates = []

            def set_active(self, active, display_name=None):
                self.active = active
                self.display_name = display_name if active else None
                return True

            def fileno(self):
                return 7 if self.active else -1

            def dispatch(self):
                updates = tuple(self.updates)
                self.updates.clear()
                return updates

            @staticmethod
            def take_release_updates():
                return ()

        class InnerEis:
            ready = True

            def __init__(self):
                self.emulating = False
                self.updates = []

            def set_emulating(self, active):
                self.emulating = active
                return True

            def inject(self, update):
                self.updates.append(update)

        interceptor = Interceptor()
        inner_eis = InnerEis()
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            gamescope_pointer_interceptor=interceptor,
        )
        runtime.inner_eis = inner_eis
        runtime._set_gamescope_pointer_intercepted(True, ":1")
        interceptor.updates.append(
            CapturedPointerUpdate(
                time.monotonic() - GAMESCOPE_POINTER_RELAY_DELAY - 0.01,
                PointerUpdate(dx=3, dy=-2),
            )
        )

        runtime._read_gamescope_pointer_events()
        runtime._flush_gamescope_pointer_updates()

        self.assertTrue(runtime.gamescope_pointer_forwarding)
        self.assertEqual(inner_eis.updates, [PointerUpdate(dx=3, dy=-2)])

    def test_direct_hid_activity_suppresses_captured_duplicate(self):
        class InnerEis:
            ready = True
            emulating = True

            def __init__(self):
                self.updates = []

            def inject(self, update):
                self.updates.append(update)

        runtime = NestedDesktopMouseRuntime(threading.Event())
        runtime.inner_eis = InnerEis()
        runtime.gamescope_pointer_forwarding = True
        received_at = (
            time.monotonic() - GAMESCOPE_POINTER_RELAY_DELAY - 0.01
        )
        runtime.gamescope_pointer_updates.append(
            CapturedPointerUpdate(
                received_at,
                PointerUpdate(left_button=True),
            )
        )
        runtime._mark_gamescope_pointer_hid_activity(received_at)

        runtime._flush_gamescope_pointer_updates()

        self.assertEqual(runtime.inner_eis.updates, [])

    def test_gamescope_cursor_compositor_restores_stale_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "cursor-hidden"
            marker.write_text("stale\n", encoding="utf-8")
            commands = []

            compositor = GamescopeCursorCompositor(
                command=lambda value: commands.append(value) or True,
                marker_path=marker,
            )

            self.assertEqual(commands, [1])
            self.assertFalse(compositor.hidden)
            self.assertFalse(marker.exists())

    def test_gamescope_cursor_compositor_changes_only_on_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "cursor-hidden"
            commands = []
            compositor = GamescopeCursorCompositor(
                command=lambda value: commands.append(value) or True,
                marker_path=marker,
            )

            compositor.set_hidden(True)
            compositor.set_hidden(True)
            self.assertTrue(marker.exists())
            compositor.set_hidden(False)
            compositor.set_hidden(False)

            self.assertEqual(commands, [0, 1])
            self.assertFalse(marker.exists())

    def test_failed_hide_keeps_marker_for_emergency_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "cursor-hidden"
            commands = []

            def command(value):
                commands.append(value)
                return value == 1

            compositor = GamescopeCursorCompositor(
                command=command,
                marker_path=marker,
            )

            self.assertFalse(compositor.set_hidden(True))
            self.assertTrue(marker.exists())
            self.assertTrue(compositor.set_hidden(False))

            self.assertEqual(commands, [0, 1])
            self.assertFalse(marker.exists())

    def test_focus_snapshot_reuses_values_until_an_event_or_fallback(self):
        class OuterX11:
            def __init__(self):
                self.changed = False
                self.reads = []

            def drain_property_events(self):
                changed = self.changed
                self.changed = False
                return changed

            def cardinals(self, name):
                self.reads.append(name)
                return {
                    "GAMESCOPE_FOCUSED_APP": [22],
                    "GAMESCOPE_FOCUSED_APP_GFX": [22],
                    "GAMESCOPE_MOUSE_FOCUS_DISPLAY": packed_display(":2"),
                    "GAMESCOPE_FOCUSABLE_WINDOWS": [],
                }[name]

        runtime = NestedDesktopMouseRuntime(threading.Event())
        runtime.outer_x11 = OuterX11()

        first = runtime._gamescope_focus_snapshot(0.0)
        cached = runtime._gamescope_focus_snapshot(0.25)
        runtime.outer_x11.changed = True
        changed = runtime._gamescope_focus_snapshot(0.3)
        fallback = runtime._gamescope_focus_snapshot(0.8)

        self.assertIs(first, cached)
        self.assertEqual(first, changed)
        self.assertEqual(changed, fallback)
        self.assertEqual(len(runtime.outer_x11.reads), 12)

    def test_prioritizes_nested_desktop_without_losing_focus_history(self):
        self.assertEqual(
            prioritize_focus_app(22, [11, 22, 769, 22]),
            (22, 11, 769),
        )

    def test_cursor_alpha_mask_uses_x11_lsb_bit_order(self):
        pixels = [
            0x00000000,
            0xFF000000,
            0x01000000,
            0x00000000,
            0xFF000000,
            0x00000000,
            0xFF000000,
            0xFF000000,
            0xFF000000,
        ]

        self.assertEqual(cursor_alpha_mask(pixels, 9, 1), b"\xd6\x01")

    def test_cursor_outline_preserves_shape_and_hotspot(self):
        snapshot = CursorSnapshot(
            x=123,
            y=456,
            width=2,
            height=1,
            xhot=0,
            yhot=0,
            serial=7,
            pixels=(0xFF000000, 0x00000000),
        )

        outlined = outlined_cursor_snapshot(snapshot)

        self.assertEqual(
            (
                outlined.x,
                outlined.y,
                outlined.width,
                outlined.height,
                outlined.xhot,
                outlined.yhot,
                outlined.serial,
            ),
            (123, 456, 4, 3, 1, 1, 7),
        )
        self.assertEqual(outlined.pixels[5], 0xFF000000)
        self.assertEqual(outlined.pixels[0], 0xFFFFFFFF)
        self.assertEqual(outlined.pixels[10], 0xFFFFFFFF)
        self.assertEqual(outlined.pixels[3], 0)

    def test_oversized_cursor_is_scaled_with_its_hotspot(self):
        snapshot = CursorSnapshot(
            x=123,
            y=456,
            width=4,
            height=2,
            xhot=2,
            yhot=1,
            serial=7,
            pixels=tuple(range(8)),
        )

        scaled = scaled_cursor_snapshot(snapshot, max_dimension=2)

        self.assertEqual(
            (scaled.width, scaled.height, scaled.xhot, scaled.yhot),
            (2, 1, 1, 0),
        )
        self.assertEqual(scaled.pixels, (0, 2))
        self.assertEqual((scaled.x, scaled.y, scaled.serial), (123, 456, 7))

    def test_cursor_overlay_repaints_after_first_map(self):
        calls = []

        class X11:
            def XMapRaised(self, display, window):
                calls.append(("map", display, window))

            def XFlush(self, display):
                calls.append(("flush", display))

        overlay = NestedDesktopCursorOverlay.__new__(
            NestedDesktopCursorOverlay
        )
        overlay.visible = False
        overlay.position_primed = True
        overlay.cursor_serial = 1
        overlay.display = 2
        overlay.window = 3
        overlay.x11 = X11()
        overlay.rendered_snapshot = object()
        overlay.refresh = lambda **options: calls.append(
            ("refresh", options)
        )
        overlay._draw = lambda snapshot: calls.append(
            ("draw", snapshot)
        )

        overlay.show()

        self.assertTrue(overlay.visible)
        self.assertEqual(
            calls,
            [
                (
                    "refresh",
                    {
                        "force_image": False,
                        "sync_position": True,
                    },
                ),
                ("map", 2, 3),
                ("flush", 2),
                ("draw", overlay.rendered_snapshot),
            ],
        )

    def test_cursor_overlay_rebases_inside_image_refresh_window(self):
        overlay = NestedDesktopCursorOverlay.__new__(
            NestedDesktopCursorOverlay
        )
        overlay.position_primed = True
        overlay.pointer_x = 10.0
        overlay.pointer_y = 20.0
        overlay.next_image_refresh = float("inf")
        overlay._snapshot = MagicMock(return_value=CursorSnapshot(
            x=640,
            y=400,
            width=1,
            height=1,
            xhot=0,
            yhot=0,
            serial=1,
            pixels=(0xFFFFFFFF,),
        ))
        overlay._move = MagicMock()

        overlay.refresh(sync_position=True)

        self.assertEqual((overlay.pointer_x, overlay.pointer_y), (640, 400))
        overlay._snapshot.assert_called_once_with()
        overlay._move.assert_called_once_with()
        self.assertEqual(overlay.next_image_refresh, float("inf"))

    def test_visible_cursor_keeps_relative_position_inside_refresh_window(self):
        overlay = NestedDesktopCursorOverlay.__new__(
            NestedDesktopCursorOverlay
        )
        overlay.position_primed = True
        overlay.pointer_x = 300.0
        overlay.pointer_y = 200.0
        overlay.next_image_refresh = float("inf")
        overlay._snapshot = MagicMock()
        overlay._move = MagicMock()

        overlay.refresh(sync_position=False)

        self.assertEqual((overlay.pointer_x, overlay.pointer_y), (300, 200))
        overlay._snapshot.assert_not_called()
        overlay._move.assert_not_called()

    def test_visible_cursor_overlay_does_not_follow_stale_xfixes_position(self):
        calls = []
        overlay = NestedDesktopCursorOverlay.__new__(
            NestedDesktopCursorOverlay
        )
        overlay.visible = True
        overlay.refresh = lambda **options: calls.append(options)

        overlay.show()

        self.assertEqual(calls, [{"sync_position": False}])

    def test_relative_cursor_motion_warps_kwin_without_visual_rebase(self):
        overlay = NestedDesktopCursorOverlay.__new__(
            NestedDesktopCursorOverlay
        )
        overlay.visible = True
        overlay.pointer_x = 100.0
        overlay.pointer_y = 200.0
        overlay.screen_width = 1280
        overlay.screen_height = 800
        overlay.display = 1
        overlay.x11 = MagicMock()
        overlay._warp_pointer = MagicMock()
        overlay._move = MagicMock()

        overlay.apply(PointerUpdate(dx=5.0, dy=-3.0))

        self.assertEqual((overlay.pointer_x, overlay.pointer_y), (105, 197))
        overlay._warp_pointer.assert_called_once_with(flush=False)
        overlay._move.assert_called_once_with(flush=False)
        overlay.x11.XFlush.assert_called_once_with(1)

    def test_decodes_gamescope_packed_display(self):
        self.assertEqual(decode_gamescope_display(packed_display(":1")), ":1")

    def test_forwards_back_without_requiring_another_running_app(self):
        nested_app = 3_058_091_282
        self.assertTrue(
            should_forward_back_button(
                nested_app,
                [nested_app],
                [nested_app],
                packed_display(":1"),
            )
        )
        self.assertFalse(
            should_forward_back_button(
                nested_app,
                [nested_app],
                [nested_app],
                packed_display(":0"),
            )
        )
        self.assertFalse(
            should_forward_back_button(
                nested_app,
                [632360],
                [632360],
                packed_display(":1"),
            )
        )

    def test_forwards_only_when_nested_desktop_is_frontmost_with_proton(self):
        nested_app = 3_058_091_282
        self.assertTrue(
            should_forward_pointer(
                nested_app,
                [nested_app],
                [nested_app],
                [632360],
                packed_display(":1"),
            )
        )
        self.assertFalse(
            should_forward_pointer(
                nested_app,
                [nested_app],
                [nested_app],
                [],
                packed_display(":1"),
            )
        )
        self.assertFalse(
            should_forward_pointer(
                nested_app,
                [632360],
                [632360],
                [632360],
                packed_display(":1"),
            )
        )
        self.assertFalse(
            should_forward_pointer(
                nested_app,
                [nested_app],
                [nested_app],
                [632360],
                packed_display(":0"),
            )
        )


class RuntimeSuspensionTests(unittest.TestCase):
    def test_focus_exit_requests_one_lazy_clipboard_flush(self):
        class InnerEis:
            ready = False
            keyboard_ready = False
            touch_ready = False

            @staticmethod
            def dispatch():
                pass

        clipboard = MagicMock()
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            clipboard_bridge=clipboard,
        )
        runtime.inner_eis = InnerEis()
        runtime.outer_x11 = MagicMock()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=22,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )
        runtime.nested_desktop_focused = True
        runtime.nested_desktop_gfx_focused = True
        runtime._gamescope_focus_snapshot = MagicMock(return_value=(
            (31,),
            (31,),
            tuple(packed_display(":1")),
            (),
        ))
        for method_name in (
            "_set_touch_forwarding",
            "_set_remote_forwarding",
            "_set_remote_relaying",
            "_set_remote_button_forwarding",
            "_set_forwarding",
            "_set_binding_forwarding",
            "_set_cursor_overlay",
            "_set_gamescope_pointer_intercepted",
        ):
            setattr(runtime, method_name, MagicMock())

        runtime._refresh_forwarding()
        runtime._refresh_forwarding()

        clipboard.release_inner_focus.assert_called_once_with()

    def test_steam_overlay_keeps_clipboard_focus_until_real_app_exit(self):
        class InnerEis:
            ready = False
            keyboard_ready = False
            touch_ready = False

            @staticmethod
            def dispatch():
                pass

        clipboard = MagicMock()
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            clipboard_bridge=clipboard,
        )
        runtime.inner_eis = InnerEis()
        runtime.outer_x11 = MagicMock()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=22,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )
        runtime.nested_desktop_focused = True
        runtime.nested_desktop_gfx_focused = True
        snapshots = iter((
            (
                (STEAM_UI_APP_ID,),
                (22,),
                tuple(packed_display(":0")),
                (),
            ),
            (
                (31,),
                (31,),
                tuple(packed_display(":1")),
                (),
            ),
        ))
        runtime._gamescope_focus_snapshot = MagicMock(
            side_effect=lambda _now: next(snapshots)
        )
        for method_name in (
            "_set_touch_forwarding",
            "_set_remote_forwarding",
            "_set_remote_relaying",
            "_set_remote_button_forwarding",
            "_set_forwarding",
            "_set_binding_forwarding",
            "_set_cursor_overlay",
            "_set_gamescope_pointer_intercepted",
        ):
            setattr(runtime, method_name, MagicMock())

        runtime._refresh_forwarding()

        clipboard.release_inner_focus.assert_not_called()
        self.assertFalse(runtime.nested_desktop_focused)
        self.assertTrue(runtime.nested_desktop_gfx_focused)

        runtime._refresh_forwarding()

        clipboard.release_inner_focus.assert_called_once_with()
        self.assertFalse(runtime.nested_desktop_gfx_focused)

    def test_clipboard_socket_wakes_the_auxiliary_event_loop(self):
        read_fd, write_fd = os.pipe()

        class Clipboard:
            dispatches = 0

            @staticmethod
            def filenos():
                return (read_fd,)

            def dispatch(self):
                os.read(read_fd, 1)
                self.dispatches += 1

        clipboard = Clipboard()
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            clipboard_bridge=clipboard,
        )
        try:
            os.write(write_fd, b"x")

            runtime._read_auxiliary_events(0.5)

            self.assertEqual(clipboard.dispatches, 1)
        finally:
            os.close(write_fd)
            os.close(read_fd)

    def test_idle_trackpad_sampling_accelerates_while_touched(self):
        class InnerEis:
            @staticmethod
            def inject(_update):
                pass

            @staticmethod
            def inject_key(_key_code, _pressed):
                pass

        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        runtime = NestedDesktopMouseRuntime(threading.Event())
        runtime.hidraw_fd = read_fd
        runtime.binding_forwarding = True
        runtime.binding_translator.set_active(True)
        runtime.inner_eis = InnerEis()

        def report(controls=0):
            payload = bytearray(64)
            payload[:3] = b"\x01\x00\x09"
            payload[8:12] = controls.to_bytes(4, "little")
            return payload

        try:
            os.write(write_fd, report())
            runtime._read_reports(0)
            self.assertEqual(
                runtime.input_frame_interval,
                IDLE_INPUT_FRAME_INTERVAL,
            )

            runtime.next_input_frame = 0.0
            os.write(write_fd, report(RIGHT_PAD_TOUCHED))
            runtime._read_reports(0)
            self.assertEqual(
                runtime.input_frame_interval,
                INPUT_FRAME_INTERVAL,
            )
        finally:
            os.close(write_fd)
            runtime.hidraw_fd = None
            os.close(read_fd)

    def test_control_channel_pauses_and_resumes_without_restarting(self):
        read_fd, write_fd = os.pipe()
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            control_fd=read_fd,
        )
        try:
            os.write(write_fd, b"suspend\n")
            runtime._read_control_commands()
            self.assertTrue(runtime.suspended)

            os.write(write_fd, b"resume\n")
            runtime._read_control_commands()
            self.assertFalse(runtime.suspended)
        finally:
            os.close(write_fd)
            os.close(read_fd)

    def test_control_channel_returns_shared_clipboard_text(self):
        class Clipboard:
            def __init__(self):
                self.dispatches = 0

            def dispatch(self):
                self.dispatches += 1

            @staticmethod
            def current_text():
                return "shared ✓"

        read_fd, write_fd = os.pipe()
        actions = []
        clipboard = Clipboard()
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            action_callback=actions.append,
            clipboard_bridge=clipboard,
            control_fd=read_fd,
        )
        try:
            os.write(write_fd, b"clipboard-read:42\n")
            runtime._read_control_commands()
        finally:
            os.close(write_fd)
            os.close(read_fd)

        prefix, request_id, available, payload = actions[0].split(":", 3)
        self.assertEqual((prefix, request_id, available), (
            "clipboard-text",
            "42",
            "1",
        ))
        self.assertEqual(
            base64.b64decode(payload).decode("utf-8"),
            "shared ✓",
        )
        self.assertEqual(clipboard.dispatches, 1)

    def test_remote_activity_requests_one_keyboard_dismiss_per_open(self):
        actions = []
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            action_callback=actions.append,
            rustdesk_connection_query=lambda _path: 1,
            suspended=True,
        )

        runtime._request_keyboard_dismiss_for_remote_input()
        runtime._request_keyboard_dismiss_for_remote_input()
        runtime.set_suspended(False)
        runtime.set_suspended(True)
        runtime._request_keyboard_dismiss_for_remote_input()

        self.assertEqual(
            actions,
            [ACTION_HIDE_KEYBOARD, ACTION_HIDE_KEYBOARD],
        )

    def test_remote_input_requests_nested_desktop_focus_once(self):
        class OuterX11:
            def __init__(self):
                self.writes = []

            @staticmethod
            def cardinals(name):
                return {
                    "GAMESCOPE_FOCUSED_APP": [31],
                    "GAMESCOPE_FOCUSED_APP_GFX": [31],
                    "GAMESCOPECTRL_BASELAYER_APPID": [31, 22, 769],
                }[name]

            def set_cardinals(self, name, values):
                self.writes.append((name, tuple(values)))

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_connection_query=lambda _path: 1,
            rustdesk_focus_on_input_enabled=True,
        )
        runtime.outer_x11 = OuterX11()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=22,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )

        runtime._request_focus_for_remote_input()
        runtime._request_focus_for_remote_input()

        self.assertEqual(
            runtime.outer_x11.writes,
            [
                (
                    "GAMESCOPECTRL_BASELAYER_APPID",
                    (22, 31, 769),
                )
            ],
        )

    def test_remote_input_does_not_rewrite_focus_when_already_frontmost(self):
        class OuterX11:
            writes = []

            @staticmethod
            def cardinals(name):
                return {
                    "GAMESCOPE_FOCUSED_APP": [22],
                    "GAMESCOPE_FOCUSED_APP_GFX": [22],
                }[name]

            @classmethod
            def set_cardinals(cls, name, values):
                cls.writes.append((name, tuple(values)))

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_connection_query=lambda _path: 1,
            rustdesk_focus_on_input_enabled=True,
        )
        runtime.outer_x11 = OuterX11()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=22,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )

        runtime._request_focus_for_remote_input()

        self.assertTrue(runtime.nested_desktop_focused)
        self.assertEqual(runtime.outer_x11.writes, [])

    def test_remote_keyboard_press_is_treated_as_remote_input(self):
        actions = []
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            action_callback=actions.append,
            rustdesk_connection_query=lambda _path: 1,
            suspended=True,
        )
        runtime.rustdesk_keyboard_fd = read_fd
        try:
            os.write(
                write_fd,
                struct.pack("@llHHi", 0, 0, 1, 30, 1),
            )

            runtime._read_rustdesk_keyboard_events()

            self.assertEqual(actions, [ACTION_HIDE_KEYBOARD])
        finally:
            os.close(write_fd)
            runtime.rustdesk_keyboard_fd = None
            os.close(read_fd)

    def test_remote_pointer_rearms_without_a_trackpad_device(self):
        class CursorOverlay:
            def __init__(self, _session):
                pass

            def show(self):
                pass

            def hide(self):
                pass

            def apply(self, _update):
                pass

            def close(self):
                pass

        class AbsoluteEis:
            ready = True
            keyboard_ready = True
            absolute_ready = True
            absolute_emulating = False
            emulating = False

            def __init__(self):
                self.dispatches = 0
                self.transitions = []

            def dispatch(self):
                self.dispatches += 1

            def absolute_bounds(self):
                return (0, 0, 1280, 800)

            def set_absolute_emulating(self, active):
                self.absolute_emulating = active
                self.transitions.append(active)
                return self.absolute_ready

            def set_emulating(self, active):
                self.emulating = active
                return self.ready

            def inject(self, _update):
                pass

            def inject_absolute(self, _update):
                pass

        class OuterX11:
            @staticmethod
            def cardinals(name):
                return {
                    "GAMESCOPE_FOCUSED_APP": [2],
                    "GAMESCOPE_FOCUSED_APP_GFX": [2],
                    "GAMESCOPE_MOUSE_FOCUS_DISPLAY": packed_display(":1"),
                    "GAMESCOPE_FOCUSABLE_WINDOWS": [30, 3, 300],
                }[name]

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_connection_query=lambda _path: 1,
            cursor_overlay_factory=CursorOverlay,
            proton_process_query=lambda pid, _root: pid == 300,
        )
        inner_eis = AbsoluteEis()
        runtime.inner_eis = inner_eis
        runtime.outer_x11 = OuterX11()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )
        runtime.rustdesk_fd = 42

        runtime._refresh_forwarding()
        inner_eis.absolute_emulating = False
        runtime._refresh_forwarding()

        self.assertEqual(inner_eis.transitions, [True, True])
        self.assertTrue(runtime.remote_forwarding)
        self.assertTrue(runtime.remote_scroll_forwarding)
        self.assertTrue(runtime.remote_button_forwarding)

    def test_disabled_mouse_bridge_keeps_keyboard_hotkeys_active(self):
        class InnerEis:
            ready = True
            keyboard_ready = True
            absolute_ready = True
            absolute_emulating = False
            emulating = False

            def __init__(self):
                self.injected_keys = []
                self.keyboard_emulating = False

            def dispatch(self):
                pass

            def set_emulating(self, _active):
                raise AssertionError(
                    "The disabled mouse bridge must not emulate a pointer"
                )

            def set_keyboard_emulating(self, active):
                self.keyboard_emulating = active
                return True

            def inject(self, _update):
                pass

            def inject_key(self, key_code, pressed):
                self.injected_keys.append((key_code, pressed))

        class OuterX11:
            @staticmethod
            def cardinals(name):
                return {
                    "GAMESCOPE_FOCUSED_APP": [2],
                    "GAMESCOPE_FOCUSED_APP_GFX": [2],
                    "GAMESCOPE_MOUSE_FOCUS_DISPLAY": packed_display(":1"),
                    "GAMESCOPE_FOCUSABLE_WINDOWS": [30, 3, 300],
                }[name]

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            mouse_enabled=False,
            rustdesk_pointer_fix_enabled=False,
            proton_process_query=lambda pid, _root: pid == 300,
        )
        inner_eis = InnerEis()
        runtime.inner_eis = inner_eis
        runtime.outer_x11 = OuterX11()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )
        runtime.hidraw_fd = 42

        runtime._refresh_forwarding()
        self.assertTrue(runtime.binding_translator.has_pointer_actions)
        self.assertFalse(
            runtime.binding_translator.pointer_actions_active
        )
        runtime._inject_binding_update(
            runtime.binding_translator.translate(trackpad_state())
        )
        runtime._inject_binding_update(
            runtime.binding_translator.translate(
                trackpad_state(buttons=BUTTON_SOURCE_MASKS["b"])
            )
        )

        self.assertFalse(runtime.forwarding)
        self.assertTrue(runtime.binding_forwarding)
        self.assertTrue(inner_eis.keyboard_emulating)
        self.assertEqual(
            inner_eis.injected_keys,
            [(EIS_KEY_CODES["KEY_ESC"], True)],
        )

    def test_mouse_bridge_ignores_native_app_and_follows_proton_app(self):
        class InnerEis:
            ready = True
            keyboard_ready = True
            absolute_ready = True
            absolute_emulating = False

            def __init__(self):
                self.emulating = False
                self.keyboard_emulating = False

            def dispatch(self):
                pass

            def set_emulating(self, active):
                self.emulating = active
                return True

            def set_keyboard_emulating(self, active):
                self.keyboard_emulating = active
                return True

            def inject(self, _update):
                pass

            def inject_key(self, _key_code, _pressed):
                pass

        class OuterX11:
            focusable_windows = [40, 4, 400]

            @classmethod
            def cardinals(cls, name):
                return {
                    "GAMESCOPE_FOCUSED_APP": [2],
                    "GAMESCOPE_FOCUSED_APP_GFX": [2],
                    "GAMESCOPE_MOUSE_FOCUS_DISPLAY": packed_display(":1"),
                    "GAMESCOPE_FOCUSABLE_WINDOWS": cls.focusable_windows,
                }[name]

        overlays = []

        class CursorOverlay:
            def __init__(self, _session):
                self.shown = 0
                self.hidden = 0
                self.closed = 0
                self.updates = []
                overlays.append(self)

            def show(self):
                self.shown += 1

            def hide(self):
                self.hidden += 1

            def apply(self, update):
                self.updates.append(update)

            def close(self):
                self.closed += 1

        cursor_commands = []
        cursor_directory = tempfile.TemporaryDirectory()
        self.addCleanup(cursor_directory.cleanup)
        cursor_compositor = GamescopeCursorCompositor(
            command=lambda value: cursor_commands.append(value) or True,
            marker_path=Path(cursor_directory.name) / "cursor-hidden",
        )
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_pointer_fix_enabled=False,
            cursor_overlay_factory=CursorOverlay,
            proton_process_query=lambda pid, _root: pid == 300,
            gamescope_cursor_compositor=cursor_compositor,
        )
        inner_eis = InnerEis()
        runtime.inner_eis = inner_eis
        runtime.outer_x11 = OuterX11()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )
        runtime.hidraw_fd = 42

        runtime._refresh_forwarding()

        self.assertTrue(runtime.binding_forwarding)
        self.assertFalse(runtime.binding_pointer_forwarding)
        self.assertFalse(runtime.forwarding)
        self.assertTrue(inner_eis.keyboard_emulating)
        self.assertFalse(inner_eis.emulating)
        self.assertEqual(overlays, [])

        OuterX11.focusable_windows = [30, 3, 300]
        runtime._refresh_forwarding()

        self.assertTrue(runtime.binding_forwarding)
        self.assertTrue(runtime.binding_pointer_forwarding)
        self.assertTrue(runtime.forwarding)
        self.assertTrue(inner_eis.emulating)
        self.assertTrue(runtime.cursor_overlay_active)
        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0].shown, 1)
        update = PointerUpdate(dx=5, dy=-3)
        runtime._apply_cursor_overlay(update)
        self.assertEqual(overlays[0].updates, [update])

        OuterX11.focusable_windows = []
        runtime._refresh_forwarding()

        self.assertTrue(runtime.binding_forwarding)
        self.assertFalse(runtime.binding_pointer_forwarding)
        self.assertFalse(runtime.forwarding)
        self.assertTrue(inner_eis.keyboard_emulating)
        self.assertFalse(inner_eis.emulating)
        self.assertFalse(runtime.cursor_overlay_active)
        self.assertEqual(overlays[0].hidden, 1)
        self.assertEqual(cursor_commands, [0, 1])

    def test_legacy_forced_software_cursor_skips_dynamic_overlay(self):
        created = []
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            cursor_overlay_factory=lambda session: created.append(session),
        )
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
            software_cursor_forced=True,
        )

        runtime._set_cursor_overlay(True)

        self.assertEqual(created, [])
        self.assertFalse(runtime.cursor_overlay_active)

    def test_remote_pointer_uses_relay_without_a_parallel_app(self):
        class AbsoluteEis:
            ready = True
            keyboard_ready = True
            absolute_ready = True
            absolute_emulating = False

            def dispatch(self):
                pass

            def set_absolute_emulating(self, active):
                self.absolute_emulating = active
                return self.absolute_ready

            def set_emulating(self, active):
                self.emulating = active
                return self.ready

            def inject(self, _update):
                pass

            def absolute_bounds(self):
                return (0, 0, 1280, 800)

            def inject_absolute(self, _update):
                pass

        class OuterX11:
            @staticmethod
            def cardinals(name):
                return {
                    "GAMESCOPE_FOCUSED_APP": [2],
                    "GAMESCOPE_FOCUSED_APP_GFX": [2],
                    "GAMESCOPE_MOUSE_FOCUS_DISPLAY": packed_display(":1"),
                    "GAMESCOPE_FOCUSABLE_WINDOWS": [],
                }[name]

        with tempfile.TemporaryDirectory() as directory:
            relay_path = Path(directory) / "pointer-relay.sock"
            runtime = NestedDesktopMouseRuntime(
                threading.Event(),
                rustdesk_relay_path=relay_path,
                rustdesk_connection_query=lambda _path: 1,
            )
            runtime.inner_eis = AbsoluteEis()
            runtime.outer_x11 = OuterX11()
            runtime.session = NestedDesktopSession(
                pid=1,
                app_id=2,
                display=":2",
                xauthority=Path("/tmp/xauth"),
                dbus_address="unix:path=/tmp/dbus",
            )
            runtime.rustdesk_fd = 42

            runtime._refresh_forwarding()

            self.assertTrue(runtime.remote_forwarding)
            self.assertTrue(runtime.remote_button_forwarding)
            self.assertTrue(runtime.remote_relaying)
            self.assertTrue(runtime.remote_scroll_forwarding)
            self.assertTrue(runtime.inner_eis.absolute_emulating)
            self.assertTrue(runtime.inner_eis.emulating)
            self.assertTrue(relay_path.is_socket())

            runtime._set_remote_forwarding(False)
            self.assertFalse(relay_path.exists())
            self.assertFalse(runtime.remote_relaying)

    def test_remote_relay_injects_motion_and_buttons_through_eis(self):
        class AbsoluteEis:
            def __init__(self):
                self.updates = []
                self.scroll_updates = []

            def absolute_bounds(self):
                return (0, 0, 1280, 800)

            def inject_absolute(self, update):
                self.updates.append(update)

            def inject(self, update):
                self.scroll_updates.append(update)

        with tempfile.TemporaryDirectory() as directory:
            relay_path = Path(directory) / "pointer-relay.sock"
            runtime = NestedDesktopMouseRuntime(
                threading.Event(),
                rustdesk_relay_path=relay_path,
            )
            runtime.inner_eis = AbsoluteEis()
            runtime.remote_forwarding = True
            runtime.remote_scroll_forwarding = True
            runtime.remote_button_forwarding = True
            self.assertTrue(runtime._set_remote_relaying(True))
            sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            try:
                for event in (
                    (3, 0, 640),
                    (3, 1, 400),
                    (0, 0, 0),
                    (1, 0x110, 1),
                    (0, 0, 0),
                    (2, 8, -1),
                    (0, 0, 0),
                ):
                    sender.sendto(
                        struct.pack("@llHHi", 0, 0, *event),
                        str(relay_path),
                    )

                runtime._read_rustdesk_relay_events()

                self.assertEqual(
                    runtime.inner_eis.updates,
                    [
                        PointerUpdate(
                            absolute_x=639.5,
                            absolute_y=399.5,
                        ),
                        PointerUpdate(left_button=True),
                    ],
                )
                self.assertEqual(
                    runtime.inner_eis.scroll_updates,
                    [
                        PointerUpdate(
                            scroll_discrete_y=90,
                        ),
                    ],
                )
            finally:
                sender.close()
                runtime._set_remote_relaying(False)

    def test_remote_motion_mode_drops_duplicated_native_buttons(self):
        class AbsoluteEis:
            def __init__(self):
                self.updates = []

            def absolute_bounds(self):
                return (0, 0, 1280, 800)

            def inject_absolute(self, update):
                self.updates.append(update)

        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        runtime = NestedDesktopMouseRuntime(threading.Event())
        runtime.rustdesk_fd = read_fd
        runtime.inner_eis = AbsoluteEis()
        runtime.remote_forwarding = True
        try:
            records = (
                (1, 0, 0x82, 0),
                (1, 0, 0x82, 1),
                (2, 1_000, 0x02, 0),
                (2, 2_000, 0x02, 1),
                (3, 1, 0x01, 0),
                (4, 0, 0x01, 0),
            )
            os.write(
                write_fd,
                b"".join(struct.pack("<IhBB", *record) for record in records),
            )

            runtime._read_rustdesk_events()

            self.assertEqual(len(runtime.inner_eis.updates), 1)
            update = runtime.inner_eis.updates[0]
            self.assertIsNotNone(update.absolute_x)
            self.assertIsNotNone(update.absolute_y)
            self.assertIsNone(update.left_button)
        finally:
            os.close(write_fd)
            runtime.rustdesk_fd = None
            os.close(read_fd)


class RustDeskIpcTests(unittest.TestCase):
    def test_round_trips_supported_frame_header_sizes(self):
        first, second = socket.socketpair()
        try:
            for payload in (
                b"small",
                b"x" * 64,
                b"x" * (0x3FFF + 1),
            ):
                first.sendall(encode_rustdesk_ipc_frame(payload))
                self.assertEqual(
                    receive_rustdesk_ipc_frame(
                        second,
                        maximum_length=len(payload),
                    ),
                    payload,
                )
        finally:
            first.close()
            second.close()

    def test_queries_authorized_video_connection_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ipc"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(1)
            requests = []

            def serve():
                connection, _ = listener.accept()
                with connection:
                    requests.append(
                        json.loads(
                            receive_rustdesk_ipc_frame(
                                connection
                            ).decode()
                        )
                    )
                    response = json.dumps(
                        {"t": "VideoConnCount", "c": 2},
                        separators=(",", ":"),
                    ).encode()
                    connection.sendall(
                        encode_rustdesk_ipc_frame(response)
                    )

            server = threading.Thread(target=serve, daemon=True)
            server.start()
            try:
                self.assertEqual(
                    query_rustdesk_video_connection_count(
                        path,
                        timeout=0.5,
                    ),
                    2,
                )
            finally:
                server.join(timeout=1)
                listener.close()

            self.assertFalse(server.is_alive())
            self.assertEqual(
                requests,
                [{"t": "VideoConnCount", "c": None}],
            )

    def test_connection_state_is_cached_and_expires_after_ipc_loss(self):
        responses = iter((1, None, None, 0))
        queries = []

        def query(path):
            queries.append(path)
            return next(responses)

        path = Path("/tmp/rustdesk-test-ipc")
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_ipc_path=path,
            rustdesk_connection_query=query,
        )

        self.assertTrue(runtime._has_active_rustdesk_connection(0.0))
        self.assertTrue(runtime._has_active_rustdesk_connection(0.25))
        self.assertTrue(runtime._has_active_rustdesk_connection(0.5))
        self.assertTrue(runtime._has_active_rustdesk_connection(2.1))
        self.assertFalse(runtime._has_active_rustdesk_connection(4.2))
        self.assertFalse(runtime._has_active_rustdesk_connection(4.7))
        self.assertEqual(queries, [path, path, path, path])

    def test_disconnect_count_disables_bridge_without_grace(self):
        responses = iter((1, 0))
        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_connection_query=lambda _path: next(responses),
        )

        self.assertTrue(runtime._has_active_rustdesk_connection(0.0))
        self.assertTrue(runtime._has_active_rustdesk_connection(0.5))
        self.assertFalse(runtime._has_active_rustdesk_connection(2.0))


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _process(
        self,
        pid: int,
        parent_pid: int,
        arguments: list[str],
        environment: dict[str, str] | None = None,
    ):
        process = self.root / "proc" / str(pid)
        process.mkdir(parents=True)
        (process / "cmdline").write_bytes(
            b"\0".join(argument.encode() for argument in arguments) + b"\0"
        )
        (process / "status").write_text(
            f"Name:\ttest\nPPid:\t{parent_pid}\n",
            encoding="utf-8",
        )
        if environment:
            (process / "environ").write_bytes(
                b"\0".join(
                    f"{key}={value}".encode()
                    for key, value in environment.items()
                )
                + b"\0"
            )

    def test_discovers_nested_display_and_app_id_through_parent_chain(self):
        authority = self.root / "run/nested-desktop.test/xauth_test"
        authority.parent.mkdir(parents=True)
        authority.write_bytes(b"cookie")
        self._process(
            100,
            1,
            ["/steam/reaper", "SteamLaunch", "AppId=123456", "--"],
        )
        self._process(
            101,
            100,
            ["/bin/sh", "steamos-nested-desktop"],
            {"KWIN_FORCE_SW_CURSOR": "1"},
        )
        self._process(
            102,
            101,
            [
                "/usr/bin/kwin_wayland",
                "--socket",
                "wayland-7",
                "--xwayland-display",
                ":2",
                "--xwayland-xauthority",
                str(authority),
            ],
        )
        dbus_address = "unix:path=/tmp/dbus-test,guid=test"
        self._process(
            103,
            101,
            ["/usr/bin/plasmashell"],
            {
                "XDG_RUNTIME_DIR": str(authority.parent),
                "DBUS_SESSION_BUS_ADDRESS": dbus_address,
            },
        )

        session = find_nested_desktop_session(self.root / "proc")

        self.assertIsNotNone(session)
        self.assertEqual(session.app_id, 123456)
        self.assertEqual(session.display, ":2")
        self.assertEqual(session.xauthority, authority)
        self.assertEqual(session.dbus_address, dbus_address)
        self.assertEqual(session.wayland_display, "wayland-7")
        self.assertTrue(session.software_cursor_forced)

    def test_detects_proton_from_wine_environment(self):
        self._process(
            200,
            1,
            ["Z:\\games\\example.exe"],
            {
                "SteamAppId": "632360",
                "WINEPREFIX": "/steamapps/compatdata/632360/pfx",
            },
        )

        self.assertTrue(process_uses_proton(200, self.root / "proc"))

    def test_detects_proton_launcher_in_parent_chain(self):
        self._process(
            210,
            1,
            ["/steamapps/common/Proton 10.0/proton", "waitforexitandrun"],
        )
        self._process(211, 210, ["/games/example.exe"])

        self.assertTrue(process_uses_proton(211, self.root / "proc"))

    def test_does_not_treat_native_linux_runtime_as_proton(self):
        self._process(
            220,
            1,
            ["/usr/lib/pressure-vessel-wrap", "--", "/usr/bin/konsole"],
            {
                "SteamAppId": "4048939261",
                "STEAM_COMPAT_DATA_PATH": "/steamapps/compatdata/4048939261",
            },
        )

        self.assertFalse(process_uses_proton(220, self.root / "proc"))

    def test_discovers_vendor_hid_interface_instead_of_mouse_interface(self):
        sys_class = self.root / "sys/class/hidraw"
        for name, descriptor in (
            ("hidraw0", b"\x05\x01mouse"),
            ("hidraw3", b"\x06\xff\xffvendor"),
        ):
            device = sys_class / name / "device"
            device.mkdir(parents=True)
            (device / "uevent").write_text(
                "HID_ID=0003:000028DE:00001205\n",
                encoding="utf-8",
            )
            (device / "report_descriptor").write_bytes(descriptor)

        result = find_steam_deck_hidraw(sys_class, self.root / "dev")

        self.assertEqual(result, self.root / "dev/hidraw3")

    def test_discovers_world_readable_rustdesk_joystick(self):
        sys_class = self.root / "sys/class/input"
        for name, device_name in (
            ("js0", "Valve Software Steam Controller"),
            ("js2", "mouce-library-fake-mouse"),
        ):
            device = sys_class / name / "device"
            device.mkdir(parents=True)
            (device / "name").write_text(device_name, encoding="utf-8")

        result = find_rustdesk_joystick(
            sys_class,
            self.root / "dev/input",
        )

        self.assertEqual(result, self.root / "dev/input/js2")

    def test_discovers_rustdesk_virtual_keyboard(self):
        sys_class = self.root / "sys/class/input"
        for name, device_name in (
            ("event4", "Valve Software Steam Controller"),
            ("event10", "RustDesk UInput Keyboard"),
        ):
            device = sys_class / name / "device"
            device.mkdir(parents=True)
            (device / "name").write_text(device_name, encoding="utf-8")

        result = find_rustdesk_keyboard(
            sys_class,
            self.root / "dev/input",
        )

        self.assertEqual(result, self.root / "dev/input/event10")

    def test_manages_only_the_nested_wayland_alias(self):
        runtime = self.root / "run/user/1000/nested-desktop.test"
        runtime.mkdir(parents=True)
        authority = runtime / "xauth_test"
        authority.write_bytes(b"cookie")
        target = runtime / "wayland-0"
        target.write_bytes(b"socket")
        session = NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=authority,
            dbus_address="unix:path=/tmp/test",
        )

        alias = ensure_nested_wayland_alias(session)

        self.assertEqual(alias, runtime.parent / "wayland-0")
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.resolve(), target)

        remove_nested_wayland_alias(session, alias)

        self.assertFalse(os.path.lexists(alias))


if __name__ == "__main__":
    unittest.main()
