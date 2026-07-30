"""Trackpad anomaly detection and safe automatic recovery state machine."""

from __future__ import annotations

import logging
import time

from .constants import (
    AUTO_CAPTURE_COOLDOWN_SECONDS,
    AUTO_CAPTURE_DELAY_SECONDS,
    AUTO_CAPTURE_TOUCHES,
    AUTO_CAPTURE_WINDOW_SECONDS,
    CLICK_PRESSURE_THRESHOLD,
    RECOVERY_ABNORMAL_PRESSURE,
    RECOVERY_ARM_TIMEOUT_SECONDS,
    RECOVERY_COOLDOWN_SECONDS,
    RECOVERY_IDLE_SECONDS,
    RECOVERY_MOTION_CLICK_WINDOW_SECONDS,
    RECOVERY_MOTION_DISTANCE,
    RECOVERY_MOTION_STEP,
    RECOVERY_RESULT_TIMEOUT_SECONDS,
    RECOVERY_SUSTAINED_PRESSURE_SECONDS,
)
from .models import TrackpadMetricsSample
from .parsing import _sample_trackpads_safely_released


LOGGER = logging.getLogger("4deus-trackpad-metrics")


class TrackpadRecoveryMixin:
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
