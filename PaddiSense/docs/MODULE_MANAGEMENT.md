# PaddiSense Module Management

This document describes how to install, remove, and manage PaddiSense modules using the Manager Card.

## Overview

PaddiSense is a modular system where each feature (Inventory, Stock Tracker, Weather, etc.) is a separate module that can be installed or removed independently. The **PaddiSense Manager** dashboard provides a UI for managing modules.

## Available Modules

| Module | ID | Description | Dependencies |
|--------|-----|-------------|--------------|
| Inventory Manager | `ipm` | Track chemicals, fertilizers, consumables | None |
| Asset Service Manager | `asm` | Equipment and service tracking | None |
| Weather Stations | `weather` | Local and API weather data | None |
| Water Management | `pwm` | Irrigation scheduling and monitoring | None |
| Real Time Rice | `rtr` | Crop growth predictions | None |
| Stock Tracker | `str` | Livestock inventory and movements | None |
| Worker Safety | `wss` | Worker check-in/check-out system | None |
| Hey Farmer | `hfm` | Farm event recording | **Requires: ipm** |

## Installing a Module

### Via Manager Card (Recommended)

1. Navigate to **PaddiSense Manager** dashboard
2. Find the module in **Available Modules** section
3. Click the **Install** button
4. Confirm the installation
5. Home Assistant will restart automatically
6. After restart, the module's dashboard appears in the sidebar

### What Happens During Install

1. **Preflight validation** - Checks YAML syntax and dependencies
2. **Symlink creation** - Links `packages/{module}.yaml` to module's package
3. **Data directory** - Creates `local_data/{module}/` for runtime data
4. **Dashboard registration** - Adds entry to `lovelace_dashboards.yaml`
5. **HA restart** - Loads the new entities and automations

### Dependency Blocking

If a module has unmet dependencies:
- The Install button shows **Blocked**
- A warning displays: `Requires: {missing modules}`
- You must install the required modules first

**Example:** Hey Farmer (hfm) requires Inventory Manager (ipm). Install IPM first.

## Removing a Module

### Via Manager Card

1. Navigate to **PaddiSense Manager** dashboard
2. Find the module in **Installed Modules** section
3. Click the **Remove** button
4. Confirm the removal
5. Home Assistant will restart automatically
6. The module's dashboard is removed from the sidebar

### What Happens During Removal

1. **Dependency check** - Warns if other modules depend on this one
2. **Symlink removal** - Removes `packages/{module}.yaml`
3. **Dashboard deregistration** - Removes from `lovelace_dashboards.yaml`
4. **Data preservation** - `local_data/{module}/` is **NOT deleted**
5. **HA restart** - Unloads the module's entities

### Dependent Module Warning

If other modules depend on the one you're removing:
- A warning displays: `Required by: {dependent modules}`
- You can still remove it (force removal)
- Dependent modules may malfunction until you reinstall or remove them

**Example:** Removing IPM while HFM is installed will show a warning because HFM needs IPM for product data.

## Data Preservation

### What's Preserved on Removal

- `local_data/{module}/` directory and all contents
- Database files (JSON)
- Configuration files
- Backup files

### What's Removed

- Package symlink (HA entities and automations)
- Dashboard registration (sidebar entry)

### Reinstalling After Removal

When you reinstall a module:
- Previous data is automatically available
- No data migration needed
- Configuration is preserved

## File Locations

```
/config/
├── PaddiSense/
│   ├── packages/           # Module symlinks (installed modules)
│   │   ├── ipm.yaml → ../ipm/package.yaml
│   │   ├── str.yaml → ../str/package.yaml
│   │   └── ...
│   ├── modules.json        # Module metadata and versions
│   ├── {module}/           # Module source files
│   │   ├── package.yaml    # HA entities, automations, scripts
│   │   ├── dashboards/     # Lovelace dashboard YAML
│   │   ├── python/         # Backend scripts (if any)
│   │   └── VERSION         # Module version
│   └── ...
├── local_data/
│   ├── {module}/           # Runtime data (preserved on removal)
│   │   ├── config.json
│   │   ├── data.json
│   │   └── backups/
│   └── ...
└── lovelace_dashboards.yaml  # Dashboard registrations
```

## Services

### Install Module
```yaml
service: paddisense.install_module
data:
  module_id: str  # ipm, asm, weather, pwm, rtr, str, wss, hfm
```

### Remove Module
```yaml
service: paddisense.remove_module
data:
  module_id: str
  force: false  # Set true to remove even if dependents exist
```

## Troubleshooting

### Module Won't Install

**Check preflight validation:**
- Ensure `package.yaml` exists and has valid YAML syntax
- Ensure `dashboards/views.yaml` exists
- Check HA logs for specific errors

**Check dependencies:**
- If blocked, install required modules first
- HFM requires IPM

### Module Won't Remove

**Check dependents:**
- Other modules may depend on this one
- Remove dependent modules first, or use force removal

**Check file permissions:**
- Symlink may be locked
- Try restarting HA and retrying

### Dashboard Not Appearing After Install

1. Clear browser cache (Ctrl+F5)
2. Check `lovelace_dashboards.yaml` for the entry
3. Verify the dashboard file path is correct
4. Check HA logs for YAML errors

### Entities Missing After Install

1. Verify the package symlink exists in `packages/`
2. Check that the symlink points to the correct file
3. Reload YAML configuration or restart HA
4. Check HA logs for entity loading errors

### Data Lost After Removal

Data is **never** deleted during removal. Check:
- `local_data/{module}/` directory still exists
- Reinstall the module to access data again

## Module Development

### Creating a New Module

1. Create module directory: `PaddiSense/{module_id}/`
2. Add required files:
   - `package.yaml` - HA entities and automations
   - `dashboards/views.yaml` - Lovelace dashboard
   - `VERSION` - Version string (e.g., `1.0.0`)
3. Add entry to `modules.json`
4. Test installation via Manager Card

### Module Metadata (modules.json)

```json
{
  "module_id": {
    "name": "Display Name",
    "description": "What this module does",
    "icon": "mdi:icon-name",
    "dashboard_slug": "unique-slug",
    "dashboard_title": "Sidebar Title",
    "dashboard_file": "module_id/dashboards/views.yaml",
    "dependencies": ["other_module_id"],
    "status": "rc",
    "version": "1.0.0"
  }
}
```

### Dependencies

To declare dependencies, add to both:
- `modules.json`: `"dependencies": ["ipm"]`
- `const.py` MODULE_METADATA: `"dependencies": ["ipm"]`

The installer will:
- Block installation if dependencies are missing
- Warn before removing a module that others depend on

## Version History

- **v1.3.0** - Added dependency checking and blocking UI
- **v1.2.0** - Added RTR configuration section
- **v1.1.0** - Initial module management UI
