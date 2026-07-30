from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import json
import logging
import os
from pathlib import Path
import select
import struct
import threading
import time
import uuid
from typing import Callable, Sequence


LOGGER = logging.getLogger("4deus-trackpad-metrics")

STEAM_DECK_HID_ID = "0003:000028DE:00001205"
REPORT_HEADER = b"\x01\x00\x09"
REPORT_SEQUENCE_OFFSET = 4
LEFT_PAD_PRESSED = 0x00020000
RIGHT_PAD_PRESSED = 0x00040000
LEFT_PAD_TOUCHED = 0x00080000
RIGHT_PAD_TOUCHED = 0x00100000
TRACKPAD_CONTROL_MASK = (
    LEFT_PAD_PRESSED
    | RIGHT_PAD_PRESSED
    | LEFT_PAD_TOUCHED
    | RIGHT_PAD_TOUCHED
)
LEFT_PAD_X_OFFSET = 16
RIGHT_PAD_X_OFFSET = 20
LEFT_PAD_PRESSURE_OFFSET = 56
RIGHT_PAD_PRESSURE_OFFSET = 58
MIN_REPORT_SIZE = RIGHT_PAD_PRESSURE_OFFSET + 2

DEFAULT_RETENTION_SECONDS = 15 * 60
DEFAULT_SAMPLE_RATE_HZ = 20
MAX_WINDOW_SAMPLES = 1_000
CLICK_PRESSURE_THRESHOLD = 2_000
AUTO_CAPTURE_TOUCHES = 2
AUTO_CAPTURE_WINDOW_SECONDS = 12
AUTO_CAPTURE_DELAY_SECONDS = 5
AUTO_CAPTURE_COOLDOWN_SECONDS = 5 * 60
MAX_AUTOMATIC_CAPTURES = 10
RECOVERY_MOTION_DISTANCE = 800
RECOVERY_MOTION_STEP = 80
RECOVERY_MOTION_CLICK_WINDOW_SECONDS = 0.2
RECOVERY_IDLE_SECONDS = 1.0
RECOVERY_ARM_TIMEOUT_SECONDS = 20
RECOVERY_COOLDOWN_SECONDS = 30
RECOVERY_ABNORMAL_PRESSURE = 6_000
RECOVERY_SUSTAINED_PRESSURE_SECONDS = 0.75
RECOVERY_RESULT_TIMEOUT_SECONDS = 15
MONITOR_MAINTENANCE_INTERVAL_SECONDS = 0.25
IDLE_REPORT_BATCH_INTERVAL_SECONDS = 0.02
MAX_REPORT_BATCH_SIZE = 64
CONTROLLER_RECONCILE_INTERVAL_SECONDS = 5
JOURNAL_FLUSH_INTERVAL_SECONDS = 3 * 60
JOURNAL_WINDOW_SECONDS = 15 * 60
MAX_JOURNAL_WINDOWS = 3
JOURNAL_REASON = "rolling-journal"
JOURNAL_PREFIX = "rolling-"
JOURNAL_SUFFIX = ".jsonl"
CAPTURE_VERSION = 1

_CONTROLLER_USB_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class TrackpadMetricsSample:
    timestamp_ms: int
    sequence: int
    stream_epoch: int
    left_touched: bool
    left_pressed: bool
    left_pressure: int
    left_x: int
    left_y: int
    right_touched: bool
    right_pressed: bool
    right_pressure: int
    right_x: int
    right_y: int
    buttons: int

    def payload(self) -> dict[str, int | bool]:
        return {
            "timestampMs": self.timestamp_ms,
            "sequence": self.sequence,
            "streamEpoch": self.stream_epoch,
            "leftTouched": self.left_touched,
            "leftPressed": self.left_pressed,
            "leftPressure": self.left_pressure,
            "leftX": self.left_x,
            "leftY": self.left_y,
            "rightTouched": self.right_touched,
            "rightPressed": self.right_pressed,
            "rightPressure": self.right_pressure,
            "rightX": self.right_x,
            "rightY": self.right_y,
            "buttons": self.buttons,
        }


@dataclass(frozen=True, slots=True)
class TrackpadCaptureSummary:
    capture_id: str
    created_at_ms: int
    reason: str
    automatic: bool
    sample_count: int
    duration_ms: int
    left_peak_pressure: int
    right_peak_pressure: int

    def payload(self) -> dict[str, int | bool | str]:
        return {
            "id": self.capture_id,
            "createdAtMs": self.created_at_ms,
            "reason": self.reason,
            "automatic": self.automatic,
            "sampleCount": self.sample_count,
            "durationMs": self.duration_ms,
            "leftPeakPressure": self.left_peak_pressure,
            "rightPeakPressure": self.right_peak_pressure,
        }


@dataclass(slots=True)
class _TrackpadGesture:
    touched: bool = False
    pressed: bool = False
    start_x: int = 0
    start_y: int = 0
    last_x: int = 0
    last_y: int = 0
    max_distance_squared: int = 0
    last_motion_at: float = float("-inf")
    abnormal_pressure_since: float | None = None


def find_steam_deck_hidraw(
    sys_class_hidraw: Path = Path("/sys/class/hidraw"),
    dev_root: Path = Path("/dev"),
) -> Path | None:
    try:
        candidates = sorted(sys_class_hidraw.glob("hidraw*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            uevent = (candidate / "device/uevent").read_text(
                encoding="utf-8",
                errors="replace",
            )
            descriptor = (
                candidate / "device/report_descriptor"
            ).read_bytes()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if f"HID_ID={STEAM_DECK_HID_ID}" not in uevent:
            continue
        if not descriptor.startswith(b"\x06\xff\xff"):
            continue
        return dev_root / candidate.name
    return None


def find_steam_deck_usb_device(
    sys_bus_usb_devices: Path = Path("/sys/bus/usb/devices"),
) -> Path | None:
    try:
        candidates = sorted(sys_bus_usb_devices.glob("*"))
    except OSError:
        return None
    for candidate in candidates:
        try:
            vendor = (candidate / "idVendor").read_text(
                encoding="utf-8",
            ).strip().lower()
            product = (candidate / "idProduct").read_text(
                encoding="utf-8",
            ).strip().lower()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if (
            vendor == "28de"
            and product == "1205"
            and (candidate / "authorized").exists()
        ):
            return candidate
    return None


def reconcile_steam_deck_controller_authorization(
    *,
    sys_bus_usb_devices: Path = Path("/sys/bus/usb/devices"),
    usb_device_finder: Callable[[], Path | None] | None = None,
) -> bool:
    with _CONTROLLER_USB_LOCK:
        usb_device = (
            usb_device_finder()
            if usb_device_finder is not None
            else find_steam_deck_usb_device(sys_bus_usb_devices)
        )
        if usb_device is None:
            return False
        authorized_path = usb_device / "authorized"
        if authorized_path.read_text(encoding="utf-8").strip() == "1":
            return False
        authorized_path.write_text("1", encoding="utf-8")
        LOGGER.warning(
            "Restored Steam Deck built-in controller USB authorization at %s",
            usb_device,
        )
        return True


def reinitialize_steam_deck_trackpad_driver(
    device_path: Path | None = None,
    *,
    sys_class_hidraw: Path = Path("/sys/class/hidraw"),
    device_finder: Callable[[], Path | None] = find_steam_deck_hidraw,
    settle_seconds: float = 0.25,
    timeout_seconds: float = 3.0,
) -> Path:
    path = device_path or device_finder()
    if path is None:
        raise RuntimeError("Steam Deck trackpad device was not found")
    raw_device_link = sys_class_hidraw / path.name / "device"
    try:
        raw_device = raw_device_link.resolve(strict=True)
    except (FileNotFoundError, OSError) as error:
        raise RuntimeError(
            f"Unable to resolve the trackpad HID device {path}"
        ) from error

    physical_device = None
    for candidate in raw_device.parent.glob("0003:28DE:1205.*"):
        try:
            uevent = (candidate / "uevent").read_text(
                encoding="utf-8",
                errors="replace",
            )
            driver = (candidate / "driver").resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        unique_id = next(
            (
                line.partition("=")[2]
                for line in uevent.splitlines()
                if line.startswith("HID_UNIQ=")
            ),
            "",
        )
        if (
            f"HID_ID={STEAM_DECK_HID_ID}" in uevent
            and unique_id
            and driver.name == "hid-steam"
        ):
            physical_device = candidate
            break
    if physical_device is None:
        raise RuntimeError(
            "Steam Deck physical controller HID was not found"
        )

    device_id = physical_device.name
    driver_directory = (physical_device / "driver").resolve(strict=True)
    unbind_path = driver_directory / "unbind"
    bind_path = driver_directory / "bind"
    unbound = False
    try:
        unbind_path.write_text(device_id, encoding="utf-8")
        unbound = True
        time.sleep(max(0.05, float(settle_seconds)))
        bind_error = None
        for _attempt in range(3):
            try:
                bind_path.write_text(device_id, encoding="utf-8")
                bind_error = None
                break
            except OSError as error:
                bind_error = error
                time.sleep(0.2)
        if bind_error is not None:
            raise bind_error
        unbound = False
    finally:
        if unbound:
            try:
                bind_path.write_text(device_id, encoding="utf-8")
            except OSError:
                LOGGER.exception(
                    "Failed to restore the Steam Deck HID driver binding"
                )

    deadline = time.monotonic() + max(0.25, float(timeout_seconds))
    while time.monotonic() < deadline:
        recovered_path = device_finder()
        if recovered_path is not None:
            return recovered_path
        time.sleep(0.1)
    raise RuntimeError(
        "Steam Deck trackpad HID did not return after reinitialization"
    )


def power_cycle_steam_deck_controller(
    device_path: Path | None = None,
    *,
    sys_class_hidraw: Path = Path("/sys/class/hidraw"),
    sys_bus_usb_devices: Path = Path("/sys/bus/usb/devices"),
    device_finder: Callable[[], Path | None] = find_steam_deck_hidraw,
    usb_device_finder: Callable[[], Path | None] | None = None,
    disabled_seconds: float = 0.75,
    timeout_seconds: float = 6.0,
) -> Path:
    path = device_path or device_finder()
    usb_device = None
    if path is not None:
        try:
            raw_device = (
                sys_class_hidraw / path.name / "device"
            ).resolve(strict=True)
        except (FileNotFoundError, OSError):
            raw_device = None
        if raw_device is not None:
            for candidate in (raw_device, *raw_device.parents):
                try:
                    vendor = (candidate / "idVendor").read_text(
                        encoding="utf-8"
                    ).strip().lower()
                    product = (candidate / "idProduct").read_text(
                        encoding="utf-8"
                    ).strip().lower()
                except (FileNotFoundError, OSError):
                    continue
                if vendor == "28de" and product == "1205":
                    usb_device = candidate
                    break
    if usb_device is None:
        usb_device = (
            usb_device_finder()
            if usb_device_finder is not None
            else find_steam_deck_usb_device(sys_bus_usb_devices)
        )
    if usb_device is None:
        raise RuntimeError(
            "Steam Deck built-in controller USB device was not found"
        )

    authorized_path = usb_device / "authorized"
    with _CONTROLLER_USB_LOCK:
        disabled = False
        try:
            authorized_path.write_text("0", encoding="utf-8")
            disabled = True
            time.sleep(max(0.25, float(disabled_seconds)))
        finally:
            if disabled:
                enable_error = None
                for _attempt in range(5):
                    try:
                        authorized_path.write_text("1", encoding="utf-8")
                        enable_error = None
                        disabled = False
                        break
                    except OSError as error:
                        enable_error = error
                        time.sleep(0.2)
                if enable_error is not None:
                    raise RuntimeError(
                        "Failed to re-enable the Steam Deck controller"
                    ) from enable_error

        deadline = time.monotonic() + max(1.0, float(timeout_seconds))
        while time.monotonic() < deadline:
            recovered_path = device_finder()
            if recovered_path is not None:
                return recovered_path
            time.sleep(0.1)
    raise RuntimeError(
        "Steam Deck controller did not return after the USB power cycle"
    )


def parse_trackpad_metrics_report(
    report: bytes,
    timestamp_ms: int,
) -> TrackpadMetricsSample | None:
    if (
        len(report) < MIN_REPORT_SIZE
        or not report.startswith(REPORT_HEADER)
    ):
        return None
    return _parse_trackpad_metrics_report(report, timestamp_ms, 0)


def _parse_trackpad_metrics_report(
    report: bytes,
    timestamp_ms: int,
    stream_epoch: int,
) -> TrackpadMetricsSample:
    buttons = int.from_bytes(report[8:16], "little")
    controls = buttons & 0xFFFFFFFF
    left_x, left_y = struct.unpack_from(
        "<hh",
        report,
        LEFT_PAD_X_OFFSET,
    )
    right_x, right_y = struct.unpack_from(
        "<hh",
        report,
        RIGHT_PAD_X_OFFSET,
    )
    left_pressure, right_pressure = struct.unpack_from(
        "<HH",
        report,
        LEFT_PAD_PRESSURE_OFFSET,
    )
    return TrackpadMetricsSample(
        timestamp_ms=timestamp_ms,
        sequence=int.from_bytes(
            report[
                REPORT_SEQUENCE_OFFSET:REPORT_SEQUENCE_OFFSET + 4
            ],
            "little",
        ),
        stream_epoch=stream_epoch,
        left_touched=bool(controls & LEFT_PAD_TOUCHED),
        left_pressed=bool(controls & LEFT_PAD_PRESSED),
        left_pressure=left_pressure,
        left_x=left_x,
        left_y=left_y,
        right_touched=bool(controls & RIGHT_PAD_TOUCHED),
        right_pressed=bool(controls & RIGHT_PAD_PRESSED),
        right_pressure=right_pressure,
        right_x=right_x,
        right_y=right_y,
        buttons=buttons,
    )


def _report_trackpads_safely_released(report: bytes) -> bool:
    controls = struct.unpack_from("<I", report, 8)[0]
    pressures = struct.unpack_from(
        "<I",
        report,
        LEFT_PAD_PRESSURE_OFFSET,
    )[0]
    return not controls & TRACKPAD_CONTROL_MASK and pressures == 0


def _sample_trackpads_safely_released(
    sample: TrackpadMetricsSample | None,
) -> bool:
    return bool(
        sample is not None
        and not sample.left_touched
        and not sample.left_pressed
        and sample.left_pressure == 0
        and not sample.right_touched
        and not sample.right_pressed
        and sample.right_pressure == 0
    )


def _state_signature(
    sample: TrackpadMetricsSample,
) -> tuple[bool, bool, int, bool, bool, int]:
    return (
        sample.left_touched,
        sample.left_pressed,
        min(2, sample.left_pressure // 1_000),
        sample.right_touched,
        sample.right_pressed,
        min(2, sample.right_pressure // 1_000),
    )


def _downsample(
    samples: Sequence[TrackpadMetricsSample],
    limit: int,
) -> list[TrackpadMetricsSample]:
    if len(samples) <= limit:
        return list(samples)
    if limit <= 1:
        return [samples[-1]]
    last_index = len(samples) - 1
    indexes = {
        round(index * last_index / (limit - 1))
        for index in range(limit)
    }
    return [samples[index] for index in sorted(indexes)]


def _capture_summary(
    capture_id: str,
    created_at_ms: int,
    reason: str,
    automatic: bool,
    samples: Sequence[TrackpadMetricsSample],
) -> TrackpadCaptureSummary:
    duration_ms = (
        samples[-1].timestamp_ms - samples[0].timestamp_ms
        if len(samples) > 1
        else 0
    )
    return TrackpadCaptureSummary(
        capture_id=capture_id,
        created_at_ms=created_at_ms,
        reason=reason,
        automatic=automatic,
        sample_count=len(samples),
        duration_ms=duration_ms,
        left_peak_pressure=max(
            (sample.left_pressure for sample in samples),
            default=0,
        ),
        right_peak_pressure=max(
            (sample.right_pressure for sample in samples),
            default=0,
        ),
    )


class TrackpadMetricsMonitor:
    def __init__(
        self,
        captures_directory: Path,
        *,
        retention_seconds: int = DEFAULT_RETENTION_SECONDS,
        sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
        device_finder: Callable[[], Path | None] = find_steam_deck_hidraw,
        metrics_enabled: bool = True,
        recovery_enabled: bool = False,
        recovery_request_callback: Callable[[int], bool | None] | None = None,
        controller_reconciler: Callable[[], bool] = (
            reconcile_steam_deck_controller_authorization
        ),
    ):
        self.captures_directory = Path(captures_directory)
        self.retention_seconds = max(1, int(retention_seconds))
        self.sample_rate_hz = max(1, int(sample_rate_hz))
        self.sample_interval = 1 / self.sample_rate_hz
        self.capacity = self.retention_seconds * self.sample_rate_hz * 2
        self.device_finder = device_finder
        self.metrics_enabled = bool(metrics_enabled)
        self.recovery_enabled = bool(recovery_enabled)
        self.recovery_request_callback = recovery_request_callback
        self.controller_reconciler = controller_reconciler
        self.live_journal_directory = (
            self.captures_directory / "rolling"
        )
        self.samples: deque[TrackpadMetricsSample] = deque(
            maxlen=self.capacity
        )
        self.pending_journal_samples: deque[
            TrackpadMetricsSample
        ] = deque()
        self.latest: TrackpadMetricsSample | None = None
        self.raw_latest: TrackpadMetricsSample | None = None
        self.device_path: Path | None = None
        self.error: str | None = None
        self.lock = threading.RLock()
        self.journal_io_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.writer_stop_event = threading.Event()
        self.writer_wakeup = threading.Event()
        self.thread: threading.Thread | None = None
        self.writer_thread: threading.Thread | None = None
        self.last_recorded_at = float("-inf")
        self.last_signature: tuple[bool, bool, int, bool, bool, int] | None = (
            None
        )
        self.suspicious_touch_times: deque[float] = deque()
        self.auto_capture_deadline: float | None = None
        self.auto_capture_cooldown_until = 0.0
        self.journal_flush_requested = False
        self.auto_capture_write_requested = False
        self.recovery_gestures = {
            "left": _TrackpadGesture(),
            "right": _TrackpadGesture(),
        }
        self.recovery_armed_at: float | None = None
        self.recovery_armed_pad = ""
        self.recovery_saw_release = False
        self.recovery_confirmed = False
        self.recovery_idle_since: float | None = None
        self.recovery_next_request_id = 1
        self.recovery_pending_request_id: int | None = None
        self.recovery_last_request_at = float("-inf")
        self.recovery_last_attempt_at_ms = 0
        self.recovery_last_success_at_ms = 0
        self.recovery_success_count = 0
        self.recovery_error: str | None = None
        self.capture_summaries = self._load_capture_summaries()
        (
            self.journal_summaries,
            restored_samples,
        ) = self._load_journal_windows()
        self.samples.extend(restored_samples[-self.capacity:])
        if self.samples:
            self.latest = self.samples[-1]
            self.last_signature = _state_signature(self.latest)
        self.stream_epoch = max(
            (sample.stream_epoch for sample in restored_samples),
            default=0,
        )

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            if self.metrics_enabled:
                self._start_writer()
            return
        self.stop_event.clear()
        if self.metrics_enabled:
            self._start_writer()
        self.thread = threading.Thread(
            target=self._run,
            name="4deus-trackpad-metrics",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        thread = self.thread
        if thread is not None:
            thread.join(timeout=2)
        self.thread = None
        self._stop_writer()
        with self.lock:
            self.device_path = None
            self.raw_latest = None
            self._clear_recovery_arm()

    def _start_writer(self):
        writer_thread = self.writer_thread
        if writer_thread is not None and writer_thread.is_alive():
            return
        self.writer_stop_event.clear()
        self.writer_wakeup.clear()
        self.writer_thread = threading.Thread(
            target=self._writer_loop,
            name="4deus-trackpad-metrics-writer",
            daemon=True,
        )
        self.writer_thread.start()

    def _stop_writer(self):
        self.writer_stop_event.set()
        self.writer_wakeup.set()
        writer_thread = self.writer_thread
        if writer_thread is not None:
            writer_thread.join(timeout=5)
        self.writer_thread = None

    def configure(
        self,
        *,
        metrics_enabled: bool,
        recovery_enabled: bool,
    ):
        metrics_enabled = bool(metrics_enabled)
        recovery_enabled = bool(recovery_enabled)
        with self.lock:
            self.metrics_enabled = metrics_enabled
            self.recovery_enabled = recovery_enabled
            if not recovery_enabled:
                self.raw_latest = None
                self._clear_recovery_arm()
        if metrics_enabled or recovery_enabled:
            self.start()
            if not metrics_enabled:
                self._stop_writer()
        else:
            self.stop()

    def running(self) -> bool:
        thread = self.thread
        return bool(thread is not None and thread.is_alive())

    def clear(self):
        self._flush_journal()
        with self.lock:
            self.samples.clear()
            self.latest = None
            self.last_recorded_at = float("-inf")
            self.last_signature = None
            self.suspicious_touch_times.clear()
            self.auto_capture_deadline = None

    def record_report(
        self,
        report: bytes,
        *,
        timestamp_ms: int | None = None,
        monotonic_time: float | None = None,
    ) -> bool:
        if (
            len(report) < MIN_REPORT_SIZE
            or not report.startswith(REPORT_HEADER)
        ):
            return False
        now = time.monotonic() if monotonic_time is None else monotonic_time
        if self._can_skip_repeated_idle_report(report, now):
            return False
        wall_time = (
            time.time_ns() // 1_000_000
            if timestamp_ms is None
            else int(timestamp_ms)
        )
        sample = _parse_trackpad_metrics_report(
            report,
            wall_time,
            self.stream_epoch,
        )
        recovery_request_id = None
        with self.lock:
            raw_previous = self.raw_latest
            self.raw_latest = sample
            changed = False
            due = False
            if self.metrics_enabled:
                signature = _state_signature(sample)
                previous = self.latest
                self.latest = sample
                changed = signature != self.last_signature
                due = now - self.last_recorded_at >= self.sample_interval
                if changed or due:
                    self.samples.append(sample)
                    cutoff = wall_time - self.retention_seconds * 1_000
                    while (
                        self.samples
                        and self.samples[0].timestamp_ms < cutoff
                    ):
                        self.samples.popleft()
                    self.pending_journal_samples.append(sample)
                    self.last_recorded_at = now
                    self.last_signature = signature
                self._observe_suspicious_touch(previous, sample, now)
            if self.recovery_enabled:
                recovery_request_id = self._observe_recovery(
                    raw_previous,
                    sample,
                    now,
                )
        if recovery_request_id is not None:
            self._dispatch_recovery_request(recovery_request_id)
        return changed or due

    def _can_skip_repeated_idle_report(
        self,
        report: bytes,
        now: float,
    ) -> bool:
        if not _report_trackpads_safely_released(report):
            return False
        if not _sample_trackpads_safely_released(self.raw_latest):
            return False
        if self.recovery_enabled and self.recovery_armed_at is not None:
            return False
        return (
            not self.metrics_enabled
            or now - self.last_recorded_at < self.sample_interval
        )

    def status(self) -> dict:
        with self.lock:
            sample_count = len(self.samples)
            retained_ms = (
                self.samples[-1].timestamp_ms
                - self.samples[0].timestamp_ms
                if sample_count > 1
                else 0
            )
            latest = self.latest
            captures = sorted(
                (
                    *self.capture_summaries.values(),
                    *self.journal_summaries.values(),
                ),
                key=lambda summary: summary.created_at_ms,
                reverse=True,
            )
            error = self.error
            device_path = self.device_path
        return {
            "running": self.metrics_enabled and self.running(),
            "devicePath": str(device_path) if device_path else "",
            "sampleCount": sample_count,
            "retainedSeconds": retained_ms / 1_000,
            "capacitySeconds": self.retention_seconds,
            "sampleRateHz": self.sample_rate_hz,
            "latest": latest.payload() if latest is not None else None,
            "captures": [capture.payload() for capture in captures],
            **({"error": error} if error else {}),
        }

    def recovery_status(self) -> dict:
        with self.lock:
            error = self.recovery_error or self.error
            return {
                "enabled": self.recovery_enabled,
                "monitoring": self.recovery_enabled and self.running(),
                "armed": self.recovery_armed_at is not None,
                "pending": self.recovery_pending_request_id is not None,
                "lastAttemptAtMs": self.recovery_last_attempt_at_ms,
                "lastSuccessAtMs": self.recovery_last_success_at_ms,
                "successCount": self.recovery_success_count,
                **({"error": error} if error else {}),
            }

    def report_recovery_result(
        self,
        request_id: int,
        success: bool,
        error: str = "",
    ) -> bool:
        with self.lock:
            if request_id != self.recovery_pending_request_id:
                return False
            self.recovery_pending_request_id = None
            if success:
                self.recovery_success_count += 1
                self.recovery_last_success_at_ms = (
                    time.time_ns() // 1_000_000
                )
                self.recovery_error = None
            else:
                self.recovery_error = (
                    error[:500] if error else "Trackpad recovery failed"
                )
        if success:
            LOGGER.info(
                "Trackpad recovery request %d completed",
                request_id,
            )
        else:
            LOGGER.warning(
                "Trackpad recovery request %d failed: %s",
                request_id,
                error,
            )
        return True

    def window(
        self,
        capture_id: str | None = None,
        max_samples: int = 600,
    ) -> dict:
        limit = max(2, min(MAX_WINDOW_SAMPLES, int(max_samples)))
        if capture_id:
            if self._is_journal_id(capture_id):
                samples = self._read_journal_window(capture_id)
                with self.lock:
                    journal_summary = self.journal_summaries.get(
                        capture_id
                    )
                summary = (
                    journal_summary.payload()
                    if journal_summary is not None
                    else _capture_summary(
                        capture_id,
                        self._journal_start_ms(capture_id),
                        JOURNAL_REASON,
                        True,
                        samples,
                    ).payload()
                )
            else:
                payload = self._read_capture(capture_id)
                samples = [
                    self._sample_from_payload(sample)
                    for sample in payload.get("samples", [])
                ]
                summary = payload.get("summary")
        else:
            with self.lock:
                samples = list(self.samples)
            summary = None
        selected = _downsample(samples, limit)
        return {
            "captureId": capture_id or "",
            "sampleCount": len(samples),
            "samples": [sample.payload() for sample in selected],
            **({"summary": summary} if summary else {}),
        }

    def capture(
        self,
        reason: str = "manual",
        *,
        automatic: bool = False,
    ) -> dict:
        with self.lock:
            samples = list(self.samples)
        if not samples:
            raise RuntimeError("No trackpad metrics are available to capture")
        created_at_ms = time.time_ns() // 1_000_000
        timestamp = datetime.fromtimestamp(
            created_at_ms / 1_000,
            timezone.utc,
        ).strftime("%Y%m%dT%H%M%SZ")
        capture_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
        summary = _capture_summary(
            capture_id,
            created_at_ms,
            reason,
            automatic,
            samples,
        )
        payload = {
            "version": CAPTURE_VERSION,
            "summary": summary.payload(),
            "samples": [sample.payload() for sample in samples],
        }
        self.captures_directory.mkdir(parents=True, exist_ok=True)
        path = self._capture_path(capture_id)
        temporary = path.with_suffix(".tmp")
        with gzip.open(temporary, "wt", encoding="utf-8") as stream:
            json.dump(payload, stream, separators=(",", ":"))
        os.replace(temporary, path)
        with self.lock:
            self.capture_summaries[capture_id] = summary
        if automatic:
            self._prune_automatic_captures()
        return summary.payload()

    def delete_capture(self, capture_id: str):
        if self._is_journal_id(capture_id):
            raise ValueError(
                "Rolling journal windows are rotated automatically"
            )
        path = self._capture_path(capture_id)
        path.unlink(missing_ok=True)
        with self.lock:
            self.capture_summaries.pop(capture_id, None)

    def _run(self):
        descriptor: int | None = None
        next_maintenance_at = 0.0
        next_reconciliation_at = 0.0
        try:
            while not self.stop_event.is_set():
                if descriptor is None:
                    self._reconcile_controller_authorization()
                    path = self.device_finder()
                    if path is None:
                        self._set_device_error(
                            None,
                            "Steam Deck trackpad device was not found",
                        )
                        self.stop_event.wait(1)
                        continue
                    try:
                        descriptor = os.open(
                            path,
                            os.O_RDONLY | os.O_NONBLOCK,
                        )
                        with self.lock:
                            self.stream_epoch += 1
                            stream_epoch = self.stream_epoch
                        self._set_device_error(path, None)
                        LOGGER.info(
                            "Opened Steam Deck trackpad HID stream "
                            "%s (epoch %d)",
                            path,
                            stream_epoch,
                        )
                    except OSError as error:
                        self._set_device_error(path, str(error))
                        self.stop_event.wait(1)
                        continue
                try:
                    batch_idle_reports = (
                        self._should_batch_idle_reports()
                    )
                    if (
                        batch_idle_reports
                        and self.stop_event.wait(
                            IDLE_REPORT_BATCH_INTERVAL_SECONDS
                        )
                    ):
                        break
                    readable, _, _ = select.select(
                        [descriptor],
                        [],
                        [],
                        0 if batch_idle_reports else 0.25,
                    )
                    if readable:
                        self._read_reports(
                            descriptor,
                            drain=batch_idle_reports,
                        )
                    now = time.monotonic()
                    if now >= next_reconciliation_at:
                        self._reconcile_controller_authorization()
                        next_reconciliation_at = (
                            now + CONTROLLER_RECONCILE_INTERVAL_SECONDS
                        )
                    if now >= next_maintenance_at:
                        self._complete_automatic_capture()
                        recovery_request_id = None
                        with self.lock:
                            if self.recovery_enabled:
                                recovery_request_id = (
                                    self._advance_recovery(now)
                                )
                        if recovery_request_id is not None:
                            self._dispatch_recovery_request(
                                recovery_request_id
                            )
                        next_maintenance_at = (
                            now + MONITOR_MAINTENANCE_INTERVAL_SECONDS
                        )
                except (OSError, ValueError) as error:
                    self._set_device_error(None, str(error))
                    os.close(descriptor)
                    descriptor = None
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            self._set_device_error(None, self.error)

    def _reconcile_controller_authorization(self) -> bool:
        try:
            return bool(self.controller_reconciler())
        except Exception:
            LOGGER.exception(
                "Failed to reconcile Steam Deck controller authorization"
            )
            return False

    def _should_batch_idle_reports(self) -> bool:
        return _sample_trackpads_safely_released(self.raw_latest)

    def _read_reports(self, descriptor: int, *, drain: bool = False):
        for _ in range(MAX_REPORT_BATCH_SIZE):
            try:
                report = os.read(descriptor, 64)
            except BlockingIOError:
                return
            if not report:
                raise OSError("Steam Deck trackpad device closed")
            self.record_report(report)
            if not drain:
                return

    def _writer_loop(self):
        last_periodic_flush = time.monotonic()
        while not self.writer_stop_event.is_set():
            elapsed = time.monotonic() - last_periodic_flush
            timeout = max(
                0.1,
                JOURNAL_FLUSH_INTERVAL_SECONDS - elapsed,
            )
            self.writer_wakeup.wait(timeout)
            self.writer_wakeup.clear()
            now = time.monotonic()
            with self.lock:
                flush_requested = self.journal_flush_requested
                self.journal_flush_requested = False
                capture_requested = self.auto_capture_write_requested
                self.auto_capture_write_requested = False
            if (
                flush_requested
                or now - last_periodic_flush
                >= JOURNAL_FLUSH_INTERVAL_SECONDS
            ):
                self._flush_journal()
                last_periodic_flush = now
            if capture_requested:
                self._save_automatic_capture()
        self._flush_journal()
        with self.lock:
            capture_requested = self.auto_capture_write_requested
            self.auto_capture_write_requested = False
        if capture_requested:
            self._save_automatic_capture()

    def _save_automatic_capture(self):
        try:
            self.capture(
                "automatic-high-pressure-touch",
                automatic=True,
            )
            LOGGER.info("Saved an automatic trackpad metrics capture")
        except Exception:
            LOGGER.exception("Failed to save automatic trackpad metrics")

    def _flush_journal(self):
        with self.journal_io_lock:
            with self.lock:
                pending = list(self.pending_journal_samples)
                self.pending_journal_samples.clear()
            if not pending:
                return
            groups: dict[int, list[TrackpadMetricsSample]] = {}
            window_ms = JOURNAL_WINDOW_SECONDS * 1_000
            for sample in pending:
                start_ms = sample.timestamp_ms // window_ms * window_ms
                groups.setdefault(start_ms, []).append(sample)
            ordered_groups = sorted(groups.items())
            for index, (start_ms, samples) in enumerate(ordered_groups):
                try:
                    self._append_journal_window(start_ms, samples)
                except Exception:
                    remaining = [
                        sample
                        for _, group in ordered_groups[index:]
                        for sample in group
                    ]
                    with self.lock:
                        self.pending_journal_samples.extendleft(
                            reversed(remaining)
                        )
                    LOGGER.exception(
                        "Failed to append trackpad metrics journal"
                    )
                    return
            self._prune_journal_windows()

    def _append_journal_window(
        self,
        start_ms: int,
        samples: Sequence[TrackpadMetricsSample],
    ):
        if not samples:
            return
        capture_id = self._journal_id(start_ms)
        path = self._journal_path(capture_id)
        self.live_journal_directory.mkdir(parents=True, exist_ok=True)
        serialized = "".join(
            json.dumps(
                self._journal_sample_payload(sample),
                separators=(",", ":"),
            )
            + "\n"
            for sample in samples
        )
        with path.open("a", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        with self.lock:
            previous = self.journal_summaries.get(capture_id)
            if previous is None:
                summary = _capture_summary(
                    capture_id,
                    start_ms,
                    JOURNAL_REASON,
                    True,
                    samples,
                )
            else:
                summary = TrackpadCaptureSummary(
                    capture_id=capture_id,
                    created_at_ms=start_ms,
                    reason=JOURNAL_REASON,
                    automatic=True,
                    sample_count=previous.sample_count + len(samples),
                    duration_ms=max(
                        previous.duration_ms,
                        samples[-1].timestamp_ms - start_ms,
                    ),
                    left_peak_pressure=max(
                        previous.left_peak_pressure,
                        max(
                            sample.left_pressure for sample in samples
                        ),
                    ),
                    right_peak_pressure=max(
                        previous.right_peak_pressure,
                        max(
                            sample.right_pressure for sample in samples
                        ),
                    ),
                )
            self.journal_summaries[capture_id] = summary

    def _prune_journal_windows(self):
        paths = sorted(
            self.live_journal_directory.glob(
                f"{JOURNAL_PREFIX}*{JOURNAL_SUFFIX}"
            ),
            key=self._journal_path_start_ms,
            reverse=True,
        )
        for path in paths[MAX_JOURNAL_WINDOWS:]:
            capture_id = path.name.removesuffix(JOURNAL_SUFFIX)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                LOGGER.exception(
                    "Failed to rotate trackpad metrics journal %s",
                    path,
                )
                continue
            with self.lock:
                self.journal_summaries.pop(capture_id, None)

    def _observe_suspicious_touch(
        self,
        previous: TrackpadMetricsSample | None,
        sample: TrackpadMetricsSample,
        now: float,
    ):
        suspicious = (
            (
                sample.left_touched
                and not (previous and previous.left_touched)
                and (
                    sample.left_pressed
                    or sample.left_pressure >= CLICK_PRESSURE_THRESHOLD
                )
            )
            or (
                sample.right_touched
                and not (previous and previous.right_touched)
                and (
                    sample.right_pressed
                    or sample.right_pressure >= CLICK_PRESSURE_THRESHOLD
                )
            )
            or (
                not sample.left_touched
                and (sample.left_pressed or sample.left_pressure > 0)
            )
            or (
                not sample.right_touched
                and (sample.right_pressed or sample.right_pressure > 0)
            )
        )
        if not suspicious:
            return
        self.journal_flush_requested = True
        self.writer_wakeup.set()
        if now < self.auto_capture_cooldown_until:
            return
        self.suspicious_touch_times.append(now)
        while (
            self.suspicious_touch_times
            and now - self.suspicious_touch_times[0]
            > AUTO_CAPTURE_WINDOW_SECONDS
        ):
            self.suspicious_touch_times.popleft()
        if len(self.suspicious_touch_times) < AUTO_CAPTURE_TOUCHES:
            return
        self.suspicious_touch_times.clear()
        self.auto_capture_deadline = now + AUTO_CAPTURE_DELAY_SECONDS
        self.auto_capture_cooldown_until = (
            now + AUTO_CAPTURE_COOLDOWN_SECONDS
        )

    def _observe_recovery(
        self,
        previous: TrackpadMetricsSample | None,
        sample: TrackpadMetricsSample,
        now: float,
    ) -> int | None:
        if (
            self.recovery_armed_at is not None
            and now - self.recovery_armed_at
            > RECOVERY_ARM_TIMEOUT_SECONDS
        ):
            self._clear_recovery_arm()

        if self.recovery_saw_release and previous is not None:
            left_started = (
                sample.left_touched and not previous.left_touched
            )
            right_started = (
                sample.right_touched and not previous.right_touched
            )
            if (
                left_started
                and (
                    sample.left_pressed
                    or sample.left_pressure
                    >= RECOVERY_ABNORMAL_PRESSURE
                )
            ) or (
                right_started
                and (
                    sample.right_pressed
                    or sample.right_pressure
                    >= RECOVERY_ABNORMAL_PRESSURE
                )
            ):
                self.recovery_confirmed = True

        left_risky, left_confirmed = self._update_recovery_gesture(
            "left",
            sample.left_touched,
            sample.left_pressed,
            sample.left_pressure,
            sample.left_x,
            sample.left_y,
            now,
        )
        if left_risky or (
            left_confirmed
            and self.recovery_armed_at is None
            and self.recovery_pending_request_id is None
        ):
            self._arm_recovery(
                now,
                "left",
                confirmed=left_confirmed,
            )
        right_risky, right_confirmed = self._update_recovery_gesture(
            "right",
            sample.right_touched,
            sample.right_pressed,
            sample.right_pressure,
            sample.right_x,
            sample.right_y,
            now,
        )
        if right_risky or (
            right_confirmed
            and self.recovery_armed_at is None
            and self.recovery_pending_request_id is None
        ):
            self._arm_recovery(
                now,
                "right",
                confirmed=right_confirmed,
            )
        return self._advance_recovery(now)

    def _update_recovery_gesture(
        self,
        pad_name: str,
        touched: bool,
        pressed: bool,
        pressure: int,
        x: int,
        y: int,
        now: float,
    ) -> tuple[bool, bool]:
        gesture = self.recovery_gestures[pad_name]
        if not touched:
            gesture.touched = False
            gesture.pressed = pressed
            gesture.max_distance_squared = 0
            gesture.last_motion_at = float("-inf")
            gesture.abnormal_pressure_since = None
            return False, False
        if pressed or pressure < RECOVERY_ABNORMAL_PRESSURE:
            gesture.abnormal_pressure_since = None
            confirmed_stuck = False
        elif gesture.abnormal_pressure_since is None:
            gesture.abnormal_pressure_since = now
            confirmed_stuck = False
        else:
            confirmed_stuck = (
                now - gesture.abnormal_pressure_since
                >= RECOVERY_SUSTAINED_PRESSURE_SECONDS
            )
        if not gesture.touched:
            gesture.touched = True
            gesture.pressed = pressed
            gesture.start_x = x
            gesture.start_y = y
            gesture.last_x = x
            gesture.last_y = y
            gesture.max_distance_squared = 0
            gesture.last_motion_at = float("-inf")
            return False, confirmed_stuck

        step_x = x - gesture.last_x
        step_y = y - gesture.last_y
        moving_now = (
            step_x * step_x + step_y * step_y
            >= RECOVERY_MOTION_STEP * RECOVERY_MOTION_STEP
        )
        if moving_now:
            gesture.last_motion_at = now
        distance_x = x - gesture.start_x
        distance_y = y - gesture.start_y
        gesture.max_distance_squared = max(
            gesture.max_distance_squared,
            distance_x * distance_x + distance_y * distance_y,
        )
        moved_enough = (
            gesture.max_distance_squared
            >= RECOVERY_MOTION_DISTANCE * RECOVERY_MOTION_DISTANCE
        )
        pressed_started = pressed and not gesture.pressed
        recent_motion = (
            now - gesture.last_motion_at
            <= RECOVERY_MOTION_CLICK_WINDOW_SECONDS
        )
        risky_click = moved_enough and pressed and (
            (pressed_started and recent_motion)
            or (gesture.pressed and moving_now)
        )
        gesture.touched = True
        gesture.pressed = pressed
        gesture.last_x = x
        gesture.last_y = y
        return risky_click, confirmed_stuck

    def _arm_recovery(
        self,
        now: float,
        pad_name: str,
        *,
        confirmed: bool = False,
    ):
        if self.recovery_pending_request_id is not None:
            return
        if self.recovery_armed_at is None:
            LOGGER.info(
                "Trackpad recovery armed after %s-pad %s",
                pad_name,
                (
                    "sustained abnormal pressure"
                    if confirmed
                    else "swipe and click"
                ),
            )
            self.recovery_armed_at = now
            self.recovery_armed_pad = pad_name
            self.recovery_saw_release = False
            self.recovery_confirmed = confirmed
            self.recovery_idle_since = None
        elif confirmed:
            self.recovery_confirmed = True

    def _advance_recovery(self, now: float) -> int | None:
        if self.recovery_pending_request_id is not None:
            if (
                now - self.recovery_last_request_at
                >= RECOVERY_RESULT_TIMEOUT_SECONDS
            ):
                request_id = self.recovery_pending_request_id
                self.recovery_pending_request_id = None
                self.recovery_error = (
                    "Trackpad recovery did not confirm completion"
                )
                LOGGER.warning(
                    "Trackpad recovery request %d timed out",
                    request_id,
                )
            return None
        if self.recovery_armed_at is None:
            return None
        if (
            now - self.recovery_armed_at
            > RECOVERY_ARM_TIMEOUT_SECONDS
        ):
            self._clear_recovery_arm()
            return None
        if not _sample_trackpads_safely_released(self.raw_latest):
            self.recovery_idle_since = None
            return None
        self.recovery_saw_release = True
        if self.recovery_idle_since is None:
            self.recovery_idle_since = now
            return None
        if now - self.recovery_idle_since < RECOVERY_IDLE_SECONDS:
            return None
        if not self.recovery_confirmed:
            return None
        if (
            now - self.recovery_last_request_at
            < RECOVERY_COOLDOWN_SECONDS
        ):
            return None

        request_id = self.recovery_next_request_id
        self.recovery_next_request_id += 1
        self.recovery_pending_request_id = request_id
        self.recovery_last_request_at = now
        self.recovery_last_attempt_at_ms = time.time_ns() // 1_000_000
        self.recovery_error = None
        self._clear_recovery_arm()
        return request_id

    def _dispatch_recovery_request(self, request_id: int):
        callback = self.recovery_request_callback
        try:
            dispatched = callback(request_id) if callback is not None else False
        except Exception as error:
            LOGGER.exception("Failed to run trackpad recovery")
            self.report_recovery_result(
                request_id,
                False,
                str(error),
            )
            return
        if dispatched is True:
            self.report_recovery_result(request_id, True)
        elif dispatched is False:
            self.report_recovery_result(
                request_id,
                False,
                "Trackpad recovery backend is unavailable",
            )

    def _clear_recovery_arm(self):
        self.recovery_armed_at = None
        self.recovery_armed_pad = ""
        self.recovery_saw_release = False
        self.recovery_confirmed = False
        self.recovery_idle_since = None

    def _complete_automatic_capture(self):
        with self.lock:
            deadline = self.auto_capture_deadline
            if deadline is None or time.monotonic() < deadline:
                return
            self.auto_capture_deadline = None
            writer_running = bool(
                self.writer_thread is not None
                and self.writer_thread.is_alive()
            )
            if not writer_running:
                capture_immediately = True
            else:
                capture_immediately = False
                self.auto_capture_write_requested = True
        if capture_immediately:
            self._save_automatic_capture()
            return
        self.writer_wakeup.set()

    def _set_device_error(
        self,
        device_path: Path | None,
        error: str | None,
    ):
        with self.lock:
            previous_error = self.error
            self.device_path = device_path
            self.error = error
        if error and error != previous_error:
            LOGGER.warning("Trackpad HID stream error: %s", error)

    @staticmethod
    def _journal_id(start_ms: int) -> str:
        return f"{JOURNAL_PREFIX}{start_ms}"

    @staticmethod
    def _is_journal_id(capture_id: str) -> bool:
        if not capture_id.startswith(JOURNAL_PREFIX):
            return False
        value = capture_id.removeprefix(JOURNAL_PREFIX)
        return bool(value) and value.isdigit()

    @classmethod
    def _journal_start_ms(cls, capture_id: str) -> int:
        if not cls._is_journal_id(capture_id):
            raise ValueError("Invalid trackpad metrics journal ID")
        return int(capture_id.removeprefix(JOURNAL_PREFIX))

    def _journal_path(self, capture_id: str) -> Path:
        self._journal_start_ms(capture_id)
        return (
            self.live_journal_directory
            / f"{capture_id}{JOURNAL_SUFFIX}"
        )

    @classmethod
    def _journal_path_start_ms(cls, path: Path) -> int:
        try:
            return cls._journal_start_ms(
                path.name.removesuffix(JOURNAL_SUFFIX)
            )
        except ValueError:
            return -1

    @staticmethod
    def _journal_sample_payload(
        sample: TrackpadMetricsSample,
    ) -> list[int]:
        return [
            sample.timestamp_ms,
            sample.sequence,
            sample.stream_epoch,
            int(sample.left_touched),
            int(sample.left_pressed),
            sample.left_pressure,
            sample.left_x,
            sample.left_y,
            int(sample.right_touched),
            int(sample.right_pressed),
            sample.right_pressure,
            sample.right_x,
            sample.right_y,
            sample.buttons,
        ]

    @staticmethod
    def _sample_from_journal_payload(
        payload: Sequence[int],
    ) -> TrackpadMetricsSample:
        if len(payload) != 14:
            raise ValueError("Invalid trackpad metrics journal record")
        return TrackpadMetricsSample(
            timestamp_ms=int(payload[0]),
            sequence=int(payload[1]),
            stream_epoch=int(payload[2]),
            left_touched=bool(payload[3]),
            left_pressed=bool(payload[4]),
            left_pressure=int(payload[5]),
            left_x=int(payload[6]),
            left_y=int(payload[7]),
            right_touched=bool(payload[8]),
            right_pressed=bool(payload[9]),
            right_pressure=int(payload[10]),
            right_x=int(payload[11]),
            right_y=int(payload[12]),
            buttons=int(payload[13]),
        )

    def _read_journal_path(
        self,
        path: Path,
    ) -> list[TrackpadMetricsSample]:
        samples: list[TrackpadMetricsSample] = []
        try:
            with path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    try:
                        payload = json.loads(line)
                        samples.append(
                            self._sample_from_journal_payload(payload)
                        )
                    except (TypeError, ValueError, json.JSONDecodeError):
                        LOGGER.warning(
                            "Ignoring an invalid trackpad journal record "
                            "in %s",
                            path,
                        )
        except (FileNotFoundError, OSError):
            return []
        unique = {
            (
                sample.timestamp_ms,
                sample.stream_epoch,
                sample.sequence,
            ): sample
            for sample in samples
        }
        return sorted(
            unique.values(),
            key=lambda sample: sample.timestamp_ms,
        )

    def _read_journal_window(
        self,
        capture_id: str,
    ) -> list[TrackpadMetricsSample]:
        return self._read_journal_path(
            self._journal_path(capture_id)
        )

    def _load_journal_windows(
        self,
    ) -> tuple[
        dict[str, TrackpadCaptureSummary],
        list[TrackpadMetricsSample],
    ]:
        try:
            paths = sorted(
                self.live_journal_directory.glob(
                    f"{JOURNAL_PREFIX}*{JOURNAL_SUFFIX}"
                ),
                key=self._journal_path_start_ms,
            )
        except OSError:
            return {}, []
        stale_paths = paths[:-MAX_JOURNAL_WINDOWS]
        paths = paths[-MAX_JOURNAL_WINDOWS:]
        for path in stale_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                LOGGER.warning(
                    "Could not rotate stale trackpad journal %s",
                    path,
                )
        summaries: dict[str, TrackpadCaptureSummary] = {}
        recent_samples: list[TrackpadMetricsSample] = []
        cutoff_ms = (
            time.time_ns() // 1_000_000
            - self.retention_seconds * 1_000
        )
        for path in paths:
            capture_id = path.name.removesuffix(JOURNAL_SUFFIX)
            samples = self._read_journal_path(path)
            if not samples:
                continue
            summaries[capture_id] = _capture_summary(
                capture_id,
                self._journal_start_ms(capture_id),
                JOURNAL_REASON,
                True,
                samples,
            )
            recent_samples.extend(
                sample
                for sample in samples
                if sample.timestamp_ms >= cutoff_ms
            )
        recent_samples.sort(key=lambda sample: sample.timestamp_ms)
        return summaries, recent_samples

    def _capture_path(self, capture_id: str) -> Path:
        if (
            not capture_id
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                for character in capture_id
            )
        ):
            raise ValueError("Invalid trackpad metrics capture ID")
        return self.captures_directory / f"{capture_id}.json.gz"

    def _read_capture(self, capture_id: str) -> dict:
        path = self._capture_path(capture_id)
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
        if payload.get("version") != CAPTURE_VERSION:
            raise ValueError("Unsupported trackpad metrics capture")
        return payload

    def _load_capture_summaries(
        self,
    ) -> dict[str, TrackpadCaptureSummary]:
        summaries: dict[str, TrackpadCaptureSummary] = {}
        try:
            paths = sorted(self.captures_directory.glob("*.json.gz"))
        except OSError:
            return summaries
        for path in paths:
            try:
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    payload = json.load(stream)
                summary = payload["summary"]
                capture = TrackpadCaptureSummary(
                    capture_id=str(summary["id"]),
                    created_at_ms=int(summary["createdAtMs"]),
                    reason=str(summary["reason"]),
                    automatic=bool(summary["automatic"]),
                    sample_count=int(summary["sampleCount"]),
                    duration_ms=int(summary["durationMs"]),
                    left_peak_pressure=int(summary["leftPeakPressure"]),
                    right_peak_pressure=int(summary["rightPeakPressure"]),
                )
                summaries[capture.capture_id] = capture
            except Exception:
                LOGGER.warning(
                    "Ignoring an invalid trackpad metrics capture: %s",
                    path,
                )
        return summaries

    @staticmethod
    def _sample_from_payload(payload: dict) -> TrackpadMetricsSample:
        return TrackpadMetricsSample(
            timestamp_ms=int(payload["timestampMs"]),
            sequence=int(payload.get("sequence", 0)),
            stream_epoch=int(payload.get("streamEpoch", 0)),
            left_touched=bool(payload["leftTouched"]),
            left_pressed=bool(payload["leftPressed"]),
            left_pressure=int(payload["leftPressure"]),
            left_x=int(payload["leftX"]),
            left_y=int(payload["leftY"]),
            right_touched=bool(payload["rightTouched"]),
            right_pressed=bool(payload["rightPressed"]),
            right_pressure=int(payload["rightPressure"]),
            right_x=int(payload["rightX"]),
            right_y=int(payload["rightY"]),
            buttons=int(payload["buttons"]),
        )

    def _prune_automatic_captures(self):
        with self.lock:
            automatic = sorted(
                (
                    summary
                    for summary in self.capture_summaries.values()
                    if summary.automatic
                ),
                key=lambda summary: summary.created_at_ms,
                reverse=True,
            )
        for summary in automatic[MAX_AUTOMATIC_CAPTURES:]:
            self.delete_capture(summary.capture_id)
