"""Unit tests for the BatteryCalibrationEngine."""

from custom_components.shade_complete.engine.battery_engine import BatteryCalibrationEngine


def test_battery_engine_initialization():
    """Test initial engine parameters and bounds."""
    engine = BatteryCalibrationEngine(
        mode="voltage",
        nominal_min=6.4,
        nominal_max=8.4,
        auto_learn=True,
        smoothing_factor=0.2,
    )
    assert engine.learned_min == 6.4
    assert engine.learned_max == 8.4
    assert engine.sample_count == 0
    assert engine.filtered_value is None
    assert engine.get_calibrated_percent() == 0


def test_battery_engine_invalid_inputs():
    """Test rejection of non-numeric, negative, or corrupt readings."""
    engine = BatteryCalibrationEngine(nominal_min=6.0, nominal_max=8.0)
    assert engine.update("invalid") is None
    assert engine.update(None) is None
    assert engine.update(-5.0) is None
    assert engine.sample_count == 0


def test_battery_smoothing_and_percent():
    """Test exponential smoothing and 0-100% normalization."""
    engine = BatteryCalibrationEngine(
        nominal_min=6.0, nominal_max=8.0, smoothing_factor=0.5, auto_learn=False
    )
    # First reading initializes filtered value directly
    res1 = engine.update(7.0)
    assert res1["filtered_value"] == 7.0
    assert res1["calibrated_percent"] == 50

    # 8.0 V should be 100%
    engine.filtered_value = 8.0
    assert engine.get_calibrated_percent() == 100

    # 6.0 V should be 0%
    engine.filtered_value = 6.0
    assert engine.get_calibrated_percent() == 0

    # Over 8.0 V clamped to 100%
    engine.filtered_value = 8.5
    assert engine.get_calibrated_percent() == 100

    # Under 6.0 V clamped to 0%
    engine.filtered_value = 5.5
    assert engine.get_calibrated_percent() == 0


def test_motor_sag_inhibit():
    """Test that updates during motor motion are ignored to avoid voltage sag corruption."""
    engine = BatteryCalibrationEngine(nominal_min=6.0, nominal_max=8.0)
    engine.update(7.4)
    filtered_before = engine.filtered_value

    # During motor inrush, voltage dips to 6.2 V
    res = engine.update(6.2, is_moving=True)
    # Filtered value must NOT have absorbed the 6.2 dip
    assert engine.filtered_value == filtered_before
    assert res["raw_value"] == 6.2


def test_online_bounds_learning():
    """Test adaptive expansion of min and max boundaries."""
    engine = BatteryCalibrationEngine(
        nominal_min=6.5, nominal_max=8.2, smoothing_factor=1.0, auto_learn=True
    )
    # Normal reading
    engine.update(7.5)
    assert engine.learned_min == 6.5
    assert engine.learned_max == 8.2

    # Battery discharges further to 6.3V
    engine.update(6.3)
    assert engine.learned_min == 6.3

    # Battery charges up to full 8.4V
    engine.update(8.4)
    assert engine.learned_max == 8.4


def test_manual_calibration_bounds():
    """Test manual override of bounds and handling inverted inputs."""
    engine = BatteryCalibrationEngine(nominal_min=6.0, nominal_max=8.0)
    engine.set_calibration_bounds(min_val=6.2, max_val=8.3)
    assert engine.learned_min == 6.2
    assert engine.learned_max == 8.3

    # Inverted min/max automatically swapped
    engine.set_calibration_bounds(min_val=9.0, max_val=5.0)
    assert engine.learned_min == 5.0
    assert engine.learned_max == 9.0


def test_zero_span_handling():
    """Test graceful handling if min equals max."""
    engine = BatteryCalibrationEngine(nominal_min=7.0, nominal_max=7.0)
    engine.filtered_value = 7.0
    assert engine.get_calibrated_percent() == 100

    engine.filtered_value = 6.9
    assert engine.get_calibrated_percent() == 0
