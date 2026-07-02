"""Initialisation et gestion Bluetooth pour Alpicool BLE Dual Zone."""
import asyncio
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from bleak import BleakClient

from .const import DOMAIN, CONF_MAC, ZONE_LEFT, ALPICOOL_SERVICE_UUID, ALPICOOL_CHARACTERISTIC_UUID

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configuration de la glacière depuis l'interface."""
    hass.data.setdefault(DOMAIN, {})
    
    address = entry.data[CONF_MAC]
    coordinator = AlpicoolBluetoothCoordinator(hass, address)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Tâche de fond pour la connexion Bluetooth
    entry.async_create_background_task(hass, coordinator.async_connect(), "alpicool_ble_connection")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Déchargement propre de l'appareil."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_disconnect()
    return unload_ok


class AlpicoolBluetoothCoordinator(DataUpdateCoordinator):
    """Gestionnaire de connexion BLE avec mise à jour forcée des entités."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialisation."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Pas de polling temporel, on met à jour à la réception (Push)
        )
        self.address = address
        self.client = None
        self.data = bytearray([0]*20)  # Contiendra les octets reçus
        self._connected = False

    async def async_connect(self):
        """Boucle permanente de connexion Bluetooth."""
        while True:
            try:
                ble_device = async_ble_device_from_address(self.hass, self.address)
                if not ble_device:
                    await asyncio.sleep(10)
                    continue

                async with BleakClient(ble_device) as client:
                    self.client = client
                    self._connected = True
                    _LOGGER.info("Connecté avec succès à la glacière %s", self.address)

                    # Écoute des paquets Bluetooth
                    await client.start_notify(ALPICOOL_CHARACTERISTIC_UUID, self._notification_handler)
                    
                    # Boucle de rafraîchissement (Ping toutes les 5 secondes)
                    while client.is_connected:
                        # Commande de requête d'état d'origine Alpicool
                        await client.write_gatt_char(
                            ALPICOOL_CHARACTERISTIC_UUID, 
                            bytes([0xFE, 0xFE, 0x03, 0x01, 0x02, 0x00]), 
                            response=False
                        )
                        await asyncio.sleep(5)
            except Exception as err:
                _LOGGER.debug("Erreur de connexion Bluetooth : %s. Nouvelle tentative...", err)
            
            self._connected = False
            await asyncio.sleep(10)

    def _notification_handler(self, sender: int, data: bytearray):
        """Réception de la trame et notification immédiate à Home Assistant."""
        if len(data) >= 14:
            self.data = data
            # Cette ligne force TOUTES les entités dépendantes (Gauche et Droite) à se rafraîchir d'un coup !
            self.async_set_updated_data(self.data)

    async def async_set_temperature(self, temp: int, zone: str):
        """Envoi de la consigne de température."""
        if not self._connected or not self.client:
            return

        cmd = bytearray([0xFE, 0xFE, 0x04, 0x03])
        if zone == ZONE_LEFT:
            cmd.extend([0x01, temp & 0xFF])
        else:
            cmd.extend([0x02, temp & 0xFF])
            
        try:
            await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, bytes(cmd), response=False)
        except Exception as err:
            _LOGGER.error("Erreur Bluetooth d'envoi de consigne: %s", err)

    async def async_set_power(self, status: bool):
        """Allumage / Extinction."""
        if not self._connected or not self.client:
            return
        val = 0x01 if status else 0x00
        cmd = bytes([0xFE, 0xFE, 0x03, 0x02, val])
        await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, cmd, response=False)

    async def async_disconnect(self):
        """Déconnexion."""
        if self.client and self._connected:
            try:
                await self.client.stop_notify(ALPICOOL_CHARACTERISTIC_UUID)
            except Exception:
                pass