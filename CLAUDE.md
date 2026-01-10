# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Repository Overview

This is a Home Assistant configuration repository for a farm/agricultural operation. The system is called **PaddiSense** - a modular farm management platform with multiple packages:

- **IPM** (Inventory Product Manager) - Track chemicals, fertilisers, seeds, lubricants
- **WSS** (Work Safety System) - Coming soon
- **PWM** (Precision Water Management) - Coming soon
- **ASM** (Asset Manager) - Coming soon
- **HFM** (Hey Farmer) - Coming soon

## Directory Structure

```
/config/
├── configuration.yaml          # Main HA config
├── PaddiSense/                 # All distributable modules
│   └── ipm/                    # Inventory Product Manager
│       ├── package.yaml        # All HA config (helpers, templates, scripts, automations)
│       ├── python/
│       │   ├── ipm_backend.py  # Write operations (add/edit product, move stock)
│       │   └── ipm_sensor.py   # Read-only JSON output for HA sensor
│       └── dashboards/
│           ├── registry.yaml   # Dashboard registration
│           └── inventory.yaml  # Dashboard views
│
└── local_data/                 # Runtime data - NOT in git
    └── ipm/
        └── inventory.json      # Product inventory data
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
