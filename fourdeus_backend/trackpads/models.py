"""Immutable samples and recovery state models."""

from dataclasses import dataclass


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
