# M2 — Localization Module

## Overview

M2 implements the localization and re-localization engine for SurakshaLander.

It:

* Simulates odometry drift.
* Maintains the rover pose and covariance.
* Performs crater-based pose correction.
* Uses RANSAC matching against a database of 100 lunar craters.
* Tracks localization uncertainty and relocalization events.

## How to Run / Test

From the project root:

```bash
cd M2
python tests/test_localizer.py
```

Expected output:

```text
test_correct_fails_without_enough_craters ... ok
test_correct_fallback ... ok
test_correct_with_real_craters ... ok
test_initial_state ... ok
test_predict_drift ... ok
test_relocalization_count_increments ... ok
test_uncertainty_levels ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.210s

OK
```

## Core API Reference

### 1. `predict(dt, odometry)`

Updates the rover pose and grows covariance based on odometry.

**Arguments:**

* `dt` — time step in seconds (`float`)
* `odometry` — dictionary:

```python
{
    "velocity": float,
    "angular_velocity": float
}
```

**Effect:**

* Updates the internal rover pose.
* Increases covariance to simulate odometry drift.

---

### 2. `correct(detected_craters, use_fallback=False, fallback_craters=None)`

Performs RANSAC-based crater matching against the crater database and corrects the rover pose.

**Arguments:**

* `detected_craters` — list of detected craters:

```python
[
    {
        "x": float,
        "y": float,
        "radius": float,
        "confidence": float
    },
    ...
]
```

* `use_fallback` — if `True`, uses fallback craters when detection fails.
* `fallback_craters` — optional fallback crater list:

```python
[
    {"x": float, "y": float},
    ...
]
```

**Returns:**

* `True` — correction was successfully applied.
* `False` — correction could not be applied.

---

### 3. `get_pose()`

**PRD-contract method (Table 8).** Returns the plain tuple M4/M5 expect per the
locked interface — nothing more.

**Returns:**

```python
(x, y, heading, covariance)
```

* `x`, `y` — local position in meters (floats).
* `heading` — rover heading in radians (float).
* `covariance` — 3×3 pose covariance matrix, as a nested list.

---

### 4. `get_telemetry()`

**Extra method, not in the PRD contract.** Use this instead of `get_pose()`
when you also need uncertainty or re-localization stats (e.g. for the
dashboard's Telemetry/Metrics panels).

**Returns:**

```python
{
    "x": float,
    "y": float,
    "heading": float,
    "covariance": [[float, ...], [float, ...], [float, ...]],
    "uncertainty": float,
    "relocalization_count": int,
    "last_error_before": float,
    "last_error_after": float
}
```

---
### 5. `get_uncertainty_level()`

Possible values: `normal`, `caution`, `re_localizing`
(matches PRD Table 11's dashboard badges: NORMAL / CAUTION / RE-LOCALIZING)

* `normal` — uncertainty < 3 m
* `caution` — uncertainty between 3 m and 5 m
* `re_localizing` — uncertainty > 5 m

---

### 6. `set_fallback_craters(fallback_craters)`

Sets fallback craters for demo reliability.

```python
fallback_craters = [
    {"x": 1200, "y": 3400},
    {"x": 1400, "y": 3600},
    {"x": 1100, "y": 3200}
]
```

## Integration Checklist

### M3 — Perception

M3 should send detected craters to M5 in the following exact format:

```python
[
    {
        "x": 1200.0,
        "y": 3400.0,
        "radius": 50.0,
        "confidence": 0.9
    },
    ...
]
```

---

### M4 — Planning

M4 should use `get_uncertainty_level()` to adjust the costmap.

| Level      | Planning behavior                                                        |
| ---------- | ------------------------------------------------------------------------ |
| `normal`   | Use normal hazard costs.                                                 |
| `caution`  | Increase slope/roughness penalties and make the rover more conservative. |
| `re_localizing` | Force re-planning or trigger re-localization.                            |

---

### M5 — Orchestrator / Dashboard

M5 should:

1. Call `predict()` every simulation step.
2. Monitor `get_uncertainty_level()`.
3. If the level becomes `critical`, call `correct()` using M3 crater detections.
4. Stream `get_pose()` through WebSocket to the dashboard.

Example flow:

```python
localizer.predict(dt, odometry)

if localizer.get_uncertainty_level() == "re_localizing":
    localizer.correct(detected_craters)

x, y, heading, covariance = localizer.get_pose()   # PRD contract
telemetry = localizer.get_telemetry()              # richer dashboard fields
```

---

### M6 — Demo Lead

M6 should provide fallback craters in the JSON configuration.

Example:

```json
{
    "fallback_craters": [
        {"x": 1200, "y": 3400},
        {"x": 1400, "y": 3600},
        {"x": 1100, "y": 3200}
    ]
}
```

## Data Dependencies

M2 depends on:

```text
stub_data/crater_db.sqlite
```

This is M1's crater database containing 100 craters with:

* ID
* Latitude
* Longitude
* Diameter

If the database is moved, update the path in `crater_loader.py` or pass the path directly:

```python
craters = load_craters("/path/to/crater_db.sqlite")
```

## Operational Flow

The expected localization flow is:

```text
Odometry
   ↓
predict()
   ↓
Pose + covariance updated
   ↓
Check uncertainty
   ↓
┌───────────────┐
│ normal        │ → Continue normally
│ caution       │ → Planning becomes conservative
│ critical      │ → Trigger crater correction
└───────────────┘
                         ↓
                 M3 crater detections
                         ↓
                     correct()
                         ↓
                 RANSAC crater matching
                         ↓
                 Pose correction
                         ↓
             Uncertainty reduced
                         ↓
                  get_pose()
```

## Status

**Complete — All 8 unit tests passing.**

## Owner

**M2 — Localization Engine Owner**
