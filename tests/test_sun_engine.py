"""Unit tests for the SunTrackingEngine."""

from datetime import time

from custom_components.shade_complete.engine.sun_engine import SunTrackingEngine


def test_parse_window_azimuth():
    """Test azimuth parsing for compass directions and numeric strings."""
    assert SunTrackingEngine.parse_window_azimuth("S") == 180.0
    assert SunTrackingEngine.parse_window_azimuth("N") == 0.0
    assert SunTrackingEngine.parse_window_azimuth("E") == 90.0
    assert SunTrackingEngine.parse_window_azimuth("W") == 270.0
    assert SunTrackingEngine.parse_window_azimuth("SW") == 225.0
    assert SunTrackingEngine.parse_window_azimuth("135.5") == 135.5
    assert SunTrackingEngine.parse_window_azimuth(400) == 40.0
    assert SunTrackingEngine.parse_window_azimuth("INVALID_DIR") == 180.0


def test_is_sun_on_window():
    """Test field of view angle checking with North wraparound."""
    # South window (180°) with 30° tolerance: 150° to 210°
    assert SunTrackingEngine.is_sun_on_window(180, 30, 180) is True
    assert SunTrackingEngine.is_sun_on_window(180, 30, 150) is True
    assert SunTrackingEngine.is_sun_on_window(180, 30, 210) is True
    assert SunTrackingEngine.is_sun_on_window(180, 30, 140) is False
    assert SunTrackingEngine.is_sun_on_window(180, 30, 220) is False

    # North window (0°) with 25° tolerance: 335° to 25°
    assert SunTrackingEngine.is_sun_on_window(0, 25, 0) is True
    assert SunTrackingEngine.is_sun_on_window(0, 25, 10) is True
    assert SunTrackingEngine.is_sun_on_window(0, 25, 350) is True
    assert SunTrackingEngine.is_sun_on_window(0, 25, 30) is False
    assert SunTrackingEngine.is_sun_on_window(0, 25, 180) is False

    # Wide tolerance >= 180 covers all
    assert SunTrackingEngine.is_sun_on_window(90, 185, 270) is True


def test_calculate_shade_position():
    """Test elevation mapping to shade open percentage."""
    # Low threshold 10, High threshold 50
    assert SunTrackingEngine.calculate_shade_position(5, 10, 50) == 0
    assert SunTrackingEngine.calculate_shade_position(10, 10, 50) == 0
    assert SunTrackingEngine.calculate_shade_position(50, 10, 50) == 100
    assert SunTrackingEngine.calculate_shade_position(60, 10, 50) == 100
    assert SunTrackingEngine.calculate_shade_position(30, 10, 50) == 50

    # With offset
    assert SunTrackingEngine.calculate_shade_position(30, 10, 50, position_offset=10) == 60
    assert SunTrackingEngine.calculate_shade_position(5, 10, 50, position_offset=-10) == 0
    assert SunTrackingEngine.calculate_shade_position(50, 10, 50, position_offset=15) == 100

    # Inverted or equal thresholds fallback
    assert SunTrackingEngine.calculate_shade_position(30, 50, 10) == 100


def test_evaluate_sun_tracking():
    """Test full evaluation pipeline under various scenarios."""
    # Scenario 1: Below horizon -> closes shade
    res = SunTrackingEngine.evaluate(
        sun_state="below_horizon",
        sun_azimuth=180,
        sun_elevation=-5,
        window_direction="S",
        azimuth_tolerance=30,
        elevation_low=10,
        elevation_high=50,
        current_time=time(22, 0),
        tracking_start_time=time(8, 0),
        tracking_end_time=time(20, 0),
    )
    assert res["active"] is False
    assert res["target_position"] == 0
    assert "horizon" in res["reason"]

    # Scenario 2: Manual override active -> pauses
    res = SunTrackingEngine.evaluate(
        sun_state="above_horizon",
        sun_azimuth=180,
        sun_elevation=30,
        window_direction="S",
        azimuth_tolerance=30,
        elevation_low=10,
        elevation_high=50,
        current_time=time(12, 0),
        tracking_start_time=time(8, 0),
        tracking_end_time=time(20, 0),
        is_manual_override=True,
    )
    assert res["active"] is False
    assert res["target_position"] is None
    assert "override" in res["reason"].lower()

    # Scenario 3: Outside tracking hours -> opens shade (100)
    res = SunTrackingEngine.evaluate(
        sun_state="above_horizon",
        sun_azimuth=180,
        sun_elevation=30,
        window_direction="S",
        azimuth_tolerance=30,
        elevation_low=10,
        elevation_high=50,
        current_time=time(6, 0),
        tracking_start_time=time(8, 0),
        tracking_end_time=time(20, 0),
    )
    assert res["active"] is False
    assert res["target_position"] == 100
    assert "Outside tracking hours" in res["reason"]

    # Scenario 4: Outside tracking hours (midnight spanning 22:00 to 06:00)
    res = SunTrackingEngine.evaluate(
        sun_state="above_horizon",
        sun_azimuth=180,
        sun_elevation=30,
        window_direction="S",
        azimuth_tolerance=30,
        elevation_low=10,
        elevation_high=50,
        current_time=time(12, 0),
        tracking_start_time=time(22, 0),
        tracking_end_time=time(6, 0),
    )
    assert res["active"] is False
    assert res["target_position"] == 100

    # Scenario 5: Poor weather suppression
    res = SunTrackingEngine.evaluate(
        sun_state="above_horizon",
        sun_azimuth=180,
        sun_elevation=30,
        window_direction="S",
        azimuth_tolerance=30,
        elevation_low=10,
        elevation_high=50,
        current_time=time(12, 0),
        tracking_start_time=time(8, 0),
        tracking_end_time=time(20, 0),
        weather_state="rainy",
    )
    assert res["active"] is False
    assert "Poor weather" in res["reason"]
    assert res["target_position"] == 100

    # Scenario 6: Sun not facing window
    res = SunTrackingEngine.evaluate(
        sun_state="above_horizon",
        sun_azimuth=90,  # East
        sun_elevation=30,
        window_direction="W",  # West (270)
        azimuth_tolerance=30,
        elevation_low=10,
        elevation_high=50,
        current_time=time(12, 0),
        tracking_start_time=time(8, 0),
        tracking_end_time=time(20, 0),
    )
    assert res["active"] is False
    assert "Sun not facing window" in res["reason"]
    assert res["target_position"] == 100

    # Scenario 7: Ideal active tracking
    res = SunTrackingEngine.evaluate(
        sun_state="above_horizon",
        sun_azimuth=185,
        sun_elevation=30,
        window_direction="S",
        azimuth_tolerance=30,
        elevation_low=10,
        elevation_high=50,
        current_time=time(12, 0),
        tracking_start_time=time(8, 0),
        tracking_end_time=time(20, 0),
        weather_state="sunny",
    )
    assert res["active"] is True
    assert res["target_position"] == 50
    assert "Tracking solar incidence" in res["reason"]


def test_is_sun_on_window_exact_boundaries():
    """Test exact boundary transitions for window azimuth tolerance."""
    # Window azimuth 90° (East), tolerance 30° -> range [60.0°, 120.0°]
    assert SunTrackingEngine.is_sun_on_window(90, 30, 60.0) is True  # Exactly on lower edge
    assert SunTrackingEngine.is_sun_on_window(90, 30, 59.9) is False  # 0.1° outside lower edge
    assert SunTrackingEngine.is_sun_on_window(90, 30, 120.0) is True  # Exactly on upper edge
    assert SunTrackingEngine.is_sun_on_window(90, 30, 120.1) is False  # 0.1° outside upper edge

    # North window 0° (North), tolerance 20° -> range [340.0°, 20.0°] across 0°
    assert SunTrackingEngine.is_sun_on_window(0, 20, 340.0) is True  # Exact lower edge
    assert SunTrackingEngine.is_sun_on_window(0, 20, 339.9) is False  # Just outside lower edge
    assert SunTrackingEngine.is_sun_on_window(0, 20, 20.0) is True  # Exact upper edge
    assert SunTrackingEngine.is_sun_on_window(0, 20, 20.1) is False  # Just outside upper edge
    assert SunTrackingEngine.is_sun_on_window(0, 20, 359.9) is True  # Near 360 North
    assert SunTrackingEngine.is_sun_on_window(0, 20, 0.1) is True  # Near 0 North

    # Zero tolerance (tolerance = 0): only exact angle matches
    assert SunTrackingEngine.is_sun_on_window(180, 0, 180.0) is True
    assert SunTrackingEngine.is_sun_on_window(180, 0, 180.1) is False

    # Negative tolerance should be handled via abs()
    assert SunTrackingEngine.is_sun_on_window(180, -30, 180.0) is True
    assert SunTrackingEngine.is_sun_on_window(180, -30, 160.0) is True
    assert SunTrackingEngine.is_sun_on_window(180, -30, 140.0) is False

    # 180° tolerance: covers entire 360° circle
    assert SunTrackingEngine.is_sun_on_window(180, 180, 0.0) is True
    assert SunTrackingEngine.is_sun_on_window(0, 180, 180.0) is True


def test_calculate_shade_position_boundaries():
    """Test elevation exact boundaries and clamping."""
    # elevation_low = 10, elevation_high = 50
    # Exact elevation_low
    assert SunTrackingEngine.calculate_shade_position(10.0, 10, 50) == 0
    # Just below elevation_low
    assert SunTrackingEngine.calculate_shade_position(9.99, 10, 50) == 0
    # Negative elevation (below horizon)
    assert SunTrackingEngine.calculate_shade_position(-15.0, 10, 50) == 0

    # Exact elevation_high
    assert SunTrackingEngine.calculate_shade_position(50.0, 10, 50) == 100
    # Just above elevation_high
    assert SunTrackingEngine.calculate_shade_position(50.01, 10, 50) == 100
    # Extreme high elevation (overhead sun)
    assert SunTrackingEngine.calculate_shade_position(89.9, 10, 50) == 100

    # Position offset clamping:
    # 50% calculated + 100 offset -> clamped to 100%
    assert SunTrackingEngine.calculate_shade_position(30, 10, 50, position_offset=100) == 100
    # 50% calculated - 100 offset -> clamped to 0%
    assert SunTrackingEngine.calculate_shade_position(30, 10, 50, position_offset=-100) == 0

    # Equal elevation_low and elevation_high (degenerate threshold boundary)
    assert SunTrackingEngine.calculate_shade_position(25, 25, 25) == 100


def test_evaluate_sun_tracking_time_boundaries():
    """Test operational time window exact boundary conditions."""
    base_kwargs = {
        "sun_state": "above_horizon",
        "sun_azimuth": 180,
        "sun_elevation": 30,
        "window_direction": "S",
        "azimuth_tolerance": 45,
        "elevation_low": 10,
        "elevation_high": 50,
        "tracking_start_time": time(8, 0, 0),
        "tracking_end_time": time(20, 0, 0),
    }

    # Exactly at start time (08:00:00) -> ACTIVE
    res_start = SunTrackingEngine.evaluate(**base_kwargs, current_time=time(8, 0, 0))
    assert res_start["active"] is True

    # 1 second before start time (07:59:59) -> OUTSIDE HOURS (INACTIVE, shade opens to 100)
    res_before = SunTrackingEngine.evaluate(**base_kwargs, current_time=time(7, 59, 59))
    assert res_before["active"] is False
    assert res_before["target_position"] == 100

    # Exactly at end time (20:00:00) -> ACTIVE
    res_end = SunTrackingEngine.evaluate(**base_kwargs, current_time=time(20, 0, 0))
    assert res_end["active"] is True

    # 1 second after end time (20:00:01) -> OUTSIDE HOURS (INACTIVE, shade opens to 100)
    res_after = SunTrackingEngine.evaluate(**base_kwargs, current_time=time(20, 0, 1))
    assert res_after["active"] is False
    assert res_after["target_position"] == 100

    # Midnight spanning tracking hours: 22:00:00 to 06:00:00
    midnight_kwargs = {
        **base_kwargs,
        "tracking_start_time": time(22, 0, 0),
        "tracking_end_time": time(6, 0, 0),
    }
    # Exactly at start (22:00:00)
    res_m_start = SunTrackingEngine.evaluate(**midnight_kwargs, current_time=time(22, 0, 0))
    assert res_m_start["active"] is True

    # 1s before start (21:59:59)
    res_m_early = SunTrackingEngine.evaluate(**midnight_kwargs, current_time=time(21, 59, 59))
    assert res_m_early["active"] is False

    # Midnight (00:00:00)
    res_m_mid = SunTrackingEngine.evaluate(**midnight_kwargs, current_time=time(0, 0, 0))
    assert res_m_mid["active"] is True

    # Exactly at end (06:00:00)
    res_m_end = SunTrackingEngine.evaluate(**midnight_kwargs, current_time=time(6, 0, 0))
    assert res_m_end["active"] is True

    # 1s after end (06:00:01)
    res_m_late = SunTrackingEngine.evaluate(**midnight_kwargs, current_time=time(6, 0, 1))
    assert res_m_late["active"] is False

