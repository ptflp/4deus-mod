from pathlib import Path
import json
import os
import socket
import struct
import tempfile
import threading
import unittest

from nested_desktop_mouse import (
    BACK_BUTTON,
    ACTION_HIDE_KEYBOARD,
    ACTION_MOUSE_LEFT,
    ACTION_MOUSE_MIDDLE,
    ACTION_MOUSE_RIGHT,
    ACTION_SHOW_KEYBOARD,
    BindingUpdate,
    BUTTON_SOURCE_MASKS,
    CursorSnapshot,
    DEFAULT_NESTED_DESKTOP_BINDINGS,
    EIS_KEY_CODES,
    IDLE_INPUT_FRAME_INTERVAL,
    INPUT_FRAME_INTERVAL,
    InputBindingTranslator,
    LEFT_PAD_TOUCHED,
    LEFT_TRIGGER,
    JoystickEvent,
    LinuxInputEvent,
    NestedDesktopCursorOverlay,
    NestedDesktopSession,
    PointerUpdate,
    RIGHT_PAD_TOUCHED,
    RIGHT_PAD_PRESSED,
    RIGHT_TRIGGER,
    TrackpadState,
    TrackpadTranslator,
    NestedDesktopMouseRuntime,
    RustDeskMouseTranslator,
    RustDeskRelayTranslator,
    RustDeskScrollInertia,
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
    query_rustdesk_video_connection_count,
    receive_rustdesk_ipc_frame,
    remove_nested_wayland_alias,
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
                    "GAMESCOPE_FOCUSABLE_APPS": [769, 22],
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

    def test_visible_cursor_overlay_does_not_follow_stale_xfixes_position(self):
        calls = []
        overlay = NestedDesktopCursorOverlay.__new__(
            NestedDesktopCursorOverlay
        )
        overlay.visible = True
        overlay.refresh = lambda **options: calls.append(options)

        overlay.show()

        self.assertEqual(calls, [{"sync_position": False}])

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
                    "GAMESCOPE_FOCUSABLE_APPS": [769, 2, 3],
                }[name]

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_connection_query=lambda _path: 1,
            cursor_overlay_factory=CursorOverlay,
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
                    "GAMESCOPE_FOCUSABLE_APPS": [769, 2, 3],
                }[name]

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            mouse_enabled=False,
            rustdesk_pointer_fix_enabled=False,
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

    def test_mouse_bindings_follow_parallel_pointer_detector(self):
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
            focusable_apps = [769, 2]

            @classmethod
            def cardinals(cls, name):
                return {
                    "GAMESCOPE_FOCUSED_APP": [2],
                    "GAMESCOPE_FOCUSED_APP_GFX": [2],
                    "GAMESCOPE_MOUSE_FOCUS_DISPLAY": packed_display(":1"),
                    "GAMESCOPE_FOCUSABLE_APPS": cls.focusable_apps,
                }[name]

        overlays = []

        class CursorOverlay:
            def __init__(self, _session):
                self.primed = 0
                self.shown = 0
                self.hidden = 0
                self.closed = 0
                self.updates = []
                overlays.append(self)

            def prime(self):
                self.primed += 1

            def show(self):
                self.shown += 1

            def hide(self):
                self.hidden += 1

            def apply(self, update):
                self.updates.append(update)

            def close(self):
                self.closed += 1

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            rustdesk_pointer_fix_enabled=False,
            cursor_overlay_factory=CursorOverlay,
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
        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0].primed, 1)
        self.assertEqual(overlays[0].shown, 0)

        OuterX11.focusable_apps = [769, 2, 3]
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

        OuterX11.focusable_apps = [769, 2]
        runtime._refresh_forwarding()

        self.assertTrue(runtime.binding_forwarding)
        self.assertFalse(runtime.binding_pointer_forwarding)
        self.assertFalse(runtime.forwarding)
        self.assertTrue(inner_eis.keyboard_emulating)
        self.assertFalse(inner_eis.emulating)
        self.assertFalse(runtime.cursor_overlay_active)
        self.assertEqual(overlays[0].hidden, 1)
        self.assertEqual(overlays[0].primed, 2)

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
                    "GAMESCOPE_FOCUSABLE_APPS": [769, 2],
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
