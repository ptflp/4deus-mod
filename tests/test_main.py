import asyncio
import importlib.util
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

spec = importlib.util.spec_from_file_location(
    "fourdeus_main",
    PROJECT_ROOT / "main.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load the plugin backend")
plugin_backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_backend)


class RecordingKeyboard:
    def __init__(self):
        self.events = []
        self.closed = False

    def write_key(self, key_code, value):
        self.events.append((key_code, value))

    def close(self):
        self.closed = True


class RecordingMouseBridge:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.is_running = True
        self.inertia_values = []
        self.mouse_enabled_values = []
        self.binding_values = []
        self.rustdesk_pointer_fix_values = []
        self.rustdesk_scroll_inertia_values = []
        self.rustdesk_focus_on_input_values = []
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

    def set_mouse_enabled(self, enabled):
        self.mouse_enabled_values.append(enabled)

    def set_bindings(self, enabled, bindings):
        self.binding_values.append((enabled, dict(bindings)))

    def set_rustdesk_pointer_fix_enabled(self, enabled):
        self.rustdesk_pointer_fix_values.append(enabled)

    def set_rustdesk_scroll_inertia_enabled(self, enabled):
        self.rustdesk_scroll_inertia_values.append(enabled)

    def set_rustdesk_focus_on_input_enabled(self, enabled):
        self.rustdesk_focus_on_input_values.append(enabled)

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
                    "enabled": False,
                    "inertiaEnabled": True,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "rustDeskPointerFixEnabled": True,
                    "rustDeskScrollInertiaEnabled": False,
                    "rustDeskFocusOnInputEnabled": False,
                },
            )
            self.assertEqual(
                plugin._load_nested_desktop_mouse_settings(),
                (
                    False,
                    True,
                    True,
                    plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    True,
                    False,
                    False,
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
                    "enabled": True,
                    "inertiaEnabled": True,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "rustDeskPointerFixEnabled": True,
                    "rustDeskScrollInertiaEnabled": False,
                    "rustDeskFocusOnInputEnabled": False,
                },
            )
            self.assertEqual(
                plugin._load_nested_desktop_mouse_settings(),
                (
                    True,
                    True,
                    True,
                    plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    True,
                    False,
                    False,
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
                    "enabled": True,
                    "inertiaEnabled": False,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "rustDeskPointerFixEnabled": True,
                    "rustDeskScrollInertiaEnabled": False,
                    "rustDeskFocusOnInputEnabled": False,
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
                    False,
                    True,
                    True,
                    plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    True,
                    False,
                    False,
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
    async def test_auto_recovery_defaults_on_and_persists(self):
        plugin = plugin_backend.Plugin()
        monitor = RecordingTrackpadMetrics()
        plugin.trackpad_metrics = monitor
        plugin.trackpad_auto_recovery_enabled = True

        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "controller-settings.json"
            plugin.controller_settings_path = settings_path

            disabled = await plugin.set_trackpad_auto_recovery_enabled(False)

            self.assertFalse(disabled["autoRecoveryEnabled"])
            self.assertFalse(disabled["monitoring"])
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {"trackpadAutoRecoveryEnabled": False},
            )
            self.assertFalse(plugin._load_controller_settings())

            enabled = await plugin.set_trackpad_auto_recovery_enabled(True)

            self.assertTrue(enabled["autoRecoveryEnabled"])
            self.assertTrue(enabled["monitoring"])
            self.assertEqual(
                monitor.configurations[-1],
                (False, True),
            )

    async def test_confirmed_recovery_power_cycles_the_usb_controller(self):
        plugin = plugin_backend.Plugin()
        plugin.trackpad_metrics = None

        with patch.object(
            plugin_backend,
            "power_cycle_steam_deck_controller",
            return_value=Path("/dev/hidraw7"),
        ) as power_cycle:
            recovered = plugin._recover_trackpad_controller(12)

        self.assertTrue(recovered)
        power_cycle.assert_called_once_with(device_path=None)


if __name__ == "__main__":
    unittest.main()
