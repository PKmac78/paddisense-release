"""PaddiSense Farm Management Integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    AVAILABLE_MODULES,
    CONF_GITHUB_TOKEN,
    CONF_LICENSE_MODULES,
    DOMAIN,
    EVENT_DATA_UPDATED,
    EVENT_MODULES_CHANGED,
    EVENT_RTR_UPDATED,
    LOVELACE_DASHBOARDS_YAML,
    PACKAGES_DIR,
    PADDISENSE_DIR,
    PLATFORMS,
    REGISTRY_MODULE,
    # Registry services
    SERVICE_ADD_BAY,
    SERVICE_ADD_FARM,
    SERVICE_ADD_PADDOCK,
    SERVICE_ADD_SEASON,
    SERVICE_DELETE_BAY,
    SERVICE_DELETE_FARM,
    SERVICE_DELETE_PADDOCK,
    SERVICE_DELETE_SEASON,
    SERVICE_EDIT_BAY,
    SERVICE_EDIT_FARM,
    SERVICE_EDIT_PADDOCK,
    SERVICE_EDIT_SEASON,
    SERVICE_EXPORT_REGISTRY,
    SERVICE_IMPORT_REGISTRY,
    SERVICE_SET_ACTIVE_SEASON,
    SERVICE_SET_CURRENT_SEASON,
    # Installer services
    SERVICE_CHECK_UPDATES,
    SERVICE_CREATE_BACKUP,
    SERVICE_INSTALL_HACS_CARDS,
    SERVICE_INSTALL_MODULE,
    SERVICE_REMOVE_MODULE,
    SERVICE_RESTORE_BACKUP,
    SERVICE_ROLLBACK,
    SERVICE_UPDATE_PADDISENSE,
    REQUIRED_HACS_CARDS,
    # RTR services
    SERVICE_SET_RTR_URL,
    SERVICE_REFRESH_RTR,
)
from .helpers import cleanup_unlicensed_modules
from .installer import BackupManager, ConfigWriter, GitManager, ModuleManager
from .registry.backend import RegistryBackend
from .rtr.backend import RTRBackend

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# SERVICE SCHEMAS
# =============================================================================

ADD_PADDOCK_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("bay_count"): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
    vol.Optional("farm_id", default="farm_1"): cv.string,
    vol.Optional("bay_prefix", default="B-"): cv.string,
    vol.Optional("current_season", default=True): cv.boolean,
})

EDIT_PADDOCK_SCHEMA = vol.Schema({
    vol.Required("paddock_id"): cv.string,
    vol.Optional("name"): cv.string,
    vol.Optional("farm_id"): cv.string,
    vol.Optional("current_season"): cv.boolean,
})

DELETE_PADDOCK_SCHEMA = vol.Schema({
    vol.Required("paddock_id"): cv.string,
})

SET_CURRENT_SEASON_SCHEMA = vol.Schema({
    vol.Required("paddock_id"): cv.string,
    vol.Optional("value"): cv.boolean,
})

ADD_BAY_SCHEMA = vol.Schema({
    vol.Required("paddock_id"): cv.string,
    vol.Required("name"): cv.string,
    vol.Optional("order"): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    vol.Optional("is_last", default=False): cv.boolean,
})

EDIT_BAY_SCHEMA = vol.Schema({
    vol.Required("bay_id"): cv.string,
    vol.Optional("name"): cv.string,
    vol.Optional("order"): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    vol.Optional("is_last"): cv.boolean,
})

DELETE_BAY_SCHEMA = vol.Schema({
    vol.Required("bay_id"): cv.string,
})

ADD_SEASON_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("start_date"): cv.string,
    vol.Required("end_date"): cv.string,
    vol.Optional("active", default=False): cv.boolean,
})

EDIT_SEASON_SCHEMA = vol.Schema({
    vol.Required("season_id"): cv.string,
    vol.Optional("name"): cv.string,
    vol.Optional("start_date"): cv.string,
    vol.Optional("end_date"): cv.string,
})

DELETE_SEASON_SCHEMA = vol.Schema({
    vol.Required("season_id"): cv.string,
})

SET_ACTIVE_SEASON_SCHEMA = vol.Schema({
    vol.Required("season_id"): cv.string,
})

ADD_FARM_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
})

EDIT_FARM_SCHEMA = vol.Schema({
    vol.Required("farm_id"): cv.string,
    vol.Optional("name"): cv.string,
})

DELETE_FARM_SCHEMA = vol.Schema({
    vol.Required("farm_id"): cv.string,
})

IMPORT_REGISTRY_SCHEMA = vol.Schema({
    vol.Required("filename"): cv.string,
})

# Installer schemas
INSTALL_MODULE_SCHEMA = vol.Schema({
    vol.Required("module_id"): vol.In(AVAILABLE_MODULES),
})

REMOVE_MODULE_SCHEMA = vol.Schema({
    vol.Required("module_id"): vol.In(AVAILABLE_MODULES),
})

UPDATE_PADDISENSE_SCHEMA = vol.Schema({
    vol.Optional("backup_first", default=True): cv.boolean,
})

RESTORE_BACKUP_SCHEMA = vol.Schema({
    vol.Required("backup_id"): cv.string,
})

# RTR schemas
SET_RTR_URL_SCHEMA = vol.Schema({
    vol.Required("url"): cv.string,
})


# =============================================================================
# SETUP
# =============================================================================

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up PaddiSense from yaml configuration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PaddiSense from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize backend
    backend = RegistryBackend()
    await hass.async_add_executor_job(backend.init)

    # Cleanup unlicensed module folders
    licensed_modules = entry.data.get(CONF_LICENSE_MODULES, [])
    if licensed_modules:
        cleanup_result = await hass.async_add_executor_job(
            cleanup_unlicensed_modules, licensed_modules
        )
        if cleanup_result.get("removed"):
            _LOGGER.info(
                "Cleaned up unlicensed modules: %s",
                ", ".join(cleanup_result["removed"])
            )

    # Initialize installer components with token from license
    git_manager = GitManager(token=entry.data.get(CONF_GITHUB_TOKEN))
    module_manager = ModuleManager()
    backup_manager = BackupManager()
    config_writer = ConfigWriter()

    # Initialize RTR backend
    rtr_backend = RTRBackend()
    await hass.async_add_executor_job(rtr_backend.init)

    # Store references
    hass.data[DOMAIN]["backend"] = backend
    hass.data[DOMAIN]["rtr_backend"] = rtr_backend
    hass.data[DOMAIN]["entry_id"] = entry.entry_id
    hass.data[DOMAIN]["git_manager"] = git_manager
    hass.data[DOMAIN]["module_manager"] = module_manager
    hass.data[DOMAIN]["backup_manager"] = backup_manager
    hass.data[DOMAIN]["config_writer"] = config_writer

    # Ensure registry (core) is always installed
    await hass.async_add_executor_job(_ensure_registry_installed)

    # Register services
    await _async_register_registry_services(hass, backend)
    await _async_register_installer_services(hass)
    await _async_register_rtr_services(hass, rtr_backend)

    # Register frontend resources
    await _async_register_frontend(hass)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove all services
        all_services = [
            # Registry
            SERVICE_ADD_PADDOCK, SERVICE_EDIT_PADDOCK, SERVICE_DELETE_PADDOCK,
            SERVICE_SET_CURRENT_SEASON, SERVICE_ADD_BAY, SERVICE_EDIT_BAY,
            SERVICE_DELETE_BAY, SERVICE_ADD_SEASON, SERVICE_EDIT_SEASON,
            SERVICE_DELETE_SEASON, SERVICE_SET_ACTIVE_SEASON, SERVICE_ADD_FARM,
            SERVICE_EDIT_FARM, SERVICE_DELETE_FARM, SERVICE_EXPORT_REGISTRY,
            SERVICE_IMPORT_REGISTRY,
            # Installer
            SERVICE_CHECK_UPDATES, SERVICE_UPDATE_PADDISENSE, SERVICE_INSTALL_MODULE,
            SERVICE_REMOVE_MODULE, SERVICE_CREATE_BACKUP, SERVICE_RESTORE_BACKUP,
            SERVICE_ROLLBACK, SERVICE_INSTALL_HACS_CARDS,
            # RTR
            SERVICE_SET_RTR_URL, SERVICE_REFRESH_RTR,
        ]
        for service in all_services:
            hass.services.async_remove(DOMAIN, service)

        # Clean up data
        hass.data[DOMAIN].pop("backend", None)
        hass.data[DOMAIN].pop("rtr_backend", None)
        hass.data[DOMAIN].pop("entry_id", None)
        hass.data[DOMAIN].pop("git_manager", None)
        hass.data[DOMAIN].pop("module_manager", None)
        hass.data[DOMAIN].pop("backup_manager", None)
        hass.data[DOMAIN].pop("config_writer", None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry - clean up dashboards and symlinks."""
    from pathlib import Path
    from .const import LOVELACE_DASHBOARDS_YAML, PACKAGES_DIR, MODULE_METADATA

    _LOGGER.info("Removing PaddiSense integration - cleaning up dashboards and packages")

    # Remove module symlinks from packages directory
    if PACKAGES_DIR.exists():
        for module_id in AVAILABLE_MODULES:
            symlink_path = PACKAGES_DIR / f"{module_id}.yaml"
            if symlink_path.exists() or symlink_path.is_symlink():
                try:
                    symlink_path.unlink()
                    _LOGGER.info("Removed package symlink: %s", symlink_path)
                except OSError as e:
                    _LOGGER.warning("Failed to remove symlink %s: %s", symlink_path, e)

    # Remove PaddiSense dashboards from lovelace_dashboards.yaml
    if LOVELACE_DASHBOARDS_YAML.exists():
        try:
            import yaml
            content = LOVELACE_DASHBOARDS_YAML.read_text(encoding="utf-8")
            dashboards = yaml.safe_load(content) or {}

            # Find and remove PaddiSense dashboards
            paddisense_slugs = []
            for module_id, meta in MODULE_METADATA.items():
                slug = meta.get("dashboard_slug", f"{module_id}-dashboard")
                paddisense_slugs.append(slug)

            # Also check for registry dashboard
            paddisense_slugs.append("paddisense-registry")

            removed = []
            for slug in paddisense_slugs:
                if slug in dashboards:
                    del dashboards[slug]
                    removed.append(slug)

            if removed:
                # Write back
                header = """# Lovelace Dashboards
# Managed by Home Assistant

"""
                new_content = header + yaml.dump(dashboards, default_flow_style=False, sort_keys=False)
                LOVELACE_DASHBOARDS_YAML.write_text(new_content, encoding="utf-8")
                _LOGGER.info("Removed dashboards: %s", ", ".join(removed))

        except Exception as e:
            _LOGGER.warning("Failed to clean up dashboards: %s", e)

    _LOGGER.info("PaddiSense cleanup complete. Restart Home Assistant to apply changes.")


# =============================================================================
# REGISTRY SERVICES
# =============================================================================

async def _async_register_registry_services(
    hass: HomeAssistant, backend: RegistryBackend
) -> None:
    """Register Farm Registry services."""

    async def handle_add_paddock(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.add_paddock,
            call.data["name"],
            call.data["bay_count"],
            call.data.get("farm_id", "farm_1"),
            call.data.get("bay_prefix", "B-"),
            call.data.get("current_season", True),
        )
        _log_service_result("add_paddock", result)
        await _async_update_sensors(hass)

    async def handle_edit_paddock(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.edit_paddock,
            call.data["paddock_id"],
            call.data.get("name"),
            call.data.get("farm_id"),
            call.data.get("current_season"),
        )
        _log_service_result("edit_paddock", result)
        await _async_update_sensors(hass)

    async def handle_delete_paddock(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.delete_paddock,
            call.data["paddock_id"],
        )
        _log_service_result("delete_paddock", result)
        await _async_update_sensors(hass)

    async def handle_set_current_season(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.set_current_season,
            call.data["paddock_id"],
            call.data.get("value"),
        )
        _log_service_result("set_current_season", result)
        await _async_update_sensors(hass)

    async def handle_add_bay(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.add_bay,
            call.data["paddock_id"],
            call.data["name"],
            call.data.get("order"),
            call.data.get("is_last", False),
        )
        _log_service_result("add_bay", result)
        await _async_update_sensors(hass)

    async def handle_edit_bay(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.edit_bay,
            call.data["bay_id"],
            call.data.get("name"),
            call.data.get("order"),
            call.data.get("is_last"),
        )
        _log_service_result("edit_bay", result)
        await _async_update_sensors(hass)

    async def handle_delete_bay(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.delete_bay,
            call.data["bay_id"],
        )
        _log_service_result("delete_bay", result)
        await _async_update_sensors(hass)

    async def handle_add_season(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.add_season,
            call.data["name"],
            call.data["start_date"],
            call.data["end_date"],
            call.data.get("active", False),
        )
        _log_service_result("add_season", result)
        await _async_update_sensors(hass)

    async def handle_edit_season(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.edit_season,
            call.data["season_id"],
            call.data.get("name"),
            call.data.get("start_date"),
            call.data.get("end_date"),
        )
        _log_service_result("edit_season", result)
        await _async_update_sensors(hass)

    async def handle_delete_season(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.delete_season,
            call.data["season_id"],
        )
        _log_service_result("delete_season", result)
        await _async_update_sensors(hass)

    async def handle_set_active_season(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.set_active_season,
            call.data["season_id"],
        )
        _log_service_result("set_active_season", result)
        await _async_update_sensors(hass)

    async def handle_add_farm(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.add_farm,
            call.data["name"],
        )
        _log_service_result("add_farm", result)
        await _async_update_sensors(hass)

    async def handle_edit_farm(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.edit_farm,
            call.data["farm_id"],
            call.data.get("name"),
        )
        _log_service_result("edit_farm", result)
        await _async_update_sensors(hass)

    async def handle_delete_farm(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.delete_farm,
            call.data["farm_id"],
        )
        _log_service_result("delete_farm", result)
        await _async_update_sensors(hass)

    async def handle_export_registry(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(backend.export_registry)
        _log_service_result("export_registry", result)

    async def handle_import_registry(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            backend.import_registry,
            call.data["filename"],
        )
        _log_service_result("import_registry", result)
        await _async_update_sensors(hass)

    # Register all registry services
    hass.services.async_register(DOMAIN, SERVICE_ADD_PADDOCK, handle_add_paddock, ADD_PADDOCK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EDIT_PADDOCK, handle_edit_paddock, EDIT_PADDOCK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_PADDOCK, handle_delete_paddock, DELETE_PADDOCK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_CURRENT_SEASON, handle_set_current_season, SET_CURRENT_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_BAY, handle_add_bay, ADD_BAY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EDIT_BAY, handle_edit_bay, EDIT_BAY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_BAY, handle_delete_bay, DELETE_BAY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_SEASON, handle_add_season, ADD_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EDIT_SEASON, handle_edit_season, EDIT_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_SEASON, handle_delete_season, DELETE_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_ACTIVE_SEASON, handle_set_active_season, SET_ACTIVE_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_FARM, handle_add_farm, ADD_FARM_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EDIT_FARM, handle_edit_farm, EDIT_FARM_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_FARM, handle_delete_farm, DELETE_FARM_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EXPORT_REGISTRY, handle_export_registry)
    hass.services.async_register(DOMAIN, SERVICE_IMPORT_REGISTRY, handle_import_registry, IMPORT_REGISTRY_SCHEMA)


# =============================================================================
# INSTALLER SERVICES
# =============================================================================

async def _async_register_installer_services(hass: HomeAssistant) -> None:
    """Register installer services."""

    async def handle_check_updates(call: ServiceCall) -> None:
        """Check for PaddiSense updates and report telemetry."""
        from .telemetry import report_update_check

        git_manager: GitManager = hass.data[DOMAIN]["git_manager"]
        module_manager: ModuleManager = hass.data[DOMAIN]["module_manager"]

        # Check for updates
        result = await hass.async_add_executor_job(git_manager.check_for_updates)
        _log_service_result("check_for_updates", result)

        # Get installed modules for telemetry
        installed = await hass.async_add_executor_job(module_manager.get_installed_modules)
        installed_ids = [m["id"] for m in installed]

        # Report telemetry (non-blocking, fire and forget)
        hass.async_create_task(
            report_update_check(
                installed_modules=installed_ids,
                local_version=result.get("local_version"),
                remote_version=result.get("remote_version"),
                update_available=result.get("update_available", False),
            )
        )

        # Update version sensor
        if result.get("success"):
            hass.bus.async_fire(EVENT_MODULES_CHANGED)

    async def handle_update_paddisense(call: ServiceCall) -> None:
        """Update PaddiSense to latest version."""
        backup_manager: BackupManager = hass.data[DOMAIN]["backup_manager"]
        git_manager: GitManager = hass.data[DOMAIN]["git_manager"]

        # Create backup first if requested
        if call.data.get("backup_first", True):
            backup_result = await hass.async_add_executor_job(
                backup_manager.create_backup, "pre_update"
            )
            if not backup_result.get("success"):
                _LOGGER.error("Backup failed, aborting update")
                return

        # Pull latest changes
        result = await hass.async_add_executor_job(git_manager.pull)
        _log_service_result("update_paddisense", result)

        if result.get("success"):
            # Trigger restart
            _LOGGER.info("PaddiSense updated, triggering restart")
            await hass.services.async_call("homeassistant", "restart")
        else:
            # Rollback on failure
            _LOGGER.error("Update failed, attempting rollback")
            await hass.async_add_executor_job(backup_manager.rollback)

    async def handle_install_module(call: ServiceCall) -> None:
        """Install a PaddiSense module."""
        module_manager: ModuleManager = hass.data[DOMAIN]["module_manager"]
        result = await hass.async_add_executor_job(
            module_manager.install_module,
            call.data["module_id"],
        )
        _log_service_result("install_module", result)

        if result.get("success") and result.get("restart_required"):
            hass.bus.async_fire(EVENT_MODULES_CHANGED)
            await hass.services.async_call("homeassistant", "restart")

    async def handle_remove_module(call: ServiceCall) -> None:
        """Remove a PaddiSense module."""
        module_manager: ModuleManager = hass.data[DOMAIN]["module_manager"]
        result = await hass.async_add_executor_job(
            module_manager.remove_module,
            call.data["module_id"],
        )
        _log_service_result("remove_module", result)

        if result.get("success") and result.get("restart_required"):
            hass.bus.async_fire(EVENT_MODULES_CHANGED)
            await hass.services.async_call("homeassistant", "restart")

    async def handle_create_backup(call: ServiceCall) -> None:
        """Create a PaddiSense backup."""
        backup_manager: BackupManager = hass.data[DOMAIN]["backup_manager"]
        result = await hass.async_add_executor_job(
            backup_manager.create_backup, "manual"
        )
        _log_service_result("create_backup", result)

    async def handle_restore_backup(call: ServiceCall) -> None:
        """Restore from a backup."""
        backup_manager: BackupManager = hass.data[DOMAIN]["backup_manager"]
        result = await hass.async_add_executor_job(
            backup_manager.restore_backup,
            call.data["backup_id"],
        )
        _log_service_result("restore_backup", result)

        if result.get("success") and result.get("restart_required"):
            await hass.services.async_call("homeassistant", "restart")

    async def handle_rollback(call: ServiceCall) -> None:
        """Rollback to previous version."""
        backup_manager: BackupManager = hass.data[DOMAIN]["backup_manager"]
        result = await hass.async_add_executor_job(backup_manager.rollback)
        _log_service_result("rollback", result)

        if result.get("success") and result.get("restart_required"):
            await hass.services.async_call("homeassistant", "restart")

    async def handle_install_hacs_cards(call: ServiceCall) -> None:
        """Install required HACS frontend cards."""
        # Check if HACS is available
        if not hass.services.has_service("hacs", "install"):
            _LOGGER.error("HACS is not installed or not ready")
            await hass.services.async_call(
                "persistent_notification", "create",
                {
                    "title": "PaddiSense",
                    "message": "HACS is not installed. Please install HACS first, then run this service again.",
                },
            )
            return

        installed = []
        failed = []

        for card in REQUIRED_HACS_CARDS:
            try:
                _LOGGER.info("Installing HACS card: %s", card["repository"])
                await hass.services.async_call(
                    "hacs", "install",
                    {
                        "repository": card["repository"],
                        "category": card["category"],
                    },
                )
                installed.append(card["repository"])
            except Exception as e:
                _LOGGER.error("Failed to install %s: %s", card["repository"], e)
                failed.append(card["repository"])

        # Notify user
        if installed:
            msg = f"Installed: {', '.join(installed)}"
            if failed:
                msg += f"\nFailed: {', '.join(failed)}"
            msg += "\n\nPlease refresh your browser (Ctrl+F5) to load the new cards."
        else:
            msg = f"Failed to install cards: {', '.join(failed)}"

        await hass.services.async_call(
            "persistent_notification", "create",
            {
                "title": "PaddiSense - HACS Cards",
                "message": msg,
            },
        )

    # Register installer services
    hass.services.async_register(DOMAIN, SERVICE_CHECK_UPDATES, handle_check_updates)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_PADDISENSE, handle_update_paddisense, UPDATE_PADDISENSE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_INSTALL_MODULE, handle_install_module, INSTALL_MODULE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_MODULE, handle_remove_module, REMOVE_MODULE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_BACKUP, handle_create_backup)
    hass.services.async_register(DOMAIN, SERVICE_RESTORE_BACKUP, handle_restore_backup, RESTORE_BACKUP_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ROLLBACK, handle_rollback)
    hass.services.async_register(DOMAIN, SERVICE_INSTALL_HACS_CARDS, handle_install_hacs_cards)


# =============================================================================
# RTR SERVICES
# =============================================================================

async def _async_register_rtr_services(
    hass: HomeAssistant, rtr_backend: RTRBackend
) -> None:
    """Register RTR (Real Time Rice) services."""

    async def handle_set_rtr_url(call: ServiceCall) -> None:
        """Set the RTR dashboard URL."""
        result = await hass.async_add_executor_job(
            rtr_backend.set_url,
            call.data["url"],
        )
        _log_service_result("set_rtr_url", result)

        if result.get("success"):
            # Auto-refresh data after setting URL
            refresh_result = await hass.async_add_executor_job(rtr_backend.refresh_data)
            _log_service_result("refresh_rtr_data", refresh_result)
            hass.bus.async_fire(EVENT_RTR_UPDATED)

    async def handle_refresh_rtr(call: ServiceCall) -> None:
        """Refresh RTR data from CSV endpoint."""
        result = await hass.async_add_executor_job(rtr_backend.refresh_data)
        _log_service_result("refresh_rtr_data", result)

        if result.get("success"):
            hass.bus.async_fire(EVENT_RTR_UPDATED)

    # Register RTR services
    hass.services.async_register(
        DOMAIN, SERVICE_SET_RTR_URL, handle_set_rtr_url, SET_RTR_URL_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_RTR, handle_refresh_rtr)


# =============================================================================
# HELPERS
# =============================================================================

def _ensure_registry_installed() -> None:
    """Ensure the registry package and dashboard are installed (core component)."""
    import yaml
    from pathlib import Path

    # Create packages directory if needed
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Install registry package symlink
    registry_package = PADDISENSE_DIR / "registry" / "package.yaml"
    symlink_path = PACKAGES_DIR / "registry.yaml"

    if registry_package.exists() and not symlink_path.exists():
        try:
            relative_target = Path("..") / "registry" / "package.yaml"
            symlink_path.symlink_to(relative_target)
            _LOGGER.info("Installed registry package symlink")
        except OSError as e:
            _LOGGER.warning("Failed to create registry symlink: %s", e)

    # Register registry dashboard
    dashboard_file = PADDISENSE_DIR / REGISTRY_MODULE["dashboard_file"]
    if dashboard_file.exists():
        try:
            dashboards = {}
            if LOVELACE_DASHBOARDS_YAML.exists():
                content = LOVELACE_DASHBOARDS_YAML.read_text(encoding="utf-8")
                dashboards = yaml.safe_load(content) or {}

            slug = REGISTRY_MODULE["dashboard_slug"]
            if slug not in dashboards:
                relative_path = str(dashboard_file.relative_to(Path("/config")))
                dashboards[slug] = {
                    "mode": "yaml",
                    "title": REGISTRY_MODULE["dashboard_title"],
                    "icon": REGISTRY_MODULE["icon"],
                    "show_in_sidebar": True,
                    "filename": relative_path,
                }

                header = """# Auto-generated by PaddiSense
# Do not edit manually - changes may be overwritten

"""
                new_content = header + yaml.dump(dashboards, default_flow_style=False, sort_keys=False)
                LOVELACE_DASHBOARDS_YAML.write_text(new_content, encoding="utf-8")
                _LOGGER.info("Registered Farm Registry dashboard")
        except Exception as e:
            _LOGGER.warning("Failed to register registry dashboard: %s", e)


def _log_service_result(service: str, result: dict[str, Any]) -> None:
    """Log service result."""
    if result.get("success"):
        _LOGGER.info("PaddiSense %s: %s", service, result.get("message", "Success"))
    else:
        _LOGGER.error("PaddiSense %s failed: %s", service, result.get("error", "Unknown error"))


async def _async_update_sensors(hass: HomeAssistant) -> None:
    """Trigger sensor update after data change."""
    hass.bus.async_fire(EVENT_DATA_UPDATED)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register frontend resources."""
    from homeassistant.components.http import StaticPathConfig

    # Register custom card JS as static paths
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            "/paddisense/paddisense-registry-card.js",
            hass.config.path("custom_components/paddisense/www/paddisense-registry-card.js"),
            cache_headers=False,
        ),
        StaticPathConfig(
            "/paddisense/paddisense-manager-card.js",
            hass.config.path("custom_components/paddisense/www/paddisense-manager-card.js"),
            cache_headers=False,
        ),
    ])

    # Auto-register resources in lovelace_resources storage
    await _async_register_lovelace_resources(hass)

    _LOGGER.info("PaddiSense frontend resources registered")


async def _async_register_lovelace_resources(hass: HomeAssistant) -> None:
    """Register PaddiSense cards in lovelace_resources storage."""
    import json
    from pathlib import Path

    resources_file = Path(hass.config.path(".storage/lovelace_resources"))

    paddisense_resources = [
        {
            "id": "paddisense_registry_card",
            "url": "/paddisense/paddisense-registry-card.js",
            "type": "module",
        },
        {
            "id": "paddisense_manager_card",
            "url": "/paddisense/paddisense-manager-card.js",
            "type": "module",
        },
    ]

    try:
        if resources_file.exists():
            content = await hass.async_add_executor_job(resources_file.read_text)
            data = json.loads(content)
        else:
            data = {
                "version": 1,
                "minor_version": 1,
                "key": "lovelace_resources",
                "data": {"items": []},
            }

        items = data.get("data", {}).get("items", [])
        existing_ids = {item.get("id") for item in items}

        # Add missing PaddiSense resources
        added = []
        for resource in paddisense_resources:
            if resource["id"] not in existing_ids:
                items.insert(0, resource)
                added.append(resource["id"])

        if added:
            data["data"]["items"] = items
            new_content = json.dumps(data, indent=2)
            await hass.async_add_executor_job(
                resources_file.write_text, new_content
            )
            _LOGGER.info("Added lovelace resources: %s", ", ".join(added))

    except Exception as e:
        _LOGGER.warning("Failed to register lovelace resources: %s", e)
