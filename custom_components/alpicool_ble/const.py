"""Constantes pour l'intégration Alpicool BLE Dual Zone."""

DOMAIN = "alpicool_ble"

CONF_MAC = "mac"
CONF_NAME = "name"

# Définition des zones inversées (Gaucher est physiquement la zone droite)
ZONE_LEFT = "right"   # Home Assistant Gauche = Compartiment Physique Droite (Négatif)
ZONE_RIGHT = "left"   # Home Assistant Droite = Compartiment Physique Gauche (Positif)

# UUID de dialogue (Écriture = FFF3 | Écoute = FFF1)
ALPICOOL_CHARACTERISTIC_UUID = "0000FFF3-0000-1000-8000-00805f9b34fb"
FRIDGE_NOTIFY_UUID = "0000FFF1-0000-1000-8000-00805f9b34fb"
