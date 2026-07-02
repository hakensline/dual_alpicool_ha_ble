"""Support pour les glacières Alpicool / Outwell double zone via Bluetooth."""
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONE_LEFT, ZONE_RIGHT, MIN_TEMP, MAX_TEMP

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configuration des entités de climat basées sur l'entrée de configuration."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Enregistrement des deux entités distinctes dans Home Assistant
    async_add_entities([
        AlpicoolBLEClimate(coordinator, entry, ZONE_LEFT),
        AlpicoolBLEClimate(coordinator, entry, ZONE_RIGHT)
    ])

class AlpicoolBLEClimate(CoordinatorEntity, ClimateEntity):
    """Représentation d'une zone de contrôle de la glacière."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, entry, zone: str) -> None:
        """Initialisation de la zone de climat."""
        super().__init__(coordinator)
        self._entry = entry
        self._zone = zone
        
        # Attribution d'un nom et d'un ID unique par zone
        zone_label = "Zone Gauche" if zone == ZONE_LEFT else "Zone Droite"
        self._attr_name = f"{zone_label}"
        self._attr_unique_id = f"{entry.entry_id}_{zone}"
        
        # Regroupement des deux zones sous le même appareil physique dans l'interface
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Glacière Outwell",
            "manufacturer": "Outwell / Alpicool",
        }

    @property
    def hvac_mode(self) -> HVACMode:
        """Retourne le statut d'alimentation général de la glacière."""
        data = self.coordinator.data
        # Si l'octet 5 indique 0, la glacière entière est éteinte
        if data and len(data) >= 6 and data[5] == 0:
            return HVACMode.OFF
        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        """Retourne la température en temps réel du compartiment."""
        data = self.coordinator.data
        if not data:
            return None
            
        try:
            # Zone Gauche (Left) = Octet 7 | Zone Droite (Right) = Octet 8
            if self._zone == ZONE_LEFT and len(data) >= 8:
                return float(int.from_bytes([data[7]], byteorder="big", signed=True))
            elif self._zone == ZONE_RIGHT and len(data) >= 9:
                return float(int.from_bytes([data[8]], byteorder="big", signed=True))
        except Exception as err:
            _LOGGER.error("Erreur de lecture de la température actuelle pour la %s: %s", self._zone, err)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Retourne la consigne de température demandée pour ce compartiment."""
        data = self.coordinator.data
        if not data:
            return None
            
        try:
            # Zone Gauche Consigne = Octet 11 | Zone Droite Consigne = Octet 12
            if self._zone == ZONE_LEFT and len(data) >= 12:
                return float(int.from_bytes([data[11]], byteorder="big", signed=True))
            elif self._zone == ZONE_RIGHT and len(data) >= 13:
                return float(int.from_bytes([data[12]], byteorder="big", signed=True))
        except Exception as err:
            _LOGGER.error("Erreur de lecture de la consigne pour la %s: %s", self._zone, err)
        return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Envoie la nouvelle température de consigne à la glacière via le coordinator."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        # On transmet la valeur et la zone cible au coordinateur Bluetooth
        # pour qu'il construise la trame avec la bonne commande de zone
        await self.coordinator.async_set_temperature(int(target_temp), self._zone)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Permet d'allumer ou éteindre l'unité complète."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_power(False)
        else:
            await self.coordinator.async_set_power(True)
