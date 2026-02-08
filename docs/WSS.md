# WSS - Worker Safety System

**Version:** 1.1.0-dev
**Status:** Implemented
**Dashboard:** `wss-safety`

## Overview

The Worker Safety System monitors worker movement via the Home Assistant Companion App, providing stationary detection and configurable escalation alerts for farm worker safety.

## Features

- **Event-Driven Detection**: Uses native HA template triggers with `for:` conditions instead of polling
- **Timer-Based Escalation**: Survives HA restarts via `timer.wss_escalation_timer` with `restore: true`
- **4-Stage Escalation Chain**: User -> Reminder -> Primary -> Secondary
- **Configurable Timing**: All thresholds adjustable via UI
- **Zone Configuration**: Toggle zones as monitored/away
- **User Discovery**: Auto-discover from HA Person entities
- **Arrival/Departure Notifications**: Primary notified when workers enter/leave
- **Daily Summary**: End-of-day summary at configurable time
- **Legacy Import**: Migrate data from old safety system

## File Structure

```
/config/PaddiSense/wss/
├── VERSION                          # 1.0.0-dev
├── package.yaml                     # Main HA package
├── python/
│   ├── wss_backend.py              # Write operations
│   └── wss_sensor.py               # Sensor output
└── dashboards/
    └── views.yaml                  # Status + Config views

/config/local_data/wss/
├── config.json                     # Timing, roles, zones
└── users.json                      # Discovered users
```

## Entities

### Sensors
| Entity | Purpose |
|--------|---------|
| `sensor.wss_data` | Main data sensor with all attributes |
| `sensor.wss_module_version` | Version from VERSION file |
| `sensor.paddisense_wss_status` | Display status ("All Clear", "Alert Active") |
| `sensor.wss_movement_trigger` | Tracks person state changes |

### Input Helpers
| Entity | Purpose |
|--------|---------|
| `input_boolean.wss_enabled` | System on/off |
| `input_select.wss_primary_user` | Primary contact dropdown |
| `input_select.wss_secondary_user` | Secondary contact dropdown |
| `input_select.wss_selected_zone` | Zone selector for configuration |
| `input_number.wss_stationary_threshold` | Minutes before alert (5-60) |
| `input_number.wss_first_reminder` | Minutes to 2nd alert (1-30) |
| `input_number.wss_primary_escalation` | Minutes to primary (1-30) |
| `input_number.wss_secondary_escalation` | Minutes to secondary (5-60) |
| `input_datetime.wss_working_hours_start` | Working hours start time |
| `input_datetime.wss_working_hours_end` | Working hours end / daily summary time |
| `input_number.wss_escalation_stage` | Current stage (0-4) |
| `input_text.wss_escalation_user` | User ID in active alert |

### Timer
| Entity | Purpose |
|--------|---------|
| `timer.wss_escalation_timer` | Main escalation timer (survives restarts) |

## Escalation Flow

```
User stationary in monitored zone
         │
         ▼ (stationary_threshold: default 15 min)
┌─────────────────────────────┐
│ STAGE 1: Alert to User      │ ← Actionable: "I'm Okay" / "Need Help"
└─────────────────────────────┘
         │
         ▼ (+first_reminder: default 5 min)
┌─────────────────────────────┐
│ STAGE 2: Second Alert       │ ← More urgent notification
└─────────────────────────────┘
         │
         ▼ (+primary_escalation: default 5 min)
┌─────────────────────────────┐
│ STAGE 3: Alert to Primary   │ ← With location map, "Alert Resolved"
└─────────────────────────────┘
         │
         ▼ (+secondary_escalation: default 10 min)
┌─────────────────────────────┐
│ STAGE 4: Alert to Secondary │ ← Continues every 5 min until reset
└─────────────────────────────┘
```

## Scripts

### System
- `script.wss_init_system` - Initialize config/users files
- `script.wss_refresh_data` - Force sensor update
- `script.wss_discover_users` - Scan Person entities for Companion App users

### User Management
- `script.wss_toggle_user` - Enable/disable user monitoring

### Zone Configuration
- `script.wss_discover_zones` - Discover zones from HA
- `script.wss_toggle_zone_monitored` - Toggle zone monitoring flag (with zone_id)
- `script.wss_toggle_zone_away` - Toggle zone away flag (with zone_id)
- `script.wss_toggle_selected_zone_monitored` - Toggle selected zone monitoring
- `script.wss_toggle_selected_zone_away` - Toggle selected zone away

### Escalation
- `script.wss_start_escalation` - Begin escalation for a user
- `script.wss_escalation_next_stage` - Progress to next stage
- `script.wss_reset_alert` - Clear active alert

### Dashboard Actions
- `script.wss_check_in_button` - User check-in
- `script.wss_help_button` - Request help (notifies all contacts)

### Config Sync
- `script.wss_sync_timing_to_config` - Save timing values to config.json
- `script.wss_sync_working_hours_to_config` - Save working hours

### Data Management
- `script.wss_export_data` - Export to backup file
- `script.wss_import_legacy` - Import from old safety system
- `script.wss_reset_data` - Reset all data (requires confirmation)

## Backend Commands

The Python backend (`wss_backend.py`) supports:

```bash
# System
python3 wss_backend.py init
python3 wss_backend.py status

# Users
python3 wss_backend.py discover_users --users_json '[...]'
python3 wss_backend.py set_user_enabled --user_id "user_xxx" --enabled true
python3 wss_backend.py set_user_track_external --user_id "user_xxx" --track_external true

# Zones
python3 wss_backend.py set_zone_config --zone_id "zone.xxx" --monitored true --away false
python3 wss_backend.py toggle_zone_monitored --zone_id "zone.xxx"
python3 wss_backend.py toggle_zone_away --zone_id "zone.xxx"

# Roles
python3 wss_backend.py set_role --role primary --user_id "user_xxx"
python3 wss_backend.py remove_admin --user_id "user_xxx"

# Timing
python3 wss_backend.py set_timing --stationary_threshold 15 --first_reminder 5
python3 wss_backend.py set_working_hours --end_time "17:00" --workdays "mon,tue,wed,thu,fri"

# Data
python3 wss_backend.py export
python3 wss_backend.py import_legacy
python3 wss_backend.py reset --token CONFIRM_RESET
```

## Data Schemas

### config.json
```json
{
  "version": "1.0.0",
  "timing": {
    "stationary_threshold_minutes": 15,
    "first_reminder_minutes": 5,
    "primary_escalation_minutes": 5,
    "secondary_escalation_minutes": 10
  },
  "working_hours": {
    "end_time": "17:00",
    "workdays": ["mon", "tue", "wed", "thu", "fri"]
  },
  "roles": {
    "primary": "user_xxx",
    "secondary": "user_yyy",
    "admins": ["user_xxx"]
  },
  "zones": {
    "zone.old_coree": {"monitored": true, "away": false, "name": "Old Coree"},
    "zone.home": {"monitored": false, "away": true, "name": "Home"}
  }
}
```

### users.json
```json
{
  "users": {
    "user_xxx": {
      "id": "user_xxx",
      "person_id": "person.john_doe",
      "username": "John Doe",
      "tracker_id": "device_tracker.johns_iphone",
      "activity_id": "sensor.johns_iphone_activity",
      "notify_id": "notify.mobile_app_johns_iphone",
      "enabled": true,
      "track_external": false
    }
  }
}
```

## Dashboard

### Status View (All Users)
- Check-in / Need Help buttons
- Worker status grid (color-coded cards)
- Location map with all workers and zones

### Config View (Admins)
- System enable toggle
- Role assignment dropdowns
- Timing threshold sliders
- Working hours configuration
- Zone toggle lists (monitored/away)
- User enable/disable list
- Data management (export, import, reset)

## Activation

1. Add to HA packages:
   ```yaml
   homeassistant:
     packages:
       wss: !include PaddiSense/wss/package.yaml
   ```

2. Restart Home Assistant

3. Initialize: `script.wss_init_system`

4. Discover users: `script.wss_discover_users`

5. Import legacy data (optional): `script.wss_import_legacy`

6. Configure via dashboard (set contacts, enable users, configure zones)

7. Enable: Turn on `input_boolean.wss_enabled`

## Zone Concepts

Zones have two independent flags:

| Flag | Meaning | Example |
|------|---------|---------|
| **Monitored** | Stationary alerts trigger in this zone | Paddocks, fields, sheds |
| **Away** | Worker is off-farm (shows grey "Away" status) | Home, town |

Status card logic:
- **Away (grey)**: Worker in an away zone or unknown location
- **Stationary (orange)**: Worker stationary in a monitored zone
- **Active (green)**: Worker in any work zone (office, paddocks, etc.)

## Requirements

- Home Assistant Companion App on worker devices
- Person entities linked to device trackers
- Activity sensors from Companion App (for stationary detection)
- HACS frontend cards:
  - `lovelace-auto-entities` - Dynamic entity filtering
  - `button-card` - Custom styled buttons
  - `lovelace-card-mod` - Card styling

## Migration from Old System

The old safety system data can be imported via `script.wss_import_legacy` which reads:
- `/config/PaddiSense/reference/old safety system files/safety_system_users (1).json`
- `/config/PaddiSense/reference/old safety system files/safety_system_zone_config (1).json`

---

*Implemented: 2026-02-08*
