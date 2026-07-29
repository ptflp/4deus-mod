from pathlib import Path
import os
import struct
import tempfile
import threading
import unittest

from nested_desktop_mouse import (
    BACK_BUTTON,
    ACTION_MOUSE_LEFT,
    ACTION_MOUSE_MIDDLE,
    ACTION_MOUSE_RIGHT,
    ACTION_SHOW_KEYBOARD,
    BindingUpdate,
    BUTTON_SOURCE_MASKS,
    DEFAULT_NESTED_DESKTOP_BINDINGS,
    EIS_KEY_CODES,
    InputBindingTranslator,
    LEFT_PAD_TOUCHED,
    LEFT_TRIGGER,
    PointerUpdate,
    RIGHT_PAD_TOUCHED,
    RIGHT_PAD_PRESSED,
    RIGHT_TRIGGER,
    TrackpadState,
    TrackpadTranslator,
    NestedDesktopMouseRuntime,
    decode_gamescope_display,
    find_nested_desktop_session,
    find_steam_deck_hidraw,
    parse_trackpad_report,
    should_forward_back_button,
    should_forward_pointer,
)


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


class RuntimeSuspensionTests(unittest.TestCase):
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
