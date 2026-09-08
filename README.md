<div align="center">

<img src="brand/logo.png" alt="Shade Complete Logo" width="600" />

# Shade Complete (`ha-shade-complete`)

**The definitive, full-featured Home Assistant integration for motorized shades, blinds, and rollers.**

[![CI Quality Gate](https://github.com/spelech/ha-shade-complete/actions/workflows/ci.yml/badge.svg)](https://github.com/spelech/ha-shade-complete/actions/workflows/ci.yml)
[![HACS Default](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](https://github.com/spelech/ha-shade-complete)

</div>

---

## 🌟 Why Shade Complete?

Most smart motorized shades (whether Z-Wave, Zigbee, Matter, Somfy, Tuya, or ESPHome) come with frustrating limitations out of the box:
- **Missing Tilt Controls**: Blinds with motorized tilt often only expose `open_tilt` or raw tilt position attributes that cannot be operated like normal covers from dashboards or voice assistants.
- **Dumb Static Schedules**: Closing shades at fixed hours fails as the sun's trajectory shifts across seasons.
- **Inaccurate or Broken Battery Reporting**: Lithium batteries discharge along a curve that confuses uncalibrated firmware—often dropping to 50% in two weeks, staying there for months, or abruptly dying at 30%. In addition, voltage sag during active motor movement triggers false "low battery" alarms.
- **Orphaned Entities**: Helper entities often clutter Home Assistant as separate virtual devices rather than living on the physical shade's device card.

**Shade Complete** solves all of this in one elegant, cohesive integration.

---

## ✨ Features

### ☀️ 1. Intelligent Solar Vector Tracking (Shade & Group Level)
- **Window Orientation & Field of View**: Configure your window's facing direction (N, NE, E, SE, S, SW, W, NW or custom degrees 0–360°) with customizable azimuth tolerance (half-angle FOV) and clean $360^\circ$ North wraparound.
- **Solar Elevation Mapping**: Seamlessly interpolates between your low elevation cutoff (e.g. $5^\circ$) and high elevation threshold (e.g. $40^\circ$) to dynamically keep direct glare out while preserving ambient daylight.
- **Overcast & Storm Suppression**: Monitors an optional `weather.*` entity to suppress tracking on cloudy, foggy, or rainy days, automatically opening shades to maximize natural light.
- **Arbitrated Manual Overrides**: If a user physically adjusts a shade or any member shade in a group via a wall remote or dashboard, Shade Complete yields immediately, detects the override, and automatically resumes tracking after a configurable timeout (or at sunset).
- **Travel Verification**: Automatically monitors movement duration; if motion is halted or intercepted before arrival, manual override is flagged instantly.
- **Group Solar Tracking**: Synchronized groups can follow the same sun-tracking geometry, coordinating multiple physical shades smoothly.

### 🔄 2. Virtual Tilt Projection & Low-Percentage Interception
- **Automatic Cover Entity Creation**: When configuring a smart shade whose underlying physical device supports tilt (or when tilt interception is enabled), Shade Complete automatically provisions both the main `SmartTrackingShadeCover` and a co-located `TiltCoverEntity` directly on the physical device's card.
- **Seamless Low-Percentage Tilt Interception**: Ever wanted to slightly tilt your blinds open using a single slider without lifting the shade roller? Enable **Low-Percentage Tilt Interception** (threshold 1–5%, configurable up to 15%). Commands in the 1–5% range are automatically converted into 0–100% slat tilt adjustments (`set_cover_tilt_position`), while commands above the threshold adjust the shade height normally.
- **Native Device Card Binding**: Inspects the Home Assistant Device Registry and binds helper entities directly to the physical shade's device card (`DeviceInfo`). Your tilt controls, sun tracking entities, and battery sensors live right beside the physical hardware!

### ⏰ 3. Automated Morning Open & Evening Close Schedules
- **Configurable per Shade or Group**: Set automated daily routines for opening and closing.
- **Flexible Trigger Modes**:
  - **Clock Time**: e.g., Open at `07:30:00` to 100% (or custom target position), close at `21:30:00`.
  - **Solar Event (Sunrise / Sunset)**: Open with a configurable offset from sunrise; close with an offset from sunset.
- **Re-Arming Daily Locks**: Prevents redundant triggers throughout the day while automatically resetting manual overrides overnight.

### 🔋 4. Adaptive Battery Intelligence & Calibration
- **Motor-Sag Rejection**: Voltage temporarily plunges when a motorized shade draws inrush current. Shade Complete inhibits calibration sampling during active motor motion, eliminating false low-battery alerts.
- **Exponential Moving Average (EMA)**: Smooths sensor noise without lag.
- **Online Bounds Learning**: Observes your battery's actual low-voltage cutoff point and full-charge peak over time, dynamically calibrating the true 0–100% scale for your specific hardware.
- **Charging Detection**: Automatically detects when the shade is plugged into a solar or USB charger and isolates charging peaks from discharge curves.
- **Low Battery Diagnostics & Alert Blueprint**: Ships with a ready-to-use Home Assistant automation blueprint (`blueprints/automation/spelech/shade_low_battery_notification.yaml`) alerting you when any shade falls below its critical battery threshold.

### 👥 5. Synchronized Shade Groups
- Group multiple individual shades or tilt entities into a single unified cover.
- Concurrent command execution via `asyncio.gather` for synchronized group movement and tilt positioning.
- Computes true average position across all member shades.
- Supports group-level solar tracking, scheduled open/close routines, and member override detection.

---

## 📊 Dashboard Card Template

Shade Complete integrates seamlessly into Lovelace. You can use the template below (also available in [`examples/dashboard_card.yaml`](examples/dashboard_card.yaml)) for an all-in-one card combining shade position, tilt slider, solar diagnostics, and battery health:

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Office Shade Controls
    show_header_toggle: false
    entities:
      - entity: cover.office_shade_smart
        name: Smart Tracking Shade
      - entity: cover.office_shade_tilt
        name: Slat Tilt Position
      - type: divider
      - entity: sensor.office_shade_battery
        name: Battery Level (Calibrated)

  - type: glance
    title: Solar Status
    show_state: true
    entities:
      - entity: cover.office_shade_smart
        attribute: tracking_status
        name: Tracking
        icon: mdi:sun-compass
      - entity: cover.office_shade_smart
        attribute: target_position
        name: Solar Target
        icon: mdi:bullseye-arrow
      - entity: cover.office_shade_smart
        attribute: manual_override
        name: Override
        icon: mdi:hand-back-right
      - entity: cover.office_shade_smart
        attribute: inactive_reason
        name: Status Detail
        icon: mdi:information-outline

  - type: glance
    title: Battery Health Diagnostics
    show_state: true
    entities:
      - entity: sensor.office_shade_battery
        attribute: raw_battery
        name: Voltage
        icon: mdi:lightning-bolt
      - entity: sensor.office_shade_battery
        attribute: learned_min
        name: Learned 0%
        icon: mdi:battery-minus
      - entity: sensor.office_shade_battery
        attribute: learned_max
        name: Learned 100%
        icon: mdi:battery-plus
      - entity: sensor.office_shade_battery
        attribute: is_charging
        name: Charging
        icon: mdi:battery-charging
```

---

## 🔔 Low Battery Automation Blueprint

A pre-built Home Assistant blueprint is included in this repository:
- Path: `blueprints/automation/spelech/shade_low_battery_notification.yaml`

### How to use:
1. In Home Assistant, navigate to **Settings** > **Automations & Scenes** > **Blueprints**.
2. Click **Import Blueprint** and provide the repository URL or copy the file into your `<config>/blueprints/automation/spelech/` directory.
3. Select your calibrated battery sensor, your desired low threshold (default $20\%$), and your mobile app device to receive notifications.

---

## 🛠️ Architecture

For an in-depth breakdown of the decoupled engine architecture and data flow, see [ARCHITECTURE.md](ARCHITECTURE.md) and our development guidelines in [AGENTS.md](AGENTS.md).

```
custom_components/shade_complete/
├── __init__.py           # Integration lifecycle, setup, and services
├── const.py              # Domain constants, defaults, and attributes
├── device.py             # Device Registry co-location resolver
├── cover.py              # SmartTrackingShadeCover, TiltCoverEntity, GroupShadeCover
├── sensor.py             # CalibratedBatterySensor
├── config_flow.py        # UI Config Flow and dynamic Options Flow
├── engine/
│   ├── sun_engine.py      # Pure domain solar vector calculations
│   ├── battery_engine.py  # Pure domain battery filtering & online 0-100 learning
│   └── schedule_engine.py # Pure domain automated closing & opening scheduler
├── translations/
│   └── en.json           # Complete English UI strings
└── brand/
    ├── icon.png          # High-resolution integration icon
    └── logo.png          # High-resolution integration logo
```

---

## 📥 Installation

### Method 1: HACS (Recommended)
1. Open **HACS** in your Home Assistant dashboard.
2. Navigate to **Integrations** > Three dots menu (top right) > **Custom repositories**.
3. Enter `https://github.com/spelech/ha-shade-complete` and select Category: **Integration**.
4. Click **Add**, find **Shade Complete**, and click **Download**.
5. Restart Home Assistant.

### Method 2: Manual Installation
1. Clone or download this repository.
2. Copy the `custom_components/shade_complete` directory into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Shade Complete**.
3. Choose your configuration mode:
   - **Smart Sun Tracking Shade**: Complete package with solar tracking, schedule, tilt intercept, and battery calibration.
   - **Virtual Tilt Entity Only**: Creates a tilt cover mapped to physical tilt.
   - **Synchronized Shade Group**: Aggregates multiple shades with optional sun tracking and scheduling.
4. Fill in your parameters using the UI form.
5. You can re-tune angles, thresholds, auto-open/close times, tilt interception, or battery parameters at any time via **Configure** on the integration card!

---

## 🛎️ Services

### `shade_complete.calibrate_battery`
Manually seed or override the learned 0–100% calibration bounds for a battery sensor:
```yaml
service: shade_complete.calibrate_battery
data:
  entity_id: sensor.living_room_shade_battery
  min_val: 6.4
  max_val: 8.4
```

### `shade_complete.reset_manual_override`
Clear an active manual override lock and immediately resume automatic solar tracking:
```yaml
service: shade_complete.reset_manual_override
data:
  entity_id: cover.living_room_shade
```

### `shade_complete.trigger_auto_close`
Immediately invoke the evening closing routine:
```yaml
service: shade_complete.trigger_auto_close
data:
  entity_id: cover.living_room_shade
```

### `shade_complete.trigger_auto_open`
Immediately invoke the morning opening routine:
```yaml
service: shade_complete.trigger_auto_open
data:
  entity_id: cover.living_room_shade
```

---

## 🧪 Development & Quality Gates

This project enforces strict 4-stage CI quality gates as defined by our engineering toolbelt:

```bash
# Run release and link integrity check
python3 scripts/verify_release.py --skip-tests --ci

# Run Ruff linter and formatter
uv run ruff check .
uv run ruff format --check .

# Run test suite with strict coverage enforcement (>= 80%)
uv run pytest --cov=custom_components/shade_complete --cov-fail-under=80 -v
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright &copy; 2026 Steven T. Pelech.
