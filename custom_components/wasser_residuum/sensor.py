from __future__ import annotations

from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from datetime import datetime, timezone
from homeassistant.util.dt import parse_datetime as ha_parse_dt
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN, DATA_CTRL, CONF_NAME,
    CONF_LASTSYNC_ENTITY, CONF_RSSI_ENTITY,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ctrl = hass.data[DOMAIN][entry.entry_id][DATA_CTRL]
    cfg = {**entry.data, **entry.options}  # options Ã¼berschreiben data
    name = cfg.get(CONF_NAME, entry.data.get(CONF_NAME, "Wasser Residuum"))

    entities = [
        FlowSensor(ctrl, name),
        VolumeSensor(ctrl, name),
        ResiduumSensor(ctrl, name),
        DiagTempRaw(ctrl, name),
        DiagTempFilt(ctrl, name),
        DiagDtUsed(ctrl, name),
        DiagOffset(ctrl, name),
        DiagUncertainty(ctrl, name),
        DiagKActive(ctrl, name),  # NEU
        DiagNightMode(ctrl, name),  # VERBESSERT v0.3.0
        DiagDeepSleep(ctrl, name),  # VERBESSERT v0.3.0
    ]

    # Optional: LastSync und RSSI
    if CONF_LASTSYNC_ENTITY in entry.data and entry.data[CONF_LASTSYNC_ENTITY]:
        entities.append(LastSyncSensor(ctrl, name, entry.data[CONF_LASTSYNC_ENTITY], hass))
    if CONF_RSSI_ENTITY in entry.data and entry.data[CONF_RSSI_ENTITY]:
        entities.append(RssiSensor(ctrl, name, entry.data[CONF_RSSI_ENTITY], hass))

    async_add_entities(entities)


class BaseEntity(SensorEntity):
    _attr_should_poll = False

    def __init__(self, ctrl, name: str, key: str, unit=None, icon=None,
                 state_class=None, device_class=None, entity_category=None):
        self.ctrl = ctrl
        self._attr_name = f"{name} {key}"
        uid_name = "".join(c if c.isalnum() else "_" for c in name).lower()
        self._attr_unique_id = f"{DOMAIN}_{uid_name}_{key.lower().replace(' ', '_')}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, name)},
            name=name,
            manufacturer="Custom",
            model="Î”Tâ†’Volumen Kalman",
        )

    async def async_added_to_hass(self):
        self.ctrl.register_entity_listener(self._on_ctrl_update)

    @callback
    def _on_ctrl_update(self):
        self.async_write_ha_state()


# --- Haupt-Sensoren -----------------------------------------------------------

class FlowSensor(BaseEntity):
    """Aktueller geschÃ¤tzter Durchfluss."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Flow",
            unit="L/min",
            icon="mdi:water-pump",
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def native_value(self) -> float | None:
        val = getattr(self.ctrl, '_last_flow', None)
        return None if val is None else round(val, 3)


class VolumeSensor(BaseEntity, RestoreEntity):
    """Kumuliertes Volumen (ohne Offset)."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Volume",
            unit="L",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL_INCREASING,
            device_class=SensorDeviceClass.WATER,
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        # Letzten State laden (falls vorhanden)
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                last_val = float(last_state.state)
            except (ValueError, TypeError):
                last_val = None

            if last_val is not None:
                # Controller auf den exakten alten Wert setzen
                self.ctrl._volume_l = last_val
                # Optional: Offset so setzen, dass Residuum nicht „platzt“
                if self.ctrl._offset_l == 0.0 or self.ctrl._offset_l > self.ctrl._volume_l:
                    self.ctrl._offset_l = self.ctrl._volume_l

                # Merker: Wir haben restauriert → Controller soll Initialisierung NICHT überschreiben
                setattr(self.ctrl, "_restored_volume", True)

        # Gleich nach dem Restore einmal State schreiben
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        val = getattr(self.ctrl, '_volume_l', None)
        return None if val is None else round(val, 3)



class ResiduumSensor(BaseEntity):
    """Residuum = Volume - Offset, geclampt [0..max_res_l]."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Residuum",
            unit="L",
            icon="mdi:gauge",
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def native_value(self) -> float | None:
        return round(self.ctrl.residuum_l, 3)

    @property
    def extra_state_attributes(self):
        return {
            "offset_l": round(getattr(self.ctrl, '_offset_l', 0.0), 3),
            "max_residuum_l": round(self.ctrl.max_res_l, 3),
            "uncertainty_l": round(getattr(self.ctrl, '_volume_uncertainty', 0.0), 3),
        }

class DiagKActive(BaseEntity):
    """Aktuell verwendeter K-Faktor (interpoliert)."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "K Active",
            unit="L/K",
            icon="mdi:tune-vertical",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> float | None:
        val = getattr(self.ctrl, '_last_k_used', None)
        return None if val is None else round(val, 2)
    
    @property
    def extra_state_attributes(self):
        if not hasattr(self.ctrl, '_kalman') or self.ctrl._kalman is None:
            return {}
        
        filt_temp, _ = self.ctrl._kalman.get_state()
        
        return {
            "k_warm": round(self.ctrl.k_warm, 2),
            "k_cold": round(self.ctrl.k_cold, 2),
            "t_warm": round(self.ctrl.t_warm, 1),
            "t_cold": round(self.ctrl.t_cold, 1),
            "current_temp": round(filt_temp, 1),
        }



# --- Diagnose-Sensoren --------------------------------------------------------

class DiagTempRaw(BaseEntity):
    """Rohe Temperatur vom Sensor."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Temp Raw",
            unit="°C",
            icon="mdi:thermometer",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> float | None:
        val = getattr(self.ctrl, '_last_temp', None)
        return None if val is None else round(val, 2)


class DiagTempFilt(BaseEntity):
    """Kalman-gefilterte Temperatur."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Temp Filtered",
            unit="°C",
            icon="mdi:thermometer-lines",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> float | None:
        if not hasattr(self.ctrl, '_kalman') or self.ctrl._kalman is None:
            return None
        filt_temp, _ = self.ctrl._kalman.get_state()
        return round(filt_temp, 2)


class DiagDtUsed(BaseEntity):
    """Letzter verwendeter Temperaturgradient."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "dT Used",
            unit="K/min",
            icon="mdi:delta",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> float | None:
        val = getattr(self.ctrl, '_last_dt_used', None)
        return None if val is None else round(val, 4)

    @property
    def extra_state_attributes(self):
        night_mode = getattr(self.ctrl, "_night_mode_active", False)
        deep_sleep = self.ctrl.deep_sleep_active
        threshold = -0.006
        if night_mode:
            threshold *= 5.0
        if deep_sleep:
            threshold *= 3.0
        return {
            "flow_active": getattr(self.ctrl, "_flow_active", False),
            "night_mode": night_mode,
            "deep_sleep": deep_sleep,
            "current_threshold": round(threshold, 4),
        }



class DiagOffset(BaseEntity):
    """Aktueller Offset (wird bei Reset auf Volume gesetzt)."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Offset",
            unit="L",
            icon="mdi:counter",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> float | None:
        val = getattr(self.ctrl, '_offset_l', None)
        return None if val is None else round(val, 3)


class DiagUncertainty(BaseEntity):
    """GeschÃ¤tzte Unsicherheit des Residuums."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Uncertainty",
            unit="L",
            icon="mdi:sigma",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> float | None:
        val = getattr(self.ctrl, '_volume_uncertainty', None)
        return None if val is None else round(val, 3)


# --- Optional: LastSync & RSSI -----------------------------------------------

class LastSyncSensor(BaseEntity):
    """Letztes Sync vom wmbusmetersd."""
    def __init__(self, ctrl, name: str, entity_id: str, hass: HomeAssistant):
        super().__init__(
            ctrl, name, "Last Sync",
            icon="mdi:clock-outline",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        self._entity_id = entity_id
        self._hass = hass
        self._last_sync_dt = None  # datetime-Objekt statt String

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        async_track_state_change_event(self._hass, [self._entity_id], self._on_entity_change)
        state = self._hass.states.get(self._entity_id)
        if state and state.state not in ("unavailable", "unknown"):
            self._last_sync_dt = ha_parse_dt(state.state)

    @callback
    def _on_entity_change(self, event):
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in ("unavailable", "unknown"):
            self._last_sync_dt = ha_parse_dt(new_state.state)
            self.async_write_ha_state()

    @property
    def native_value(self):
        # Muss datetime-Objekt zurÃ¼ckgeben, nicht String/isoformat()
        return self._last_sync_dt


class RssiSensor(BaseEntity):
    """RSSI vom wmbusmetersd."""
    def __init__(self, ctrl, name: str, entity_id: str, hass: HomeAssistant):
        super().__init__(
            ctrl, name, "RSSI",
            unit="dBm",
            icon="mdi:wifi",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        self._entity_id = entity_id
        self._hass = hass
        self._rssi = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        async_track_state_change_event(self._hass, [self._entity_id], self._on_entity_change)
        state = self._hass.states.get(self._entity_id)
        if state and state.state not in ("unavailable", "unknown"):
            try:
                self._rssi = int(state.state)
            except (ValueError, TypeError):
                pass

    @callback
    def _on_entity_change(self, event):
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in ("unavailable", "unknown"):
            try:
                self._rssi = int(new_state.state)
                self.async_write_ha_state()
            except (ValueError, TypeError):
                pass

    @property
    def native_value(self):
        return self._rssi


# --- VERBESSERT v0.3.0: Nacht-Abkühlungs-Schutz -------------------------------

class DiagNightMode(BaseEntity):
    """Zeigt an ob Nacht-Modus aktiv ist (strengere Schwellwerte)."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Night Mode",
            icon="mdi:weather-night",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> str:
        """Gibt 'Active' oder 'Inactive' zurück."""
        is_active = getattr(self.ctrl, '_night_mode_active', False)
        return "Active" if is_active else "Inactive"

    @property
    def icon(self) -> str:
        """Dynamisches Icon basierend auf Status."""
        is_active = getattr(self.ctrl, '_night_mode_active', False)
        return "mdi:weather-night" if is_active else "mdi:white-balance-sunny"

    @property
    def extra_state_attributes(self):
        from datetime import datetime
        now = datetime.now()
        return {
            "current_hour": now.hour,
            "night_hours": "22:00-06:00",
            "threshold_multiplier": "5x" if getattr(self.ctrl, '_night_mode_active', False) else "1x",
        }


class DiagDeepSleep(BaseEntity):
    """Zeigt an ob Deep-Sleep-Modus aktiv ist (>2h keine Zapfung)."""
    def __init__(self, ctrl, name: str):
        super().__init__(
            ctrl, name, "Deep Sleep",
            icon="mdi:sleep",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> str:
        """Gibt 'Active' oder 'Inactive' zurück."""
        is_active = self.ctrl.deep_sleep_active
        return "Active" if is_active else "Inactive"

    @property
    def icon(self) -> str:
        """Dynamisches Icon basierend auf Status."""
        is_active = self.ctrl.deep_sleep_active
        return "mdi:sleep" if is_active else "mdi:sleep-off"

    @property
    def extra_state_attributes(self):
        import time
        last_flow_time = getattr(self.ctrl, '_last_flow_time', None)
        if last_flow_time:
            idle_hours = (time.time() - last_flow_time) / 3600.0
        else:
            idle_hours = 999.9

        return {
            "idle_hours": round(idle_hours, 1),
            "threshold_hours": 2.0,
            "threshold_multiplier": "3x" if self.ctrl.deep_sleep_active else "1x",
        }