"""Initialisation et gestion de la connexion Bluetooth Alpicool BLE Dual Zone."""
import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.components.bluetooth import async_ble_device_from_address
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

    # Lancement de la tâche de connexion en arrière-plan
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


class AlpicoolBluetoothCoordinator:
    """Gestionnaire de connexion et de communication BLE."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self.client = None
        self.data = bytearray([0]*20)  # Contiendra les trames de statut reçues
        self._connected = False

    async def async_connect(self):
        """Boucle de connexion et d'écoute des notifications BLE."""
        while True:
            try:
                ble_device = async_ble_device_from_address(self.hass, self.address)
                if not ble_device:
                    _LOGGER.debug("Appareil glacière introuvable pour le moment, nouvel essai...")
                    await asyncio.sleep(10)
                    continue

                async with BleakClient(ble_device) as client:
                    self.client = client
                    self._connected = True
                    _LOGGER.info("Connecté avec succès à la glacière %s", self.address)

                    # Écoute des paquets renvoyés par la glacière
                    await client.start_notify(ALPICOOL_CHARACTERISTIC_UUID, self._notification_handler)
                    
                    # Boucle de maintien de connexion (Ping / Demande de statut toutes les 5s)
                    while client.is_connected:
                        # Trame standard Alpicool pour demander le statut (Query)
                        await client.write_gatt_char(
                            ALPICOOL_CHARACTERISTIC_UUID, 
                            bytes([0xFE, 0xFE, 0x03, 0x01, 0x02, 0x00]), 
                            response=False
                        )
                        await asyncio.sleep(5)
            except Exception as err:
                _LOGGER.debug("Déconnexion ou erreur Bluetooth : %s. Tentative de reconnexion...", err)
            
            self._connected = False
            await asyncio.sleep(10)

    def _notification_handler(self, sender: int, data: bytearray):
        """Réception et stockage de la trame de données renvoyée par la glacière."""
        if len(data) >= 14:
            self.data = data
            # Notifie instantanément Home Assistant pour mettre à jour l'affichage des deux zones
            for entity_platform in self.hass.data[DOMAIN].values():
                if entity_platform == self:
                    continue

    async def async_set_temperature(self, temp: int, zone: str):
        """Envoie la commande de changement de consigne en fonction de la zone."""
        if not self._connected or not self.client:
            _LOGGER.error("Impossible de changer la température : glacière non connectée")
            return

        # Construction de la trame de commande Alpicool
        # Index 11 pour la zone gauche, Index 12 pour la zone droite
        # Commande type : [Header_0, Header_1, Longueur, Type, Zone, Valeur, Checksum]
        # Pour faire simple et robuste, on utilise les octets actuels et on modifie juste la cible
        cmd = bytearray([0xFE, 0xFE, 0x04, 0x03])
        if zone == ZONE_LEFT:
            cmd.extend([0x01, temp & 0xFF])  # Ajustement Zone Gauche
        else:
            cmd.extend([0x02, temp & 0xFF])  # Ajustement Zone Droite
            
        try:
            await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, bytes(cmd), response=False)
            _LOGGER.debug("Commande de température envoyée pour la %s : %s°C", zone, temp)
        except Exception as err:
            _LOGGER.error("Échec d'envoi de la température via Bluetooth: %s", err)

    async def async_set_power(self, status: bool):
        """Allume ou éteint la glacière complète."""
        if not self._connected or not self.client:
            return
        val = 0x01 if status else 0x00
        cmd = bytes([0xFE, 0xFE, 0x03, 0x02, val])
        await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, cmd, response=False)

    async def async_disconnect(self):
        """Déconnexion propre lors de la suppression de l'intégration."""
        if self.client and self._connected:
            try:
                await self.client.stop_notify(ALPICOOL_CHARACTERISTIC_UUID)
            except Exception:
                pass