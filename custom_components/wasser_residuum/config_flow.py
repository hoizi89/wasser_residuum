from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN, CONF_NAME, CONF_TEMP_ENTITY, CONF_TOTAL_ENTITY,
    CONF_LASTSYNC_ENTITY, CONF_RSSI_ENTITY, CONF_TOTAL_UNIT,
    CONF_K_WARM, CONF_K_COLD, CONF_T_WARM, CONF_T_COLD,
    CONF_CLIP, CONF_MAX_RES_L,
    DEFAULT_NAME, DEFAULT_K_WARM, DEFAULT_K_COLD, DEFAULT_T_WARM, DEFAULT_T_COLD,
    DEFAULT_CLIP, DEFAULT_MAX_RES_L, DEFAULT_TOTAL_UNIT,
    RANGE_K, RANGE_T, RANGE_CLIP, RANGE_MAX_RES,
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

        current_t_warm = self.config_entry.options.get(CONF_T_WARM, DEFAULT_T_WARM)
        current_t_cold = self.config_entry.options.get(CONF_T_COLD, DEFAULT_T_COLD)
        current_clip = self.config_entry.options.get(CONF_CLIP, DEFAULT_CLIP)
        current_max = self.config_entry.options.get(CONF_MAX_RES_L, DEFAULT_MAX_RES_L)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_T_WARM, default=current_t_warm): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=RANGE_T["min"],
                        max=RANGE_T["max"],
                        step=RANGE_T["step"],
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_T_COLD, default=current_t_cold): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=RANGE_T["min"],
                        max=RANGE_T["max"],
                        step=RANGE_T["step"],
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_CLIP, default=current_clip): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=RANGE_CLIP["min"],
                        max=RANGE_CLIP["max"],
                        step=RANGE_CLIP["step"],
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
