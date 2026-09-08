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
