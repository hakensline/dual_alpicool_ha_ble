"""Initialisation et gestion Bluetooth sécurisée pour Alpicool BLE Dual Zone."""
import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

from .const import DOMAIN, CONF_MAC, ZONE_LEFT, ALPICOOL_CHARACTERISTIC_UUID, FRIDGE_NOTIFY_UUID

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configuration de la glacière depuis l'interface."""
    hass.data.setdefault(DOMAIN, {})
    
    address = entry.data.get(CONF_MAC, entry.unique_id)
    coordinator = AlpicoolBluetoothCoordinator(hass, address)
    hass.data[DOMAIN][entry.entry_id] = coordinator

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
        self.data = bytearray([0]*30)
        self._connected = False

    async def async_connect(self):
        """Boucle permanente de connexion Bluetooth."""
        while True:
            try:
                ble_device = async_ble_device_from_address(self.hass, self.address)
                if not ble_device:
                    await asyncio.sleep(10)
                    continue

                _LOGGER.info("Tentative de connexion à %s", self.address)
                
                self.client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    ble_device.address,
                    disconnected_callback=self._on_disconnected,
                    use_services_cache=False
                )
                
                self._connected = True
                _LOGGER.info("Connecté avec succès à la glacière %s", self.address)

                await self.client.start_notify(FRIDGE_NOTIFY_UUID, self._notification_handler)
                
                while self.client.is_connected and self._connected:
                    # Ping régulier pour maintenir la connexion et demander l'état
                    await self.client.write_gatt_char(
                        ALPICOOL_CHARACTERISTIC_UUID, 
                        bytes([0xFE, 0xFE, 0x03, 0x01, 0x02, 0x00]), 
                        response=False
                    )
                    await asyncio.sleep(5)
                    
            except Exception as err:
                _LOGGER.debug("Erreur de connexion : %s", err)
            
            self._connected = False
            await asyncio.sleep(10)

    def _on_disconnected(self, client):
        """Déclenché automatiquement lors d'une perte de liaison."""
        self._connected = False

    def _notification_handler(self, sender: int, data: bytearray):
        """Réception de la trame et mouchard de débogage."""
        # --- MOUCHARD DE TRACE POUR DÉBOGAGE (Visible en WARNING) ---
        if len(data) >= 14:
            _LOGGER.warning("=== ALPICOOL TRACE === Trame reçue (Hex): %s (Longueur: %s)", data.hex(), len(data))
            self.data = data
            self.async_set_updated_data(self.data)

    async def async_set_temperature(self, temp: int, zone: str):
        """Envoi de la consigne de température."""
        if not self._connected or not self.client:
            return

        # Construction de la commande hexadécimale : FE FE 04 03 (ZONE) (TEMP)
        cmd = bytearray([0xFE, 0xFE, 0x04, 0x03])
        
        # On détermine l'index de zone en fonction du label inversé
        # Label inversé : ZONE_LEFT="right", ZONE_RIGHT="left"
        # Physiquement : Gauche=0x01, Droite=0x02
        if zone == ZONE_LEFT: # C'est le label HA "Gauche", on pilote la zone PHYSIQUE droite
            cmd.extend([0x02, temp & 0xFF])
        else: # C'est le label HA "Droite", on pilote la zone PHYSIQUE gauche
            cmd.extend([0x01, temp & 0xFF])
            
        try:
            await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, bytes(cmd), response=False)
        except Exception as err:
            _LOGGER.error("Erreur Bluetooth consigne : %s", err)

    async def async_set_power(self, status: bool):
        """Allumage / Extinction global."""
        if not self._connected or not self.client:
            return
        val = 0x01 if status else 0x00
        cmd = bytes([0xFE, 0xFE, 0x03, 0x02, val])
        try:
            await self.client.write_gatt_char(ALPICOOL_CHARACTERISTIC_UUID, cmd, response=False)
        except Exception:
            pass

    async def async_disconnect(self):
        """Déchargement propre."""
        self._connected = False
        if self.client:
            try:
                await self.client.stop_notify(FRIDGE_NOTIFY_UUID)
                await self.client.disconnect()
            except Exception:
                pass
