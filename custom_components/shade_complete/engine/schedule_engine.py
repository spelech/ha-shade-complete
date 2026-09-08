"""Automated scheduled opening and closing calculation engine."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta


class ScheduleClosingEngine:
    """Evaluates scheduled and solar (sunrise/sunset) automation triggers for opening & closing."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        close_enabled: bool | None = None,
        mode: str = "time",
        close_mode: str | None = None,
        target_time: time | str = "21:30:00",
        close_time: time | str | None = None,
        sunset_offset_minutes: int = 15,
        open_enabled: bool = False,
        open_mode: str = "time",
        open_target_time: time | str = "07:30:00",
        open_time: time | str | None = None,
        sunrise_offset_minutes: int = 0,
        open_position: int = 100,
    ) -> None:
        """Initialize the scheduling engine."""
        self.enabled = enabled if close_enabled is None else close_enabled
        self.mode = mode if close_mode is None else close_mode
        c_time = target_time if close_time is None else close_time
        self.target_time = self._parse_time(c_time, time(21, 30, 0))
        self.sunset_offset_minutes = sunset_offset_minutes

        self.open_enabled = open_enabled
        self.open_mode = open_mode
        o_time = open_target_time if open_time is None else open_time
        self.open_target_time = self._parse_time(o_time, time(7, 30, 0))
        self.sunrise_offset_minutes = sunrise_offset_minutes
        self.open_position = max(0, min(100, int(open_position)))

        self.last_closed_date: date | None = None
        self.last_opened_date: date | None = None

    @staticmethod
    def _parse_time(val: time | str, default: time) -> time:
        """Parse time object or string HH:MM:SS."""
        if isinstance(val, time):
            return val
        if isinstance(val, str):
            parts = [int(p) for p in val.strip().split(":")]
            if len(parts) == 2:
                return time(parts[0], parts[1])
            if len(parts) >= 3:
                return time(parts[0], parts[1], parts[2])
        return default

    def should_trigger_close(
        self,
        *,
        current_dt: datetime,
        is_closed: bool,
        sunset_dt: datetime | None = None,
    ) -> bool:
        """Evaluate if auto-close condition has met for the current day."""
        if not self.enabled or is_closed:
            return False

        today = current_dt.date()
        if self.last_closed_date == today:
            return False

        if self.mode == "sunset" and sunset_dt is not None:
            trigger_dt = sunset_dt + timedelta(minutes=self.sunset_offset_minutes)
            if current_dt >= trigger_dt:
                self.last_closed_date = today
                return True
            return False

        # Time-based mode
        current_time = current_dt.time()
        if current_time >= self.target_time:
            self.last_closed_date = today
            return True

        return False

    def should_trigger_open(
        self,
        *,
        current_dt: datetime,
        current_position: int | None,
        sunrise_dt: datetime | None = None,
    ) -> bool:
        """Evaluate if auto-open condition has met for the current day."""
        if not self.open_enabled:
            return False

        # If shade is already at or above target open position, don't trigger
        if current_position is not None and current_position >= self.open_position:
            return False

        today = current_dt.date()
        if self.last_opened_date == today:
            return False

        if self.open_mode == "sunrise" and sunrise_dt is not None:
            trigger_dt = sunrise_dt + timedelta(minutes=self.sunrise_offset_minutes)
            if current_dt >= trigger_dt:
                self.last_opened_date = today
                return True
            return False

        # Time-based mode
        current_time = current_dt.time()
        if current_time >= self.open_target_time:
            self.last_opened_date = today
            return True

        return False

    def reset_daily_trigger(self) -> None:
        """Clear trigger locks for testing or manual override reset."""
        self.last_closed_date = None
        self.last_opened_date = None
