import asyncio
import json
import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
decky_plugin = types.ModuleType("decky_plugin")
decky_plugin.logger = logging.getLogger("4deus-mod-test")
decky_plugin.DECKY_USER_HOME = str(PROJECT_ROOT)
decky_plugin.DECKY_PLUGIN_DIR = str(PROJECT_ROOT)
sys.modules.setdefault("decky_plugin", decky_plugin)

from fourdeus_backend import plugin as plugin_backend
from fourdeus_backend.endpoints import controller as controller_endpoints
from fourdeus_backend.nested_desktop.touch import TouchscreenInertiaConfig
import main as decky_entrypoint


class RecordingKeyboard:
    def __init__(self):
        self.events = []
        self.closed = False

    def write_key(self, key_code, value):
        self.events.append((key_code, value))

    def close(self):
        self.closed = True


class PreparedRecordingKeyboard(RecordingKeyboard):
    def __init__(self):
        super().__init__()
        self.prepare_calls = 0

    def prepare(self):
        self.prepare_calls += 1
        return self.prepare_calls == 1


class FailingKeyboard(RecordingKeyboard):
    def write_key(self, key_code, value):
        raise OSError("detached uinput device")


class EntrypointTests(unittest.TestCase):
    def test_decky_entrypoint_exports_the_backend_plugin(self):
        self.assertIs(decky_entrypoint.Plugin, plugin_backend.Plugin)


class RecordingMouseBridge:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.is_running = True
        self.module_enabled_values = []
        self.inertia_values = []
        self.mouse_enabled_values = []
        self.gamescope_pointer_relay_values = []
        self.clipboard_values = []
        self.clipboard_files_values = []
        self.binding_values = []
        self.rustdesk_pointer_fix_values = []
        self.rustdesk_scroll_inertia_values = []
        self.rustdesk_focus_on_input_values = []
        self.touchscreen_values = []
        self.touchscreen_inertia_values = []
        self.touchscreen_inertia_configs = []
        self.suspended_values = []

    def start(self):
        self.started += 1
        self.is_running = True

    def stop(self):
        self.stopped += 1
        self.is_running = False

    def running(self):
        return self.is_running

    def set_inertia_enabled(self, enabled):
        self.inertia_values.append(enabled)

    def set_module_enabled(self, enabled):
        self.module_enabled_values.append(enabled)
        if enabled:
            self.start()
        else:
            self.stop()

    def set_mouse_enabled(self, enabled):
        self.mouse_enabled_values.append(enabled)

    def set_gamescope_pointer_relay_enabled(self, enabled):
        self.gamescope_pointer_relay_values.append(enabled)

    def set_clipboard_enabled(self, enabled):
        self.clipboard_values.append(enabled)

    def set_clipboard_files_enabled(self, enabled):
        self.clipboard_files_values.append(enabled)

    def set_bindings(self, enabled, bindings):
        self.binding_values.append((enabled, dict(bindings)))

    def set_rustdesk_pointer_fix_enabled(self, enabled):
        self.rustdesk_pointer_fix_values.append(enabled)

    def set_rustdesk_scroll_inertia_enabled(self, enabled):
        self.rustdesk_scroll_inertia_values.append(enabled)

    def set_rustdesk_focus_on_input_enabled(self, enabled):
        self.rustdesk_focus_on_input_values.append(enabled)

    def set_touchscreen_enabled(self, enabled):
        self.touchscreen_values.append(enabled)

    def set_touchscreen_inertia_enabled(self, enabled):
        self.touchscreen_inertia_values.append(enabled)

    def set_touchscreen_inertia_config(self, config):
        self.touchscreen_inertia_configs.append(config)

    @staticmethod
    def touchscreen_available():
        return True

    def set_suspended(self, suspended):
        self.suspended_values.append(suspended)


class RecordingTrackpadMetrics:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.is_running = False
        self.captures = []
        self.window_requests = []
        self.cleared = 0
        self.deleted = []
        self.metrics_enabled = False
        self.recovery_enabled = False
        self.configurations = []
        self.recovery_results = []

    def configure(self, *, metrics_enabled, recovery_enabled):
        self.configurations.append((metrics_enabled, recovery_enabled))
        should_run = metrics_enabled or recovery_enabled
        if should_run and not self.is_running:
            self.started += 1
        elif not should_run and self.is_running:
            self.stopped += 1
        self.is_running = should_run
        self.metrics_enabled = metrics_enabled
        self.recovery_enabled = recovery_enabled

    def start(self):
        self.started += 1
        self.is_running = True

    def stop(self):
        self.stopped += 1
        self.is_running = False

    def status(self):
        return {
            "running": self.metrics_enabled and self.is_running,
            "devicePath": "/dev/hidraw0" if self.is_running else "",
            "sampleCount": 3,
            "retainedSeconds": 2,
            "capacitySeconds": 900,
            "sampleRateHz": 20,
            "latest": None,
            "captures": list(self.captures),
        }

    def recovery_status(self):
        return {
            "enabled": self.recovery_enabled,
            "monitoring": self.recovery_enabled and self.is_running,
            "armed": False,
            "pending": False,
            "lastAttemptAtMs": 0,
            "lastSuccessAtMs": 0,
            "successCount": 0,
        }

    def report_recovery_result(self, request_id, success, error=""):
        self.recovery_results.append((request_id, success, error))
        return True

    def window(self, capture_id, max_samples):
        self.window_requests.append((capture_id, max_samples))
        return {
            "captureId": capture_id or "",
            "sampleCount": 0,
            "samples": [],
        }

    def capture(self):
        self.captures.insert(0, {
            "id": "capture-1",
            "createdAtMs": 1,
            "reason": "manual",
            "automatic": False,
            "sampleCount": 3,
            "durationMs": 2_000,
            "leftPeakPressure": 100,
            "rightPeakPressure": 200,
        })

    def clear(self):
        self.cleared += 1

    def delete_capture(self, capture_id):
        self.deleted.append(capture_id)
        self.captures = [
            capture
            for capture in self.captures
            if capture["id"] != capture_id
        ]


class SendSystemKeyTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_chord_prepares_a_hotplugged_keyboard(self):
        plugin = plugin_backend.Plugin()
        keyboard = PreparedRecordingKeyboard()
        plugin.keyboard = keyboard

        sleep = AsyncMock()
        with patch.object(plugin_backend.asyncio, "sleep", sleep):
            sent = await plugin.send_system_key("KEY_ESC")

        self.assertTrue(sent)
        self.assertEqual(keyboard.prepare_calls, 1)
        self.assertEqual(sleep.await_count, 2)

    async def test_detached_keyboard_is_recreated_and_retried(self):
        plugin = plugin_backend.Plugin()
        failed = FailingKeyboard()
        replacement = RecordingKeyboard()
        plugin.keyboard = failed

        with (
            patch.object(
                plugin_backend,
                "VirtualKeyboard",
                return_value=replacement,
            ),
            patch.object(plugin_backend.asyncio, "sleep", AsyncMock()),
            self.assertLogs(plugin_backend.logger, level="ERROR"),
        ):
            sent = await plugin.send_system_key("KEY_ESC")

        self.assertTrue(sent)
        self.assertTrue(failed.closed)
        self.assertIs(plugin.keyboard, replacement)
        self.assertEqual(
            replacement.events,
            [
                (plugin_backend.KEY_CODES["KEY_ESC"], 1),
                (plugin_backend.KEY_CODES["KEY_ESC"], 0),
            ],
        )

    async def test_retry_request_id_is_idempotent(self):
        plugin = plugin_backend.Plugin()
        keyboard = RecordingKeyboard()
        plugin.keyboard = keyboard

        with patch.object(plugin_backend.asyncio, "sleep", AsyncMock()):
            first = await plugin.send_system_key(
                "KEY_LEFTSHIFT",
                with_alt=True,
                request_id="frontend-session-1",
            )
            retry = await plugin.send_system_key(
                "KEY_LEFTSHIFT",
                with_alt=True,
                request_id="frontend-session-1",
            )

        self.assertTrue(first)
        self.assertTrue(retry)
        self.assertEqual(
            keyboard.events,
            [
                (plugin_backend.KEY_LEFTALT, 1),
                (plugin_backend.KEY_LEFTSHIFT, 1),
                (plugin_backend.KEY_LEFTSHIFT, 0),
                (plugin_backend.KEY_LEFTALT, 0),
            ],
        )

    async def test_recreated_keyboard_restores_held_modifiers(self):
        plugin = plugin_backend.Plugin()
        failed = RecordingKeyboard()
        replacement = RecordingKeyboard()
        plugin.keyboard = failed
        plugin.held_key_codes.add(plugin_backend.KEY_LEFTCTRL)

        with (
            patch.object(
                plugin_backend,
                "VirtualKeyboard",
                return_value=replacement,
            ),
            patch.object(plugin_backend.asyncio, "sleep", AsyncMock()),
        ):
            recreated = await plugin._recreate_system_keyboard(failed)

        self.assertTrue(recreated)
        self.assertTrue(failed.closed)
        self.assertEqual(
            replacement.events,
            [(plugin_backend.KEY_LEFTCTRL, 1)],
        )

    async def test_alt_shift_emits_a_complete_chord(self):
        plugin = plugin_backend.Plugin()
        keyboard = RecordingKeyboard()
        plugin.keyboard = keyboard

        with patch.object(plugin_backend.asyncio, "sleep", AsyncMock()):
            sent = await plugin.send_system_key(
                "KEY_LEFTSHIFT",
                with_alt=True,
            )

        self.assertTrue(sent)
        self.assertEqual(
            keyboard.events,
            [
                (plugin_backend.KEY_LEFTALT, 1),
                (plugin_backend.KEY_CODES["KEY_LEFTSHIFT"], 1),
                (plugin_backend.KEY_CODES["KEY_LEFTSHIFT"], 0),
                (plugin_backend.KEY_LEFTALT, 0),
            ],
        )

    async def test_start_emits_left_meta(self):
        plugin = plugin_backend.Plugin()
        keyboard = RecordingKeyboard()
        plugin.keyboard = keyboard

        with patch.object(plugin_backend.asyncio, "sleep", AsyncMock()):
            sent = await plugin.send_system_key("KEY_LEFTMETA")

        self.assertTrue(sent)
        self.assertEqual(
            keyboard.events,
            [
                (plugin_backend.KEY_CODES["KEY_LEFTMETA"], 1),
                (plugin_backend.KEY_CODES["KEY_LEFTMETA"], 0),
            ],
        )

    async def test_cmd_space_emits_a_complete_chord(self):
        plugin = plugin_backend.Plugin()
        keyboard = RecordingKeyboard()
        plugin.keyboard = keyboard

        with patch.object(plugin_backend.asyncio, "sleep", AsyncMock()):
            sent = await plugin.send_system_key(
                "KEY_SPACE",
                with_meta=True,
            )

        self.assertTrue(sent)
        self.assertEqual(
            keyboard.events,
            [
                (plugin_backend.KEY_LEFTMETA, 1),
                (plugin_backend.KEY_CODES["KEY_SPACE"], 1),
                (plugin_backend.KEY_CODES["KEY_SPACE"], 0),
                (plugin_backend.KEY_LEFTMETA, 0),
            ],
        )

    async def test_control_can_be_held_and_released(self):
        plugin = plugin_backend.Plugin()
        keyboard = RecordingKeyboard()
        plugin.keyboard = keyboard

        pressed = await plugin.set_system_key_state("KEY_LEFTCTRL", True)
        released = await plugin.set_system_key_state("KEY_LEFTCTRL", False)

        self.assertTrue(pressed)
        self.assertTrue(released)
        self.assertEqual(
            keyboard.events,
            [
                (plugin_backend.KEY_LEFTCTRL, 1),
                (plugin_backend.KEY_LEFTCTRL, 0),
            ],
        )

    async def test_alt_can_be_sent_as_a_standalone_key(self):
        plugin = plugin_backend.Plugin()
        keyboard = RecordingKeyboard()
        plugin.keyboard = keyboard

        with patch.object(plugin_backend.asyncio, "sleep", AsyncMock()):
            sent = await plugin.send_system_key("KEY_LEFTALT")

        self.assertTrue(sent)
        self.assertEqual(
            keyboard.events,
            [
                (plugin_backend.KEY_LEFTALT, 1),
                (plugin_backend.KEY_LEFTALT, 0),
            ],
        )

    async def test_quick_chord_preserves_an_already_held_modifier(self):
        plugin = plugin_backend.Plugin()
        keyboard = RecordingKeyboard()
        plugin.keyboard = keyboard

        with patch.object(plugin_backend.asyncio, "sleep", AsyncMock()):
            await plugin.set_system_key_state("KEY_LEFTCTRL", True)
            sent = await plugin.send_system_key(
                "KEY_DELETE",
                with_control=True,
                with_shift=True,
            )
            await plugin.set_system_key_state("KEY_LEFTCTRL", False)

        self.assertTrue(sent)
        self.assertEqual(
            keyboard.events,
            [
                (plugin_backend.KEY_LEFTCTRL, 1),
                (plugin_backend.KEY_LEFTSHIFT, 1),
                (plugin_backend.KEY_CODES["KEY_DELETE"], 1),
                (plugin_backend.KEY_CODES["KEY_DELETE"], 0),
                (plugin_backend.KEY_LEFTSHIFT, 0),
                (plugin_backend.KEY_LEFTCTRL, 0),
            ],
        )

    async def test_diagnostics_are_bounded_before_logging(self):
        plugin = plugin_backend.Plugin()
        with self.assertLogs(plugin_backend.logger, level="INFO") as captured:
            logged = await plugin.log_keyboard_diagnostics("x" * 5000)

        self.assertTrue(logged)
        message = captured.output[-1]
        self.assertIn("Keyboard diagnostics:", message)
        self.assertLess(len(message), 4100)


class NestedDesktopMouseSettingTests(unittest.IsolatedAsyncioTestCase):
    async def test_module_switch_preserves_settings_and_stops_the_worker(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            disabled = await plugin.set_nested_desktop_module_enabled(False)

            self.assertFalse(disabled["moduleEnabled"])
            self.assertFalse(disabled["running"])
            self.assertTrue(disabled["enabled"])
            self.assertTrue(disabled["bindingsEnabled"])
            self.assertEqual(bridge.module_enabled_values, [False])
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["moduleEnabled"])
            self.assertTrue(payload["enabled"])
            self.assertTrue(payload["bindingsEnabled"])

            enabled = await plugin.set_nested_desktop_module_enabled(True)

            self.assertTrue(enabled["moduleEnabled"])
            self.assertTrue(enabled["running"])
            self.assertEqual(bridge.module_enabled_values, [False, True])

    async def test_bindings_start_worker_when_mouse_bridge_is_disabled(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        bridge.is_running = False
        keyboard = RecordingKeyboard()
        plugin.nested_desktop_mouse = bridge
        plugin.nested_desktop_mouse_enabled = False
        plugin.nested_desktop_bindings_enabled = True
        plugin.rustdesk_pointer_fix_enabled = False

        with patch.object(
            plugin_backend,
            "VirtualKeyboard",
            return_value=keyboard,
        ):
            await plugin._main()
            await plugin._unload()

        self.assertEqual(bridge.started, 1)
        self.assertEqual(bridge.stopped, 1)
        self.assertTrue(keyboard.closed)

    async def test_keyboard_visibility_suspends_without_stopping_bridge(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        paused = await plugin.set_nested_desktop_keyboard_visible(True)
        duplicate = await plugin.set_nested_desktop_keyboard_visible(True)
        resumed = await plugin.set_nested_desktop_keyboard_visible(False)

        self.assertTrue(paused)
        self.assertTrue(duplicate)
        self.assertTrue(resumed)
        self.assertEqual(bridge.suspended_values, [True, False])
        self.assertEqual(bridge.started, 0)
        self.assertEqual(bridge.stopped, 0)

    async def test_setting_is_persisted_and_controls_the_bridge(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge
        plugin.nested_desktop_mouse_enabled = True
        plugin.nested_desktop_mouse_inertia_enabled = True

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            disabled = await plugin.set_nested_desktop_mouse_enabled(False)

            self.assertFalse(disabled["enabled"])
            self.assertTrue(disabled["running"])
            self.assertEqual(bridge.mouse_enabled_values, [False])
            self.assertEqual(bridge.stopped, 0)
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "moduleEnabled": True,
                    "enabled": False,
                    "gamescopePointerRelayEnabled": True,
                    "inertiaEnabled": True,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "clipboardEnabled": False,
                    "clipboardFilesEnabled": True,
                    "rustDeskPointerFixEnabled": True,
                    "rustDeskScrollInertiaEnabled": False,
                    "rustDeskFocusOnInputEnabled": False,
                    "touchEnabled": True,
                    "touchInertiaEnabled": True,
                    "touchInertiaConfig": {
                        "durationMs": 600,
                        "startSpeed": 420,
                        "minDistance": 36,
                    },
                },
            )
            self.assertEqual(
                plugin._load_nested_desktop_mouse_settings(),
                (
                    True,
                    False,
                    True,
                    True,
                    True,
                    plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    False,
                    True,
                    True,
                    False,
                    False,
                    True,
                    True,
                    TouchscreenInertiaConfig(),
                ),
            )

            enabled = await plugin.set_nested_desktop_mouse_enabled(True)

            self.assertTrue(enabled["enabled"])
            self.assertTrue(enabled["running"])
            self.assertEqual(
                bridge.mouse_enabled_values,
                [False, True],
            )
            self.assertEqual(bridge.started, 0)
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "moduleEnabled": True,
                    "enabled": True,
                    "gamescopePointerRelayEnabled": True,
                    "inertiaEnabled": True,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "clipboardEnabled": False,
                    "clipboardFilesEnabled": True,
                    "rustDeskPointerFixEnabled": True,
                    "rustDeskScrollInertiaEnabled": False,
                    "rustDeskFocusOnInputEnabled": False,
                    "touchEnabled": True,
                    "touchInertiaEnabled": True,
                    "touchInertiaConfig": {
                        "durationMs": 600,
                        "startSpeed": 420,
                        "minDistance": 36,
                    },
                },
            )
            self.assertEqual(
                plugin._load_nested_desktop_mouse_settings(),
                (
                    True,
                    True,
                    True,
                    True,
                    True,
                    plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    False,
                    True,
                    True,
                    False,
                    False,
                    True,
                    True,
                    TouchscreenInertiaConfig(),
                ),
            )

    async def test_invalid_value_does_not_change_the_setting(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge
        plugin.nested_desktop_mouse_enabled = True
        plugin.nested_desktop_mouse_inertia_enabled = True

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_nested_desktop_mouse_enabled("false")

            self.assertIn("error", result)
            self.assertTrue(result["enabled"])
            self.assertFalse(settings_path.exists())
            self.assertEqual(bridge.started, 0)
            self.assertEqual(bridge.stopped, 0)

    async def test_clipboard_defaults_off_and_can_be_enabled(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        self.assertFalse(plugin.nested_desktop_clipboard_enabled)
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_nested_desktop_clipboard_enabled(True)

            self.assertTrue(result["clipboardEnabled"])
            self.assertEqual(bridge.clipboard_values, [True])
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["clipboardEnabled"])

    async def test_clipboard_files_default_on_and_can_be_disabled(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        self.assertTrue(plugin.nested_desktop_clipboard_files_enabled)
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = (
                await plugin
                .set_nested_desktop_clipboard_files_enabled(False)
            )

            self.assertFalse(result["clipboardFilesEnabled"])
            self.assertEqual(bridge.clipboard_files_values, [False])
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["clipboardFilesEnabled"])

    async def test_reads_shared_clipboard_for_the_steam_keyboard(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        bridge.read_clipboard_text = MagicMock(return_value="shared text")
        plugin.nested_desktop_mouse = bridge
        plugin.nested_desktop_clipboard_enabled = True

        text = await plugin.read_nested_desktop_clipboard_text()

        self.assertEqual(text, "shared text")
        bridge.read_clipboard_text.assert_called_once_with()

    async def test_gamescope_pointer_relay_defaults_on_and_can_be_disabled(
        self,
    ):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        self.assertTrue(
            plugin.nested_desktop_gamescope_pointer_relay_enabled
        )
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = (
                await plugin
                .set_nested_desktop_gamescope_pointer_relay_enabled(False)
            )

            self.assertFalse(result["gamescopePointerRelayEnabled"])
            self.assertEqual(
                bridge.gamescope_pointer_relay_values,
                [False],
            )
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["gamescopePointerRelayEnabled"])

    async def test_inertia_setting_is_persisted_and_applied(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge
        plugin.nested_desktop_mouse_enabled = True
        plugin.nested_desktop_mouse_inertia_enabled = True

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            disabled = (
                await plugin.set_nested_desktop_mouse_inertia_enabled(False)
            )

            self.assertFalse(disabled["inertiaEnabled"])
            self.assertEqual(bridge.inertia_values, [False])
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "moduleEnabled": True,
                    "enabled": True,
                    "gamescopePointerRelayEnabled": True,
                    "inertiaEnabled": False,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "clipboardEnabled": False,
                    "clipboardFilesEnabled": True,
                    "rustDeskPointerFixEnabled": True,
                    "rustDeskScrollInertiaEnabled": False,
                    "rustDeskFocusOnInputEnabled": False,
                    "touchEnabled": True,
                    "touchInertiaEnabled": True,
                    "touchInertiaConfig": {
                        "durationMs": 600,
                        "startSpeed": 420,
                        "minDistance": 36,
                    },
                },
            )

    async def test_invalid_inertia_value_does_not_change_the_setting(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge
        plugin.nested_desktop_mouse_enabled = True
        plugin.nested_desktop_mouse_inertia_enabled = True

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = (
                await plugin.set_nested_desktop_mouse_inertia_enabled("false")
            )

            self.assertIn("error", result)
            self.assertTrue(result["inertiaEnabled"])
            self.assertFalse(settings_path.exists())
            self.assertEqual(bridge.inertia_values, [])

    async def test_touchscreen_defaults_on_and_can_be_disabled(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_nested_desktop_touch_enabled(False)

            self.assertFalse(result["touchEnabled"])
            self.assertTrue(result["touchAvailable"])
            self.assertEqual(bridge.touchscreen_values, [False])
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["touchEnabled"])

    async def test_touchscreen_inertia_is_guarded_and_persisted(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            disabled = (
                await plugin.set_nested_desktop_touch_inertia_enabled(False)
            )
            tuned = await plugin.set_nested_desktop_touch_inertia_config(
                750,
                500,
                42,
            )

            self.assertFalse(disabled["touchInertiaEnabled"])
            self.assertEqual(
                tuned["touchInertiaConfig"],
                {
                    "durationMs": 750,
                    "startSpeed": 500,
                    "minDistance": 42,
                },
            )
            self.assertEqual(bridge.touchscreen_inertia_values, [False])
            self.assertEqual(
                bridge.touchscreen_inertia_configs,
                [TouchscreenInertiaConfig(750, 500, 42)],
            )
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["touchInertiaEnabled"])
            self.assertEqual(
                payload["touchInertiaConfig"],
                tuned["touchInertiaConfig"],
            )

            invalid = (
                await plugin.set_nested_desktop_touch_inertia_config(
                    10_000,
                    500,
                    42,
                )
            )
            self.assertIn("error", invalid)
            self.assertEqual(
                plugin.nested_desktop_touch_inertia_config,
                TouchscreenInertiaConfig(750, 500, 42),
            )

    def test_legacy_setting_defaults_inertia_to_enabled(self):
        plugin = plugin_backend.Plugin()
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            settings_path.write_text(
                json.dumps({"enabled": False}),
                encoding="utf-8",
            )
            plugin.nested_desktop_mouse_settings_path = settings_path

            self.assertEqual(
                plugin._load_nested_desktop_mouse_settings(),
                (
                    True,
                    False,
                    True,
                    True,
                    True,
                    plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    False,
                    True,
                    True,
                    False,
                    False,
                    True,
                    True,
                    TouchscreenInertiaConfig(),
                ),
            )

    async def test_rustdesk_pointer_fix_defaults_on_and_can_be_disabled(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_rustdesk_pointer_fix_enabled(False)

            self.assertFalse(result["rustDeskPointerFixEnabled"])
            self.assertEqual(
                bridge.rustdesk_pointer_fix_values,
                [False],
            )
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["rustDeskPointerFixEnabled"])

    async def test_enabling_rustdesk_pointer_fix_installs_system_hook(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge
        manager = types.SimpleNamespace(
            executable=PROJECT_ROOT / "package.json",
            install=MagicMock(),
        )
        plugin.rustdesk_pointer_fix = manager

        with tempfile.TemporaryDirectory() as directory:
            plugin.nested_desktop_mouse_settings_path = (
                Path(directory) / "nested-desktop-mouse.json"
            )
            result = await plugin.set_rustdesk_pointer_fix_enabled(True)

        self.assertTrue(result["rustDeskPointerFixEnabled"])
        manager.install.assert_called_once_with(restart=True)

    async def test_rustdesk_scroll_inertia_defaults_off_and_can_be_enabled(
        self,
    ):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_rustdesk_scroll_inertia_enabled(True)

            self.assertTrue(result["rustDeskScrollInertiaEnabled"])
            self.assertEqual(
                bridge.rustdesk_scroll_inertia_values,
                [True],
            )
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["rustDeskScrollInertiaEnabled"])

    async def test_invalid_rustdesk_scroll_inertia_is_rejected(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_rustdesk_scroll_inertia_enabled("true")

            self.assertIn("error", result)
            self.assertFalse(result["rustDeskScrollInertiaEnabled"])
            self.assertFalse(settings_path.exists())
            self.assertEqual(bridge.rustdesk_scroll_inertia_values, [])

    async def test_rustdesk_focus_on_input_defaults_off_and_can_be_enabled(
        self,
    ):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge
        self.assertFalse(plugin.rustdesk_focus_on_input_enabled)

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_rustdesk_focus_on_input_enabled(True)

            self.assertTrue(result["rustDeskFocusOnInputEnabled"])
            self.assertEqual(
                bridge.rustdesk_focus_on_input_values,
                [True],
            )
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["rustDeskFocusOnInputEnabled"])

    async def test_invalid_rustdesk_focus_on_input_is_rejected(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_rustdesk_focus_on_input_enabled("true")

            self.assertIn("error", result)
            self.assertFalse(result["rustDeskFocusOnInputEnabled"])
            self.assertFalse(settings_path.exists())
            self.assertEqual(bridge.rustdesk_focus_on_input_values, [])

    async def test_bindings_can_be_disabled_and_persisted(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_nested_desktop_bindings_enabled(False)

            self.assertFalse(result["bindingsEnabled"])
            self.assertEqual(
                bridge.binding_values,
                [(False, plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS)],
            )
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["bindingsEnabled"])

    async def test_binding_can_be_removed_and_reset_to_steam_defaults(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            plugin.nested_desktop_mouse_settings_path = (
                Path(directory) / "nested-desktop-mouse.json"
            )

            removed = await plugin.set_nested_desktop_binding("b", "none")
            reset = await plugin.reset_nested_desktop_bindings()

            self.assertEqual(removed["bindings"]["b"], "none")
            self.assertEqual(reset["bindings"]["b"], "KEY_ESC")
            self.assertEqual(
                bridge.binding_values[-1],
                (True, plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS),
            )

    async def test_invalid_binding_is_rejected_without_persisting(self):
        plugin = plugin_backend.Plugin()
        bridge = RecordingMouseBridge()
        plugin.nested_desktop_mouse = bridge

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "nested-desktop-mouse.json"
            plugin.nested_desktop_mouse_settings_path = settings_path

            result = await plugin.set_nested_desktop_binding(
                "unknown",
                "KEY_ESC",
            )

            self.assertIn("error", result)
            self.assertFalse(settings_path.exists())
            self.assertEqual(bridge.binding_values, [])


class DeveloperSettingTests(unittest.IsolatedAsyncioTestCase):
    def test_controller_module_gate_stops_developer_metrics(self):
        plugin = plugin_backend.Plugin()
        monitor = RecordingTrackpadMetrics()
        plugin.trackpad_metrics = monitor
        plugin.controller_module_enabled = False
        plugin.developer_mode = True
        plugin.trackpad_metrics_enabled = True
        plugin.trackpad_auto_recovery_enabled = True

        plugin._sync_trackpad_metrics()

        self.assertEqual(monitor.configurations, [(False, False)])

    async def test_metrics_require_developer_mode_and_persist(self):
        plugin = plugin_backend.Plugin()
        monitor = RecordingTrackpadMetrics()
        plugin.trackpad_metrics = monitor
        plugin.developer_mode = False
        plugin.trackpad_metrics_enabled = False

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "developer-settings.json"
            plugin.developer_settings_path = settings_path

            rejected = await plugin.set_trackpad_metrics_enabled(True)
            self.assertIn("error", rejected)
            self.assertFalse(settings_path.exists())

            await plugin.set_developer_mode(True)
            enabled = await plugin.set_trackpad_metrics_enabled(True)

            self.assertTrue(enabled["developerMode"])
            self.assertTrue(enabled["trackpadMetricsEnabled"])
            self.assertTrue(enabled["metrics"]["running"])
            self.assertEqual(monitor.started, 1)
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "developerMode": True,
                    "trackpadMetricsEnabled": True,
                },
            )

            disabled = await plugin.set_developer_mode(False)
            self.assertFalse(disabled["developerMode"])
            self.assertTrue(disabled["trackpadMetricsEnabled"])
            self.assertFalse(disabled["metrics"]["running"])
            self.assertEqual(
                plugin._load_developer_settings(),
                (False, True),
            )

    async def test_metrics_capture_window_clear_and_delete_are_forwarded(
        self,
    ):
        plugin = plugin_backend.Plugin()
        monitor = RecordingTrackpadMetrics()
        plugin.trackpad_metrics = monitor
        plugin.developer_mode = True
        plugin.trackpad_metrics_enabled = True

        captured = await plugin.capture_trackpad_metrics()
        window = await plugin.get_trackpad_metrics_window(
            "capture-1",
            400,
        )
        cleared = await plugin.clear_trackpad_metrics_buffer()
        deleted = await plugin.delete_trackpad_metrics_capture("capture-1")

        self.assertEqual(captured["metrics"]["captures"][0]["id"], "capture-1")
        self.assertEqual(window["captureId"], "capture-1")
        self.assertEqual(monitor.window_requests, [("capture-1", 400)])
        self.assertEqual(monitor.cleared, 1)
        self.assertEqual(cleared["metrics"]["sampleCount"], 3)
        self.assertEqual(monitor.deleted, ["capture-1"])
        self.assertEqual(deleted["metrics"]["captures"], [])

    async def test_unload_stops_metrics_monitor(self):
        plugin = plugin_backend.Plugin()
        monitor = RecordingTrackpadMetrics()
        plugin.trackpad_metrics = monitor
        plugin.nested_desktop_mouse = None
        plugin.keyboard = None

        await plugin._unload()

        self.assertEqual(monitor.stopped, 1)


class ControllerSettingTests(unittest.IsolatedAsyncioTestCase):
    async def test_module_switch_preserves_recovery_preference(self):
        plugin = plugin_backend.Plugin()
        monitor = RecordingTrackpadMetrics()
        plugin.trackpad_metrics = monitor
        plugin.trackpad_auto_recovery_enabled = True

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "controller-settings.json"
            plugin.controller_settings_path = settings_path

            disabled = await plugin.set_controller_module_enabled(False)

            self.assertFalse(disabled["moduleEnabled"])
            self.assertTrue(disabled["autoRecoveryEnabled"])
            self.assertFalse(disabled["monitoring"])
            self.assertEqual(monitor.configurations[-1], (False, False))
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "moduleEnabled": False,
                    "trackpadAutoRecoveryEnabled": True,
                },
            )

            enabled = await plugin.set_controller_module_enabled(True)

            self.assertTrue(enabled["moduleEnabled"])
            self.assertTrue(enabled["autoRecoveryEnabled"])
            self.assertTrue(enabled["monitoring"])
            self.assertEqual(monitor.configurations[-1], (False, True))

    async def test_auto_recovery_defaults_off_and_persists(self):
        plugin = plugin_backend.Plugin()
        monitor = RecordingTrackpadMetrics()
        plugin.trackpad_metrics = monitor
        plugin.trackpad_auto_recovery_enabled = False

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "controller-settings.json"
            plugin.controller_settings_path = settings_path
            self.assertEqual(
                plugin._load_controller_settings(),
                (True, False),
            )

            disabled = await plugin.set_trackpad_auto_recovery_enabled(False)

            self.assertFalse(disabled["autoRecoveryEnabled"])
            self.assertFalse(disabled["monitoring"])
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "moduleEnabled": True,
                    "trackpadAutoRecoveryEnabled": False,
                },
            )
            self.assertEqual(
                plugin._load_controller_settings(),
                (True, False),
            )

            enabled = await plugin.set_trackpad_auto_recovery_enabled(True)

            self.assertTrue(enabled["autoRecoveryEnabled"])
            self.assertTrue(enabled["monitoring"])
            self.assertEqual(
                plugin._load_controller_settings(),
                (True, True),
            )
            self.assertEqual(
                monitor.configurations[-1],
                (False, True),
            )

    async def test_confirmed_recovery_power_cycles_the_usb_controller(self):
        plugin = plugin_backend.Plugin()
        plugin.trackpad_metrics = None

        with patch.object(
            controller_endpoints,
            "power_cycle_steam_deck_controller",
            return_value=Path("/dev/hidraw7"),
        ) as power_cycle:
            recovered = plugin._recover_trackpad_controller(12)

        self.assertTrue(recovered)
        power_cycle.assert_called_once_with(device_path=None)


if __name__ == "__main__":
    unittest.main()
