# HFM Enhancement Plan: Multi-User, Applicators, Weather & Multi-Paddock

**Version:** 2.0.0
**Status:** Complete
**Date:** 2026-02-09

---

## Overview

This document details the enhancement of the Hey Farmer Module (HFM) to support:

1. **Multi-user simultaneous data entry** via per-device draft storage
2. **Applicator management** with denormalized attributes in events
3. **Weather data capture** from BOM integration
4. **Multi-farm/multi-paddock selection** with record expansion

---

## Current State

- HFM v1.0.0-rc.1 uses shared input helpers for wizard state
- Single paddock per event
- No applicator tracking
- No weather capture
- No time-of-application tracking

---

## 1. Per-Device Draft Storage

### 1.1 Architecture

```
/config/local_data/hfm/
├── config.json           # Module configuration
├── applicators.json      # NEW: Applicator definitions
├── events.json           # Confirmed events
└── drafts/               # NEW: Per-device wizard state
    ├── <device_id>.json
    └── ...
```

### 1.2 Draft Schema

```json
{
  "device_id": "browser_abc123",
  "user_name": "John",
  "wizard_step": 3,
  "started_at": "2026-02-09T10:30:00",
  "updated_at": "2026-02-09T10:45:00",
  "data": {
    "event_type": "chemical",
    "date": "2026-02-09",
    "start_time": "06:30",
    "duration_minutes": 90,
    "farm_id": "farm_1",
    "paddocks": ["sw5", "sw4_e", "w17"],
    "products": [
      {
        "product_id": "prod_001",
        "product_name": "Roundup PowerMax",
        "rate": 2.5,
        "rate_unit": "L/ha"
      }
    ],
    "applicator_id": "app_red_boom",
    "notes": ""
  }
}
```

### 1.3 Backend Commands

| Command | Arguments | Purpose |
|---------|-----------|---------|
| `load_draft` | `--device-id` | Get or create draft for device |
| `update_draft` | `--device-id --data` | Update draft fields (JSON) |
| `clear_draft` | `--device-id` | Delete draft (abandon) |
| `submit_draft` | `--device-id` | Convert draft to event(s) |
| `cleanup_drafts` | `--max-age-hours 24` | Remove stale drafts |

### 1.4 Sensor Changes

**New sensor:** `sensor.hfm_drafts`

```yaml
sensor:
  - platform: command_line
    name: hfm_drafts
    command: "python3 /config/PaddiSense/hfm/python/hfm_drafts_sensor.py"
    scan_interval: 10
    value_template: "{{ value_json.draft_count }}"
    json_attributes:
      - drafts
      - last_updated
```

Attributes expose all active drafts keyed by device_id for dashboard access.

### 1.5 Device Identification

Using `browser_mod` integration to get unique browser ID:

```yaml
# On dashboard load, capture device ID
automation:
  - alias: HFM Capture Device ID
    trigger:
      - platform: event
        event_type: browser_mod_connected
    action:
      - service: shell_command.hfm_load_draft
        data:
          device_id: "{{ trigger.event.data.browser_id }}"
```

---

## 2. Applicator Management

### 2.1 Applicator Data Structure

**File:** `/config/local_data/hfm/applicators.json`

```json
{
  "version": "1.0.0",
  "applicators": [
    {
      "id": "app_red_boom",
      "name": "Red Boom",
      "type": "boom_spray",
      "active": true,
      "attributes": {
        "tank_size_l": 3000,
        "nozzle_type": "TeeJet XR110-02",
        "nozzle_spacing_mm": 500,
        "spray_width_m": 24,
        "operating_pressure_bar": 3.0,
        "water_rate_l_ha": 100,
        "vehicle": "Case Puma 185",
        "calibration_date": "2026-01-15",
        "notes": "Primary sprayer"
      },
      "created": "2026-01-10T08:00:00",
      "modified": "2026-02-01T14:30:00"
    }
  ],
  "attribute_templates": {
    "boom_spray": {
      "tank_size_l": {"label": "Tank Size", "unit": "L", "type": "number"},
      "nozzle_type": {"label": "Nozzle Type", "type": "text"},
      "nozzle_spacing_mm": {"label": "Nozzle Spacing", "unit": "mm", "type": "number"},
      "spray_width_m": {"label": "Spray Width", "unit": "m", "type": "number"},
      "operating_pressure_bar": {"label": "Operating Pressure", "unit": "bar", "type": "number"},
      "water_rate_l_ha": {"label": "Water Rate", "unit": "L/ha", "type": "number"},
      "vehicle": {"label": "Vehicle", "type": "text"},
      "calibration_date": {"label": "Last Calibration", "type": "date"},
      "notes": {"label": "Notes", "type": "text"}
    },
    "broadcast": {
      "capacity_t": {"label": "Capacity", "unit": "t", "type": "number"},
      "spread_width_m": {"label": "Spread Width", "unit": "m", "type": "number"},
      "spinner_type": {"label": "Spinner Type", "type": "text"},
      "vehicle": {"label": "Vehicle", "type": "text"},
      "calibration_date": {"label": "Last Calibration", "type": "date"},
      "notes": {"label": "Notes", "type": "text"}
    },
    "aerial": {
      "aircraft_type": {"label": "Aircraft Type", "type": "text"},
      "tank_size_l": {"label": "Tank Size", "unit": "L", "type": "number"},
      "swath_width_m": {"label": "Swath Width", "unit": "m", "type": "number"},
      "operator_name": {"label": "Operator/Company", "type": "text"},
      "licence_number": {"label": "Licence Number", "type": "text"},
      "notes": {"label": "Notes", "type": "text"}
    },
    "fertigation": {
      "system_name": {"label": "System Name", "type": "text"},
      "injection_rate_l_hr": {"label": "Injection Rate", "unit": "L/hr", "type": "number"},
      "tank_size_l": {"label": "Tank Size", "unit": "L", "type": "number"},
      "notes": {"label": "Notes", "type": "text"}
    }
  },
  "modified": "2026-02-09T10:00:00"
}
```

### 2.2 Backend Commands

| Command | Arguments | Purpose |
|---------|-----------|---------|
| `add_applicator` | `--name --type --attributes` | Create new applicator |
| `edit_applicator` | `--id --name --type --attributes` | Update applicator |
| `delete_applicator` | `--id` | Remove applicator (soft delete) |
| `list_applicators` | `--active-only` | Get applicator list |

### 2.3 Event Storage (Denormalized)

When saved, applicator snapshot is embedded:

```json
{
  "id": "evt_abc123",
  "applicator": {
    "id": "app_red_boom",
    "name": "Red Boom",
    "type": "boom_spray",
    "snapshot_at": "2026-02-09T06:30:00",
    "attributes": {
      "tank_size_l": 3000,
      "spray_width_m": 24,
      "water_rate_l_ha": 100,
      "nozzle_type": "TeeJet XR110-02",
      "vehicle": "Case Puma 185"
    }
  }
}
```

### 2.4 UI: Applicator Settings

New view at `/hfm-heyfarm/hfm-applicators`:

- List all applicators with key attributes
- Add/Edit form with type-specific fields
- Active/Inactive toggle
- Delete with confirmation

---

## 3. Weather Data Capture

### 3.1 BOM Entity Mapping

**Available sensors (confirmed):**

| Purpose | Entity ID | Unit |
|---------|-----------|------|
| Wind Speed | `sensor.bom_wind_speed_kilometre` | km/h |
| Wind Direction | `sensor.bom_wind_direction` | degrees |
| Wind Gust | `sensor.bom_gust_speed_kilometre` | km/h |
| Temperature | `sensor.bom_temp` | °C |
| Humidity | `sensor.bom_humidity` | % |

**Configuration in config.json:**

```json
{
  "weather_entities": {
    "wind_speed": "sensor.bom_wind_speed_kilometre",
    "wind_direction": "sensor.bom_wind_direction",
    "wind_gust": "sensor.bom_gust_speed_kilometre",
    "temperature": "sensor.bom_temp",
    "humidity": "sensor.bom_humidity"
  }
}
```

### 3.2 Time Capture Fields

For chemical/nutrient events, capture:

| Field | Format | Example |
|-------|--------|---------|
| `date` | YYYY-MM-DD | 2026-02-09 |
| `start_time` | HH:MM | 06:30 |
| `duration_minutes` | integer | 90 |

End time calculated: `start_time + duration_minutes`

### 3.3 Weather Snapshot Logic

**On submit_draft:**

1. Check if date is today
2. If today and start_time within last 2 hours → use current sensor values
3. If today but earlier → query HA recorder history for that time
4. If yesterday/past → query HA recorder (if within retention) or mark as "unavailable"

**Python implementation:**

```python
def capture_weather(hass_api, config, event_date, start_time):
    """Capture weather conditions at application time."""
    entities = config.get("weather_entities", {})

    # Build timestamp
    event_datetime = datetime.strptime(f"{event_date} {start_time}", "%Y-%m-%d %H:%M")
    now = datetime.now()

    weather = {
        "source": "bom",
        "captured_at": now.isoformat(),
        "event_time": event_datetime.isoformat()
    }

    # If recent (within 2 hours), use current values
    if (now - event_datetime).total_seconds() < 7200:
        weather["wind_speed_kmh"] = get_state(entities["wind_speed"])
        weather["wind_direction_deg"] = get_state(entities["wind_direction"])
        weather["wind_gust_kmh"] = get_state(entities["wind_gust"])
        weather["temperature_c"] = get_state(entities["temperature"])
        weather["humidity_pct"] = get_state(entities["humidity"])
        weather["data_source"] = "current"
    else:
        # Query history API
        history = query_history(entities, event_datetime)
        if history:
            weather.update(history)
            weather["data_source"] = "history"
        else:
            weather["data_source"] = "unavailable"

    # Add cardinal direction
    if weather.get("wind_direction_deg"):
        weather["wind_direction"] = degrees_to_cardinal(weather["wind_direction_deg"])

    return weather
```

### 3.4 Event Storage

```json
{
  "id": "evt_abc123",
  "application_timing": {
    "date": "2026-02-09",
    "start_time": "06:30",
    "duration_minutes": 90,
    "end_time": "08:00"
  },
  "weather": {
    "source": "bom",
    "data_source": "current",
    "captured_at": "2026-02-09T08:15:00",
    "event_time": "2026-02-09T06:30:00",
    "wind_speed_kmh": 8,
    "wind_direction_deg": 135,
    "wind_direction": "SE",
    "wind_gust_kmh": 12,
    "temperature_c": 18,
    "humidity_pct": 72
  }
}
```

---

## 4. Multi-Farm & Multi-Paddock Selection

### 4.1 Farm Registry Integration

**Confirmed structure:**

- Multi-farm supported via `farm_id` on paddocks
- Current farms: `farm_1` (RRAPL), `states_input_text_registry_new` (Peter)
- 7 paddocks on farm_1
- `area_ha` field supported but not yet populated

### 4.2 Selection UI Flow

```
STEP 3: WHERE

┌─────────────────────────────────────────────────────────┐
│  SELECT FARM                                             │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │    RRAPL     │  │    Peter     │                     │
│  │      ✓       │  │              │                     │
│  └──────────────┘  └──────────────┘                     │
├─────────────────────────────────────────────────────────┤
│  SELECT PADDOCKS                    [Select All] [Clear]│
│                                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │  SW4E  │ │  SW4W  │ │  SW5   │ │  W17   │           │
│  │        │ │   ✓    │ │   ✓    │ │   ✓    │           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
│  ┌────────┐ ┌────────┐ ┌────────┐                      │
│  │  W18   │ │  W19   │ │ Test   │                      │
│  │        │ │        │ │        │                      │
│  └────────┘ └────────┘ └────────┘                      │
│                                                          │
│  Selected: 3 paddocks                                   │
└─────────────────────────────────────────────────────────┘
```

### 4.3 Draft Structure

```json
{
  "data": {
    "farm_id": "farm_1",
    "paddocks": ["sw4_w", "sw5", "w17"]
  }
}
```

### 4.4 Record Expansion

On `submit_draft`, if multiple paddocks selected:

**Input:** 1 draft with 3 paddocks
**Output:** 3 event records in events.json

```json
{
  "events": [
    {
      "id": "evt_a1b2c3_001",
      "batch_id": "batch_x9y8z7",
      "batch_index": 1,
      "batch_total": 3,
      "farm": {"id": "farm_1", "name": "RRAPL"},
      "paddock": {"id": "sw4_w", "name": "SW4 West"},
      ...
    },
    {
      "id": "evt_a1b2c3_002",
      "batch_id": "batch_x9y8z7",
      "batch_index": 2,
      "batch_total": 3,
      "farm": {"id": "farm_1", "name": "RRAPL"},
      "paddock": {"id": "sw5", "name": "SW5"},
      ...
    },
    {
      "id": "evt_a1b2c3_003",
      "batch_id": "batch_x9y8z7",
      "batch_index": 3,
      "batch_total": 3,
      "farm": {"id": "farm_1", "name": "RRAPL"},
      "paddock": {"id": "w17", "name": "W17"},
      ...
    }
  ]
}
```

**batch_id** enables:
- Grouped display: "Applied to 3 paddocks"
- Bulk operations (edit all, delete all)
- Export grouping

---

## 5. Complete Event Schema v2.0

```json
{
  "id": "evt_a1b2c3_001",
  "schema_version": "2.0.0",

  "batch_id": "batch_x9y8z7",
  "batch_index": 1,
  "batch_total": 3,

  "event_type": "chemical",

  "farm": {
    "id": "farm_1",
    "name": "RRAPL"
  },

  "paddock": {
    "id": "sw5",
    "name": "SW5",
    "area_ha": null
  },

  "application_timing": {
    "date": "2026-02-09",
    "start_time": "06:30",
    "duration_minutes": 90,
    "end_time": "08:00"
  },

  "products": [
    {
      "id": "prod_roundup",
      "name": "Roundup PowerMax",
      "category": "Chemical",
      "rate": 2.5,
      "rate_unit": "L/ha",
      "total_applied": null,
      "total_unit": "L"
    }
  ],

  "applicator": {
    "id": "app_red_boom",
    "name": "Red Boom",
    "type": "boom_spray",
    "snapshot_at": "2026-02-09T06:30:00",
    "attributes": {
      "tank_size_l": 3000,
      "spray_width_m": 24,
      "water_rate_l_ha": 100,
      "nozzle_type": "TeeJet XR110-02",
      "vehicle": "Case Puma 185"
    }
  },

  "weather": {
    "source": "bom",
    "data_source": "current",
    "captured_at": "2026-02-09T08:15:00",
    "event_time": "2026-02-09T06:30:00",
    "wind_speed_kmh": 8,
    "wind_direction_deg": 135,
    "wind_direction": "SE",
    "wind_gust_kmh": 12,
    "temperature_c": 18,
    "humidity_pct": 72
  },

  "application_method": "boom_spray",
  "crop_stage": null,
  "irrigation_type": null,

  "operator": {
    "device_id": "browser_abc123",
    "user_name": "John"
  },

  "notes": "Pre-plant knockdown",

  "confirmation_status": "confirmed",
  "recorded_at": "2026-02-09T08:15:00",
  "modified_at": null
}
```

---

## 6. Updated Wizard Flow

```
STEP 1: EVENT TYPE
├── Nutrient | Chemical | Irrigation | Crop Stage
└── Sets available fields for subsequent steps

STEP 2: WHEN
├── Date: Today / Yesterday / Specific Date
├── Start Time: [HH:MM] picker (Nutrient/Chemical only)
└── Duration: [minutes] dropdown (Nutrient/Chemical only)

STEP 3: WHERE
├── Farm: [toggle buttons if multiple farms]
├── Paddocks: [multi-select toggle grid]
└── Summary: "3 paddocks selected"

STEP 4: WHAT
├── Products: 1-6 slots with rate/unit (Nutrient/Chemical)
├── Applicator: [dropdown] (Nutrient/Chemical)
├── Irrigation Type: [dropdown] (Irrigation only)
└── Crop Stage: [dropdown] (Crop Stage only)

STEP 5: CONDITIONS (Nutrient/Chemical only)
├── Weather preview (auto-populated)
├── Wind: 8 km/h SE, Gusts: 12 km/h
├── Temp: 18°C, Humidity: 72%
└── [Refresh] button if data stale

STEP 6: NOTES
└── Free text (255 chars)

STEP 7: REVIEW & SUBMIT
├── Full summary of all fields
├── "This will create 3 records" (if multi-paddock)
└── [Submit] button
```

---

## 7. Implementation Phases

### Phase 1: Draft System Foundation
**Files to create/modify:**
- `hfm_backend.py` - Add draft CRUD commands
- `hfm_drafts_sensor.py` - New sensor for draft state
- `package.yaml` - Add shell commands and sensor
- Create `/config/local_data/hfm/drafts/` directory

**Deliverables:**
- [x] `load_draft` command
- [x] `update_draft` command
- [x] `clear_draft` command
- [x] `submit_draft` command (basic, single paddock)
- [x] `cleanup_drafts` command
- [x] Drafts sensor with all active drafts
- [x] Automation for 24-hour cleanup

### Phase 2: Applicator Management
**Files to create/modify:**
- `hfm_backend.py` - Add applicator CRUD
- `applicators.json` - Initial structure with templates
- `package.yaml` - Add shell commands
- `views.yaml` - New applicator settings view

**Deliverables:**
- [x] Applicator data structure
- [x] `add_applicator` command
- [x] `edit_applicator` command
- [x] `delete_applicator` command
- [x] Applicator list in sensor
- [x] Settings UI for applicator management

### Phase 3: Weather Integration
**Files to modify:**
- `hfm_backend.py` - Add weather capture
- `config.json` - Add weather entity mapping
- `hfm_sensor.py` - Expose weather config

**Deliverables:**
- [x] Weather entity configuration
- [x] Current weather capture function
- [x] Historical weather query (HA recorder)
- [x] Weather snapshot in events
- [x] Step 5 UI for weather display

### Phase 4: Multi-Paddock & Record Expansion
**Files to modify:**
- `hfm_backend.py` - Multi-paddock submit logic
- `views.yaml` - Farm/paddock selection UI

**Deliverables:**
- [x] Farm selection in draft
- [x] Multi-paddock selection in draft
- [x] Record expansion on submit
- [x] Batch ID linking
- [x] Multi-select toggle UI
- [x] History view batch grouping

### Phase 5: Dashboard Refactor
**Files to modify:**
- `views.yaml` - Complete wizard rewrite
- `package.yaml` - Remove old input helpers

**Deliverables:**
- [x] Device ID capture on load
- [x] All wizard steps reading from draft sensor
- [x] All interactions calling update_draft
- [x] Hybrid mode supporting both draft and legacy paths
- [x] 6-step wizard UI with multi-paddock support

### Phase 6: Migration & Testing
**Deliverables:**
- [x] Migration script for existing events
- [x] Multi-device concurrent testing
- [x] Export verification with new fields
- [x] VERSION bump to 2.0.0

---

## 8. Retained Input Helpers

Only these helpers remain after refactor:

| Helper | Purpose |
|--------|---------|
| `input_text.hfm_current_device` | Tracks active device ID |

All other form state moves to draft JSON files.

---

## 9. Shell Commands Summary

### Draft Operations
```yaml
hfm_load_draft: "python3 .../hfm_backend.py load_draft --device-id '{{ device_id }}'"
hfm_update_draft: "python3 .../hfm_backend.py update_draft --device-id '{{ device_id }}' --data '{{ data }}'"
hfm_clear_draft: "python3 .../hfm_backend.py clear_draft --device-id '{{ device_id }}'"
hfm_submit_draft: "python3 .../hfm_backend.py submit_draft --device-id '{{ device_id }}'"
hfm_cleanup_drafts: "python3 .../hfm_backend.py cleanup_drafts --max-age-hours 24"
```

### Applicator Operations
```yaml
hfm_add_applicator: "python3 .../hfm_backend.py add_applicator --name '{{ name }}' --type '{{ type }}' --attributes '{{ attributes }}'"
hfm_edit_applicator: "python3 .../hfm_backend.py edit_applicator --id '{{ id }}' --name '{{ name }}' --attributes '{{ attributes }}'"
hfm_delete_applicator: "python3 .../hfm_backend.py delete_applicator --id '{{ id }}'"
```

### Existing (Retained)
```yaml
hfm_init: "python3 .../hfm_backend.py init"
hfm_export: "python3 .../hfm_backend.py export"
hfm_confirm_event: "python3 .../hfm_backend.py confirm_event --id '{{ id }}'"
hfm_delete_event: "python3 .../hfm_backend.py delete_event --id '{{ id }}'"
```

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| browser_mod not installed | Fallback to manual device selection |
| BOM sensors unavailable | Mark weather as "unavailable", don't block submit |
| Draft corruption | Validation on load, auto-clear invalid drafts |
| Concurrent submit race | File locking in Python backend |
| Large paddock count UI | Scrollable grid with search filter |

---

## Appendix A: Migration Notes

### Event Schema Migration (v1 → v2)

Existing events need:
- Add `schema_version: "2.0.0"`
- Wrap paddock in object: `"paddock": "sw5"` → `"paddock": {"id": "sw5", "name": "SW5"}`
- Add farm object from registry lookup
- Add `batch_id: null`, `batch_index: null`, `batch_total: null`
- Add `application_timing: null` (for non-chemical/nutrient)
- Add `weather: null`
- Add `applicator: null`
- Rename `recorded_by_device` → `operator.device_id`

Script will be provided in Phase 6.
