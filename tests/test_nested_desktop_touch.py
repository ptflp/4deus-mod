from pathlib import Path
import os
import struct
import tempfile
import threading
import unittest

from fourdeus_backend.nested_desktop.constants import (
    LINUX_ABS_MT_POSITION_X,
    LINUX_ABS_MT_POSITION_Y,
    LINUX_ABS_MT_SLOT,
    LINUX_ABS_MT_TRACKING_ID,
    LINUX_EV_ABS,
    LINUX_EV_SYN,
    LINUX_SYN_REPORT,
)
from fourdeus_backend.nested_desktop.discovery import (
    find_steam_deck_touchscreen,
)
from fourdeus_backend.nested_desktop.eis import EisConnection
from fourdeus_backend.nested_desktop.models import (
    LinuxInputEvent,
    NestedDesktopSession,
    TouchFrame,
    TouchUpdate,
)
from fourdeus_backend.nested_desktop.runtime import (
    NestedDesktopMouseRuntime,
)
from fourdeus_backend.nested_desktop.touch import (
    TouchscreenInertia,
    TouchscreenInertiaConfig,
    TouchscreenParser,
    TouchscreenReader,
)


def event(event_type: int, code: int, value: int) -> LinuxInputEvent:
    return LinuxInputEvent(event_type, code, value)


def packed_display(value: str) -> list[int]:
    encoded = value.encode("ascii") + b"\0"
    encoded += b"\0" * ((4 - len(encoded) % 4) % 4)
    return [
        int.from_bytes(encoded[index : index + 4], "little")
        for index in range(0, len(encoded), 4)
    ]


class TouchscreenParserTests(unittest.TestCase):
    def test_rotates_portrait_panel_coordinates_into_landscape(self):
        parser = TouchscreenParser((0, 800), (0, 1280))
        frames = []
        for item in (
            event(LINUX_EV_ABS, LINUX_ABS_MT_TRACKING_ID, 41),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_X, 800),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_Y, 0),
            event(LINUX_EV_SYN, LINUX_SYN_REPORT, 0),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_X, 400),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_Y, 640),
            event(LINUX_EV_SYN, LINUX_SYN_REPORT, 0),
            event(LINUX_EV_ABS, LINUX_ABS_MT_TRACKING_ID, -1),
            event(LINUX_EV_SYN, LINUX_SYN_REPORT, 0),
        ):
            frame = parser.feed(item)
            if frame:
                frames.append(frame)

        self.assertEqual(
            frames,
            [
                (TouchUpdate(41, "down", 0.0, 0.0),),
                (TouchUpdate(41, "motion", 0.5, 0.5),),
                (TouchUpdate(41, "up"),),
            ],
        )

    def test_preserves_independent_multitouch_slots(self):
        parser = TouchscreenParser((0, 800), (0, 1280))
        for item in (
            event(LINUX_EV_ABS, LINUX_ABS_MT_SLOT, 0),
            event(LINUX_EV_ABS, LINUX_ABS_MT_TRACKING_ID, 10),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_X, 800),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_Y, 0),
            event(LINUX_EV_ABS, LINUX_ABS_MT_SLOT, 1),
            event(LINUX_EV_ABS, LINUX_ABS_MT_TRACKING_ID, 11),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_X, 0),
            event(LINUX_EV_ABS, LINUX_ABS_MT_POSITION_Y, 1280),
        ):
            self.assertIsNone(parser.feed(item))

        frame = parser.feed(event(LINUX_EV_SYN, LINUX_SYN_REPORT, 0))

        self.assertEqual(
            frame,
            (
                TouchUpdate(10, "down", 0.0, 0.0),
                TouchUpdate(11, "down", 1.0, 1.0),
            ),
        )

    def test_reader_groups_kernel_records_by_syn_frame(self):
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        reader = TouchscreenReader(
            read_fd,
            x_bounds=(0, 800),
            y_bounds=(0, 1280),
        )
        try:
            records = (
                (LINUX_EV_ABS, LINUX_ABS_MT_TRACKING_ID, 7),
                (LINUX_EV_ABS, LINUX_ABS_MT_POSITION_X, 400),
                (LINUX_EV_ABS, LINUX_ABS_MT_POSITION_Y, 640),
                (LINUX_EV_SYN, LINUX_SYN_REPORT, 0),
            )
            os.write(
                write_fd,
                b"".join(
                    struct.pack("@llHHi", 0, 0, *record)
                    for record in records
                ),
            )

            self.assertEqual(
                reader.read_frames(),
                (
                    TouchFrame(
                        0.0,
                        (TouchUpdate(7, "down", 0.5, 0.5),),
                    ),
                ),
            )
        finally:
            os.close(write_fd)
            reader.close()


class TouchscreenDiscoveryTests(unittest.TestCase):
    def test_selects_only_the_direct_steam_deck_touchscreen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number, name in (
                (3, "FTS3528:00 2808:1015 UNKNOWN"),
                (7, "FTS3528:00 2808:1015"),
            ):
                device = root / "sys" / f"event{number}" / "device"
                device.mkdir(parents=True)
                (device / "name").write_text(name, encoding="utf-8")

            self.assertEqual(
                find_steam_deck_touchscreen(
                    root / "sys",
                    root / "dev",
                ),
                root / "dev" / "event7",
            )


class TouchscreenRuntimeTests(unittest.TestCase):
    def test_focus_and_keyboard_visibility_gate_touch_forwarding(self):
        class Reader:
            fd = 7

            @staticmethod
            def close():
                pass

        class InnerEis:
            touch_ready = True
            absolute_emulating = False

            def __init__(self):
                self.transitions = []

            @staticmethod
            def dispatch():
                pass

            def set_touch_emulating(self, active):
                self.transitions.append(active)
                return True

            @staticmethod
            def close():
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

        runtime = NestedDesktopMouseRuntime(
            threading.Event(),
            mouse_enabled=False,
            bindings_enabled=False,
            rustdesk_pointer_fix_enabled=False,
        )
        runtime.touchscreen_reader = Reader()
        runtime.inner_eis = InnerEis()
        runtime.outer_x11 = OuterX11()
        runtime.session = NestedDesktopSession(
            pid=1,
            app_id=2,
            display=":2",
            xauthority=Path("/tmp/xauth"),
            dbus_address="unix:path=/tmp/dbus",
        )

        runtime._refresh_forwarding()
        self.assertTrue(runtime.touch_forwarding)

        runtime.set_suspended(True)
        self.assertFalse(runtime.touch_forwarding)
        self.assertEqual(runtime.inner_eis.transitions, [True, False])

    def test_runtime_drains_but_injects_only_when_forwarding(self):
        updates = (TouchUpdate(1, "down", 0.25, 0.75),)
        frames = (TouchFrame(1.0, updates),)

        class Reader:
            fd = 7

            def __init__(self):
                self.reads = 0

            def read_frames(self):
                self.reads += 1
                return frames

            @staticmethod
            def close():
                pass

        class InnerEis:
            def __init__(self):
                self.frames = []

            def inject_touch(self, frame):
                self.frames.append(frame)

        runtime = NestedDesktopMouseRuntime(threading.Event())
        reader = Reader()
        runtime.touchscreen_reader = reader
        runtime.inner_eis = InnerEis()

        runtime._read_touchscreen_events()
        runtime.touch_forwarding = True
        runtime._read_touchscreen_events()

        self.assertEqual(reader.reads, 2)
        self.assertEqual(runtime.inner_eis.frames, [updates])


class TouchscreenInertiaTests(unittest.TestCase):
    @staticmethod
    def frame(
        timestamp: float,
        *updates: TouchUpdate,
    ) -> TouchFrame:
        return TouchFrame(timestamp, updates)

    def fast_swipe(self, inertia: TouchscreenInertia, now: float = 10.0):
        for frame in (
            self.frame(1.0, TouchUpdate(4, "down", 0.5, 0.85)),
            self.frame(1.016, TouchUpdate(4, "motion", 0.5, 0.76)),
            self.frame(1.032, TouchUpdate(4, "motion", 0.5, 0.66)),
        ):
            self.assertTrue(inertia.process(frame, now))
        return inertia.process(
            self.frame(1.04, TouchUpdate(4, "up")),
            now,
        )

    def test_fast_single_swipe_decays_before_releasing_contact(self):
        inertia = TouchscreenInertia()

        released = self.fast_swipe(inertia)

        self.assertEqual(released, ())
        self.assertTrue(inertia.active)
        positions = []
        final = ()
        now = 10.0
        for _ in range(120):
            now += 1 / 60
            update = inertia.tick(now)
            if update and update[0].phase == "motion":
                positions.append(update[0].y)
            if update and update[0].phase == "up":
                final = update
                break
        self.assertGreater(len(positions), 2)
        self.assertTrue(all(
            current < previous
            for previous, current in zip(positions, positions[1:])
        ))
        self.assertEqual(final, (TouchUpdate(4, "up"),))
        self.assertFalse(inertia.active)

    def test_tap_and_slow_release_never_start_inertia(self):
        inertia = TouchscreenInertia()
        inertia.process(
            self.frame(1.0, TouchUpdate(1, "down", 0.4, 0.4)),
            5.0,
        )
        tap_up = inertia.process(
            self.frame(1.04, TouchUpdate(1, "up")),
            5.04,
        )
        self.assertEqual(tap_up, ((TouchUpdate(1, "up"),),))

        for frame in (
            self.frame(2.0, TouchUpdate(2, "down", 0.5, 0.8)),
            self.frame(2.2, TouchUpdate(2, "motion", 0.5, 0.7)),
            self.frame(2.4, TouchUpdate(2, "motion", 0.5, 0.6)),
        ):
            inertia.process(frame, 6.0)
        slow_up = inertia.process(
            self.frame(2.6, TouchUpdate(2, "up")),
            6.6,
        )

        self.assertEqual(slow_up, ((TouchUpdate(2, "up"),),))
        self.assertFalse(inertia.active)

    def test_multitouch_and_reversed_path_do_not_coast(self):
        inertia = TouchscreenInertia()
        frames = (
            self.frame(1.0, TouchUpdate(1, "down", 0.2, 0.8)),
            self.frame(1.01, TouchUpdate(2, "down", 0.8, 0.8)),
            self.frame(
                1.02,
                TouchUpdate(1, "motion", 0.2, 0.6),
                TouchUpdate(2, "motion", 0.8, 0.6),
            ),
            self.frame(1.03, TouchUpdate(2, "up")),
            self.frame(1.04, TouchUpdate(1, "up")),
        )
        for frame in frames:
            output = inertia.process(frame, 8.0)
        self.assertEqual(output, ((TouchUpdate(1, "up"),),))
        self.assertFalse(inertia.active)

        for frame in (
            self.frame(2.0, TouchUpdate(3, "down", 0.5, 0.8)),
            self.frame(2.016, TouchUpdate(3, "motion", 0.5, 0.5)),
            self.frame(2.032, TouchUpdate(3, "motion", 0.5, 0.72)),
        ):
            inertia.process(frame, 9.0)
        output = inertia.process(
            self.frame(2.04, TouchUpdate(3, "up")),
            9.04,
        )
        self.assertEqual(output, ((TouchUpdate(3, "up"),),))

    def test_new_contact_cancels_active_coasting_before_its_down(self):
        inertia = TouchscreenInertia()
        self.fast_swipe(inertia)

        output = inertia.process(
            self.frame(2.0, TouchUpdate(8, "down", 0.2, 0.2)),
            10.02,
        )

        self.assertEqual(
            output,
            (
                (TouchUpdate(4, "up"),),
                (TouchUpdate(8, "down", 0.2, 0.2),),
            ),
        )
        self.assertFalse(inertia.active)

    def test_advanced_values_are_clamped_on_load_and_rejected_on_input(self):
        config = TouchscreenInertiaConfig.from_mapping(
            {
                "durationMs": 9_999,
                "startSpeed": -1,
                "minDistance": "44",
            }
        )
        self.assertEqual(config.duration_ms, 1_200)
        self.assertEqual(config.start_speed, 180)
        self.assertEqual(config.min_distance, 44)

        with self.assertRaises(ValueError):
            TouchscreenInertiaConfig.from_user_values(100, 420, 36)


class EisTouchInjectionTests(unittest.TestCase):
    def test_maps_normalized_contacts_to_the_eis_region(self):
        class Lib:
            def __init__(self):
                self.calls = []
                self.next_touch = 0

            def ei_device_touch_new(self, _device):
                self.next_touch += 1
                return self.next_touch

            def ei_touch_down(self, touch, x, y):
                self.calls.append(("down", touch, x, y))

            def ei_touch_motion(self, touch, x, y):
                self.calls.append(("motion", touch, x, y))

            def ei_touch_up(self, touch):
                self.calls.append(("up", touch))

            def ei_touch_unref(self, touch):
                self.calls.append(("unref", touch))

            def ei_device_frame(self, device, timestamp):
                self.calls.append(("frame", device, timestamp))

            @staticmethod
            def ei_now(_ei):
                return 123

            def ei_dispatch(self, _ei):
                self.calls.append(("dispatch",))

        connection = object.__new__(EisConnection)
        connection.lib = Lib()
        connection.ei = 1
        connection.touch_device = 2
        connection.touch_ready = True
        connection.touch_emulating = True
        connection.active_touches = {}
        connection.touch_bounds = lambda: (10, 20, 1280, 800)

        connection.inject_touch(
            (
                TouchUpdate(9, "down", 1.0, 1.0),
                TouchUpdate(9, "motion", 0.5, 0.5),
            )
        )
        connection.inject_touch((TouchUpdate(9, "up"),))

        self.assertIn(("down", 1, 1289.0, 819.0), connection.lib.calls)
        self.assertIn(("motion", 1, 649.5, 419.5), connection.lib.calls)
        self.assertIn(("up", 1), connection.lib.calls)
        self.assertEqual(connection.active_touches, {})


if __name__ == "__main__":
    unittest.main()
