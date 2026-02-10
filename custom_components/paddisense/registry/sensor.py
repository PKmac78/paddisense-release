"""PaddiSense Registry Sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    ATTR_ACTIVE_SEASON,
    ATTR_ACTIVE_SEASON_NAME,
    ATTR_BAYS,
    ATTR_FARMS,
    ATTR_GROWER,
    ATTR_HIERARCHY,
    ATTR_PADDOCKS,
    ATTR_SEASONS,
    ATTR_TOTAL_BAYS,
    ATTR_TOTAL_FARMS,
    ATTR_TOTAL_PADDOCKS,
    ATTR_TOTAL_SEASONS,
    DOMAIN,
    EVENT_DATA_UPDATED,
)
from ..helpers import (
    extract_farms,
    extract_grower,
    get_active_season,
    load_registry_config,
    load_server_yaml,
)

_LOGGER = logging.getLogger(__name__)


class PaddiSenseRegistrySensor(SensorEntity):
    """Sensor representing the PaddiSense Farm Registry state."""

    _attr_has_entity_name = True
    _attr_name = "Registry"
    _attr_icon = "mdi:barn"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the registry sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_registry"
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
            self.hass.bus.async_listen(EVENT_DATA_UPDATED, self._handle_update)
        )

    @callback
    def _handle_update(self, event) -> None:
        """Handle data update event."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        """Update sensor state from registry data."""
        config = load_registry_config()
        server_config = load_server_yaml()

        paddocks = config.get("paddocks", {})
        bays = config.get("bays", {})
        seasons = config.get("seasons", {})
        registry_farms = config.get("farms", {})

        farms = extract_farms(server_config, registry_farms)
        grower = extract_grower(server_config)
        active_season_id = get_active_season(seasons)

        # Build hierarchy
        hierarchy = {}
        for farm_id, farm in farms.items():
            farm_paddocks = {
                pid: {
                    **p,
                    "bays": {
                        bid: b
                        for bid, b in bays.items()
                        if b.get("paddock_id") == pid
                    },
                }
                for pid, p in paddocks.items()
                if p.get("farm_id") == farm_id
            }
            hierarchy[farm_id] = {
                **farm,
                "paddocks": farm_paddocks,
            }

        # Set state
        if config.get("initialized"):
            self._attr_native_value = "ready"
        else:
            self._attr_native_value = "not_initialized"

        # Set attributes
        self._attr_extra_state_attributes = {
            ATTR_GROWER: grower,
            ATTR_PADDOCKS: paddocks,
            ATTR_BAYS: bays,
            ATTR_SEASONS: seasons,
            ATTR_FARMS: farms,
            ATTR_HIERARCHY: hierarchy,
            ATTR_ACTIVE_SEASON: active_season_id,
            ATTR_ACTIVE_SEASON_NAME: (
                seasons.get(active_season_id, {}).get("name")
                if active_season_id
                else None
            ),
            ATTR_TOTAL_PADDOCKS: len(paddocks),
            ATTR_TOTAL_BAYS: len(bays),
            ATTR_TOTAL_SEASONS: len(seasons),
            ATTR_TOTAL_FARMS: len(farms),
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        self._update_state()
