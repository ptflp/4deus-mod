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

    def write_key(self, key_code, value):
        self.events.append((key_code, value))


class RecordingMouseBridge:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.is_running = True
        self.inertia_values = []
        self.binding_values = []
        self.rustdesk_pointer_fix_values = []
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

    def set_bindings(self, enabled, bindings):
        self.binding_values.append((enabled, dict(bindings)))

    def set_rustdesk_pointer_fix_enabled(self, enabled):
        self.rustdesk_pointer_fix_values.append(enabled)

    def set_suspended(self, suspended):
        self.suspended_values.append(suspended)


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
            self.assertFalse(disabled["running"])
            self.assertEqual(bridge.stopped, 1)
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "enabled": False,
                    "inertiaEnabled": True,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "rustDeskPointerFixEnabled": True,
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
                ),
            )

            enabled = await plugin.set_nested_desktop_mouse_enabled(True)

            self.assertTrue(enabled["enabled"])
            self.assertTrue(enabled["running"])
            self.assertEqual(bridge.started, 1)
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "enabled": True,
                    "inertiaEnabled": True,
                    "bindingsEnabled": True,
                    "bindings": plugin_backend.DEFAULT_NESTED_DESKTOP_BINDINGS,
                    "rustDeskPointerFixEnabled": True,
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


if __name__ == "__main__":
    unittest.main()
