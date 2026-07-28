import importlib.util
import logging
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
decky_plugin = types.ModuleType("decky_plugin")
decky_plugin.logger = logging.getLogger("4deus-mod-test")
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

    async def test_diagnostics_are_bounded_before_logging(self):
        plugin = plugin_backend.Plugin()
        with self.assertLogs(plugin_backend.logger, level="INFO") as captured:
            logged = await plugin.log_keyboard_diagnostics("x" * 5000)

        self.assertTrue(logged)
        message = captured.output[-1]
        self.assertIn("Keyboard diagnostics:", message)
        self.assertLess(len(message), 4100)


if __name__ == "__main__":
    unittest.main()
