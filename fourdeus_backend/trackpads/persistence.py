"""Trackpad metrics capture and rolling-journal persistence."""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import json
import logging
import os
from pathlib import Path
import time
import uuid
from typing import Sequence

from .constants import (
    CAPTURE_VERSION,
    JOURNAL_FLUSH_INTERVAL_SECONDS,
    JOURNAL_PREFIX,
    JOURNAL_REASON,
    JOURNAL_SUFFIX,
    JOURNAL_WINDOW_SECONDS,
    MAX_AUTOMATIC_CAPTURES,
    MAX_JOURNAL_WINDOWS,
    MAX_WINDOW_SAMPLES,
)
from .models import TrackpadCaptureSummary, TrackpadMetricsSample
from .parsing import _capture_summary, _downsample


LOGGER = logging.getLogger("4deus-trackpad-metrics")


class TrackpadPersistenceMixin:
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
