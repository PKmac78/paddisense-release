# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Home Assistant configuration repository for a farm/agricultural operation. The main custom development is **PaddiSense** - an Integrated Pest Management (IPM) inventory tracking system for managing chemicals, fertilisers, seeds, and lubricants across multiple storage locations.

## Architecture

### Configuration Loading

Home Assistant loads configuration via `configuration.yaml`:
- **Packages**: `PaddiSense/YAMLS/*.yaml` are loaded as named packages via `!include_dir_named`
- **Shell commands**: `PaddiSense/Shell/shell_command.yaml`
- **Dashboards**: `PaddiSense/Dashboards/registry/*.yaml` registers Lovelace dashboards

### PaddiSense IPM System

The inventory system follows a clear separation:

**Python Backend** (`PaddiSense/Python/`):
- `ipm_inventory.py` - Write operations: `upsert_product`, `move_stock`, `list` (CLI with argparse)
- `ipm_read_v2.py` - Read-only: outputs JSON for Home Assistant command_line sensor

**Data Storage**:
- Runtime data lives in `PaddiSense/data/ipm_inventory.json` (gitignored - each install maintains own inventory)
- Products stored with `stock_by_location` dict for multi-location tracking
- Transactions logged for audit trail

**YAML Configuration** (`PaddiSense/YAMLS/`):
- `ipm_command_line_sensors.yaml` - Sensor that runs `ipm_read_v2.py` every 5 minutes
- `ipm_templates.yaml` - Template sensors for filtering, selection state, UI helpers
- `ipm_helpers.yaml` - Input helpers (input_select, input_number, input_text, input_boolean)
- `ipm_automations.yaml` - Automations for updating dropdowns when filters change
- `ipm_scripts.yaml` - Scripts for commit, save, load operations calling shell commands

**Shell Commands** (`PaddiSense/Shell/shell_command.yaml`):
- `ipm_move_stock` - Calls `ipm_inventory.py move_stock`
- `ipm_upsert_product` - Calls `ipm_inventory.py upsert_product`

**Dashboard** (`PaddiSense/Dashboards/views/ipm-inventory.yaml`):
- Three views: Movement (stock in/out), Manage Products (add/edit), Stock Overview (read-only)
- Uses `custom:button-card` templates for UI
- Product selection uses composite key format: `ID|Location`

### Data Flow

1. `sensor.ipm_inventory_products` runs Python script, exposes JSON as attributes
2. Template sensors (`sensor.ipm_inventory_catalog`, `sensor.ipm_filtered_products`) process/filter data
3. Automations update `input_select` options based on filter state
4. Scripts call shell commands which invoke Python backend
5. After changes, sensor is refreshed via `homeassistant.update_entity`

### ESPHome

Shared ESPHome configuration in `esphome/Includes/`:
- `.base.yaml` - Common config for ESP32 devices (API, OTA, WiFi, utilities)
- `.rb_hardware.yaml` - RiceBoard-specific hardware config
- Individual device YAMLs are gitignored; only shared includes are tracked

## Git Workflow

Sync PaddiSense changes:
```bash
git add PaddiSense
git commit -m "description"
git push
```

## Key Entities

- `sensor.ipm_inventory_products` - Source of truth, JSON with products/locations
- `input_select.ipm_product_key` - Selected product in format `PRODUCT_ID|Location`
- `input_select.ipm_category` / `ipm_subcategory_filter` - Filtering
- `script.ipm_commit` - Commits stock movement
- `script.ipm_save_product` - Saves new/edited product

## Important Patterns

- Product IDs are auto-generated slugs from product names (uppercase, alphanumeric + underscores)
- Categories are normalized (e.g., "fertilizer" → "Fertiliser")
- Stock cannot go negative (clamped to 0)
- Template sensors use Jinja2 namespace pattern for list building in loops
- Input_select options use "please update" as reset placeholder
