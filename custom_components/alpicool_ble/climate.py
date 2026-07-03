"""Support for Alpicool fridges via BLE."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Alpicool BLE climate platform."""
    api = hass.data[DOMAIN][entry.entry_id]
    address = entry.data["address"]

    # Modification : On force la création de deux entités distinctes pour les deux zones
    async_add_entities([
        AlpicoolBLEClimateDual(api, entry, address, "left"),
        AlpicoolBLEClimateDual(api, entry, address, "right")
    ])


class AlpicoolBLEClimateDual(ClimateEntity):
    """Representation of a single zone inside an Alpicool BLE fridge."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = -20
    _attr_max_temp = 20
    _attr_target_temperature_step = 1

    def __init__(self, api, entry: ConfigEntry, address: str, zone: str) -> None:
        """Initialize the climate entity."""
        self.api = api
        self._entry = entry
        self._address = address
        self._zone = zone
        
        # Identification unique pour chaque zone
        zone_label = "Zone Gauche" if zone == "left" else "Zone Droite"
        self._attr_name = f"{zone_label}"
        self._attr_unique_id = f"{entry.unique_id}_{zone}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        @callback
        def async_update_state():
            """Update the entity's state."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_{self._address}_update", async_update_state
            )
        )

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.api.is_available and len(self.api.status) > 0

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self.api.status.get("powered_on", True):
            return HVACMode.COOL
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature depending on the zone."""
        if self._zone == "left":
            temp = self.api.status.get("left_current")
        else:
            # Récupère la zone droite décodée par l'API de Gruni22
            temp = self.api.status.get("right_current")
        return float(temp) if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature depending on the zone."""
        if self._zone == "left":
            target = self.api.status.get("left_target")
        else:
            # Récupère la consigne droite décodée par l'API de Gruni22
            target = self.api.status.get("right_target")
        return float(target) if target is not None else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        # Appel direct de la méthode native de Gruni22 : async_set_temperature(zone, temp)
        await self.api.async_set_temperature(self._zone, int(target_temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the fridge on or off."""
        is_on = 1 if hvac_mode == HVACMode.COOL else 0
        await self.api.async_set_values({"powered_on": is_on})