from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN, DATA_CTRL, CONF_NAME, RANGE_K


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ctrl = hass.data[DOMAIN][entry.entry_id][DATA_CTRL]
    name = entry.data[CONF_NAME]
    async_add_entities([
        KWarmNumber(ctrl, name),
        KColdNumber(ctrl, name),
    ])


class BaseNumber(NumberEntity):
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, ctrl, name: str, key: str, rng: dict, unit=None, icon=None, mode=NumberMode.AUTO):
        self.ctrl = ctrl
        self._attr_name = f"{name} {key}"
        uid_name = "".join(c if c.isalnum() else "_" for c in name).lower()
        self._attr_unique_id = f"{DOMAIN}_{uid_name}_{key.lower().replace(' ', '_')}"
        self._attr_native_min_value = rng["min"]
        self._attr_native_max_value = rng["max"]
        self._attr_native_step = rng["step"]
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_mode = mode
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, name)},
            name=name,
            manufacturer="Custom",
            model="ΔT→Volumen Dual-K",
        )

    async def async_added_to_hass(self):
        self.ctrl.register_entity_listener(self._on_ctrl_update)

    @callback
    def _on_ctrl_update(self):
        self.async_write_ha_state()


class KWarmNumber(BaseNumber):
    def __init__(self, ctrl, name):
        super().__init__(ctrl, name, "K Warm", RANGE_K, "L/K", 
                        icon="mdi:thermometer-high", mode=NumberMode.BOX)

    @property
    def native_value(self):
        return self.ctrl.k_warm

    async def async_set_native_value(self, value: float):
        await self.ctrl.async_set_k_warm(float(value))


class KColdNumber(BaseNumber):
    def __init__(self, ctrl, name):
        super().__init__(ctrl, name, "K Cold", RANGE_K, "L/K", 
                        icon="mdi:thermometer-low", mode=NumberMode.BOX)

    @property
    def native_value(self):
        return self.ctrl.k_cold

    async def async_set_native_value(self, value: float):
        await self.ctrl.async_set_k_cold(float(value))
