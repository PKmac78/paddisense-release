"""PaddiSense Sensor Platform."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_AVAILABLE_MODULES,
    ATTR_INSTALLED_MODULES,
    ATTR_INSTALLED_VERSION,
    ATTR_LAST_CHECKED,
    ATTR_LATEST_VERSION,
    ATTR_UPDATE_AVAILABLE,
    CONF_LICENSE_EXPIRY,
    CONF_LICENSE_GROWER,
    CONF_LICENSE_MODULES,
    CONF_LICENSE_SEASON,
    CONF_GROWER_NAME,
    CONF_FARM_NAME,
    DOMAIN,
    EVENT_DATA_UPDATED,
    EVENT_MODULES_CHANGED,
    FREE_MODULES,
)
from .helpers import get_version
from .registration import load_registration, get_allowed_modules
from .registry.sensor import PaddiSenseRegistrySensor
from .rtr.sensor import get_rtr_sensors

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PaddiSense sensors."""
    entities = [
        PaddiSenseRegistrySensor(hass, entry),
        PaddiSenseVersionSensor(hass, entry),
    ]

    # Add RTR sensors
    rtr_backend = hass.data.get(DOMAIN, {}).get("rtr_backend")
    if rtr_backend:
        rtr_sensors = get_rtr_sensors(hass, entry, rtr_backend)
        entities.extend(rtr_sensors)

    async_add_entities(entities, True)


class PaddiSenseVersionSensor(SensorEntity):
    """Sensor showing PaddiSense version and update status."""

    _attr_has_entity_name = True
    _attr_name = "Version"
    _attr_icon = "mdi:package-variant"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the version sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_version"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "PaddiSense",
            "manufacturer": "PaddiSense",
            "model": "Farm Registry",
        }
        self._last_checked: str | None = None
        self._latest_version: str | None = None
        self._update_available = False
        self._installed_modules: list[dict] = []
        self._available_modules: list[dict] = []

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MODULES_CHANGED, self._handle_update)
        )
        # Initial module scan
        await self._async_update_module_info()

    @callback
    def _handle_update(self, event) -> None:
        """Handle modules changed event."""
        self.hass.async_create_task(self._async_update_module_info())

    async def _async_update_module_info(self) -> None:
        """Update module information."""
        backend = self.hass.data.get(DOMAIN, {}).get("backend")
        if not backend:
            return

        from .installer import ModuleManager
        module_manager = ModuleManager()

        self._installed_modules = await self.hass.async_add_executor_job(
            module_manager.get_installed_modules
        )
        self._available_modules = await self.hass.async_add_executor_job(
            module_manager.get_available_modules
        )

        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        """Return the current version."""
        return get_version()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        # Get registration info (grower data)
        reg_data = load_registration()
        grower_name = reg_data.get("grower_name", "Not registered")
        grower_email = reg_data.get("grower_email", "")

        # Get allowed modules (all free modules if registered)
        allowed_modules = get_allowed_modules()

        return {
            ATTR_INSTALLED_VERSION: get_version(),
            ATTR_LATEST_VERSION: self._latest_version,
            ATTR_UPDATE_AVAILABLE: self._update_available,
            ATTR_LAST_CHECKED: self._last_checked,
            ATTR_INSTALLED_MODULES: self._installed_modules,
            ATTR_AVAILABLE_MODULES: self._available_modules,
            # Registration info (replaces license info)
            "license_grower": grower_name,
            "license_expiry": "Never (Free)",
            "license_modules": allowed_modules,
            "license_season": "All Seasons",
            "grower_name": grower_name,
            "grower_email": grower_email,
            "farm_name": "All Farms",
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        # Version is read fresh on each access via get_version()
        pass

    def set_update_info(
        self,
        latest_version: str | None,
        update_available: bool,
    ) -> None:
        """Set update information from check_for_updates service."""
        self._latest_version = latest_version
        self._update_available = update_available
        self._last_checked = datetime.now().isoformat()
        self.async_write_ha_state()
