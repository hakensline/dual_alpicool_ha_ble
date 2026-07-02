"""Initialisation et gestion Bluetooth sécurisée pour Alpicool BLE Dual Zone."""
import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# Utilisation du connecteur recommandé par Home Assistant
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

from .const import DOMAIN, CONF_MAC, ZONE_LEFT, ALPICOOL_CHARACTERISTIC_UUID

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configuration de la glacière depuis l'interface."""
    hass.data.setdefault(DOMAIN, {})
    
    address = entry.data.get(CONF_MAC, entry.unique_id)
    coordinator = AlpicoolBluetoothCoordinator(hass, address)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Tâche de fond pour la connexion Bluetooth stable
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
    """Gestionnaire de connexion BLE robuste."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialisation."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self.address = address
        self.client = None
        self.data = bytearray([0]*20)
        self._connected = False

    async def async_connect(self):
        """Boucle permanente de connexion Bluetooth utilisant bleak-retry-connector."""
        while True:
            try:
                ble_device = async_ble_device_from_address(self.hass, self.address)
                if not ble_device:
                    _LOGGER.debug("Glacière introuvable dans les scans Bluetooth locaux...")
                    await asyncio.sleep(10)
                    continue

                _LOGGER.info("Tentative de connexion sécurisée à la glacière %s", self.address)
                
                # Connexion via le wrapper officiel de Home Assistant
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    ble_device.address,
                    disconnected_callback=self._on_disconnected
                )
                
                self.client = client
                self._connected = True
                _LOGGER.info("Connecté avec succès à la glacière %s !", self.address)

                # Écoute des paquets Bluetooth
                await client.start_notify(ALPICOOL_CHARACTERISTIC_UUID, self._notification_handler)
                
                # Boucle de rafraîchissement (Ping toutes les 5 secondes)
                while client.is_connected and self._connected:
                    # Requête d'état standard Alpicool
                    await client.write_gatt_char(
                        ALPICOOL_CHARACTERISTIC_UUID, 
                        bytes([0xFE, 0xFE, 0x03, 0x01, 0x02, 0x00]), 
                        response=False
                    )
                    await asyncio.sleep(5)
                    
            except Exception as err:
                _LOGGER.debug("Statut de connexion déconnecté ou erreur : %s. Reconnexion dans 10s...", err)
            
            self._connected = False
            await asyncio.sleep(10)

    def _on_disconnected(self, client):
        """Déclenché automatiquement par le wrapper lors d'une perte de liaison."""
        _LOGGER.info("Liaison Bluetooth perdue avec la glacière")
        self._connected = False

    def _notification_handler(self, sender: int, data: bytearray):
        """Réception de la trame brute et injection directe dans le climate."""
        if len(data) >= 14:
            self.data = data
            _LOGGER.debug("Trame reçue (Hex): %s", data.hex())
            # Pousse les octets reçus aux deux entités Climate d'un coup
            self.async_set_updated_data(self.data)

    async def async_set_temperature(self, temp: int, zone: str):
        """Envoi de la consigne de température."""
        if not self._connected or not self.client:
            _LOGGER.error("Impossible d'envoyer la commande : Glacière non connectée en Bluetooth")
            return

        cmd = bytearray([0xFE, 0xFE, 0x04, 0x03])
        if zone == ZONE_LEFT:
            cmd.extend([0x01, temp & 0xFF])
        else:
            cmd.extend([0x02, temp & 0xFF])
            
        try:
            await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, bytes(cmd), response=False)
        except Exception as err:
            _LOGGER.error("Erreur Bluetooth lors de l'envoi de consigne : %s", err)

    async def async_set_power(self, status: bool):
        """Allumage / Extinction global."""
        if not self._connected or not self.client:
            return
        val = 0x01 if status else 0x00
        cmd = bytes([0xFE, 0xFE, 0x03, 0x02, val])
        await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, cmd, response=False)

    async def async_disconnect(self):
        """Déchargement propre."""
        self._connected = False
        if self.client:
            try:
                await self.client.stop_notify(ALPICOOL_CHARACTERISTIC_UUID)
                await self.client.disconnect()
            except Exception as err:
                _LOGGER.error("Erreur lors de la deconnexion : %s", err)