# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Repository Overview

This is a Home Assistant configuration repository for a farm/agricultural operation. The system is called **PaddiSense** - a modular farm management platform with multiple packages:

- **IPM** (Inventory Product Manager) - Track chemicals, fertilisers, seeds, lubricants
- **ASM** (Asset Service Manager) - Track assets, parts, and service events
- **Weather** - Weather station integration with Delta T, ETo, Degree Days
- **WSS** (Work Safety System) - Coming soon
- **PWM** (Precision Water Management) - Coming soon
- **HFM** (Hey Farmer) - Coming soon

## Current System Baseline (16 January 2026)

### IPM Inventory
- **Total Products:** 11
- **Categories in use:** Chemical (3), Fertiliser (2), Seed (4), Lubricant (2)
- **Active Constituents tracked:** Glyphosate, Nitrogen, Act1, Act 2
- **Products with stock:** 9 (2 products have zero stock: Peter Seed, New Seed)
- **Transactions logged:** 16

### ASM Assets & Parts
- **Total Assets:** 2 (Case Magnum 280, Case Puma 140)
- **Total Parts:** 3 (Tyre 8960, little tyre, Big tyre rear)
- **Low Stock Alerts:** 1 (little tyre at 0 stock)
- **Service Events:** 6 recorded
- **Transactions logged:** 25

### Weather Station
- **Data Source:** Ecowitt Gateway (ecowittgateway_1)
- **Location:** Latitude -35.5575, Elevation 180m
- **Calculated Sensors:** Delta T, Evapotranspiration (ETo), Degree Days, Cumulative Degree Days
- **Statistics Sensors:** Min/Max Temperature, Min/Max Humidity, Avg Wind Speed
- **Utility Meter:** Daily Solar Radiation (MJ/m2/day)

## Directory Structure

```
/config/
├── configuration.yaml          # Main HA config
├── PaddiSense/                 # All distributable modules
│   ├── ipm/                    # Inventory Product Manager
│   │   ├── package.yaml        # All HA config (helpers, templates, scripts, automations)
│   │   ├── python/
│   │   │   ├── ipm_backend.py  # Write operations (add/edit product, move stock)
│   │   │   └── ipm_sensor.py   # Read-only JSON output for HA sensor
│   │   └── dashboards/
│   │       └── inventory.yaml  # Dashboard views
│   │
│   ├── asm/                    # Asset Service Manager
│   │   ├── package.yaml        # All HA config
│   │   ├── python/
│   │   │   ├── asm_backend.py  # Write operations (assets, parts, services)
│   │   │   └── asm_sensor.py   # Read-only JSON output for HA sensor
│   │   └── dashboards/
│   │       └── views.yaml      # Dashboard views (Assets, Parts, Report, Service)
│   │
│   └── weather/                # Weather Station Integration
│       ├── package.yaml        # Template sensors, statistics, automations
│       ├── python/             # (empty - no backend needed)
│       └── dashboards/
│           └── weatherview.yaml
│
└── local_data/                 # Runtime data - NOT in git
    ├── ipm/
    │   └── inventory.json      # Product inventory data
    └── asm/
        └── data.json           # Asset, part, and service event data
```

## Module Design Principles

Each module (ipm, wss, etc.) should be:
1. **Self-contained** - All files in one folder for easy distribution
2. **Single package.yaml** - All HA configuration in one file
3. **Data separation** - Runtime data in `/config/local_data/`, not tracked in git

## IPM System Architecture

### Data Flow
1. `sensor.ipm_products` runs Python sensor script every 5 minutes
2. Template sensors filter/transform the data for UI
3. User interactions trigger scripts
4. Scripts call shell commands which invoke Python backend
5. Python backend updates `inventory.json`
6. Sensor refreshes to reflect changes

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

### Category Structure
```
Chemical    → Adjuvant, Fungicide, Herbicide, Insecticide, Pesticide, Rodenticide, Seed Treatment
Fertiliser  → Nitrogen, Phosphorus, Potassium, NPK Blend, Trace Elements, Organic
Seed        → Wheat, Barley, Canola, Rice, Oats, Pasture, Other
Lubricant   → Engine Oil, Hydraulic Oil, Grease, Gear Oil, Transmission Fluid, Coolant
```

### Storage Locations
Chem Shed, Seed Shed, Oil Shed, Silo 1-13

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
2. Template sensors filter parts by asset selection
3. User interactions trigger scripts
4. Scripts call shell commands which invoke Python backend
5. Python backend updates `data.json`
6. Service events auto-deduct parts from stock
7. Sensor refreshes to reflect changes

### Key Entities
- `sensor.asm_data` - Main data source (JSON attributes: assets, parts, events, event_labels)
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

### Key Features
- Parts can be assigned to specific assets or marked as "universal" (all assets)
- Flexible custom attributes (15 slots) for both assets and parts
- Single stock count per part (simpler than IPM's multi-location)
- Service events consume parts and auto-deduct from stock
- Service history dropdown uses datetime labels (e.g., "2026-01-16 15:11 - Asset - Type")
- Transaction logging for audit trail

## Weather System Architecture

### Data Source
Uses Ecowitt Gateway integration sensors:
- `sensor.ecowittgateway_1_outdoor_temperature`
- `sensor.ecowittgateway_1_humidity`
- `sensor.ecowittgateway_1_wind_speed`
- `sensor.ecowittgateway_1_solar_radiation`

### Calculated Sensors
- **Delta T** - Spray condition indicator (dry bulb - wet bulb temperature)
- **Evapotranspiration (ETo)** - Penman-Monteith equation for reference grass crop (mm/day)
- **Degree Days** - Daily thermal accumulation above 10°C base temperature
- **Filtered Solar Radiation** - Cleaned solar data converted to MJ for calculations

### Statistics Sensors (24-hour rolling)
- Min/Max Temperature, Min/Max Humidity, Avg Wind Speed

### Helpers
- `input_number.weather_station_1_cdd` - Cumulative Degree Days running total
- `utility_meter.weather_station_1_solar_radiation_mj_m2_day` - Daily solar accumulator

### Automation
- Daily CDD automation adds degree day value to cumulative total at 23:59:30
- Reset script available: `script.reset_weather_station_1_cdd`

## Git Workflow

To sync changes:
```bash
git add PaddiSense CLAUDE.md configuration.yaml .gitignore
git commit -m "Description of changes"
git push
```

## Important Notes

- Product IDs are auto-generated from names (uppercase, alphanumeric + underscores)
- Products can exist in multiple locations (e.g., Urea in Silo 1 and Silo 3)
- Stock cannot go negative (clamped to 0)
- Transactions are logged for audit trail
- The UI uses two-step selection: Product Name → Location (if multiple)
