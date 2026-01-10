# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Repository Overview

This is a Home Assistant configuration repository for a farm/agricultural operation. The system is called **PaddiSense** - a modular farm management platform with multiple packages:

- **IPM** (Inventory Product Manager) - Track chemicals, fertilisers, seeds, lubricants
- **ASM** (Asset Service Manager) - Track assets, parts, and service events
- **WSS** (Work Safety System) - Coming soon
- **PWM** (Precision Water Management) - Coming soon
- **HFM** (Hey Farmer) - Coming soon

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
│   └── asm/                    # Asset Service Manager
│       ├── package.yaml        # All HA config
│       ├── python/
│       │   ├── asm_backend.py  # Write operations (assets, parts, services)
│       │   └── asm_sensor.py   # Read-only JSON output for HA sensor
│       └── dashboards/
│           └── views.yaml      # Dashboard views (Assets, Parts, Report, Service)
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
- `sensor.ipm_products` - Main data source (JSON attributes)
- `input_select.ipm_product` - Product selection by NAME (user-friendly)
- `input_select.ipm_location` - Location selection (for multi-location products)
- `input_number.ipm_quantity` - Stock change amount
- `script.ipm_save_movement` - Commit stock changes
- `script.ipm_add_product` / `script.ipm_save_product` - Product management

### Category Structure
```
Chemical    → Adjuvant, Fungicide, Herbicide, Insecticide, Pesticide, Rodenticide, Seed Treatment
Fertiliser  → Nitrogen, Phosphorus, Potassium, NPK Blend, Trace Elements, Organic
Seed        → Wheat, Barley, Canola, Rice, Oats, Pasture, Other
Lubricant   → Engine Oil, Hydraulic Oil, Grease, Gear Oil, Transmission Fluid, Coolant
```

### Storage Locations
Chem Shed, Seed Shed, Oil Shed, Silo 1-13

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
- `sensor.asm_data` - Main data source (JSON attributes: assets, parts, events)
- `input_select.asm_asset` - Asset selection by NAME
- `input_select.asm_part` - Part selection
- `input_select.asm_service_asset` - Asset for service recording
- `input_select.asm_service_type` - Service type selection
- `script.asm_add_asset` / `script.asm_save_asset` - Asset management
- `script.asm_add_part` - Part management
- `script.asm_record_service` - Record service with auto-deduct

### Asset Categories
Tractor, Pump, Harvester, Vehicle

### Part Categories
Filter, Belt, Oil, Grease, Battery, Tyre, Hose

### Service Types
250 Hr Service, 500 Hr Service, 1000 Hr Service, Annual Service, Repair, Inspection, Other

### Key Features
- Parts can be assigned to specific assets or marked as "universal" (all assets)
- Flexible custom attributes (5 slots) for both assets and parts
- Single stock count per part (simpler than IPM's multi-location)
- Service events consume parts and auto-deduct from stock
- Transaction logging for audit trail

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
