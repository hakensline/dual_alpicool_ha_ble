"""Support pour les glacières Alpicool / Outwell double zone via DataUpdateCoordinator."""
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONE_LEFT, ZONE_RIGHT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configuration des entités basées sur le coordinateur."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        AlpicoolBLEClimateCoordinator(coordinator, entry, ZONE_LEFT),
        AlpicoolBLEClimateCoordinator(coordinator, entry, ZONE_RIGHT)
    ])

class AlpicoolBLEClimateCoordinator(CoordinatorEntity, ClimateEntity):
    """Représentation d'une zone de la glacière."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = -20
    _attr_max_temp = 20
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, entry: ConfigEntry, zone: str) -> None:
        """Initialisation de la zone."""
        super().__init__(coordinator)
        self._entry = entry
        self._zone = zone
        
        zone_label = "Zone Gauche" if zone == ZONE_LEFT else "Zone Droite"
        self._attr_name = f"{zone_label}"
        self._attr_unique_id = f"{entry.entry_id}_{zone}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Glacière Outwell",
            "manufacturer": "Outwell / Alpicool",
        }

    @property
    def available(self) -> bool:
        """Vérifie la disponibilité réelle."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def hvac_mode(self) -> HVACMode:
        """Détermine si la glacière est allumée."""
        data = self.coordinator.data
        if data and len(data) >= 6 and data[5] == 0:
            return HVACMode.OFF
        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        """Extrait la température en temps réel."""
        data = self.coordinator.data
        if not data or len(data) < 14:
            return None
            
        try:
            if self._zone == ZONE_LEFT:
                return float(int.from_bytes([data[7]], byteorder="big", signed=True))
            elif self._zone == ZONE_RIGHT:
                return float(int.from_bytes([data[8]], byteorder="big", signed=True))
        except Exception:
            return None

    @property
    def target_temperature(self) -> float | None:
        """Extrait la consigne."""
        data = self.coordinator.data
        if not data or len(data) < 14:
            return None
            
        try:
            if self._zone == ZONE_LEFT:
                return float(int.from_bytes([data[11]], byteorder="big", signed=True))
            elif self._zone == ZONE_RIGHT:
                return float(int.from_bytes([data[12]], byteorder="big", signed=True))
        except Exception:
            return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Transmet la consigne."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            await self.coordinator.async_set_temperature(int(target_temp), self._zone)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Allume ou éteint l'appareil."""
        status = (hvac_mode == HVACMode.COOL)
        await self.coordinator.async_set_power(status)
