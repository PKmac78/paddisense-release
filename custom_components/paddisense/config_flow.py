"""Config flow for PaddiSense integration."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AVAILABLE_MODULES,
    CONFIG_DIR,
    CONF_AGREEMENTS,
    CONF_FARM_ID,
    CONF_FARM_NAME,
    CONF_GITHUB_TOKEN,
    CONF_GROWER_EMAIL,
    CONF_GROWER_NAME,
    CONF_IMPORT_EXISTING,
    CONF_INSTALL_TYPE,
    CONF_LICENSE_MODULES,
    CONF_REGISTERED,
    CONF_REGISTRATION_DATE,
    CONF_SELECTED_MODULES,
    CONF_SERVER_ID,
    DOMAIN,
    FREE_MODULES,
    INSTALL_TYPE_FRESH,
    INSTALL_TYPE_IMPORT,
    INSTALL_TYPE_UPGRADE,
)

# Dev mode bypass - skip some checks if .dev_mode file exists
DEV_MODE_FILE = CONFIG_DIR / ".dev_mode"

from .helpers import (
    existing_data_detected,
    existing_repo_detected,
    extract_grower,
    get_existing_data_summary,
    get_repo_summary,
    get_saved_license_key,
    load_server_yaml,
    save_license_key,
)
from .installer import BackupManager, ConfigWriter, GitManager, ModuleManager
from .license import LicenseError, track_activation, validate_license
from .registration import register_locally
from .registry.backend import RegistryBackend

_LOGGER = logging.getLogger(__name__)

# Email validation regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class PaddiSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PaddiSense."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict = {}
        self._existing_data: dict = {}
        self._repo_summary: dict = {}
        self._git_available = False

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step - welcome and detection."""
        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        # Check for existing repo and data
        has_repo = await self.hass.async_add_executor_job(existing_repo_detected)
        has_data = await self.hass.async_add_executor_job(existing_data_detected)

        if has_repo:
            self._repo_summary = await self.hass.async_add_executor_job(get_repo_summary)

        if has_data:
            self._existing_data = await self.hass.async_add_executor_job(get_existing_data_summary)

        # Determine available options
        if has_repo and has_data:
            return await self.async_step_welcome_upgrade()
        elif has_data:
            return await self.async_step_welcome_import()
        else:
            return await self.async_step_welcome_fresh()

    async def async_step_welcome_fresh(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Welcome screen for fresh installation."""
        if user_input is not None:
            self._data[CONF_INSTALL_TYPE] = INSTALL_TYPE_FRESH
            return await self.async_step_registration()

        return self.async_show_form(
            step_id="welcome_fresh",
            description_placeholders={
                "title": "Welcome to PaddiSense!",
            },
        )

    async def async_step_welcome_upgrade(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Welcome screen when existing installation detected."""
        if user_input is not None:
            install_type = user_input.get("install_type", INSTALL_TYPE_UPGRADE)
            self._data[CONF_INSTALL_TYPE] = install_type
            return await self.async_step_registration()

        return self.async_show_form(
            step_id="welcome_upgrade",
            data_schema=vol.Schema({
                vol.Required("install_type", default=INSTALL_TYPE_UPGRADE): vol.In({
                    INSTALL_TYPE_UPGRADE: "Upgrade existing installation",
                    INSTALL_TYPE_FRESH: "Fresh installation (re-download)",
                }),
            }),
            description_placeholders={
                "version": self._repo_summary.get("version", "unknown"),
                "module_count": str(self._repo_summary.get("module_count", 0)),
                "paddock_count": str(self._existing_data.get("paddock_count", 0)),
                "bay_count": str(self._existing_data.get("bay_count", 0)),
            },
        )

    async def async_step_welcome_import(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Welcome screen when only data exists (no repo)."""
        if user_input is not None:
            if user_input.get(CONF_IMPORT_EXISTING):
                self._data[CONF_INSTALL_TYPE] = INSTALL_TYPE_IMPORT
                self._data[CONF_IMPORT_EXISTING] = True
            else:
                self._data[CONF_INSTALL_TYPE] = INSTALL_TYPE_FRESH

            return await self.async_step_registration()

        return self.async_show_form(
            step_id="welcome_import",
            data_schema=vol.Schema({
                vol.Required(CONF_IMPORT_EXISTING, default=True): bool,
            }),
            description_placeholders={
                "paddock_count": str(self._existing_data.get("paddock_count", 0)),
                "bay_count": str(self._existing_data.get("bay_count", 0)),
                "season_count": str(self._existing_data.get("season_count", 0)),
            },
        )

    async def async_step_registration(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle registration - grower name and email (local only)."""
        errors = {}

        # Check for dev mode
        is_dev_mode = await self.hass.async_add_executor_job(DEV_MODE_FILE.exists)

        if user_input is not None:
            grower_name = user_input.get(CONF_GROWER_NAME, "").strip()
            grower_email = user_input.get(CONF_GROWER_EMAIL, "").strip()

            # Validate grower name
            if not grower_name:
                errors[CONF_GROWER_NAME] = "required"

            # Validate email format
            if not grower_email:
                errors[CONF_GROWER_EMAIL] = "required"
            elif not EMAIL_REGEX.match(grower_email):
                errors[CONF_GROWER_EMAIL] = "invalid_email"

            # If validation passed, register locally
            if not errors:
                # Local registration - no external calls
                result = await self.hass.async_add_executor_job(
                    register_locally, grower_name, grower_email
                )

                self._data[CONF_GROWER_NAME] = grower_name
                self._data[CONF_GROWER_EMAIL] = grower_email
                self._data[CONF_REGISTERED] = True
                self._data[CONF_SERVER_ID] = result["server_id"]
                self._data[CONF_REGISTRATION_DATE] = result["registered_at"]
                self._data[CONF_LICENSE_MODULES] = result.get("modules_allowed", list(FREE_MODULES))
                self._data[CONF_GITHUB_TOKEN] = ""  # Public repo access
                self._data[CONF_FARM_NAME] = ""
                self._data[CONF_FARM_ID] = ""
                self._data[CONF_SELECTED_MODULES] = []
                self._data[CONF_AGREEMENTS] = {}

                # In dev mode, allow all modules and skip license
                if is_dev_mode:
                    self._data[CONF_LICENSE_MODULES] = list(AVAILABLE_MODULES)
                    return await self.async_step_git_check()

                # Proceed to license key step
                return await self.async_step_license()

        # Try to get defaults from server.yaml
        server_config = await self.hass.async_add_executor_job(load_server_yaml)
        grower = extract_grower(server_config)

        return self.async_show_form(
            step_id="registration",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_GROWER_NAME,
                    default=grower.get("name", ""),
                ): str,
                vol.Required(
                    CONF_GROWER_EMAIL,
                    default=grower.get("email", ""),
                ): str,
            }),
            errors=errors,
        )

    async def async_step_license(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle license key entry (optional)."""
        errors = {}

        # Load saved license key for pre-fill
        saved_license = await self.hass.async_add_executor_job(get_saved_license_key)

        if user_input is not None:
            license_key = user_input.get("license_key", "").strip()

            if license_key:
                # Validate the license key
                try:
                    license_info = await self.hass.async_add_executor_job(
                        validate_license, license_key
                    )

                    # Check email matches registration
                    if license_info.email != self._data.get(CONF_GROWER_EMAIL):
                        errors["license_key"] = "email_mismatch"
                    else:
                        # License valid - update modules and token
                        self._data[CONF_LICENSE_MODULES] = license_info.modules
                        if license_info.github_token:
                            self._data[CONF_GITHUB_TOKEN] = license_info.github_token

                        # Save license key locally for future reinstalls
                        await self.hass.async_add_executor_job(
                            save_license_key, license_key
                        )

                        # Track activation (fire-and-forget)
                        try:
                            from homeassistant.helpers.instance_id import async_get
                            ha_uuid = await async_get(self.hass)
                        except Exception:
                            ha_uuid = None
                        await track_activation(license_info, ha_uuid)

                        _LOGGER.info(
                            "License activated for %s with modules: %s",
                            license_info.email,
                            license_info.modules,
                        )

                except LicenseError as err:
                    error_code = str(err)
                    if error_code == "expired":
                        errors["license_key"] = "license_expired"
                    elif error_code == "invalid_format":
                        errors["license_key"] = "invalid_format"
                    else:
                        errors["license_key"] = "invalid_license"

            # If no errors (either no key or valid key), proceed
            if not errors:
                return await self.async_step_git_check()

        return self.async_show_form(
            step_id="license",
            data_schema=vol.Schema({
                vol.Optional("license_key", default=saved_license): str,
            }),
            errors=errors,
            description_placeholders={
                "email": self._data.get(CONF_GROWER_EMAIL, ""),
            },
        )

    async def async_step_git_check(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Check if git is available."""
        is_dev_mode = await self.hass.async_add_executor_job(DEV_MODE_FILE.exists)
        git_manager = GitManager(token=self._data.get(CONF_GITHUB_TOKEN))
        is_cloned = await self.hass.async_add_executor_job(git_manager.is_repo_cloned)

        if is_dev_mode and is_cloned:
            _LOGGER.info("Dev mode: Skipping git operations, using existing repo")
            return await self.async_step_install()

        self._git_available = await self.hass.async_add_executor_job(
            git_manager.is_git_available
        )

        if not self._git_available:
            return self.async_abort(reason="git_not_available")

        return await self.async_step_clone_repo()

    async def async_step_clone_repo(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Clone the PaddiSense repository."""
        # Clean up old installation first (preserves local_data)
        await self.hass.async_add_executor_job(self._cleanup_old_install)

        git_manager = GitManager(token=self._data.get(CONF_GITHUB_TOKEN))

        # Always do fresh clone after cleanup
        result = await self.hass.async_add_executor_job(git_manager.clone)

        if not result.get("success"):
            return self.async_abort(
                reason="clone_failed",
                description_placeholders={"error": result.get("error", "Unknown error")},
            )

        return await self.async_step_install()

    def _cleanup_old_install(self) -> None:
        """Clean up old installation while preserving local data."""
        import shutil
        from .const import PADDISENSE_DIR, PACKAGES_DIR, DATA_DIR, LOVELACE_DASHBOARDS_YAML

        _LOGGER.info("Cleaning up old PaddiSense installation...")

        # Backup local_data if it exists inside PaddiSense dir
        local_data_backup = None
        old_local_data = PADDISENSE_DIR / "local_data"
        if old_local_data.exists():
            local_data_backup = Path("/config/.paddisense_data_backup")
            if local_data_backup.exists():
                shutil.rmtree(local_data_backup)
            shutil.copytree(old_local_data, local_data_backup)
            _LOGGER.info("Backed up local_data")

        # Remove old PaddiSense directory
        if PADDISENSE_DIR.exists():
            shutil.rmtree(PADDISENSE_DIR)
            _LOGGER.info("Removed old PaddiSense directory")

        # Clean old package symlinks
        if PACKAGES_DIR.exists():
            for item in PACKAGES_DIR.iterdir():
                if item.is_symlink() or item.suffix == ".yaml":
                    item.unlink()
            _LOGGER.info("Cleaned old package symlinks")

        # Clear lovelace_dashboards.yaml
        if LOVELACE_DASHBOARDS_YAML.exists():
            LOVELACE_DASHBOARDS_YAML.unlink()
            _LOGGER.info("Removed old lovelace_dashboards.yaml")

        # Restore local_data to proper location
        if local_data_backup and local_data_backup.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            for item in local_data_backup.iterdir():
                target = DATA_DIR / item.name
                if item.is_dir():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
            shutil.rmtree(local_data_backup)
            _LOGGER.info("Restored local_data to %s", DATA_DIR)

    async def async_step_install(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Perform installation."""
        # Initialize backend (creates data directories)
        backend = RegistryBackend()
        await self.hass.async_add_executor_job(backend.init)

        # Update configuration.yaml
        config_writer = ConfigWriter()

        await self.hass.async_add_executor_job(
            config_writer.create_lovelace_dashboards_file
        )

        config_result = await self.hass.async_add_executor_job(
            config_writer.update_configuration
        )
        if not config_result.get("success"):
            _LOGGER.warning("Could not update configuration.yaml: %s", config_result)

        # Install core registry module (Manager dashboard)
        await self.hass.async_add_executor_job(self._install_core_registry)

        return self.async_create_entry(
            title=self._data.get(CONF_GROWER_NAME, "PaddiSense"),
            data=self._data,
        )

    def _install_core_registry(self) -> None:
        """Install the core registry module with Manager dashboard."""
        from .const import PADDISENSE_DIR, PACKAGES_DIR, LOVELACE_DASHBOARDS_YAML
        import yaml

        # Create packages directory if needed
        PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Create symlink for registry package
        registry_symlink = PACKAGES_DIR / "registry.yaml"
        if not registry_symlink.exists() and not registry_symlink.is_symlink():
            relative_target = Path("..") / "registry" / "package.yaml"
            try:
                registry_symlink.symlink_to(relative_target)
                _LOGGER.info("Installed registry package")
            except OSError as e:
                _LOGGER.warning("Could not create registry symlink: %s", e)

        # Register Manager dashboard
        dashboards = {}
        if LOVELACE_DASHBOARDS_YAML.exists():
            try:
                content = LOVELACE_DASHBOARDS_YAML.read_text(encoding="utf-8")
                dashboards = yaml.safe_load(content) or {}
            except (yaml.YAMLError, IOError):
                dashboards = {}

        # Add manager dashboard
        dashboards["paddisense-manager"] = {
            "mode": "yaml",
            "title": "PaddiSense",
            "icon": "mdi:view-dashboard",
            "show_in_sidebar": True,
            "filename": "PaddiSense/registry/dashboards/manager.yaml",
        }

        # Write dashboards file
        header = """# Auto-generated by PaddiSense
# Do not edit manually - changes may be overwritten
# Manage modules via PaddiSense Manager

"""
        content = header + yaml.dump(dashboards, default_flow_style=False, sort_keys=False)
        LOVELACE_DASHBOARDS_YAML.write_text(content, encoding="utf-8")
        _LOGGER.info("Registered PaddiSense Manager dashboard")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PaddiSenseOptionsFlow:
        """Get the options flow for this handler."""
        return PaddiSenseOptionsFlow(config_entry)


class PaddiSenseOptionsFlow(config_entries.OptionsFlow):
    """Handle PaddiSense options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "update_profile",
                "backup_restore",
            ],
        )

    async def async_step_update_profile(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Update grower profile (name and email)."""
        errors = {}

        if user_input is not None:
            grower_name = user_input.get(CONF_GROWER_NAME, "").strip()
            grower_email = user_input.get(CONF_GROWER_EMAIL, "").strip()

            if not grower_name:
                errors[CONF_GROWER_NAME] = "required"
            if not grower_email:
                errors[CONF_GROWER_EMAIL] = "required"
            elif not EMAIL_REGEX.match(grower_email):
                errors[CONF_GROWER_EMAIL] = "invalid_email"

            if not errors:
                new_data = {**self._config_entry.data}
                new_data[CONF_GROWER_NAME] = grower_name
                new_data[CONF_GROWER_EMAIL] = grower_email

                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="update_profile",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_GROWER_NAME,
                    default=self._config_entry.data.get(CONF_GROWER_NAME, ""),
                ): str,
                vol.Required(
                    CONF_GROWER_EMAIL,
                    default=self._config_entry.data.get(CONF_GROWER_EMAIL, ""),
                ): str,
            }),
            errors=errors,
        )

    async def async_step_backup_restore(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Backup and restore options."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "backup":
                backup_manager = BackupManager()
                await self.hass.async_add_executor_job(
                    backup_manager.create_backup, "manual"
                )
                return self.async_create_entry(title="", data={})
            elif action == "restore":
                return await self.async_step_restore_backup()

        return self.async_show_form(
            step_id="backup_restore",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In({
                    "backup": "Create Backup",
                    "restore": "Restore from Backup",
                }),
            }),
        )

    async def async_step_restore_backup(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Restore from backup."""
        backup_manager = BackupManager()
        backups = await self.hass.async_add_executor_job(backup_manager.list_backups)

        if not backups:
            return self.async_abort(reason="no_backups")

        if user_input is not None:
            result = await self.hass.async_add_executor_job(
                backup_manager.restore_backup,
                user_input["backup_id"],
            )
            if result.get("success") and result.get("restart_required"):
                await self.hass.services.async_call("homeassistant", "restart")
            return self.async_create_entry(title="", data={})

        backup_options = {
            b["backup_id"]: f"{b['backup_id']} ({b.get('tag', '')})"
            for b in backups[:10]
        }

        return self.async_show_form(
            step_id="restore_backup",
            data_schema=vol.Schema({
                vol.Required("backup_id"): vol.In(backup_options),
            }),
        )
