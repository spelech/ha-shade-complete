# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-08

### Added
- Complete rewrite and fusion of `smart_sun_shade` and `coverTiltEntityCreator`.
- Pure domain `SunTrackingEngine` supporting customizable window orientation, elevation thresholds, sensitivity limits, and weather overrides.
- Pure domain `BatteryCalibrationEngine` with exponential moving average, motor-sag drop filtering, and dynamic online min/max 0-100% learning.
- Pure domain `ScheduleClosingEngine` supporting fixed daily closing schedules and sunset offset automation.
- `TiltCoverEntity` with native physical device co-location in the Home Assistant Device Registry.
- `GroupShadeCover` for synchronized control and aggregated telemetry across multiple shades.
- Diagnostic sensors: `CalibratedBatterySensor` and `ShadeTrackingStatusSensor`.
- Full Home Assistant UI `ConfigFlow` and dynamic `OptionsFlow` with English translations.
- Custom service calls: `calibrate_battery`, `reset_manual_override`, and `trigger_auto_close`.
- Multi-stage GitHub Actions CI quality gates and test suite achieving >=80% coverage.
