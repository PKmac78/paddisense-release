"""PaddiSense RTR (Real Time Rice) Sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    ATTR_RTR_CSV_URL,
    ATTR_RTR_LAST_UPDATED,
    ATTR_RTR_PADDOCK_COUNT,
    ATTR_RTR_URL_SET,
    DOMAIN,
    EVENT_RTR_UPDATED,
)
from .backend import RTRBackend

_LOGGER = logging.getLogger(__name__)


class PaddiSenseRTRSensor(SensorEntity):
    """Summary sensor showing RTR configuration status."""

    _attr_icon = "mdi:rice"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        backend: RTRBackend,
    ) -> None:
        """Initialize the RTR summary sensor."""
        self.hass = hass
        self._entry = entry
        self._backend = backend
        self._attr_unique_id = f"{DOMAIN}_rtr"
        self._attr_name = "PaddiSense RTR"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "PaddiSense",
            "manufacturer": "PaddiSense",
            "model": "Farm Registry",
        }
        self._update_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_RTR_UPDATED, self._handle_update)
        )

    @callback
    def _handle_update(self, event) -> None:
        """Handle RTR data update event."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        """Update sensor state from RTR data."""
        status = self._backend.get_status()
        data = self._backend.get_data()

        if status.get("configured"):
            paddock_count = status.get("paddock_count", 0)
            if paddock_count > 0:
                self._attr_native_value = f"{paddock_count} paddocks"
            else:
                self._attr_native_value = "Configured (no data)"
        else:
            self._attr_native_value = "Not configured"

        self._attr_extra_state_attributes = {
            ATTR_RTR_URL_SET: status.get("configured", False),
            ATTR_RTR_LAST_UPDATED: status.get("last_updated"),
            ATTR_RTR_PADDOCK_COUNT: status.get("paddock_count", 0),
            ATTR_RTR_CSV_URL: status.get("csv_url"),
            # Include full paddock data for dashboard rendering
            "paddocks": data.get("paddocks", {}),
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        self._update_state()


class PaddiSenseRTRPaddockSensor(SensorEntity):
    """Sensor for individual paddock RTR predictions."""

    _attr_icon = "mdi:sprout"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        backend: RTRBackend,
        paddock_id: str,
        paddock_data: dict[str, Any],
    ) -> None:
        """Initialize the RTR paddock sensor."""
        self.hass = hass
        self._entry = entry
        self._backend = backend
        self._paddock_id = paddock_id
        self._paddock_data = paddock_data

        paddock_name = paddock_data.get("paddock", paddock_id)
        self._attr_unique_id = f"{DOMAIN}_rtr_{paddock_id}"
        # Entity ID will be sensor.paddisense_rtr_{paddock_id}
        self._attr_name = f"PaddiSense RTR {paddock_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "PaddiSense",
            "manufacturer": "PaddiSense",
            "model": "Farm Registry",
        }
        self._update_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_RTR_UPDATED, self._handle_update)
        )

    @callback
    def _handle_update(self, event) -> None:
        """Handle RTR data update event."""
        # Refresh paddock data from backend
        data = self._backend.get_data()
        paddocks = data.get("paddocks", {})

        if self._paddock_id in paddocks:
            self._paddock_data = paddocks[self._paddock_id]
            self._update_state()
            self.async_write_ha_state()

    def _update_state(self) -> None:
        """Update sensor state from paddock data."""
        data = self._paddock_data

        self._attr_native_value = data.get("paddock", self._paddock_id)

        self._attr_extra_state_attributes = {
            "paddock": data.get("paddock", ""),
            "farm": data.get("farm", ""),
            "year": data.get("year", ""),
            "variety": data.get("variety", ""),
            "sow_date": data.get("sow_date", ""),
            "sow_method": data.get("sow_method", ""),
            "pi_date": data.get("pi_date", ""),
            "flowering_date": data.get("flowering_date", ""),
            "moisture_date": data.get("moisture_date", ""),
            "moisture_predict": data.get("moisture_predict", ""),
            "harvest_date": data.get("harvest_date", ""),
            "warnings": data.get("warnings", ""),
            "last_updated": self._backend.get_status().get("last_updated"),
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        # Refresh data from backend
        data = self._backend.get_data()
        paddocks = data.get("paddocks", {})

        if self._paddock_id in paddocks:
            self._paddock_data = paddocks[self._paddock_id]
            self._update_state()


def get_rtr_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    backend: RTRBackend,
) -> list[SensorEntity]:
    """Get all RTR sensors (summary + paddock sensors).

    Args:
        hass: Home Assistant instance
        entry: Config entry
        backend: RTR backend instance

    Returns:
        List of sensor entities
    """
    sensors: list[SensorEntity] = []

    # Always add the summary sensor
    sensors.append(PaddiSenseRTRSensor(hass, entry, backend))

    # Add paddock sensors for each paddock with RTR data
    data = backend.get_data()
    paddocks = data.get("paddocks", {})

    for paddock_id, paddock_data in paddocks.items():
        sensors.append(
            PaddiSenseRTRPaddockSensor(hass, entry, backend, paddock_id, paddock_data)
        )

    return sensors
