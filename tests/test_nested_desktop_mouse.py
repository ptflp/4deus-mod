from pathlib import Path
import struct
import tempfile
import unittest

from nested_desktop_mouse import (
    LEFT_PAD_TOUCHED,
    LEFT_TRIGGER,
    PointerUpdate,
    RIGHT_PAD_TOUCHED,
    RIGHT_PAD_PRESSED,
    RIGHT_TRIGGER,
    TrackpadState,
    TrackpadTranslator,
    decode_gamescope_display,
    find_nested_desktop_session,
    find_steam_deck_hidraw,
    parse_trackpad_report,
    should_forward_pointer,
)


def trackpad_state(
    *,
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
) -> TrackpadState:
    return TrackpadState(
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
            LEFT_PAD_TOUCHED
            | RIGHT_PAD_TOUCHED
            | RIGHT_PAD_PRESSED
            | LEFT_TRIGGER
            | RIGHT_TRIGGER
        )
        report[8:12] = controls.to_bytes(4, "little")
        struct.pack_into("<hh", report, 16, 4321, -8765)
        struct.pack_into("<hh", report, 20, -1234, 5678)
        struct.pack_into("<H", report, 58, 3456)

        state = parse_trackpad_report(bytes(report))

        self.assertEqual(
            state,
            trackpad_state(
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
            ),
        )

    def test_ignores_other_hid_reports(self):
        self.assertIsNone(parse_trackpad_report(b"\0" * 64))
        self.assertIsNone(parse_trackpad_report(b"\x01\x00\x09"))
        self.assertIsNone(
            parse_trackpad_report(b"\x01\x00\x09" + b"\0" * 56)
        )


class TrackpadTranslatorTests(unittest.TestCase):
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

    def test_maps_triggers_to_mouse_buttons_and_releases_on_stop(self):
        translator = TrackpadTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())

        pressed = translator.translate(
            trackpad_state(left_trigger=True, right_trigger=True)
        )
        released = translator.set_active(False)

        self.assertEqual(
            pressed,
            PointerUpdate(left_button=True, right_button=True),
        )
        self.assertEqual(
            released,
            PointerUpdate(left_button=False, right_button=False),
        )

    def test_maps_right_pad_press_to_left_mouse_button(self):
        translator = TrackpadTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())

        pressed = translator.translate(trackpad_state(right_pressed=True))
        released = translator.translate(trackpad_state())

        self.assertEqual(pressed, PointerUpdate(left_button=True))
        self.assertEqual(released, PointerUpdate(left_button=False))

    def test_maps_right_pad_pressure_to_left_mouse_button_with_hysteresis(self):
        translator = TrackpadTranslator()
        translator.set_active(True)
        translator.translate(
            trackpad_state(right_touched=True, right_pressure=500)
        )

        pressed = translator.translate(
            trackpad_state(right_touched=True, right_pressure=2_100)
        )
        held = translator.translate(
            trackpad_state(right_touched=True, right_pressure=1_500)
        )
        released = translator.translate(
            trackpad_state(right_touched=True, right_pressure=900)
        )

        self.assertEqual(pressed, PointerUpdate(left_button=True))
        self.assertEqual(held, PointerUpdate())
        self.assertEqual(released, PointerUpdate(left_button=False))

    def test_does_not_click_when_pressure_is_already_high_on_activation(self):
        translator = TrackpadTranslator()
        pressed = trackpad_state(
            right_touched=True,
            right_pressure=3_000,
        )
        translator.translate(pressed)
        translator.set_active(True)

        held = translator.translate(pressed)
        released = translator.translate(trackpad_state())

        self.assertEqual(held, PointerUpdate())
        self.assertEqual(released, PointerUpdate())

    def test_keeps_left_mouse_button_held_across_both_click_sources(self):
        translator = TrackpadTranslator()
        translator.set_active(True)
        translator.translate(trackpad_state())

        pad_pressed = translator.translate(
            trackpad_state(right_pressed=True)
        )
        trigger_pressed = translator.translate(
            trackpad_state(right_pressed=True, right_trigger=True)
        )
        pad_released = translator.translate(
            trackpad_state(right_trigger=True)
        )
        trigger_released = translator.translate(trackpad_state())

        self.assertEqual(pad_pressed, PointerUpdate(left_button=True))
        self.assertEqual(trigger_pressed, PointerUpdate())
        self.assertEqual(pad_released, PointerUpdate())
        self.assertEqual(trigger_released, PointerUpdate(left_button=False))

    def test_does_not_press_if_triggers_were_already_held_on_activation(self):
        translator = TrackpadTranslator()
        translator.translate(
            trackpad_state(left_trigger=True, right_trigger=True)
        )
        translator.set_active(True)

        held = translator.translate(
            trackpad_state(left_trigger=True, right_trigger=True)
        )
        released = translator.translate(trackpad_state())

        self.assertEqual(held, PointerUpdate())
        self.assertEqual(released, PointerUpdate())

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
            trackpad_state(left_touched=True, left_y=130)
        )
        first_inertia = translator.translate(trackpad_state())
        updates = [
            translator.translate(trackpad_state())
            for _ in range(80)
        ]

        self.assertEqual(scrolled, PointerUpdate(scroll_y=-3))
        self.assertAlmostEqual(first_inertia.scroll_y, -1.65)
        self.assertTrue(any(update.scroll_y for update in updates))
        self.assertTrue(any(update.scroll_stop_y for update in updates))
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

    def test_idle_frames_can_be_skipped_after_initial_sync(self):
        translator = TrackpadTranslator()
        translator.set_active(True)

        self.assertTrue(translator.needs_idle_tick)
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
            trackpad_state(left_touched=True, left_y=130)
        )
        translator.translate(trackpad_state())

        caught = translator.translate(
            trackpad_state(left_touched=True, left_y=130)
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
    def test_decodes_gamescope_packed_display(self):
        self.assertEqual(decode_gamescope_display(packed_display(":1")), ":1")

    def test_forwards_only_when_nested_desktop_is_frontmost_with_an_app(self):
        nested_app = 3_058_091_282
        self.assertTrue(
            should_forward_pointer(
                nested_app,
                [nested_app],
                [nested_app],
                [769, nested_app, 632360],
                packed_display(":1"),
            )
        )
        self.assertFalse(
            should_forward_pointer(
                nested_app,
                [nested_app],
                [nested_app],
                [769, nested_app],
                packed_display(":1"),
            )
        )
        self.assertFalse(
            should_forward_pointer(
                nested_app,
                [632360],
                [632360],
                [769, nested_app, 632360],
                packed_display(":1"),
            )
        )
        self.assertFalse(
            should_forward_pointer(
                nested_app,
                [nested_app],
                [nested_app],
                [769, nested_app, 632360],
                packed_display(":0"),
            )
        )


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
        self._process(101, 100, ["/bin/sh", "steamos-nested-desktop"])
        self._process(
            102,
            101,
            [
                "/usr/bin/kwin_wayland",
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


if __name__ == "__main__":
    unittest.main()
