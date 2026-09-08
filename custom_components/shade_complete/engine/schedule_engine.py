"""Automated scheduled closing calculation engine."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta


class ScheduleClosingEngine:
    """Evaluates scheduled and sunset-based closing automation triggers."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        mode: str = "time",
        target_time: time | str = "21:30:00",
        sunset_offset_minutes: int = 15,
    ) -> None:
        """Initialize the closing engine."""
        self.enabled = enabled
        self.mode = mode
        self.target_time = self._parse_time(target_time)
        self.sunset_offset_minutes = sunset_offset_minutes
        self.last_closed_date: date | None = None

    @staticmethod
    def _parse_time(val: time | str) -> time:
        """Parse time object or string HH:MM:SS."""
        if isinstance(val, time):
            return val
        if isinstance(val, str):
            parts = [int(p) for p in val.strip().split(":")]
            if len(parts) == 2:
                return time(parts[0], parts[1])
            if len(parts) >= 3:
                return time(parts[0], parts[1], parts[2])
        return time(21, 30, 0)

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

    def reset_daily_trigger(self) -> None:
        """Clear trigger lock for testing or manual override reset."""
        self.last_closed_date = None
