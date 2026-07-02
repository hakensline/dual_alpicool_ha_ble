"""Constantes pour l'intégration Alpicool BLE Dual Zone."""

DOMAIN = "alpicool_ble"

# Configuration
CONF_MAC = "mac"
CONF_NAME = "name"

# Identifiants uniques des zones pour Home Assistant
ZONE_LEFT = "left"
ZONE_RIGHT = "right"

# UUIDs Bluetooth standards utilisés par les cartes de contrôle Alpicool/Outwell
# Service de communication série transparent (UART)
ALPICOOL_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
ALPICOOL_CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"

# Headers de commandes du protocole Alpicool (Payload Bluetooth)
# Le protocole utilise souvent des commandes de type "FE FE" suivies de la longueur et de l'action
CMD_HEADER = [0xFE, 0xFE]
CMD_POWER_ON = [0x01]
CMD_POWER_OFF = [0x00]

# Constantes de fonctionnement
MIN_TEMP = -20
MAX_TEMP = 20
