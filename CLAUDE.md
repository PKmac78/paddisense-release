# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Repository Overview

This is a Home Assistant configuration repository for a farm/agricultural operation. The system is called **PaddiSense** - a modular farm management platform with multiple packages:

- **IPM** (Inventory Product Manager) - Track chemicals, fertilisers, seeds, lubricants
- **ASM** (Asset Service Manager) - Track assets, parts, and service events
- **Weather** - Unified weather module: local Ecowitt gateway + remote API stations (up to 4 slots)
- **PWM** (Precision Water Management) - Paddock/bay irrigation control with ESPHome integration
- **WSS** (Work Safety System) - Coming soon
- **HFM** (Hey Farmer) - Coming soon

## Current System Baseline (18 January 2026)

### Home Assistant
- **Core:** 2026.1.2
- **Supervisor:** 2026.01.1
- **Operating System:** 16.3
- **Frontend:** 20260107.2

### IPM Inventory (v1.0.0)
- **Total Products:** 11
- **Categories in use:** Chemical (3), Fertiliser (2), Seed (4), Lubricant (2)
- **Active Constituents tracked:** Glyphosate, Nitrogen, Act1, Act 2
- **Locations configured:** 17
- **Transactions logged:** 21

### ASM Assets & Parts (v1.0.0)
- **Total Assets:** 2 (Case Magnum 280, Case Puma 140)
- **Total Parts:** 3 (Tyre 8960, little tyre, Big tyre rear)
- **Low Stock Alerts:** 1 (little tyre at 0 stock)
- **Service Events:** 6 recorded
- **Transactions logged:** 25
- **Configuration:** Categories (Asset, Part, Service Type) configurable via config.json

### Weather (Unified Package v2.0.0)
**Local Gateway:**
- **Data Source:** Ecowitt Gateway (ecowittgateway_1)
- **Location:** Latitude -35.5575, Elevation 180m
- **Calculated Sensors:** Delta T, Evapotranspiration (ETo), Degree Days, Cumulative Degree Days
- **Statistics Sensors:** Min/Max Temperature, Min/Max Humidity, Avg Wind Speed
- **Utility Meter:** Daily Solar Radiation (MJ/m2/day)

**Remote API Stations:**
- **Total Stations Configured:** 2
- **Station 1:** Algudgerie (IMEI: ****9168, Lat: -15.0, Elev: 2m) - Enabled
- **Station 2:** The Relm (IMEI: ****2226, Lat: -15.0, Elev: 2m) - Enabled
- **Slots Available:** 4 (2 used, 2 empty)
- **API Endpoint:** Ecowitt `/api/v3/device/info`
- **Update Interval:** 60 seconds
- **Sensors per Station:** 18 raw + 3 derived (Delta T, ETo, Degree Day)
- **Statistics:** Min/Max Temp, Min/Max Humidity, Avg Wind Speed (24hr rolling)
- **Automations:** CDD daily accumulation at 23:59:30

**Package Structure:**
- Single `weather/package.yaml` contains ALL weather functionality
- Local gateway sensors, API sensors, binary sensors consolidated under one `template:` key
- All command_line, shell_command, input helpers merged (no duplicate YAML keys)

### PWM Water Management (v1.0.0)
- **Total Paddocks:** 7 (Test Field, SW4-E, SW4-W, SW5, W17, W18, W19)
- **Total Bays:** 29 with device assignments
- **Farms Configured:** 1 (farm_1)
- **Device Types:** door, valve, spur, channel_supply
- **Named Slots:** supply_1, supply_2, drain_1, drain_2 per bay
- **Automation States:** Off, Flush, Pond, Drain, Saturate, Maintain
- **Sensor Pattern:** command_line sensor reads config.json every 30s
- **Data Structure:** Shared with future HFM module

**Special Configurations:**
- W17 B-01 has dual supply: door (supply_1) + NML spur (supply_2)
- W17 B-03 has Channel Supply on supply_2
- Test Field B-05 is last bay with drain door

## Deployment Architecture

PaddiSense uses git for distribution with per-server customization via local config files.

### Separation of Concerns
```
Repository (shared via git)          Per-Server (NOT in git)
─────────────────────────────        ─────────────────────────
PaddiSense/                          server.yaml       ← module selection + farm config
├── install.sh                       secrets.yaml      ← API keys
├── update.sh                        local_data/       ← runtime data
├── server.yaml.example              ├── ipm/
├── ipm/      (v1.0.0)               │   ├── inventory.json
├── asm/      (v1.0.0)               │   └── config.json
├── weather/  (v2.0.0)               ├── asm/
│   └── python/                      │   ├── data.json
│       ├── weather_api_backend.py   │   └── config.json
│       └── weather_api_sensor.py    ├── weather/
└── pwm/      (v1.0.0)               │   └── config.json
    └── python/                      ├── weather_api/
        ├── pwm_backend.py           │   └── config.json
        └── pwm_sensor.py            └── pwm/
                                         └── config.json
```

### New Server Deployment

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USER/paddisense.git /config/PaddiSense

# 2. Create server config (choose which modules to enable)
cp /config/PaddiSense/server.yaml.example /config/server.yaml
nano /config/server.yaml

# 3. Run installer
./PaddiSense/install.sh

# 4. Add secrets (if using weather_api)
echo 'ecowitt_app_key: "YOUR_KEY"' >> /config/secrets.yaml
echo 'ecowitt_api_key: "YOUR_KEY"' >> /config/secrets.yaml

# 5. Update configuration.yaml (installer shows exact snippet)

# 6. Restart Home Assistant and initialize each module
```

### Server Configuration (server.yaml)

Each server has its own `server.yaml` (not tracked in git):
```yaml
server:
  name: "My Farm"
  location: "Farm Location"

modules:
  ipm: true           # Inventory Product Manager
  asm: true           # Asset Service Manager
  weather: true       # Unified: local gateway + API stations

weather:
  latitude: -35.0
  elevation: 100
  # API stations require secrets.yaml: ecowitt_app_key, ecowitt_api_key
```

### Updating Servers

```bash
# Check for updates
./PaddiSense/update.sh --status

# Update with optional backup
./PaddiSense/update.sh --backup

# Dry run (see what would change)
./PaddiSense/update.sh --dry-run
```

### What Gets Updated vs Protected

| Updated (git pull) | Protected (local) |
|-------------------|-------------------|
| package.yaml files | local_data/*.json |
| Python scripts | secrets.yaml |
| Dashboards | server.yaml |
| VERSION files | HA database |

## Directory Structure

```
/config/
├── configuration.yaml          # Main HA config
├── server.yaml                 # Per-server config (NOT in git)
├── secrets.yaml                # API keys, passwords (NOT in git)
├── PaddiSense/                 # All distributable modules
│   ├── install.sh              # Installation script
│   ├── update.sh               # Update script
│   ├── server.yaml.example     # Template for server config
│   │
│   ├── ipm/                    # Inventory Product Manager
│   │   ├── VERSION             # Module version (e.g., 1.0.0)
│   │   ├── package.yaml        # All HA config (helpers, templates, scripts, automations)
│   │   ├── python/
│   │   │   ├── ipm_backend.py  # Write operations (add/edit product, move stock)
│   │   │   └── ipm_sensor.py   # Read-only JSON output for HA sensor
│   │   └── dashboards/
│   │       └── inventory.yaml  # Dashboard views
│   │
│   ├── asm/                    # Asset Service Manager
│   │   ├── VERSION             # Module version (e.g., 1.0.0)
│   │   ├── package.yaml        # All HA config
│   │   ├── python/
│   │   │   ├── asm_backend.py  # Write operations (assets, parts, services)
│   │   │   └── asm_sensor.py   # Read-only JSON output for HA sensor
│   │   └── dashboards/
│   │       └── views.yaml      # Dashboard views (Assets, Parts, Report, Service, Settings)
│   │
│   ├── weather/                # Unified Weather Module (local + API)
│   │   ├── VERSION             # Module version (e.g., 2.0.0)
│   │   ├── package.yaml        # ALL weather config (local sensors, API sensors, helpers, scripts)
│   │   ├── python/
│   │   │   ├── weather_api_backend.py  # API station management commands
│   │   │   └── weather_api_sensor.py   # API fetching + JSON output
│   │   └── dashboards/
│   │       ├── views.yaml          # PRIMARY: Unified dashboard (Forecast, Temps, Local, Stations, Settings)
│   │       ├── weatherview.yaml    # Legacy: Subset of views (deprecated)
│   │       └── weatherviewlocal.yaml  # Detailed local gateway charts (multiple stations)
│   │
│   └── pwm/                    # Precision Water Management
│       ├── VERSION             # Module version (e.g., 1.0.0)
│       ├── package.yaml        # All HA config (templates, automations, scripts)
│       ├── python/
│       │   ├── pwm_backend.py  # Write operations (paddock/bay management)
│       │   └── pwm_sensor.py   # Read config + server.yaml, output JSON
│       └── dashboards/
│           └── views.yaml      # Dashboard views (Overview, Paddock, Bay Editor, Reports, Settings)
│
└── local_data/                 # Runtime data - NOT in git
    ├── ipm/
    │   ├── inventory.json      # Product inventory data
    │   ├── config.json         # User configuration (locations, custom actives)
    │   └── backups/            # Backup files
    ├── asm/
    │   ├── data.json           # Asset, part, and service event data
    │   ├── config.json         # User configuration (categories, service types)
    │   └── backups/            # Backup files
    ├── weather/
    │   └── config.json         # Local station configuration (name, enabled)
    ├── weather_api/
    │   └── config.json         # API station configurations (name, imei, lat, elev)
    └── pwm/
        ├── config.json         # Paddock and bay configurations
        └── backups/            # Backup files
```

## Module Design Principles

Each module (ipm, wss, etc.) should be:
1. **Self-contained** - All files in one folder for easy distribution
2. **Single package.yaml** - All HA configuration in one file
3. **Data separation** - Runtime data in `/config/local_data/`, not tracked in git
4. **Version tracking** - Each module has a `VERSION` file (e.g., `1.0.0`)

## Version Management

Each module contains a `VERSION` file in its root directory:
- `/config/PaddiSense/ipm/VERSION` - IPM version (currently 1.0.0)
- `/config/PaddiSense/asm/VERSION` - ASM version (currently 1.0.0)
- `/config/PaddiSense/weather/VERSION` - Weather version (currently 2.0.0, unified local+API)
- `/config/PaddiSense/pwm/VERSION` - PWM version (currently 1.0.0)

Versions are:
- Read by sensors and output as the `version` attribute
- Displayed on Settings pages in each module
- Shown during install/update script execution
- Updated automatically when pulling updates from the repository

## IPM System Architecture

### Data Flow
1. `sensor.ipm_products` runs Python sensor script every 5 minutes
2. Sensor reads both `inventory.json` (products) and `config.json` (locations)
3. Template sensors filter/transform the data for UI
4. User interactions trigger scripts
5. Scripts call shell commands which invoke Python backend
6. Python backend updates `inventory.json` or `config.json`
7. Sensor refreshes to reflect changes

### Configuration File (config.json)
User-configurable settings stored separately from inventory data:
```json
{
  "locations": ["Chem Shed", "Seed Shed", "Oil Shed", "Silo 1", ...],
  "custom_actives": [],
  "created": "2026-01-16T...",
  "modified": "2026-01-16T..."
}
```

### Key Entities
- `sensor.ipm_products` - Main data source (JSON attributes including `active_names`)
- `input_select.ipm_product` - Product selection by NAME (user-friendly)
- `input_select.ipm_location` - Location selection (for multi-location products)
- `input_select.ipm_category` - Filter by category
- `input_select.ipm_subcategory` - Filter by subcategory
- `input_select.ipm_active_filter` - Filter by active constituent name
- `input_number.ipm_quantity` - Stock change amount
- `script.ipm_save_movement` - Commit stock changes
- `script.ipm_add_product` / `script.ipm_save_product` - Product management

### Dashboard Views (inventory.yaml)
1. **Stock Movement** - Select product/location, adjust stock with +/- buttons
2. **Product Editor** - Add new or edit existing products (including active constituents)
3. **Stock Overview** - Filterable report view showing all products with:
   - Category, Subcategory, Active Constituent, and Search filters
   - Stock cards displaying: name, category, total stock, stock bar, active constituents (name, concentration, group), locations
4. **Settings** - System configuration and management:
   - System status (initialized, config/database status, counts)
   - Initialize button for first-time setup
   - Locations manager (add/remove storage locations)
   - Data refresh controls

### Category Structure
```
Chemical    → Adjuvant, Fungicide, Herbicide, Insecticide, Pesticide, Rodenticide, Seed Treatment
Fertiliser  → Nitrogen, Phosphorus, Potassium, NPK Blend, Trace Elements, Organic
Seed        → Wheat, Barley, Canola, Rice, Oats, Pasture, Other
Lubricant   → Engine Oil, Hydraulic Oil, Grease, Gear Oil, Transmission Fluid, Coolant
```

### Storage Locations
Default locations: Chem Shed, Seed Shed, Oil Shed, Silo 1-13

Locations are configurable via the Settings view. Custom locations can be added/removed as needed. Locations with stock cannot be removed until stock is moved or depleted.

### Active Constituents (Chemicals/Fertilisers)
Products in the Chemical and Fertiliser categories can have up to 6 active constituents. Each active has:
- `name` - Name of the active ingredient (dropdown with ~100 common actives)
- `concentration` - Numeric concentration value
- `unit` - Concentration unit (g/L, g/kg, ml/L, %)
- `group` - Chemical group (stored per active, not per product)

**Data field:** `active_constituents` (array in product JSON)

### Chemical Groups
Available groups: None, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 22, M (multi-site)

## ASM System Architecture

### Data Flow
1. `sensor.asm_data` runs Python sensor script every 5 minutes
2. Sensor reads both `data.json` (assets, parts, events) and `config.json` (categories)
3. Template sensors filter parts by asset selection
4. User interactions trigger scripts
5. Scripts call shell commands which invoke Python backend
6. Python backend updates `data.json` or `config.json`
7. Service events auto-deduct parts from stock
8. Sensor refreshes to reflect changes

### Configuration File (config.json)
User-configurable settings stored separately from asset/part data:
```json
{
  "asset_categories": ["Tractor", "Pump", "Harvester", "Vehicle"],
  "part_categories": ["Filter", "Belt", "Oil", "Grease", "Battery", "Tyre", "Hose"],
  "service_types": ["250 Hr Service", "500 Hr Service", "1000 Hr Service", "Annual Service", "Repair", "Inspection", "Other"],
  "part_units": ["ea", "L", "kg", "m"],
  "created": "2026-01-17T...",
  "modified": "2026-01-17T..."
}
```

### Key Entities
- `sensor.asm_data` - Main data source (JSON attributes: assets, parts, events, event_labels, initialized, status)
- `input_select.asm_asset` - Asset selection by NAME
- `input_select.asm_part` - Part selection
- `input_select.asm_service_asset` - Asset for service recording
- `input_select.asm_service_type` - Service type selection
- `input_select.asm_service_event` - Service history viewer (labels include datetime)
- `sensor.asm_selected_service_event` - Selected event details for display
- `script.asm_add_asset` / `script.asm_save_asset` - Asset management
- `script.asm_add_part` - Part management
- `script.asm_record_service` - Record service with auto-deduct
- `script.asm_delete_service` - Delete a service event
- `script.asm_init_system` - Initialize system (Settings)
- `script.asm_export_data` - Export backup (Settings)
- `script.asm_refresh_data` - Refresh sensor (Settings)

### Asset Categories
Tractor, Pump, Harvester, Vehicle

### Part Categories
Filter, Belt, Oil, Grease, Battery, Tyre, Hose

### Service Types
250 Hr Service, 500 Hr Service, 1000 Hr Service, Annual Service, Repair, Inspection, Other

### Dashboard Views (views.yaml)
1. **Assets** - View/add/edit assets with custom attributes
2. **Parts** - View/add/edit parts, assign to assets or mark universal
3. **Service** - Record service events with parts consumption, view/delete history
4. **Report** - Service history and parts usage reports
5. **Settings** - System configuration and management:
   - System status (initialized, config/database status, counts)
   - Initialize button for first-time setup
   - Export backup button
   - Data refresh controls
   - Categories display (read-only)

### Key Features
- Parts can be assigned to specific assets or marked as "universal" (all assets)
- Flexible custom attributes (15 slots) for both assets and parts
- Single stock count per part (simpler than IPM's multi-location)
- Service events consume parts and auto-deduct from stock
- Service history dropdown uses datetime labels (e.g., "2026-01-16 15:11 - Asset - Type")
- Transaction logging for audit trail
- Backup/export functionality with auto-backup before imports/resets

### Backend Commands (asm_backend.py)
**Asset Management:**
- `add_asset --name --category --attributes`
- `edit_asset --id --name --category --attributes`
- `delete_asset --id`

**Part Management:**
- `add_part --name --part_number --category --unit --stock --min_stock --assets --universal --attributes`
- `edit_part --id ...`
- `delete_part --id`
- `adjust_stock --id --delta`

**Service Management:**
- `record_service --asset --type --parts --notes --hours`
- `delete_service --id`

**System Management:**
- `init` - Initialize system (creates config + database)
- `status` - Return system status as JSON
- `export` - Export data to timestamped backup
- `import_backup --filename` - Import from backup (auto-creates pre-import backup)
- `reset --token CONFIRM_RESET` - Full reset with confirmation
- `backup_list` - List available backups

## Weather System Architecture (Unified v2.0.0)

The weather module is a unified package combining local Ecowitt gateway support and remote API station access in a single `package.yaml` file.

**IMPORTANT:** The package.yaml must have NO duplicate root-level YAML keys. All template sensors, command_line sensors, shell_commands, and input helpers are consolidated under single keys.

### Package Structure
```
weather/package.yaml contains:
- template:         17 items (local sensors, binary sensors, API station sensors)
- command_line:     2 sensors (Weather API Data, Weather Local Config)
- shell_command:    11 commands (API + local station management)
- input_number:     8 helpers (CDD trackers for local + 4 API stations)
- input_text:       3 helpers (station name inputs)
- input_select:     1 helper (editor mode)
- sensor:           Statistics sensors (min/max/avg)
- utility_meter:    Solar radiation daily meter
- automation:       5 automations (CDD accumulation)
- script:           13 scripts (station management, refresh, reset)
```

### Local Gateway

**Data Source:** Ecowitt Gateway integration sensors:
- `sensor.ecowittgateway_1_outdoor_temperature`
- `sensor.ecowittgateway_1_humidity`
- `sensor.ecowittgateway_1_wind_speed`
- `sensor.ecowittgateway_1_solar_radiation`

**Configuration:** `local_data/weather/config.json`
```json
{
  "local_stations": {
    "1": {
      "enabled": true,
      "name": "My Weather Station",
      "entity_prefix": "ecowittgateway_1"
    }
  },
  "version": "1.0.0"
}
```

**Key Entities:**
- `sensor.weather_local_config` - Reads local station config
- `binary_sensor.weather_local_station_1_enabled` - True when local station is configured and enabled
- `input_text.weather_local_station_name` - Input for editing station name

**Calculated Sensors:**
- **Delta T** - Spray condition indicator (dry bulb - wet bulb temperature)
- **Evapotranspiration (ETo)** - Penman-Monteith equation for reference grass crop (mm/day)
- **Degree Days** - Daily thermal accumulation above 10°C base temperature
- **Filtered Solar Radiation** - Cleaned solar data converted to MJ for calculations

**Statistics Sensors (24-hour rolling):**
- Min/Max Temperature, Min/Max Humidity, Avg Wind Speed

**Helpers:**
- `input_number.weather_station_1_cdd` - Cumulative Degree Days running total
- `utility_meter.weather_station_1_solar_radiation_mj_m2_day` - Daily solar accumulator

### Remote API Stations

Fetches weather data from Ecowitt's cloud API for remote stations without local gateway access. Supports up to 4 station slots.

**Data Flow:**
1. `sensor.weather_api_data` runs Python sensor script every 60 seconds
2. Sensor reads `local_data/weather_api/config.json` for station configurations
3. Sensor reads `secrets.yaml` for API credentials (ecowitt_app_key, ecowitt_api_key)
4. For each enabled station, fetches from Ecowitt API and converts units
5. Template sensors extract individual values from main sensor

**Configuration:** `local_data/weather_api/config.json`
```json
{
  "stations": {
    "1": {
      "enabled": true,
      "name": "Talkook",
      "imei": "ABC123DEF456",
      "latitude": -35.5575,
      "elevation": 180
    }
  },
  "created": "2026-01-17T...",
  "modified": "2026-01-17T..."
}
```

**Required Secrets (secrets.yaml):**
```yaml
ecowitt_app_key: "YOUR_APPLICATION_KEY"
ecowitt_api_key: "YOUR_API_KEY"
```

**Key Entities:**
- `sensor.weather_api_data` - Main data source (JSON with all stations)
- `binary_sensor.weather_api_station_{1-4}_configured` - True when station slot has config
- `sensor.weather_api_station_{1-4}_temperature` - Per-station temperature
- `sensor.weather_api_station_{1-4}_humidity` - Per-station humidity
- `sensor.weather_api_station_{1-4}_delta_t` - Per-station Delta T (derived)
- `sensor.weather_api_station_{1-4}_evapotranspiration` - Per-station ETo (derived)
- `sensor.weather_api_station_{1-4}_degree_day` - Per-station Degree Day (derived)
- `input_number.weather_api_station_{1-4}_cdd` - Cumulative Degree Days

**Station Sensors (per slot):**
- **Raw:** temperature, humidity, feels_like, dew_point, solar_radiation, uv_index
- **Rain:** rain_rate, rain_hourly, rain_daily, rain_monthly, rain_yearly
- **Wind:** wind_speed, wind_gust, wind_direction
- **Pressure:** pressure_relative, pressure_absolute
- **Battery:** battery (if available)
- **Derived:** delta_t, evapotranspiration, degree_day

**Backend Commands (weather_api_backend.py):**
- `init` - Initialize system
- `status` - Return system status
- `add_station --slot --name --imei --latitude --elevation`
- `edit_station --slot [--name] [--imei] [--latitude] [--elevation]`
- `remove_station --slot`
- `enable_station --slot` / `disable_station --slot`
- `list_stations` - List configured stations

**Unit Conversions (handled by sensor):**
- Temperature: Fahrenheit → Celsius
- Wind Speed: mph → km/h
- Rainfall: inches → mm
- Pressure: inHg → hPa

### Dashboard Files (weather/dashboards/)
- **views.yaml** - PRIMARY unified dashboard combining local gateway + API stations:
  1. Forecast - BOM weather forecast with platinum-weather-card
  2. Temps - 7-day temperature forecast with colour-coded tiles
  3. Local - Local Ecowitt gateway data (conditional, shows when local station enabled)
  4. Stations - API stations overview (conditional, shows configured stations)
  5. Settings - Combined settings for local gateway and API station management
- **weatherviewlocal.yaml** - Detailed charts for multiple local gateways (ecowittgateway_1, 2, 4, 5)
- **weatherview.yaml** - Legacy file (deprecated, use views.yaml instead)

### configuration.yaml Reference
```yaml
weather-service:
  mode: yaml
  title: Weather Package
  icon: mdi:weather-cloudy
  show_in_sidebar: true
  filename: PaddiSense/weather/dashboards/views.yaml
```

## Git Workflow

To sync changes:
```bash
git add PaddiSense CLAUDE.md configuration.yaml .gitignore
git commit -m "Description of changes"
git push
```

## PWM System Architecture (v1.0.0)

PWM (Precision Water Management) controls automated irrigation for rice paddocks using ESPHome water level sensors and door actuators.

### Hierarchy
```
Grower (server)
└── Farm (server.yaml)          ← Full config: ID, name, location, water source, channels
    └── Paddock (UI config)     ← Created/managed via dashboard Settings
        └── Bay (UI config)     ← Multiple bays per paddock, each with devices
```

**Scale:** Up to 5 farms, 20 paddocks each, 10 bays each (1000 bays max)

### Server Configuration (server.yaml)
Farms defined at server level with full configuration:
```yaml
modules:
  pwm: true

pwm:
  farms:
    farm_1:
      name: "Main Farm"
      location:
        latitude: -35.5575
        longitude: 145.123
      water_source: "channel"      # channel, bore, river
      channel_info:
        name: "Main Channel"
        supply_point: "Offtake A"
    farm_2:
      name: "North Block"
      # ... additional farms
```

### Data Structure (Shared with HFM)
The farm/paddock/bay hierarchy is shared between PWM and future Hey Farmer (HFM) module.

**Configuration:** `local_data/pwm/config.json`
```json
{
  "paddocks": {
    "sw5": {
      "farm_id": "farm_1",
      "name": "Sheepwash 5",
      "enabled": true,
      "automation_state_individual": false,
      "bay_prefix": "B-",
      "bay_count": 5,
      "created": "2026-01-18T...",
      "modified": "2026-01-18T..."
    }
  },
  "bays": {
    "sw5_b_01": {
      "paddock_id": "sw5",
      "name": "B-01",
      "order": 1,
      "supply_1": { "device": "esphome_device_1", "type": "door" },
      "supply_2": { "device": null, "type": null },
      "drain_1": { "device": "esphome_device_2", "type": "door" },
      "drain_2": { "device": null, "type": null },
      "level_sensor": "esphome_device_1",
      "settings": {
        "water_level_min": 5,
        "water_level_max": 15,
        "water_level_offset": 0,
        "flush_time_on_water": 3600
      }
    }
  },
  "version": "1.0.0",
  "created": "2026-01-18T...",
  "modified": "2026-01-18T..."
}
```

### Device Slots (Named Slots Approach)
Each bay can have:
- `supply_1`, `supply_2` - Up to 2 water supply doors
- `drain_1`, `drain_2` - Up to 2 drain doors
- `level_sensor` - Water depth sensor

**Device Discovery:** Sensors matching pattern `*_1m_water_depth` are listed in dropdown for assignment.

### Automation States
Per paddock and per bay (when individual mode enabled):
- **Flush** - Fill bay, hold water for timer duration, release to next bay
- **Pond** - Maintain water level between min/max thresholds
- **Drain** - Empty the bay completely
- **Off** - No automation

### Door Control States
- **Open** - Door fully open
- **HoldOne** - Sync state before action
- **Close** - Door fully closed
- **HoldTwo** - Secondary hold state

### Data Flow (sensor.pwm_data Approach)
Uses the same proven pattern as IPM, ASM, and Weather for reliability:

1. `sensor.pwm_data` runs Python sensor script every 30 seconds
2. Sensor reads `local_data/pwm/config.json` for paddock/bay configurations
3. Sensor reads `server.yaml` for farm definitions
4. Sensor outputs JSON with all paddocks, bays, farms, and device lists
5. Template sensors extract individual values from main sensor attributes
6. User interactions trigger scripts → shell commands → Python backend
7. Backend updates config.json → sensor refreshes

```yaml
# Main data sensor
command_line:
  - sensor:
      name: PWM Data
      unique_id: pwm_data
      command: "python3 /config/PaddiSense/pwm/python/pwm_sensor.py"
      scan_interval: 30
      value_template: "{{ value_json.status }}"
      json_attributes:
        - farms
        - paddocks
        - bays
        - devices
        - initialized
        - version

# Template sensors extract from main sensor
template:
  - sensor:
      - name: "PWM SW5 B-01 Water Depth"
        state: >-
          {% set bays = state_attr('sensor.pwm_data', 'bays') or {} %}
          {% set bay = bays.get('sw5_b_01', {}) %}
          {% set device = bay.get('level_sensor', '') %}
          {% if device %}
            {% set depth_id = 'sensor.' ~ device ~ '_' ~ device ~ '_1m_water_depth' %}
            {% set offset = bay.get('settings', {}).get('water_level_offset', 0) %}
            {{ (states(depth_id) | float(0) - offset) | round(1) }}
          {% else %}
            unavailable
          {% endif %}
```

### Key Entities (Dynamic)
Per paddock:
- `sensor.pwm_<paddock>_automation_state` - Current mode
- `sensor.pwm_<paddock>_supply_water_depth` - Channel supply level
- `input_select.pwm_<paddock>_drain_door_control` - Drain door control

Per bay:
- `sensor.pwm_<paddock>_<bay>_water_depth` - Calculated water depth
- `sensor.pwm_<paddock>_<bay>_automation_state` - Bay mode
- `sensor.pwm_<paddock>_<bay>_door_control` - Supply door control
- `sensor.pwm_<paddock>_<bay>_flush_active` - Flush in progress flag

### Backend Commands (pwm_backend.py)
**Paddock Management:**
- `add_paddock --farm --name --bay_prefix --bay_count`
- `edit_paddock --id [--name] [--enabled] [--individual_mode]`
- `delete_paddock --id`

**Bay Management:**
- `edit_bay --id --supply_1 --drain_1 --level_sensor --settings`
- `assign_device --bay --slot --device` (e.g., `--slot supply_1`)

**System Management:**
- `init` - Initialize system
- `status` - Return system status
- `list_devices` - List available ESPHome devices matching pattern
- `export` / `import_backup` / `reset`

### Dashboard Views (views.yaml)
1. **Overview** - All paddocks with status badges, quick automation controls
2. **Paddock** - Per-paddock detail view with bay cards, water level visualization
3. **Bay Editor** - Configure bay settings, assign devices to slots
4. **Reports** - Water usage, automation history, event logs
5. **Settings** - System status, paddock management, device discovery

### Module File Structure
```
PaddiSense/pwm/
├── VERSION                 # Module version (1.0.0)
├── package.yaml            # All HA config (dynamic templates, scripts, automations)
├── python/
│   ├── pwm_backend.py      # Write operations (paddock/bay management)
│   └── pwm_sensor.py       # Read config.json, output JSON for templates
└── dashboards/
    └── views.yaml          # Dashboard views

local_data/pwm/
├── config.json             # Paddock and bay configurations
└── backups/                # Backup files
```

### ESPHome Integration
ESPHome devices expose:
- `sensor.<device>_<device>_1m_water_depth` - Water level in cm
- `input_select.<device>_actuator_state` - Door control (Open/HoldOne/Close/HoldTwo)

**Note:** Firmware is evolving to handle more logic on-device. Current implementation uses HA for all timers and automation logic; future versions may offload timing to ESP.

### Irrigation Automation Logic (Preserved from v2025.12)
The automation logic from the legacy shell script is mature and well-tested:

1. **Flush Mode:**
   - Close drain door, open supply door
   - Fill until water level reaches minimum
   - Start flush timer when level maintained for 5 minutes
   - When timer expires, turn off flush_active
   - Release water to next bay (cascade effect)
   - Turn off automation when all bays complete flush

2. **Pond Mode:**
   - Below min: Open supply, close drain (if last bay)
   - Optimal: Close supply, hold position
   - Above max: Close supply, open drain to release excess
   - Monitors supply channel level vs bay level

3. **Drain Mode:**
   - Repeatedly open drain until level below -8cm
   - Uses 45-minute intervals with brief open pulses

4. **Propagation:**
   - Paddock-level state propagates to all bays (unless individual mode)
   - All bays off → paddock automation turns off

## Important Notes

- Product IDs are auto-generated from names (uppercase, alphanumeric + underscores)
- Products can exist in multiple locations (e.g., Urea in Silo 1 and Silo 3)
- Stock cannot go negative (clamped to 0)
- Transactions are logged for audit trail
- The UI uses two-step selection: Product Name → Location (if multiple)
