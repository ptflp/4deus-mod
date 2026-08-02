import unittest

from fourdeus_backend import keyboard as keyboard_backend


class VirtualKeyboardTests(unittest.TestCase):
    def test_prepare_neutralizes_modifiers_only_once(self):
        keyboard = keyboard_backend.VirtualKeyboard.__new__(
            keyboard_backend.VirtualKeyboard
        )
        keyboard.prepared = False
        events = []
        keyboard._write_event = lambda *event: events.append(event)

        self.assertTrue(keyboard.prepare())
        self.assertFalse(keyboard.prepare())
        self.assertEqual(
            events,
            [
                *(
                    (keyboard_backend.EV_KEY, key_code, 0)
                    for key_code in keyboard_backend.MODIFIER_KEY_CODES
                ),
                (
                    keyboard_backend.EV_SYN,
                    keyboard_backend.SYN_REPORT,
                    0,
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
