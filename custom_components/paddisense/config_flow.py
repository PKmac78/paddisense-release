"""Config flow for PaddiSense integration."""
from __future__ import annotations

import logging
import re
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
    load_server_yaml,
)
from .installer import BackupManager, ConfigWriter, GitManager, ModuleManager
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

                # In dev mode, allow all modules
                if is_dev_mode:
                    self._data[CONF_LICENSE_MODULES] = list(AVAILABLE_MODULES)

                return await self.async_step_git_check()

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
        git_manager = GitManager(token=self._data.get(CONF_GITHUB_TOKEN))

        is_cloned = await self.hass.async_add_executor_job(git_manager.is_repo_cloned)

        if is_cloned:
            result = await self.hass.async_add_executor_job(git_manager.pull)
        else:
            result = await self.hass.async_add_executor_job(git_manager.clone)

        if not result.get("success"):
            return self.async_abort(
                reason="clone_failed",
                description_placeholders={"error": result.get("error", "Unknown error")},
            )

        return await self.async_step_install()

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

        return self.async_create_entry(
            title=self._data.get(CONF_GROWER_NAME, "PaddiSense"),
            data=self._data,
        )

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
