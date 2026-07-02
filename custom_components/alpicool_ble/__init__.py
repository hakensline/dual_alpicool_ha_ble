"""Initialisation de l'intégration Alpicool BLE Dual Zone."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configuration de l'intégration depuis une entrée de config."""
    hass.data.setdefault(DOMAIN, {})
    
    # Ici, on simule un coordinateur simple ou on stocke les données d'entrée
    # (À adapter si le dépôt d'origine utilise un vrai data coordinator)
    class DummyCoordinator:
        def __init__(self):
            self.data = bytearray([0]*20) # Tableau d'octets vide par défaut
        async def async_set_temperature(self, temp, zone):
            _LOGGER.info("Définition température %s°C pour la zone %s", temp, zone)
        async def async_set_power(self, status):
            _LOGGER.info("Définition alimentation : %s", status)

    hass.data[DOMAIN][entry.entry_id] = DummyCoordinator()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Déchargement d'une entrée de configuration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok