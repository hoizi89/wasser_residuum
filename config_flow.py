from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN, CONF_NAME, CONF_TEMP_ENTITY, CONF_TOTAL_ENTITY,
    CONF_LASTSYNC_ENTITY, CONF_RSSI_ENTITY, CONF_TOTAL_UNIT,
    CONF_K, CONF_MAX_RES_L,
    DEFAULT_NAME, DEFAULT_K, DEFAULT_MAX_RES_L, DEFAULT_TOTAL_UNIT,
    RANGE_K, RANGE_MAX_RES,
)


class WasserResiduumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_TEMP_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_TOTAL_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_LASTSYNC_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_RSSI_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_TOTAL_UNIT, default=DEFAULT_TOTAL_UNIT): vol.In(["L", "m3"]),
            })
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return WasserResiduumOptionsFlow(config_entry)


class WasserResiduumOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_k = self.config_entry.options.get(CONF_K, DEFAULT_K)
        current_max = self.config_entry.options.get(CONF_MAX_RES_L, DEFAULT_MAX_RES_L)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_K, default=current_k): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=RANGE_K["min"],
                        max=RANGE_K["max"],
                        step=RANGE_K["step"],
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_MAX_RES_L, default=current_max): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=RANGE_MAX_RES["min"],
                        max=RANGE_MAX_RES["max"],
                        step=RANGE_MAX_RES["step"],
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            })
        )
