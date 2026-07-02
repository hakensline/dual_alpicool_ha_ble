"""Flux de configuration pour Alpicool BLE Dual Zone."""
import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_MAC, CONF_NAME

_LOGGER = logging.getLogger(__name__)

class AlpicoolBLEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestion du flux de configuration pour l'appareil Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialisation du flux."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Étape déclenchée par la découverte automatique Bluetooth de HA."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        name = discovery_info.name or "Glacière Outwell"
        self.context["title_placeholders"] = {"name": name}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirmation de l'appareil découvert."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or "Glacière Outwell",
                # On double les clés dans "data" pour satisfaire tous les fichiers à coup sûr
                data={
                    CONF_MAC: self._discovery_info.address,
                    "address": self._discovery_info.address,
                    CONF_NAME: self._discovery_info.name,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or "Glacière Outwell"
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configuration manuelle via l'interface si l'appareil n'est pas détecté."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac_address = user_input[CONF_MAC].upper().strip()
            await self.async_set_unique_id(mac_address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or f"Glacière ({mac_address})",
                # Idem ici, on stocke sous "mac" et sous "address" pour éviter tout KeyError général
                data={
                    CONF_MAC: mac_address,
                    "address": mac_address,
                    CONF_NAME: user_input.get(CONF_NAME),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): str,
                    vol.Optional(CONF_NAME, default="Glacière Outwell"): str,
                }
            ),
            errors=errors,
        )