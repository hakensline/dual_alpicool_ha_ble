"""Constantes pour l'intégration Alpicool BLE Dual Zone."""

DOMAIN = "alpicool_ble"

CONF_MAC = "mac"
CONF_NAME = "name"

# Les identifiants de zone indispensables pour climate.py
ZONE_LEFT = "left"
ZONE_RIGHT = "right"

# UUID Bluetooth standards utilisés par Alpicool / Outwell
ALPICOOL_SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"  # À ajuster si ton modèle utilise un autre UUID
ALPICOOL_CHARACTERISTIC_UUID = "0000FFF3-0000-1000-8000-00805f9b34fb"