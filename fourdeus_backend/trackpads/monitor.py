"""Low-overhead trackpad metrics monitor orchestration."""

from __future__ import annotations

from collections import deque
import logging
import os
from pathlib import Path
import select
import threading
import time
from typing import Callable

from .constants import (
    CONTROLLER_RECONCILE_INTERVAL_SECONDS,
    DEFAULT_RETENTION_SECONDS,
    DEFAULT_SAMPLE_RATE_HZ,
    IDLE_REPORT_BATCH_INTERVAL_SECONDS,
    MAX_REPORT_BATCH_SIZE,
    MIN_REPORT_SIZE,
    MONITOR_MAINTENANCE_INTERVAL_SECONDS,
    RECOVERY_IDLE_REPORT_BATCH_INTERVAL_SECONDS,
    REPORT_HEADER,
)
from .controller import (
    find_steam_deck_hidraw,
    reconcile_steam_deck_controller_authorization,
)
from .models import TrackpadMetricsSample, _TrackpadGesture
from .parsing import (
    _parse_trackpad_metrics_report,
    _report_control_state,
    _report_trackpads_safely_released,
    _sample_trackpads_safely_released,
    _state_signature,
)
from .persistence import TrackpadPersistenceMixin
from .recovery import TrackpadRecoveryMixin


LOGGER = logging.getLogger("4deus-trackpad-metrics")


class TrackpadMetricsMonitor(
    TrackpadPersistenceMixin,
    TrackpadRecoveryMixin,
):
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
                            self._idle_report_batch_interval()
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

    def _idle_report_batch_interval(self) -> float:
        if self.metrics_enabled:
            return IDLE_REPORT_BATCH_INTERVAL_SECONDS
        return RECOVERY_IDLE_REPORT_BATCH_INTERVAL_SECONDS

    def _read_reports(self, descriptor: int, *, drain: bool = False):
        pending_report: bytes | None = None
        pending_state: int | None = None
        for _ in range(MAX_REPORT_BATCH_SIZE):
            try:
                report = os.read(descriptor, 64)
            except BlockingIOError:
                if pending_report is not None:
                    self.record_report(pending_report)
                return
            if not report:
                raise OSError("Steam Deck trackpad device closed")
            if not drain:
                self.record_report(report)
                return
            state = _report_control_state(report)
            if (
                pending_report is not None
                and state != pending_state
            ):
                self.record_report(pending_report)
            pending_report = report
            pending_state = state
        if pending_report is not None:
            self.record_report(pending_report)

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
