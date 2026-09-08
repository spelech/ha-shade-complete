"""Unit tests for the ScheduleClosingEngine."""

from datetime import date, datetime

from custom_components.shade_complete.engine.schedule_engine import ScheduleClosingEngine


def test_schedule_engine_disabled():
    """Test that disabled scheduler never triggers."""
    engine = ScheduleClosingEngine(enabled=False, target_time="21:30:00")
    dt = datetime(2026, 9, 8, 22, 0, 0)
    assert engine.should_trigger_close(current_dt=dt, is_closed=False) is False


def test_schedule_engine_already_closed():
    """Test that if shade is already closed, scheduler does not trigger."""
    engine = ScheduleClosingEngine(enabled=True, target_time="21:30:00")
    dt = datetime(2026, 9, 8, 22, 0, 0)
    assert engine.should_trigger_close(current_dt=dt, is_closed=True) is False


def test_schedule_engine_time_trigger():
    """Test time-based trigger and single-dispatch daily locking."""
    engine = ScheduleClosingEngine(enabled=True, target_time="21:30:00")

    # Before 21:30
    dt_before = datetime(2026, 9, 8, 21, 15, 0)
    assert engine.should_trigger_close(current_dt=dt_before, is_closed=False) is False
    assert engine.last_closed_date is None

    # At 21:30
    dt_at = datetime(2026, 9, 8, 21, 30, 0)
    assert engine.should_trigger_close(current_dt=dt_at, is_closed=False) is True
    assert engine.last_closed_date == date(2026, 9, 8)

    # 5 minutes later on the same day -> already triggered, must not re-trigger
    dt_after = datetime(2026, 9, 8, 21, 35, 0)
    assert engine.should_trigger_close(current_dt=dt_after, is_closed=False) is False

    # Next day at 21:30 -> triggers again
    dt_next_day = datetime(2026, 9, 9, 21, 30, 0)
    assert engine.should_trigger_close(current_dt=dt_next_day, is_closed=False) is True
    assert engine.last_closed_date == date(2026, 9, 9)


def test_schedule_engine_sunset_trigger():
    """Test sunset mode with offset calculation."""
    engine = ScheduleClosingEngine(enabled=True, mode="sunset", sunset_offset_minutes=15)
    sunset = datetime(2026, 9, 8, 19, 45, 0)

    # Before trigger time (sunset + 15 = 20:00)
    dt_early = datetime(2026, 9, 8, 19, 50, 0)
    assert (
        engine.should_trigger_close(current_dt=dt_early, is_closed=False, sunset_dt=sunset) is False
    )

    # At trigger time (20:00)
    dt_trigger = datetime(2026, 9, 8, 20, 0, 0)
    assert (
        engine.should_trigger_close(current_dt=dt_trigger, is_closed=False, sunset_dt=sunset)
        is True
    )


def test_reset_daily_trigger():
    """Test manual reset of the daily lock."""
    engine = ScheduleClosingEngine(enabled=True, target_time="21:30:00")
    dt = datetime(2026, 9, 8, 22, 0, 0)
    assert engine.should_trigger_close(current_dt=dt, is_closed=False) is True

    # Manually reset lock
    engine.reset_daily_trigger()
    assert engine.last_closed_date is None
    assert engine.should_trigger_close(current_dt=dt, is_closed=False) is True
