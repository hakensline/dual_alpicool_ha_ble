"""Constantes pour l'intégration Alpicool BLE Dual Zone."""

DOMAIN = "alpicool_ble"

CONF_MAC = "mac"
CONF_NAME = "name"

# Les identifiants de zone pour le Dual Zone
ZONE_LEFT = "left"
ZONE_RIGHT = "right"

# UUID Bluetooth (Pour notre Coordinateur)
ALPICOOL_SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"
ALPICOOL_CHARACTERISTIC_UUID = "0000FFF3-0000-1000-8000-00805f9b34fb"

# UUID Bluetooth (Pour la compatibilité avec le api.py de Gruni22)
FRIDGE_NOTIFY_UUID = "0000FFF1-0000-1000-8000-00805f9b34fb"
FRIDGE_RW_CHARACTERISTIC_UUID = "0000FFF3-0000-1000-8000-00805f9b34fb"

class Request:
    """Commandes pour l'API Alpicool de Gruni22."""
    BIND = 0x00
    QUERY = 0x01
    SET = 0x02
    SET_LEFT = 0x03
    SET_RIGHT = 0x04