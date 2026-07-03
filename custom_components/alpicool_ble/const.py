"""Constantes pour l'intégration Alpicool BLE Dual Zone."""

DOMAIN = "alpicool_ble"

CONF_MAC = "mac"
CONF_NAME = "name"

ZONE_LEFT = "left"
ZONE_RIGHT = "right"

# UUID de dialogue (Écriture de commandes = FFF3 | Écoute des trames = FFF1)
ALPICOOL_CHARACTERISTIC_UUID = "0000FFF3-0000-1000-8000-00805f9b34fb"
FRIDGE_NOTIFY_UUID = "0000FFF1-0000-1000-8000-00805f9b34fb"
