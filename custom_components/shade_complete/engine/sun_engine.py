"""Solar tracking and position calculation engine."""

from __future__ import annotations

from datetime import time
from typing import Any

from ..const import (
    COMPASS_AZIMUTH_MAP,
    WEATHER_POOR_CONDITIONS,
)


class SunTrackingEngine:
    """Calculates solar alignment, window incidence, and shade targets."""

    @staticmethod
    def parse_window_azimuth(value: str | float | int) -> float:
        """Convert compass heading or numeric string/float to normalized azimuth degrees (0-360)."""
        if isinstance(value, str):
            clean = value.strip().upper()
            if clean in COMPASS_AZIMUTH_MAP:
                return COMPASS_AZIMUTH_MAP[clean]
            try:
                return float(clean) % 360.0
            except ValueError:
                return 180.0
        return float(value) % 360.0

    @staticmethod
    def is_sun_on_window(window_azimuth: float, tolerance: float, sun_azimuth: float) -> bool:
        """Determine if the solar azimuth falls within the window's field of view."""
        w_az = window_azimuth % 360.0
        s_az = sun_azimuth % 360.0
        tol = abs(tolerance)

        if tol >= 180.0:
            return True

        min_az = (w_az - tol) % 360.0
        max_az = (w_az + tol) % 360.0

        if min_az <= max_az:
            return min_az <= s_az <= max_az
        # Handles 0/360 wraparound across North
        return s_az >= min_az or s_az <= max_az

    @staticmethod
    def calculate_shade_position(
        elevation: float,
        elevation_low: float,
        elevation_high: float,
        position_offset: int = 0,
    ) -> int:
        """Compute the shade open percentage (0-100) based on solar elevation."""
        if elevation_high <= elevation_low:
            return 100

        if elevation <= elevation_low:
            raw_target = 0
        elif elevation >= elevation_high:
            raw_target = 100
        else:
            fraction = (elevation - elevation_low) / (elevation_high - elevation_low)
            raw_target = int(round(fraction * 100))

        adjusted = raw_target + position_offset
        return max(0, min(100, adjusted))

    @classmethod
    def evaluate(
        cls,
        *,
        sun_state: str,
        sun_azimuth: float,
        sun_elevation: float,
        window_direction: str | float | int,
        azimuth_tolerance: float,
        elevation_low: float,
        elevation_high: float,
        current_time: time,
        tracking_start_time: time,
        tracking_end_time: time,
        weather_state: str | None = None,
        is_manual_override: bool = False,
        position_offset: int = 0,
    ) -> dict[str, Any]:
        """Evaluate full sun tracking conditions and return decision payload."""
        if sun_state == "below_horizon":
            return {
                "active": False,
                "reason": "Sun below horizon",
                "target_position": 0,
            }

        if is_manual_override:
            return {
                "active": False,
                "reason": "Manual override active",
                "target_position": None,
            }

        # Check operational time window
        if tracking_start_time <= tracking_end_time:
            if not (tracking_start_time <= current_time <= tracking_end_time):
                return {
                    "active": False,
                    "reason": f"Outside tracking hours ({tracking_start_time}-{tracking_end_time})",
                    "target_position": 100,
                }
        else:
            # Span midnight
            if not (current_time >= tracking_start_time or current_time <= tracking_end_time):
                return {
                    "active": False,
                    "reason": f"Outside tracking hours ({tracking_start_time}-{tracking_end_time})",
                    "target_position": 100,
                }

        # Weather suppression
        if weather_state and weather_state.lower() in WEATHER_POOR_CONDITIONS:
            return {
                "active": False,
                "reason": f"Poor weather condition ({weather_state})",
                "target_position": 100,
            }

        window_azimuth = cls.parse_window_azimuth(window_direction)
        on_window = cls.is_sun_on_window(window_azimuth, azimuth_tolerance, sun_azimuth)

        if not on_window:
            return {
                "active": False,
                "reason": (
                    f"Sun not facing window (Az: {sun_azimuth:.1f}°, Win: {window_azimuth:.1f}°)"
                ),
                "target_position": 100,
            }

        # Sun is on window and above horizon during active hours
        target = cls.calculate_shade_position(
            elevation=sun_elevation,
            elevation_low=elevation_low,
            elevation_high=elevation_high,
            position_offset=position_offset,
        )

        return {
            "active": True,
            "reason": "Tracking solar incidence",
            "target_position": target,
        }
