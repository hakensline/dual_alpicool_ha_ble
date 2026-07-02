"""Support pour les glacières Alpicool / Outwell double zone via Bluetooth."""
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configuration des entités basées sur l'entrée de config."""
    api = hass.data[DOMAIN][entry.entry_id]
    
    # Sécurité : on teste "address", et si elle n'existe pas, on tente "mac"
    address = entry.data.get("address", entry.data.get("mac", "00:00:00:00:00:00"))
    
    # Ajout des deux zones distinctes
    async_add_entities([
        AlpicoolBLEClimateDual(api, entry, address, "left"),
        AlpicoolBLEClimateDual(api, entry, address, "right")
    ])

class AlpicoolBLEClimateDual(ClimateEntity):
    """Représentation d'une zone de la glacière."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = -20
    _attr_max_temp = 20
    _attr_target_temperature_step = 1

    def __init__(self, api, entry, address: str, zone: str) -> None:
        """Initialisation de la zone."""
        self.api = api
        self._entry = entry
        self._address = address
        self._zone = zone
        
        zone_label = "Zone Gauche" if zone == "left" else "Zone Droite"
        self._attr_name = f"{zone_label}"
        self._attr_unique_id = f"{entry.entry_id}_{zone}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
        }

    async def async_added_to_hass(self) -> None:
        """S'abonne aux notifications de mise à jour Bluetooth."""
        @callback
        def async_update_state():
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_{self._address}_update", async_update_state
            )
        )

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        """Vérifie la disponibilité globale via l'API."""
        return getattr(self.api, "is_available", True) and len(self.api.status) > 0

    @property
    def hvac_mode(self) -> HVACMode:
        """Détermine si la glacière est allumée."""
        if self.api.status.get("powered_on", True):
            return HVACMode.COOL
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Lit la température de la zone dans le dictionnaire de l'API."""
        if self._zone == "left":
            temp = self.api.status.get("left_current")
        else:
            temp = self.api.status.get("right_current", self.api.status.get("left_current"))
        return float(temp) if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Lit la consigne de la zone dans le dictionnaire de l'API."""
        if self._zone == "left":
            target = self.api.status.get("left_target")
        else:
            target = self.api.status.get("right_target", self.api.status.get("left_target"))
        return float(target) if target is not None else None

    async def async_set_temperature(self, **kwargs) -> None:
        """Envoie le changement de consigne à l'API."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        temp_int = int(target_temp)
        # Appel de la méthode officielle présente dans api.py
        await self.api.async_set_temperature(self._zone, temp_int)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Allume ou éteint la glacière globale."""
        is_on = 1 if hvac_mode == HVACMode.COOL else 0
        await self.api.async_set_values({"powered_on": is_on})