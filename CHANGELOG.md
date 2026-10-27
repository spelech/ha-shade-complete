# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.9] - 2026-10-27

### Fixed
- **Group Transit Verification & False Manual Override Immunity**:
  - Prevented group shade transit from completing prematurely based on average position when member shades are still in flight. Movement now completes early only when all member entities have reported and reached within position sensitivity tolerance.
  - Eliminated false manual override triggers for delayed or in-flight member motor position updates that settle at the commanded target position (`requested_position` or `last_set_position`).
  - Cleared lingering `_requested_position` upon manual override engagement to prevent stale commanded positions from persisting after human intervention.

## [1.2.8] - 2026-10-18

### Fixed
- **Clean Group Device Naming**:
  - Prevented `TiltCoverEntity` from polluting group device names in Home Assistant's Device Registry with `"<Name> Tilt"`. Group devices now cleanly maintain their configured name (e.g., `"Bay Window Shades"`).
- **Opt-In Virtual Tilt Entity Creation**:
  - Made the secondary virtual `TiltCoverEntity` (`cover.<name>_tilt`) opt-in via `create_tilt_entity` (default: `False`). Since `SmartTrackingShadeCover` and `GroupShadeCover` already natively support tilt positions and controls directly, duplicate virtual tilt cover entities are no longer automatically spawned for every device.

## [1.2.7] - 2026-10-16

### Added
- **Configurable Weather Entity & Cloud Coverage Threshold**:
  - Weather entity is now selectable in initial setup (`smart_shade`, `group`) and changeable in runtime Options Flow (`solar_tracking`, `all_settings`). Leaving it empty seamlessly falls back to system weather auto-discovery (`weather.home`).
  - Cloud coverage threshold is now exposed and configurable (0–100%, step 5%) in setup flows and runtime Options Flow.

### Fixed
- **Tilt Override & Sun Tracking Immunity**:
  - Linked `TiltCoverEntity` directly to its parent shade/group cover so that open tilt, close tilt, and tilt position commands issued via Google Assistant or dashboards immediately engage manual override.
  - Added manual override trigger to `BaseShadeCover` tilt service calls (`async_open_cover_tilt`, `async_close_cover_tilt`, `async_set_cover_tilt_position`, `async_stop_cover_tilt`).
  - Added physical member tilt monitoring: external tilt changes (>5% delta) from physical remotes or wands immediately trigger manual override.
  - Added automatic tilt closure upon full shade closure: when arrival at position 0 is verified or completed early, `close_cover_tilt` is dispatched to ensure vanes seal tight.
  - Enhanced nighttime evaluation below horizon: if position is already 0 but vanes remain partially open, automatically dispatches `close_cover_tilt` without unnecessary roller movement.
  - Preserved manual hold when override timeout is disabled, and properly reset overrides on explicit scheduled morning open / evening close.

## [1.2.6] - 2026-10-16

### Added
- **Intelligent Weather & Cloud Coverage Factoring**:
  - Automatically auto-detects system weather entity (`weather.home` or default `weather.*`) when no explicit weather entity is configured.
  - Added cloud coverage evaluation: suppresses solar tracking closing when cloud coverage exceeds threshold (default 70%) or during partly cloudy skies with high coverage (>=60%), keeping shades open (target 100%) on cloudy days.
  - Exposed `weather_condition` and `cloud_coverage` diagnostic attributes on shade entities.

### Fixed
- **Premature Motion Completion Prevention**:
  - Ensures shade covers and group member covers do not mark movement as completed early while motors are actively in transit (`opening` or `closing` states), preventing spurious manual override triggers and ensuring positions commanded via Google Assistant or dashboards are fully retained.

## [1.2.5] - 2026-10-12

### Fixed
- **Tilt Closure on Full Shade Close**:
  - Dispatches native `cover.close_cover` and `cover.close_cover_tilt` for shades supporting tilt when commanded to position 0 or closed.
  - Prevents Motionblinds hardware protocol restore-angle behavior where position 0 previously caused blinds to reopen slats to their saved tilt value.
  - Factors tilt position into `BaseShadeCover.is_closed` so shades with open slats are correctly reported as not closed.
- **Nighttime & External Manual Override Preservation**:
  - Preserves active manual overrides when the sun is below the horizon instead of resetting override locks and commanding closure every 60-second ticker.
  - Prioritizes manual override state in `SunTrackingEngine.evaluate` to prevent forced zero-target at night.
  - Immediately detects external transit (`opening` / `closing` states) from Google Assistant or physical remotes to lock manual override.

## [1.1.0] - 2026-10-04

### Added
- **Automatic Physical Cover Hiding (`hidden_by=INTEGRATION`)**:
  - Automatically flags consumed physical shade entities as `hidden_by=integration` in the Home Assistant Entity Registry during setup.
  - Keeps underlying motor telemetry and service dispatch fully operational while seamlessly preventing duplicate entities on dashboards and in voice assistants (Google Assistant, Alexa).
  - Automatically restores visibility (`hidden_by=None`) upon integration unload or removal.
  - Configurable toggle (`hide_underlying`) in single shade, tilt-only, and group setup flows, as well as the dynamic options menu.

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
