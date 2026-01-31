"""Constants for PaddiSense integration."""
from pathlib import Path

DOMAIN = "paddisense"
VERSION = "1.0.0"

# =============================================================================
# PATHS
# =============================================================================

CONFIG_DIR = Path("/config")
PADDISENSE_DIR = CONFIG_DIR / "PaddiSense"
DATA_DIR = CONFIG_DIR / "local_data"
BACKUP_DIR = DATA_DIR / "paddisense_backups"

# Registry paths
REGISTRY_DATA_DIR = DATA_DIR / "registry"
REGISTRY_CONFIG_FILE = REGISTRY_DATA_DIR / "config.json"
REGISTRY_BACKUP_DIR = REGISTRY_DATA_DIR / "backups"

# Configuration files
SERVER_YAML = CONFIG_DIR / "server.yaml"
CONFIGURATION_YAML = CONFIG_DIR / "configuration.yaml"
LOVELACE_DASHBOARDS_YAML = CONFIG_DIR / "lovelace_dashboards.yaml"

# Module repo
MODULES_JSON = PADDISENSE_DIR / "modules.json"
PADDISENSE_VERSION_FILE = PADDISENSE_DIR / "VERSION"
PACKAGES_DIR = PADDISENSE_DIR / "packages"

# =============================================================================
# GIT
# =============================================================================

PADDISENSE_REPO_URL = "https://github.com/PKmac78/PaddiSense.git"  # Your module repo
PADDISENSE_REPO_BRANCH = "main"

# =============================================================================
# MODULES
# =============================================================================

AVAILABLE_MODULES = ["ipm", "asm", "weather", "pwm"]

MODULE_METADATA = {
    "ipm": {
        "name": "Inventory Manager",
        "description": "Track chemicals, fertilizers, and consumables",
        "icon": "mdi:warehouse",
        "dashboard_slug": "ipm-inventory",
        "dashboard_title": "Inventory Manager",
    },
    "asm": {
        "name": "Asset Service Manager",
        "description": "Track equipment, parts, and service history",
        "icon": "mdi:tractor",
        "dashboard_slug": "asm-service",
        "dashboard_title": "Asset Service Manager",
    },
    "weather": {
        "name": "Weather Stations",
        "description": "Local gateway and API weather data",
        "icon": "mdi:weather-cloudy",
        "dashboard_slug": "weather-station",
        "dashboard_title": "Weather",
    },
    "pwm": {
        "name": "Water Management",
        "description": "Irrigation scheduling and bay monitoring",
        "icon": "mdi:water",
        "dashboard_slug": "pwm-irrigation",
        "dashboard_title": "Water Management",
    },
}

# =============================================================================
# CONFIG FLOW
# =============================================================================

CONF_GROWER_NAME = "grower_name"
CONF_FARM_NAME = "farm_name"
CONF_FARM_ID = "farm_id"
CONF_TIMEZONE = "timezone"
CONF_IMPORT_EXISTING = "import_existing"
CONF_SELECTED_MODULES = "selected_modules"
CONF_INSTALL_TYPE = "install_type"

# License key configuration
CONF_LICENSE_KEY = "license_key"
CONF_LICENSE_GROWER = "license_grower"
CONF_LICENSE_EXPIRY = "license_expiry"
CONF_LICENSE_MODULES = "license_modules"
CONF_LICENSE_SEASON = "license_season"
CONF_GITHUB_TOKEN = "github_token"

# Install types
INSTALL_TYPE_FRESH = "fresh"
INSTALL_TYPE_UPGRADE = "upgrade"
INSTALL_TYPE_IMPORT = "import"

# Default values
DEFAULT_FARM_ID = "farm_1"
DEFAULT_BAY_PREFIX = "B-"

# =============================================================================
# SERVICES - REGISTRY
# =============================================================================

SERVICE_ADD_PADDOCK = "add_paddock"
SERVICE_EDIT_PADDOCK = "edit_paddock"
SERVICE_DELETE_PADDOCK = "delete_paddock"
SERVICE_SET_CURRENT_SEASON = "set_current_season"
SERVICE_ADD_BAY = "add_bay"
SERVICE_EDIT_BAY = "edit_bay"
SERVICE_DELETE_BAY = "delete_bay"
SERVICE_ADD_SEASON = "add_season"
SERVICE_EDIT_SEASON = "edit_season"
SERVICE_DELETE_SEASON = "delete_season"
SERVICE_SET_ACTIVE_SEASON = "set_active_season"
SERVICE_ADD_FARM = "add_farm"
SERVICE_EDIT_FARM = "edit_farm"
SERVICE_DELETE_FARM = "delete_farm"
SERVICE_EXPORT_REGISTRY = "export_registry"
SERVICE_IMPORT_REGISTRY = "import_registry"

# =============================================================================
# SERVICES - INSTALLER
# =============================================================================

SERVICE_CHECK_UPDATES = "check_for_updates"
SERVICE_UPDATE_PADDISENSE = "update_paddisense"
SERVICE_INSTALL_MODULE = "install_module"
SERVICE_REMOVE_MODULE = "remove_module"
SERVICE_CREATE_BACKUP = "create_backup"
SERVICE_RESTORE_BACKUP = "restore_backup"
SERVICE_ROLLBACK = "rollback"
SERVICE_INSTALL_HACS_CARDS = "install_hacs_cards"

# Required HACS frontend cards
REQUIRED_HACS_CARDS = [
    {"repository": "custom-cards/button-card", "category": "plugin"},
    {"repository": "thomasloven/lovelace-card-mod", "category": "plugin"},
]

# Registry is always installed (core component)
REGISTRY_MODULE = {
    "id": "registry",
    "name": "Farm Registry",
    "dashboard_slug": "paddisense-registry",
    "dashboard_title": "Farm Registry",
    "dashboard_file": "registry/dashboards/config.yaml",
    "icon": "mdi:barn",
}

# =============================================================================
# PLATFORMS & ATTRIBUTES
# =============================================================================

PLATFORMS = ["sensor"]

# Registry sensor attributes
ATTR_PADDOCKS = "paddocks"
ATTR_BAYS = "bays"
ATTR_SEASONS = "seasons"
ATTR_FARMS = "farms"
ATTR_HIERARCHY = "hierarchy"
ATTR_GROWER = "grower"
ATTR_ACTIVE_SEASON = "active_season"
ATTR_ACTIVE_SEASON_NAME = "active_season_name"
ATTR_TOTAL_PADDOCKS = "total_paddocks"
ATTR_TOTAL_BAYS = "total_bays"
ATTR_TOTAL_SEASONS = "total_seasons"
ATTR_TOTAL_FARMS = "total_farms"

# Version sensor attributes
ATTR_INSTALLED_VERSION = "installed_version"
ATTR_LATEST_VERSION = "latest_version"
ATTR_UPDATE_AVAILABLE = "update_available"
ATTR_LAST_CHECKED = "last_checked"
ATTR_INSTALLED_MODULES = "installed_modules"
ATTR_AVAILABLE_MODULES = "available_modules"

# =============================================================================
# EVENTS
# =============================================================================

EVENT_DATA_UPDATED = f"{DOMAIN}_data_updated"
EVENT_MODULES_CHANGED = f"{DOMAIN}_modules_changed"
