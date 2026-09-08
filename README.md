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

### ☀️ 1. Intelligent Solar Vector Tracking
- **Window Orientation & Field of View**: Configure your window's facing direction (N, NE, E, SE, S, SW, W, NW or custom degrees 0–360°) with customizable azimuth tolerance (half-angle FOV) and clean $360^\circ$ North wraparound.
- **Solar Elevation Mapping**: Seamlessly interpolates between your low elevation cutoff (e.g. $5^\circ$) and high elevation threshold (e.g. $40^\circ$) to dynamically keep direct glare out while preserving ambient daylight.
- **Overcast & Storm Suppression**: Monitors an optional `weather.*` entity to suppress tracking on cloudy, foggy, or rainy days, automatically opening shades to maximize natural light.
- **Arbitrated Manual Overrides**: If a user physically adjusts the shade via a wall remote or dashboard, Shade Complete yields immediately, detects the override, and automatically resumes tracking after a configurable timeout (or at sunset).
- **Travel Verification**: Automatically monitors movement duration; if motion is halted or intercepted before arrival, manual override is flagged instantly.

### 🔄 2. Virtual Tilt Projection & Device Co-Location
- Wraps any physical cover with tilt capabilities into a fully featured Cover entity that transparently maps `open`, `close`, `stop`, and `set_cover_position` directly to the underlying `open_cover_tilt`, `close_cover_tilt`, and `set_cover_tilt_position` commands.
- **Native Device Card Binding**: Inspects the Home Assistant Device Registry and binds helper entities directly to the physical shade's device card (`DeviceInfo`). Your tilt controls, sun tracking entities, and battery sensors live right beside the physical hardware!

### 🌙 3. Automated Scheduled Evening Closing
- Settable per shade or per group.
- Automatically commands shades to $0\%$ (closed) at a chosen daily clock time (e.g. `21:30:00`) or a dynamic offset from sunset.
- Re-arms automatically each day and resets daily manual overrides at night.

### 🔋 4. Adaptive Battery Intelligence & 0–100% Learning
- **Motor-Sag Rejection**: Voltage temporarily plunges when a motorized shade draws inrush current. Shade Complete inhibits calibration sampling during active motor motion, eliminating false low-battery alerts.
- **Exponential Moving Average (EMA)**: Smooths sensor noise without lag.
- **Online Bounds Learning**: Observes your battery's actual low-voltage cutoff point and full-charge peak over time, dynamically calibrating the true 0–100% scale for your specific hardware.
- **Charging Detection**: Automatically detects when the shade is plugged into a solar or USB charger and isolates charging peaks from discharge curves.

### 👥 5. Synchronized Shade Groups
- Group multiple individual shades or tilt entities into a single unified cover.
- Concurrent command execution via `asyncio.gather` for synchronized group movement.
- Computes true average position across all member shades.

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
│   └── schedule_engine.py # Pure domain automated closing scheduler
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
   - **Smart Sun Tracking Shade**: Complete package with solar tracking, schedule, and battery calibration.
   - **Virtual Tilt Entity Only**: Creates a tilt cover mapped to physical tilt.
   - **Synchronized Shade Group**: Aggregates multiple shades.
4. Fill in your parameters using the UI form.
5. You can re-tune angles, thresholds, auto-close times, or battery parameters at any time via **Configure** on the integration card!

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
