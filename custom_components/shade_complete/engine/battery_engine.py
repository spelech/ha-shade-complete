"""Adaptive battery monitoring, motor-sag filtering, and 0-100 scale learning engine."""

from __future__ import annotations

from typing import Any


class BatteryCalibrationEngine:
    """Manages adaptive calibration, smoothing, and true state-of-charge calculation."""

    def __init__(
        self,
        *,
        mode: str = "voltage",
        nominal_min: float = 6.4,
        nominal_max: float = 8.4,
        auto_learn: bool = True,
        smoothing_factor: float = 0.2,
    ) -> None:
        """Initialize the battery calibration engine."""
        self.mode = mode
        self.auto_learn = auto_learn
        self.smoothing_factor = max(0.01, min(1.0, smoothing_factor))

        self.learned_min: float = nominal_min
        self.learned_max: float = nominal_max

        self.filtered_value: float | None = None
        self.last_raw_value: float | None = None
        self.sample_count: int = 0
        self.is_charging: bool = False

    def update(
        self,
        raw_reading: float | int | str,
        *,
        is_moving: bool = False,
    ) -> dict[str, Any] | None:
        """Process a new battery reading, apply filtering, and learn bounds."""
        try:
            val = float(raw_reading)
        except (ValueError, TypeError):
            return None

        # Discard invalid non-positive readings
        if val <= 0.0:
            return None

        self.last_raw_value = val

        # If motor is currently moving, suppress updates to avoid transient voltage sag
        if is_moving:
            return self.get_state()

        # Update Exponential Moving Average (EMA)
        if self.filtered_value is None:
            self.filtered_value = val
        else:
            # Charge detection heuristic: rapid sustained rise indicates external charging
            if val > self.filtered_value + 0.15:
                self.is_charging = True
            elif val < self.filtered_value - 0.05:
                self.is_charging = False

            self.filtered_value = (
                self.smoothing_factor * val + (1.0 - self.smoothing_factor) * self.filtered_value
            )

        self.sample_count += 1

        # Online bounds learning
        if self.auto_learn and self.filtered_value is not None:
            # Only adapt min when not charging
            if not self.is_charging and self.filtered_value < self.learned_min:
                self.learned_min = round(self.filtered_value, 2)

            # Adapt max when reaching sustained peaks
            if self.filtered_value > self.learned_max:
                self.learned_max = round(self.filtered_value, 2)

        return self.get_state()

    def get_calibrated_percent(self) -> int:
        """Calculate the normalized 0-100% scale using learned bounds."""
        if self.filtered_value is None:
            return 0

        span = self.learned_max - self.learned_min
        if span <= 0:
            return 100 if self.filtered_value >= self.learned_max else 0

        raw_pct = ((self.filtered_value - self.learned_min) / span) * 100.0
        clamped = max(0.0, min(100.0, raw_pct))
        return int(round(clamped))

    def set_calibration_bounds(
        self,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> None:
        """Manually override or calibrate learned bounds."""
        if min_val is not None:
            self.learned_min = float(min_val)
        if max_val is not None:
            self.learned_max = float(max_val)
        if self.learned_min > self.learned_max:
            self.learned_min, self.learned_max = self.learned_max, self.learned_min

    def get_state(self) -> dict[str, Any]:
        """Return the current engine diagnostics and calculated percentage."""
        return {
            "raw_value": self.last_raw_value,
            "filtered_value": round(self.filtered_value, 2)
            if self.filtered_value is not None
            else None,
            "calibrated_percent": self.get_calibrated_percent(),
            "learned_min": self.learned_min,
            "learned_max": self.learned_max,
            "sample_count": self.sample_count,
            "is_charging": self.is_charging,
        }
