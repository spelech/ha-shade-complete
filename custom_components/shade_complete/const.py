"""Constants for the Shade Complete integration."""

from __future__ import annotations

DOMAIN = "shade_complete"

# Setup Modes
CONF_MODE = "mode"
MODE_SMART_SHADE = "smart_shade"
MODE_TILT_ONLY = "tilt_only"
MODE_GROUP = "group"

# Entity Association
CONF_TARGET_COVER = "target_cover"
CONF_TARGET_COVERS = "target_covers"
CONF_NAME = "name"
CONF_DEVICE_ID = "device_id"

# Sun Tracking Parameters
CONF_WINDOW_DIRECTION = "window_direction"
CONF_AZIMUTH_TOLERANCE = "azimuth_tolerance"
CONF_ELEVATION_LOW = "elevation_low_threshold"
CONF_ELEVATION_HIGH = "elevation_high_threshold"
CONF_POSITION_SENSITIVITY = "position_change_sensitivity"
CONF_POSITION_OFFSET = "position_offset"
CONF_TRACKING_START_TIME = "tracking_start_time"
CONF_TRACKING_END_TIME = "tracking_end_time"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_TRAVEL_TIME_SECONDS = "travel_time_seconds"
CONF_ENABLE_OVERRIDE_TIMEOUT = "enable_override_timeout"
CONF_OVERRIDE_TIMEOUT_MINUTES = "override_timeout_minutes"

# Automated Scheduled Closing & Opening
CONF_ENABLE_AUTO_CLOSE = "enable_auto_close"
CONF_AUTO_CLOSE_MODE = "auto_close_mode"
AUTO_CLOSE_MODE_TIME = "time"
AUTO_CLOSE_MODE_SUNSET = "sunset"
CONF_AUTO_CLOSE_TIME = "auto_close_time"
CONF_AUTO_CLOSE_SUNSET_OFFSET = "auto_close_sunset_offset"

CONF_ENABLE_AUTO_OPEN = "enable_auto_open"
CONF_AUTO_OPEN_MODE = "auto_open_mode"
AUTO_OPEN_MODE_TIME = "time"
AUTO_OPEN_MODE_SUNRISE = "sunrise"
CONF_AUTO_OPEN_TIME = "auto_open_time"
CONF_AUTO_OPEN_SUNRISE_OFFSET = "auto_open_sunrise_offset"
CONF_AUTO_OPEN_POSITION = "auto_open_position"

# Adaptive Battery Calibration
CONF_BATTERY_SENSOR = "battery_sensor"
CONF_BATTERY_MODE = "battery_mode"
BATTERY_MODE_VOLTAGE = "voltage"
BATTERY_MODE_PERCENTAGE = "percentage"
CONF_BATTERY_MIN = "battery_min"
CONF_BATTERY_MAX = "battery_max"
CONF_BATTERY_AUTO_LEARN = "battery_auto_learn"
CONF_BATTERY_SMOOTHING_FACTOR = "battery_smoothing_factor"
CONF_BATTERY_LOW_THRESHOLD = "battery_low_threshold"

# Low Percentage Tilt Interception
CONF_ENABLE_TILT_INTERCEPT = "enable_tilt_intercept"
CONF_TILT_INTERCEPT_THRESHOLD = "tilt_intercept_threshold"

# Defaults
DEFAULT_WINDOW_DIRECTION = "S"
DEFAULT_AZIMUTH_TOLERANCE = 22.5
DEFAULT_ELEVATION_LOW = 5.0
DEFAULT_ELEVATION_HIGH = 40.0
DEFAULT_POSITION_SENSITIVITY = 10
DEFAULT_POSITION_OFFSET = 0
DEFAULT_TRACKING_START_TIME = "08:00:00"
DEFAULT_TRACKING_END_TIME = "21:00:00"
DEFAULT_TRAVEL_TIME_SECONDS = 15
DEFAULT_OVERRIDE_TIMEOUT_MINUTES = 120
DEFAULT_ENABLE_AUTO_CLOSE = False
DEFAULT_AUTO_CLOSE_TIME = "21:30:00"
DEFAULT_AUTO_CLOSE_SUNSET_OFFSET = 15
DEFAULT_ENABLE_AUTO_OPEN = False
DEFAULT_AUTO_OPEN_TIME = "07:30:00"
DEFAULT_AUTO_OPEN_SUNRISE_OFFSET = 0
DEFAULT_AUTO_OPEN_POSITION = 100
DEFAULT_BATTERY_MODE = BATTERY_MODE_VOLTAGE
DEFAULT_BATTERY_MIN_VOLTAGE = 6.4
DEFAULT_BATTERY_MAX_VOLTAGE = 8.4
DEFAULT_BATTERY_MIN_PERCENT = 0.0
DEFAULT_BATTERY_MAX_PERCENT = 100.0
DEFAULT_BATTERY_AUTO_LEARN = True
DEFAULT_BATTERY_SMOOTHING = 0.2
DEFAULT_BATTERY_LOW_THRESHOLD = 20
DEFAULT_ENABLE_TILT_INTERCEPT = False
DEFAULT_TILT_INTERCEPT_THRESHOLD = 5

# Compass Azimuth Map
COMPASS_AZIMUTH_MAP: dict[str, float] = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
}

# Weather Conditions that Disqualify Sun Tracking
WEATHER_POOR_CONDITIONS = {
    "cloudy",
    "fog",
    "foggy",
    "hail",
    "lightning",
    "lightning-rainy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
}

# Services
SERVICE_CALIBRATE_BATTERY = "calibrate_battery"
SERVICE_RESET_OVERRIDE = "reset_manual_override"
SERVICE_TRIGGER_AUTO_CLOSE = "trigger_auto_close"
SERVICE_TRIGGER_AUTO_OPEN = "trigger_auto_open"

# Attributes
ATTR_PROXIED_ENTITY = "proxied_entity"
ATTR_TRACKING_STATUS = "tracking_status"
ATTR_INACTIVE_REASON = "inactive_reason"
ATTR_TARGET_POSITION = "target_position"
ATTR_MANUAL_OVERRIDE = "manual_override"
ATTR_IS_MOVING = "is_moving"
ATTR_LAST_COMMAND_TIME = "last_command_time"
ATTR_RAW_BATTERY = "raw_battery"
ATTR_CALIBRATED_PERCENT = "calibrated_percent"
ATTR_LEARNED_MIN = "learned_min"
ATTR_LEARNED_MAX = "learned_max"
ATTR_CALIBRATION_SAMPLES = "calibration_samples"
ATTR_IS_CHARGING = "is_charging"
