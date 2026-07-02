"""Support pour les glacières Alpicool / Outwell double zone via DataUpdateCoordinator."""
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONE_LEFT, ZONE_RIGHT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configuration des entités basées sur le coordinateur."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Ajout des deux zones distinctes (Left et Right basés sur const.py)
    async_add_entities([
        AlpicoolBLEClimateCoordinator(coordinator, entry, ZONE_LEFT),
        AlpicoolBLEClimateCoordinator(coordinator, entry, ZONE_RIGHT)
    ])

class AlpicoolBLEClimateCoordinator(CoordinatorEntity, ClimateEntity):
    """Représentation d'une zone de la glacière gérée par coordinateur."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = -20
    _attr_max_temp = 20
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, entry, zone: str) -> None:
        """Initialisation de la zone."""
        super().__init__(coordinator)
        self._entry = entry
        self._zone = zone
        
        # Attribution des étiquettes de zone
        zone_label = "Zone Gauche" if zone == ZONE_LEFT else "Zone Droite"
        self._attr_name = f"{zone_label}"
        self._attr_unique_id = f"{entry.entry_id}_{zone}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Glacière Outwell",
            "manufacturer": "Outwell / Alpicool",
        }

    @property
    def hvac_mode(self) -> HVACMode:
        """Détermine si la glacière entière est allumée."""
        data = self.coordinator.data
        # Si l'octet 5 indique 0, l'appareil est éteint
        if data and len(data) >= 6 and data[5] == 0:
            return HVACMode.OFF
        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        """Extrait la température en temps réel du tableau d'octets."""
        data = self.coordinator.data
        if not data or len(data) < 10:
            return None
            
        try:
            # Zone Gauche = Octet 7 | Zone Droite = Octet 8
            if self._zone == ZONE_LEFT:
                return float(int.from_bytes([data[7]], byteorder="big", signed=True))
            elif self._zone == ZONE_RIGHT:
                return float(int.from_bytes([data[8]], byteorder="big", signed=True))
        except Exception as err:
            _LOGGER.error("Erreur lecture température courante (%s): %s", self._zone, err)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Extrait la consigne du tableau d'octets."""
        data = self.coordinator.data
        if not data or len(data) < 14:
            return None
            
        try:
            # Zone Gauche Consigne = Octet 11 | Zone Droite Consigne = Octet 12
            if self._zone == ZONE_LEFT:
                return float(int.from_bytes([data[11]], byteorder="big", signed=True))
            elif self._zone == ZONE_RIGHT:
                return float(int.from_bytes([data[12]], byteorder="big", signed=True))
        except Exception as err:
            _LOGGER.error("Erreur lecture consigne (%s): %s", self._zone, err)
        return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Transmet la consigne au coordinateur."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        await self.coordinator.async_set_temperature(int(target_temp), self._zone)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Allume ou éteint l'appareil complet."""
        status = (hvac_mode == HVACMode.COOL)
        await self.coordinator.async_set_power(status)