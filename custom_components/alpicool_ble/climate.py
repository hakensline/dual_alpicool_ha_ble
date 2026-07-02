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
    address = entry.data["address"]
    
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
        """Initialisation."""
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
        """S'abonne aux mises à jour du dispatcher de Gruni22."""
        @callback
        def async_update_state():
            """Force la mise à jour des états dans HA quand l'API reçoit des données."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_{self._address}_update", async_update_state
            )
        )

    @property
    def should_poll(self) -> bool:
        """Les mises à jour sont poussées par le dispatcher."""
        return False

    @property
    def available(self) -> bool:
        """Vérifie si l'API est bien connectée."""
        return self.api.is_connected if hasattr(self.api, "is_connected") else True

    @property
    def hvac_mode(self) -> HVACMode:
        """Statut d'alimentation récupéré de l'API."""
        # Si l'API possède une propriété d'alimentation (souvent 'power' ou 'is_on')
        if hasattr(self.api, "power") and not self.api.power:
            return HVACMode.OFF
        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        """Récupère la température actuelle de la zone correspondante depuis l'API."""
        # Dans les modèles double zone Alpicool, Gruni22 stocke souvent 
        # la zone 1 dans 'temperature' ou 'current_temperature'.
        # On va vérifier si 'temperature_right' existe dans son api.py
        if self._zone == "left":
            return float(self.api.temperature) if hasattr(self.api, "temperature") else None
        else:
            if hasattr(self.api, "temperature_right"):
                return float(self.api.temperature_right)
            # Si le fichier api.py d'origine n'a pas encore la variable, on l'aidera juste après
            return float(self.api.temperature) if hasattr(self.api, "temperature") else None

    @property
    def target_temperature(self) -> float | None:
        """Consigne de température de la zone."""
        if self._zone == "left":
            return float(self.api.target_temperature) if hasattr(self.api, "target_temperature") else None
        else:
            if hasattr(self.api, "target_temperature_right"):
                return float(self.api.target_temperature_right)
            return float(self.api.target_temperature) if hasattr(self.api, "target_temperature") else None

    async def async_set_temperature(self, **kwargs) -> None:
        """Définit la température via les méthodes de l'API."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        temp_int = int(target_temp)
        if self._zone == "left":
            if hasattr(self.api, "set_temperature"):
                await self.api.set_temperature(temp_int)
        else:
            if hasattr(self.api, "set_temperature_right"):
                await self.api.set_temperature_right(temp_int)
            elif hasattr(self.api, "set_temperature"):
                await self.api.set_temperature(temp_int)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Allume ou éteint la glacière."""
        if hasattr(self.api, "set_power"):
            await self.api.set_power(hvac_mode != HVACMode.OFF)