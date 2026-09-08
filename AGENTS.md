# 🤖 ha-shade-complete AGENTS.md

Architectural guidelines, execution rules, and domain standards for AI coding assistants working on the `ha-shade-complete` integration.

---

## 🤝 1. Collaboration & Workflow Discipline

1. **Feature Branching**: All changes must start on a feature branch off `develop` (`feat/*`, `fix/*`). Never push directly to `main` or `develop`.
2. **Conventional Commits**: Enforce standard commit prefixes:
   - `feat:` New user-facing functionality or entities
   - `fix:` Bug fixes or algorithm corrections
   - `test:` Test additions or harness modifications
   - `docs:` Documentation or architectural updates
   - `chore:` Dependency or build system updates
3. **CI Gates**: Every PR must pass all 4 CI gates (Integrity, Ruff lint/format, Pytest with >=80% coverage, CodeQL).

---

## 🏛️ 2. Architectural Design & Boundaries

1. **Engine Decomposition (Single Responsibility Principle)**:
   - Core mathematical and state-machine logic (sun calculation, battery calibration, closing scheduler) MUST remain decoupled from Home Assistant entity lifecycles.
   - Algorithms live in `custom_components/shade_complete/engine/` and must be testable as pure Python classes without requiring a running Home Assistant instance.
2. **Device Registry Cohabitation**:
   - Helper entities (virtual tilt, calibrated battery, tracking sensors) must look up the target cover's `device_id` in the `entity_registry` and bind directly to its physical device via `DeviceInfo(identifiers=..., connections=...)`.
   - Never create duplicate orphaned devices for physical shades that already have a device card in Home Assistant.
3. **Robust State Recovery**:
   - Restore previous positions, learned battery calibration bounds, and override states across Home Assistant restarts using `RestoreEntity` or config entry options.
4. **Resilient Calibration**:
   - Battery readings must be filtered against transient voltage drops caused by motor movement. Outlier readings during active movement should be discarded or de-weighted.

---

## 💻 3. Python Standards

- **Python Version**: >=3.12 (Strict typing, dataclasses, async/await).
- **Linter & Formatter**: `ruff` with line length 100.
- **Test Runner**: `pytest` with `pytest-asyncio` and `pytest-cov`. Maintain >=80% branch and line coverage.
