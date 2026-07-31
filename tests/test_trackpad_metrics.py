import json
import os
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import patch

import trackpad_metrics


def make_report(
    *,
    left_touched=False,
    left_pressed=False,
    left_pressure=0,
    left_x=0,
    left_y=0,
    right_touched=False,
    right_pressed=False,
    right_pressure=0,
    right_x=0,
    right_y=0,
    sequence=0,
):
    report = bytearray(64)
    report[:3] = trackpad_metrics.REPORT_HEADER
    report[4:8] = int(sequence).to_bytes(4, "little")
    controls = 0
    if left_touched:
        controls |= trackpad_metrics.LEFT_PAD_TOUCHED
    if left_pressed:
        controls |= trackpad_metrics.LEFT_PAD_PRESSED
    if right_touched:
        controls |= trackpad_metrics.RIGHT_PAD_TOUCHED
    if right_pressed:
        controls |= trackpad_metrics.RIGHT_PAD_PRESSED
    report[8:16] = controls.to_bytes(8, "little")
    struct.pack_into("<hh", report, 16, left_x, left_y)
    struct.pack_into("<hh", report, 20, right_x, right_y)
    struct.pack_into(
        "<HH",
        report,
        56,
        left_pressure,
        right_pressure,
    )
    return bytes(report)


class TrackpadReportTests(unittest.TestCase):
    def test_parser_reads_both_trackpads(self):
        sample = trackpad_metrics.parse_trackpad_metrics_report(
            make_report(
                left_touched=True,
                left_pressure=1234,
                left_x=-120,
                left_y=345,
                right_touched=True,
                right_pressed=True,
                right_pressure=5678,
                right_x=901,
                right_y=-234,
                sequence=73,
            ),
            42,
        )

        self.assertIsNotNone(sample)
        self.assertEqual(sample.timestamp_ms, 42)
        self.assertEqual(sample.sequence, 73)
        self.assertTrue(sample.left_touched)
        self.assertFalse(sample.left_pressed)
        self.assertEqual(sample.left_pressure, 1234)
        self.assertEqual((sample.left_x, sample.left_y), (-120, 345))
        self.assertTrue(sample.right_touched)
        self.assertTrue(sample.right_pressed)
        self.assertEqual(sample.right_pressure, 5678)
        self.assertEqual((sample.right_x, sample.right_y), (901, -234))

    def test_parser_ignores_other_hid_reports(self):
        self.assertIsNone(
            trackpad_metrics.parse_trackpad_metrics_report(bytes(64), 1)
        )

    def test_reinitialize_rebinds_only_the_physical_hid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            interface = root / "interface"
            raw_device = interface / "0003:28DE:1205.0005"
            physical_device = interface / "0003:28DE:1205.0003"
            driver = root / "drivers" / "hid-steam"
            hidraw = root / "class" / "hidraw" / "hidraw3"
            raw_device.mkdir(parents=True)
            physical_device.mkdir()
            driver.mkdir(parents=True)
            hidraw.mkdir(parents=True)
            (driver / "bind").write_text("", encoding="utf-8")
            (driver / "unbind").write_text("", encoding="utf-8")
            (physical_device / "uevent").write_text(
                "\n".join([
                    f"HID_ID={trackpad_metrics.STEAM_DECK_HID_ID}",
                    "HID_UNIQ=serial",
                ]),
                encoding="utf-8",
            )
            os.symlink(driver, physical_device / "driver")
            os.symlink(raw_device, hidraw / "device")

            recovered = (
                trackpad_metrics.reinitialize_steam_deck_trackpad_driver(
                    Path("/dev/hidraw3"),
                    sys_class_hidraw=root / "class" / "hidraw",
                    device_finder=lambda: Path("/dev/hidraw7"),
                    settle_seconds=0.05,
                    timeout_seconds=0.25,
                )
            )

            self.assertEqual(recovered, Path("/dev/hidraw7"))
            self.assertEqual(
                (driver / "unbind").read_text(encoding="utf-8"),
                physical_device.name,
            )
            self.assertEqual(
                (driver / "bind").read_text(encoding="utf-8"),
                physical_device.name,
            )

    def test_finds_the_builtin_controller_usb_device(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unrelated = root / "1-2"
            controller = root / "1-3"
            unrelated.mkdir()
            controller.mkdir()
            (unrelated / "idVendor").write_text("1234\n", encoding="utf-8")
            (unrelated / "idProduct").write_text("5678\n", encoding="utf-8")
            (unrelated / "authorized").write_text("1\n", encoding="utf-8")
            (controller / "idVendor").write_text("28DE\n", encoding="utf-8")
            (controller / "idProduct").write_text("1205\n", encoding="utf-8")
            (controller / "authorized").write_text("1\n", encoding="utf-8")

            self.assertEqual(
                trackpad_metrics.find_steam_deck_usb_device(root),
                controller,
            )

    def test_reconciliation_restores_usb_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = Path(directory) / "1-3"
            controller.mkdir()
            (controller / "idVendor").write_text("28de\n", encoding="utf-8")
            (controller / "idProduct").write_text("1205\n", encoding="utf-8")
            authorized = controller / "authorized"
            authorized.write_text("0\n", encoding="utf-8")

            restored = (
                trackpad_metrics
                .reconcile_steam_deck_controller_authorization(
                    usb_device_finder=lambda: controller,
                )
            )
            already_enabled = (
                trackpad_metrics
                .reconcile_steam_deck_controller_authorization(
                    usb_device_finder=lambda: controller,
                )
            )

            self.assertTrue(restored)
            self.assertFalse(already_enabled)
            self.assertEqual(authorized.read_text(encoding="utf-8"), "1")

    def test_power_cycle_resolves_usb_parent_from_hidraw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            usb_device = root / "usb" / "1-3"
            raw_device = (
                usb_device
                / "1-3:1.2"
                / "0003:28DE:1205.0005"
            )
            hidraw = root / "class" / "hidraw" / "hidraw3"
            raw_device.mkdir(parents=True)
            hidraw.mkdir(parents=True)
            (usb_device / "idVendor").write_text(
                "28de\n",
                encoding="utf-8",
            )
            (usb_device / "idProduct").write_text(
                "1205\n",
                encoding="utf-8",
            )
            (usb_device / "authorized").write_text("1\n", encoding="utf-8")
            os.symlink(raw_device, hidraw / "device")

            with patch.object(trackpad_metrics.time, "sleep"):
                recovered = (
                    trackpad_metrics.power_cycle_steam_deck_controller(
                        Path("/dev/hidraw3"),
                        sys_class_hidraw=root / "class" / "hidraw",
                        device_finder=lambda: Path("/dev/hidraw7"),
                    )
                )

            self.assertEqual(recovered, Path("/dev/hidraw7"))
            self.assertEqual(
                (usb_device / "authorized").read_text(encoding="utf-8"),
                "1",
            )

    def test_power_cycle_falls_back_to_usb_scan_for_stale_hidraw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            usb_device = root / "usb" / "1-3"
            usb_device.mkdir(parents=True)
            (usb_device / "idVendor").write_text(
                "28de\n",
                encoding="utf-8",
            )
            (usb_device / "idProduct").write_text(
                "1205\n",
                encoding="utf-8",
            )
            (usb_device / "authorized").write_text("1\n", encoding="utf-8")

            with patch.object(trackpad_metrics.time, "sleep"):
                recovered = (
                    trackpad_metrics.power_cycle_steam_deck_controller(
                        Path("/dev/hidraw99"),
                        sys_class_hidraw=root / "class" / "hidraw",
                        sys_bus_usb_devices=root / "usb",
                        device_finder=lambda: Path("/dev/hidraw4"),
                    )
                )

            self.assertEqual(recovered, Path("/dev/hidraw4"))
            self.assertEqual(
                (usb_device / "authorized").read_text(encoding="utf-8"),
                "1",
            )


class TrackpadMetricsMonitorTests(unittest.TestCase):
    def make_monitor(self, directory, **options):
        return trackpad_metrics.TrackpadMetricsMonitor(
            Path(directory),
            device_finder=lambda: None,
            controller_reconciler=lambda: False,
            **options,
        )

    def test_periodic_sampling_and_state_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                retention_seconds=5,
                sample_rate_hz=2,
            )
            idle = make_report()
            touched = make_report(
                right_touched=True,
                right_pressure=300,
            )

            self.assertTrue(
                monitor.record_report(
                    idle,
                    timestamp_ms=1_000,
                    monotonic_time=0,
                )
            )
            self.assertFalse(
                monitor.record_report(
                    idle,
                    timestamp_ms=1_100,
                    monotonic_time=0.1,
                )
            )
            self.assertTrue(
                monitor.record_report(
                    touched,
                    timestamp_ms=1_200,
                    monotonic_time=0.2,
                )
            )
            self.assertTrue(
                monitor.record_report(
                    touched,
                    timestamp_ms=1_700,
                    monotonic_time=0.71,
                )
            )

            window = monitor.window()
            self.assertEqual(window["sampleCount"], 3)
            self.assertEqual(
                [sample["timestampMs"] for sample in window["samples"]],
                [1_000, 1_200, 1_700],
            )

    def test_repeated_idle_reports_use_the_allocation_free_fast_path(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                retention_seconds=5,
                sample_rate_hz=2,
            )

            monitor.record_report(
                make_report(sequence=1),
                timestamp_ms=1_000,
                monotonic_time=0,
            )
            first_sample = monitor.raw_latest

            self.assertFalse(
                monitor.record_report(
                    make_report(sequence=2),
                    timestamp_ms=1_100,
                    monotonic_time=0.1,
                )
            )
            self.assertIs(monitor.raw_latest, first_sample)

            monitor.recovery_enabled = True
            monitor.recovery_armed_at = 0.05
            self.assertFalse(
                monitor.record_report(
                    make_report(sequence=3),
                    timestamp_ms=1_200,
                    monotonic_time=0.2,
                )
            )
            self.assertEqual(monitor.raw_latest.sequence, 3)

    def test_idle_reader_drains_buffered_reports_in_one_wakeup(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            reports = [
                make_report(sequence=1),
                make_report(right_touched=True, sequence=2),
                make_report(sequence=3),
            ]
            with (
                patch.object(
                    trackpad_metrics.os,
                    "read",
                    side_effect=[*reports, BlockingIOError()],
                ),
                patch.object(monitor, "record_report") as record_report,
            ):
                monitor._read_reports(7, drain=True)

            self.assertEqual(
                [call.args[0] for call in record_report.call_args_list],
                reports,
            )

    def test_recovery_only_monitor_uses_deep_idle_batching(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                metrics_enabled=False,
                recovery_enabled=True,
            )
            recovery_interval = (
                trackpad_metrics.RECOVERY_IDLE_REPORT_BATCH_INTERVAL_SECONDS
            )

            self.assertEqual(
                monitor._idle_report_batch_interval(),
                recovery_interval,
            )
            self.assertEqual(
                monitor._idle_report_batch_interval(),
                0.2,
            )

    def test_metrics_monitor_keeps_configured_sample_cadence(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                metrics_enabled=True,
                recovery_enabled=True,
            )

            self.assertEqual(
                monitor._idle_report_batch_interval(),
                trackpad_metrics.IDLE_REPORT_BATCH_INTERVAL_SECONDS,
            )
            self.assertEqual(
                monitor._idle_report_batch_interval(),
                monitor.sample_interval,
            )

    def test_idle_reader_collapses_repeated_control_state(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            reports = [
                make_report(sequence=1),
                make_report(sequence=2),
                make_report(sequence=3),
            ]
            with (
                patch.object(
                    trackpad_metrics.os,
                    "read",
                    side_effect=[*reports, BlockingIOError()],
                ),
                patch.object(monitor, "record_report") as record_report,
            ):
                monitor._read_reports(7, drain=True)

            record_report.assert_called_once_with(reports[-1])

    def test_idle_reader_preserves_pressure_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            reports = [
                make_report(sequence=1),
                make_report(right_pressure=1, sequence=2),
                make_report(sequence=3),
            ]
            with (
                patch.object(
                    trackpad_metrics.os,
                    "read",
                    side_effect=[*reports, BlockingIOError()],
                ),
                patch.object(monitor, "record_report") as record_report,
            ):
                monitor._read_reports(7, drain=True)

            self.assertEqual(
                [call.args[0] for call in record_report.call_args_list],
                reports,
            )

    def test_active_reader_processes_one_report_per_wakeup(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            reports = [
                make_report(right_touched=True, sequence=1),
                make_report(right_touched=True, sequence=2),
            ]
            with (
                patch.object(
                    trackpad_metrics.os,
                    "read",
                    side_effect=reports,
                ) as read,
                patch.object(monitor, "record_report") as record_report,
            ):
                monitor._read_reports(7)

            read.assert_called_once_with(7, 64)
            record_report.assert_called_once_with(reports[0])

    def test_old_samples_are_pruned_by_time(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                retention_seconds=2,
                sample_rate_hz=20,
            )
            monitor.record_report(
                make_report(),
                timestamp_ms=1_000,
                monotonic_time=0,
            )
            monitor.record_report(
                make_report(right_touched=True),
                timestamp_ms=4_000,
                monotonic_time=3,
            )

            window = monitor.window()
            self.assertEqual(window["sampleCount"], 1)
            self.assertEqual(window["samples"][0]["timestampMs"], 4_000)

    def test_manual_capture_survives_live_buffer_clear_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            monitor.record_report(
                make_report(right_touched=True, right_pressure=400),
                timestamp_ms=1_000,
                monotonic_time=0,
            )
            monitor.record_report(
                make_report(right_touched=True, right_pressure=900),
                timestamp_ms=1_100,
                monotonic_time=1,
            )

            summary = monitor.capture()
            capture_id = summary["id"]
            monitor.clear()

            self.assertEqual(monitor.window()["sampleCount"], 0)
            self.assertEqual(
                monitor.window(capture_id)["sampleCount"],
                2,
            )

            restored = self.make_monitor(directory)
            self.assertEqual(
                restored.status()["captures"][0]["id"],
                capture_id,
            )
            self.assertEqual(
                restored.window(capture_id)["sampleCount"],
                2,
            )

            restored.delete_capture(capture_id)
            self.assertEqual(
                [
                    capture
                    for capture in restored.status()["captures"]
                    if capture["reason"]
                    != trackpad_metrics.JOURNAL_REASON
                ],
                [],
            )
            self.assertFalse(
                (Path(directory) / f"{capture_id}.json.gz").exists()
            )

    def test_suspicious_pressure_creates_automatic_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            high_touch = make_report(
                right_touched=True,
                right_pressure=2_500,
            )
            released = make_report()
            monitor.record_report(
                high_touch,
                timestamp_ms=1_000,
                monotonic_time=1,
            )
            monitor.record_report(
                released,
                timestamp_ms=1_100,
                monotonic_time=1.5,
            )
            monitor.record_report(
                high_touch,
                timestamp_ms=1_200,
                monotonic_time=2,
            )

            self.assertEqual(monitor.auto_capture_deadline, 7)
            with patch.object(
                trackpad_metrics.time,
                "monotonic",
                return_value=8,
            ):
                monitor._complete_automatic_capture()

            captures = monitor.status()["captures"]
            self.assertEqual(len(captures), 1)
            self.assertTrue(captures[0]["automatic"])
            self.assertEqual(
                captures[0]["reason"],
                "automatic-high-pressure-touch",
            )

    def test_pressed_touch_start_is_suspicious(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            pressed_touch = make_report(
                right_touched=True,
                right_pressed=True,
                right_pressure=8_000,
            )
            released = make_report()
            monitor.record_report(
                pressed_touch,
                timestamp_ms=1_000,
                monotonic_time=1,
            )
            monitor.record_report(
                released,
                timestamp_ms=1_100,
                monotonic_time=1.5,
            )
            monitor.record_report(
                pressed_touch,
                timestamp_ms=1_200,
                monotonic_time=2,
            )

            self.assertEqual(monitor.auto_capture_deadline, 7)
            self.assertTrue(monitor.journal_flush_requested)

    def test_journal_is_append_only_and_restores_recent_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            now_ms = time.time_ns() // 1_000_000
            monitor.record_report(
                make_report(
                    left_touched=True,
                    left_pressure=300,
                    sequence=10,
                ),
                timestamp_ms=now_ms - 1_000,
                monotonic_time=0,
            )
            monitor._flush_journal()
            journal_path = next(
                (Path(directory) / "rolling").glob("*.jsonl")
            )
            first_write = journal_path.read_bytes()

            monitor.record_report(
                make_report(
                    right_touched=True,
                    right_pressure=400,
                    sequence=20,
                ),
                timestamp_ms=now_ms,
                monotonic_time=1,
            )
            monitor._flush_journal()

            self.assertTrue(
                journal_path.read_bytes().startswith(first_write)
            )
            restored = self.make_monitor(directory)
            restored_samples = restored.window()["samples"]
            self.assertEqual(len(restored_samples), 2)
            self.assertEqual(
                [sample["sequence"] for sample in restored_samples],
                [10, 20],
            )

    def test_journal_rotates_to_three_fifteen_minute_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            window_ms = (
                trackpad_metrics.JOURNAL_WINDOW_SECONDS * 1_000
            )
            now_ms = time.time_ns() // 1_000_000
            base_ms = now_ms // window_ms * window_ms
            for index in range(4):
                monitor.record_report(
                    make_report(
                        right_touched=bool(index % 2),
                        sequence=index,
                    ),
                    timestamp_ms=base_ms + index * window_ms,
                    monotonic_time=index,
                )
                monitor._flush_journal()

            paths = sorted(
                (Path(directory) / "rolling").glob("*.jsonl")
            )
            self.assertEqual(len(paths), 3)
            self.assertNotIn(
                trackpad_metrics.TrackpadMetricsMonitor._journal_id(
                    base_ms
                ),
                [path.stem for path in paths],
            )
            journal_captures = [
                capture
                for capture in monitor.status()["captures"]
                if capture["reason"] == trackpad_metrics.JOURNAL_REASON
            ]
            self.assertEqual(len(journal_captures), 3)

    def test_capture_file_is_compact_json_gzip(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(directory)
            monitor.record_report(
                make_report(left_touched=True, left_pressure=500),
                timestamp_ms=1_000,
                monotonic_time=0,
            )

            summary = monitor.capture()
            capture_path = (
                Path(directory) / f"{summary['id']}.json.gz"
            )
            self.assertTrue(capture_path.exists())
            self.assertFalse(capture_path.read_bytes().startswith(b"{"))
            self.assertEqual(
                json.loads(
                    json.dumps(monitor.window(summary["id"]))
                )["sampleCount"],
                1,
            )

    def test_recovery_ignores_an_ordinary_trackpad_click(self):
        with tempfile.TemporaryDirectory() as directory:
            requests = []
            monitor = self.make_monitor(
                directory,
                recovery_enabled=True,
                recovery_request_callback=(
                    lambda request_id: requests.append(request_id) or True
                ),
            )
            monitor.record_report(
                make_report(
                    right_touched=True,
                    right_pressure=400,
                    right_x=100,
                ),
                monotonic_time=0,
            )
            monitor.record_report(
                make_report(
                    right_touched=True,
                    right_pressed=True,
                    right_pressure=9_000,
                    right_x=110,
                ),
                monotonic_time=0.1,
            )
            monitor.record_report(make_report(), monotonic_time=0.2)
            monitor.record_report(make_report(), monotonic_time=2)

            self.assertEqual(requests, [])
            self.assertFalse(monitor.recovery_status()["armed"])

    def test_recovery_waits_for_both_trackpads_to_be_released(self):
        with tempfile.TemporaryDirectory() as directory:
            requests = []
            monitor = self.make_monitor(
                directory,
                recovery_enabled=True,
                recovery_request_callback=(
                    lambda request_id: requests.append(request_id) or True
                ),
            )
            monitor.record_report(
                make_report(
                    right_touched=True,
                    right_pressure=7_000,
                ),
                monotonic_time=0,
            )
            monitor.record_report(
                make_report(
                    right_touched=True,
                    right_pressure=7_000,
                ),
                monotonic_time=0.76,
            )
            monitor.record_report(
                make_report(
                    left_touched=True,
                    left_pressure=200,
                ),
                monotonic_time=0.8,
            )
            monitor.record_report(
                make_report(
                    left_touched=True,
                    left_pressure=200,
                ),
                monotonic_time=2.6,
            )

            self.assertEqual(requests, [])
            self.assertTrue(monitor.recovery_status()["armed"])

            monitor.record_report(make_report(), monotonic_time=2.7)
            monitor.record_report(make_report(), monotonic_time=3.71)

            self.assertEqual(requests, [1])
            status = monitor.recovery_status()
            self.assertFalse(status["armed"])
            self.assertFalse(status["pending"])
            self.assertEqual(status["successCount"], 1)

    def test_new_touch_restarts_the_safe_idle_countdown(self):
        with tempfile.TemporaryDirectory() as directory:
            requests = []
            monitor = self.make_monitor(
                directory,
                recovery_enabled=True,
                recovery_request_callback=(
                    lambda request_id: requests.append(request_id) or True
                ),
            )
            monitor.record_report(
                make_report(right_touched=True, right_x=0),
                monotonic_time=0,
            )
            monitor.record_report(
                make_report(right_touched=True, right_x=900),
                monotonic_time=0.05,
            )
            monitor.record_report(
                make_report(
                    right_touched=True,
                    right_pressed=True,
                    right_pressure=8_000,
                    right_x=1_050,
                ),
                monotonic_time=0.1,
            )
            monitor.recovery_confirmed = True
            monitor.record_report(make_report(), monotonic_time=0.2)
            monitor.record_report(
                make_report(left_touched=True, left_pressure=100),
                monotonic_time=1,
            )
            monitor.record_report(make_report(), monotonic_time=1.1)
            monitor.record_report(make_report(), monotonic_time=2)

            self.assertEqual(requests, [])

            monitor.record_report(make_report(), monotonic_time=2.11)

            self.assertEqual(requests, [1])

    def test_recovery_has_a_thirty_second_normal_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            requests = []
            monitor = self.make_monitor(
                directory,
                recovery_enabled=True,
                recovery_request_callback=(
                    lambda request_id: requests.append(request_id) or True
                ),
            )

            def confirmed_stuck(start):
                monitor.record_report(
                    make_report(
                        right_touched=True,
                        right_pressure=7_000,
                    ),
                    monotonic_time=start,
                )
                monitor.record_report(
                    make_report(
                        right_touched=True,
                        right_pressure=7_000,
                    ),
                    monotonic_time=start + 0.76,
                )
                monitor.record_report(
                    make_report(),
                    monotonic_time=start + 0.8,
                )
                monitor.record_report(
                    make_report(),
                    monotonic_time=start + 1.81,
                )

            confirmed_stuck(0)
            confirmed_stuck(5)

            self.assertEqual(requests, [1])

            confirmed_stuck(31)

            self.assertEqual(requests, [1, 2])

    def test_recovery_only_mode_does_not_collect_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                metrics_enabled=False,
                recovery_enabled=True,
            )
            monitor.record_report(
                make_report(right_touched=True, right_pressure=500),
                monotonic_time=0,
            )

            self.assertEqual(monitor.window()["sampleCount"], 0)
            self.assertFalse(monitor.status()["running"])

    def test_sustained_abnormal_pressure_triggers_safe_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            requests = []
            monitor = self.make_monitor(
                directory,
                recovery_enabled=True,
                recovery_request_callback=(
                    lambda request_id: requests.append(request_id) or True
                ),
            )
            stuck = make_report(
                right_touched=True,
                right_pressure=7_000,
                right_x=100,
            )
            monitor.record_report(stuck, monotonic_time=0)
            monitor.record_report(stuck, monotonic_time=0.5)

            self.assertFalse(monitor.recovery_status()["armed"])

            monitor.record_report(stuck, monotonic_time=0.76)

            self.assertTrue(monitor.recovery_status()["armed"])
            self.assertTrue(monitor.recovery_confirmed)
            self.assertEqual(requests, [])

            monitor.record_report(make_report(), monotonic_time=0.8)
            monitor.record_report(make_report(), monotonic_time=1.81)

            self.assertEqual(requests, [1])

    def test_physical_press_is_not_mistaken_for_stuck_pressure(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                recovery_enabled=True,
            )
            pressed = make_report(
                right_touched=True,
                right_pressed=True,
                right_pressure=9_000,
                right_x=100,
            )
            monitor.record_report(pressed, monotonic_time=0)
            monitor.record_report(pressed, monotonic_time=2)

            self.assertFalse(monitor.recovery_status()["armed"])

    def test_missing_frontend_result_does_not_block_recovery_forever(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = self.make_monitor(
                directory,
                recovery_enabled=True,
                recovery_request_callback=lambda _request_id: True,
            )
            monitor.recovery_pending_request_id = 4
            monitor.recovery_last_request_at = 10

            with monitor.lock:
                monitor._advance_recovery(
                    10 + trackpad_metrics.RECOVERY_RESULT_TIMEOUT_SECONDS
                )

            status = monitor.recovery_status()
            self.assertFalse(status["pending"])
            self.assertIn("did not confirm", status["error"])


if __name__ == "__main__":
    unittest.main()
