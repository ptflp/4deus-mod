"""Steam Deck trackpad report parsing and sampling helpers."""

from __future__ import annotations

import struct
from typing import Sequence

from .constants import (
    LEFT_PAD_PRESSED,
    LEFT_PAD_PRESSURE_OFFSET,
    LEFT_PAD_TOUCHED,
    LEFT_PAD_X_OFFSET,
    MIN_REPORT_SIZE,
    REPORT_HEADER,
    REPORT_SEQUENCE_OFFSET,
    RIGHT_PAD_PRESSED,
    RIGHT_PAD_PRESSURE_OFFSET,
    RIGHT_PAD_TOUCHED,
    RIGHT_PAD_X_OFFSET,
    TRACKPAD_CONTROL_MASK,
)
from .models import TrackpadCaptureSummary, TrackpadMetricsSample


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


def _report_control_state(report: bytes) -> int | None:
    if (
        len(report) < MIN_REPORT_SIZE
        or not report.startswith(REPORT_HEADER)
    ):
        return None
    controls = int.from_bytes(report[8:12], "little")
    left_pressure = int.from_bytes(
        report[
            LEFT_PAD_PRESSURE_OFFSET:LEFT_PAD_PRESSURE_OFFSET + 2
        ],
        "little",
    )
    right_pressure = int.from_bytes(
        report[
            RIGHT_PAD_PRESSURE_OFFSET:RIGHT_PAD_PRESSURE_OFFSET + 2
        ],
        "little",
    )
    return (
        controls & TRACKPAD_CONTROL_MASK
        | bool(left_pressure) << 32
        | bool(right_pressure) << 33
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
