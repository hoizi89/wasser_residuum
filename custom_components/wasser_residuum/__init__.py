from __future__ import annotations

import logging
import time
import numpy as np
import statistics
from collections import deque
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import (
    DOMAIN, DATA_CTRL, CONF_TEMP_ENTITY, CONF_TOTAL_ENTITY, CONF_TOTAL_UNIT,
    CONF_K_WARM, CONF_K_COLD, CONF_T_WARM, CONF_T_COLD,
    CONF_CLIP, CONF_MAX_RES_L,
    DEFAULT_K_WARM, DEFAULT_K_COLD, DEFAULT_T_WARM, DEFAULT_T_COLD,
    DEFAULT_CLIP, DEFAULT_MAX_RES_L,
    DEFAULT_TOTAL_UNIT, PLATFORMS,
    RANGE_K,
)

_LOGGER = logging.getLogger(__name__)

KMIN = float(RANGE_K.get("min", 0.5))
KMAX = float(RANGE_K.get("max", 15.0))

# Spezielles Limit für kalte Leitung und maximale K-Änderung pro Tick,
# damit die Auto-Kalibrierung nachts nicht sofort auf 15 L/K hochschießt.
KMAX_COLD = min(10.0, KMAX)
K_ADAPT_MAX_STEP = 0.25  # max. 25 % Richtung Ziel-K pro 10L-Tick

def _m3_to_l(v: float) -> float:
    return v * 1000.0


class SimpleKalman:
    """1D Kalman-Filter für Temperatur + dT/dt."""
    def __init__(self, init_temp=20.0):
        self.x = np.array([init_temp, 0.0], dtype=float)
        self.P = np.eye(2) * 1.0
        self.Q = np.diag([0.005, 0.0005])
        self.R = 0.08
        
    def predict(self, dt_s):
        if dt_s <= 0:
            return
        F = np.array([[1.0, dt_s], [0.0, 1.0]])
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q
        
    def update(self, z_temp):
        H = np.array([[1.0, 0.0]])
        y = z_temp - H @ self.x
        S = (H @ self.P @ H.T + self.R).item()
        K = (self.P @ H.T / S).ravel()
        self.x = self.x + K * y
        I = np.eye(2)
        self.P = (I - np.outer(K, H)) @ self.P
        
    def get_state(self):
        temp = float(self.x[0])
        dt_per_min = float(self.x[1] * 60.0)
        return temp, dt_per_min


class WasserResiduumController:
    """Kernlogik mit Kalman-Filter, Baseline-Korrektur, Hydrus-Fusion & Dual-K-Interpolation."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.temp_entity = entry.data[CONF_TEMP_ENTITY]
        self.total_entity = entry.data[CONF_TOTAL_ENTITY]
        self.total_unit = entry.data.get(CONF_TOTAL_UNIT, DEFAULT_TOTAL_UNIT).lower()
        
        # Dual-K Parameter für Warm/Kalt-Interpolation
        self.k_warm = entry.options.get(CONF_K_WARM, DEFAULT_K_WARM)
        self.k_cold = entry.options.get(CONF_K_COLD, DEFAULT_K_COLD)
        self.t_warm = entry.options.get(CONF_T_WARM, DEFAULT_T_WARM)
        self.t_cold = entry.options.get(CONF_T_COLD, DEFAULT_T_COLD)

        self.clip = entry.options.get(CONF_CLIP, DEFAULT_CLIP)
        self.max_res_l = entry.options.get(CONF_MAX_RES_L, DEFAULT_MAX_RES_L)
        
        # Interne Zustände
        self._kalman = None
        self._last_ts = None
        self._last_temp = None
        self._last_temp_relative = None
        
        self._dt_history = deque(maxlen=15)
        self._flow_active = False
        self._last_flow_time = None
        
        self._volume_l = 0.0
        self._offset_l = 0.0
        self._volume_uncertainty = 0.0
        self._last_hydrus_total = None
        self._last_hydrus_change_time = None  # NEU: Für Hydrus-Korrelation
        self._last_flow = None
        self._last_dt_used = None
        self._last_k_used = None
        
        # Baseline-Korrektur: 12h-Fenster für langsame Temperaturänderungen
        self._temp_history_6h = deque(maxlen=720)
        self._temp_history_since_tick = []
        self._last_temp_relative = None

        # Nacht-Abkühlungs-Schutz
        self._dt_gradient_history = deque(maxlen=5)
        self._last_dt_baseline_corrected = None
        self._flow_confirmation_counter = 0
        self._night_mode_active = False

        self._remove_temp_listener = None
        self._remove_total_listener = None
    
    def _get_interpolated_k(self, current_temp: float) -> float:
        """
        Interpoliert K linear zwischen k_warm und k_cold basierend auf Temperatur.
        
        - Oberhalb t_warm: k_warm
        - Unterhalb t_cold: k_cold
        - Dazwischen: lineare Interpolation
        """
        if current_temp >= self.t_warm:
            return self.k_warm
        if current_temp <= self.t_cold:
            return self.k_cold
        
        # Lineare Interpolation
        temp_range = self.t_warm - self.t_cold
        if temp_range <= 0:
            return self.k_warm
        
        ratio = (current_temp - self.t_cold) / temp_range
        k_interpolated = self.k_cold + ratio * (self.k_warm - self.k_cold)

        return max(KMIN, min(KMAX, float(k_interpolated)))

    def _is_night_time(self) -> bool:
        """Prüft ob aktuell Nacht (22:00-06:00). Strengere Schwellwerte in dieser Zeit."""
        now = datetime.now()
        hour = now.hour
        return hour >= 22 or hour < 6

    def _is_deep_sleep_mode(self) -> bool:
        """Prüft ob >2h keine Zapfung. Extra-strenge Schwellwerte in diesem Modus."""
        if self._last_flow_time is None:
            return True
        idle_hours = (time.time() - self._last_flow_time) / 3600.0
        return idle_hours > 2.0

    def _calculate_baseline(self) -> float:
        """Gleitende Baseline über 12h. Nachts 1. Perzentil, tags 2. Perzentil."""
        if len(self._temp_history_6h) < 60:
            return self._last_temp if self._last_temp else 15.0

        percentile = 1.0 if self._is_night_time() else 2.0
        baseline = np.percentile(self._temp_history_6h, percentile)
        return float(baseline)
    
    def _should_accept_thermal_flow(self, dt_baseline_corrected: float, dt_gradient: float = None) -> bool:
        """
        Gatekeeper für thermischen Flow. Berücksichtigt Hydrus-Tick-Zeit,
        Tageszeit, Sleep-Mode und Gradient-Geschwindigkeit.
        """
        # Basis-Schwellwert abhängig von Zeit seit letztem Hydrus-Tick
        if self._last_hydrus_change_time is None:
            base_threshold = -0.10
        else:
            time_since_hydrus = time.time() - self._last_hydrus_change_time
            if time_since_hydrus < 300:
                base_threshold = -0.01
            elif time_since_hydrus < 1800:
                base_threshold = -0.08
            else:
                base_threshold = -0.20

        # Nacht-Modus: 3x strengerer Schwellwert
        if self._is_night_time():
            base_threshold *= 3.0
            _LOGGER.debug("Nacht-Modus: Schwellwert %.4f", base_threshold)

        # Deep-Sleep: weitere 2x Verschärfung
        if self._is_deep_sleep_mode():
            base_threshold *= 2.0
            _LOGGER.debug("Deep-Sleep: Schwellwert %.4f", base_threshold)

        # Gradient-Check: Stetige Änderungen nachts ablehnen
        if dt_gradient is not None and abs(dt_gradient) < 0.005 and self._is_night_time():
            _LOGGER.debug("Stetige Änderung nachts: d²T/dt²=%.6f → abgelehnt", dt_gradient)
            return False

        return dt_baseline_corrected < base_threshold
    
    def set_options(self, k_warm=None, k_cold=None, t_warm=None, t_cold=None,
                   clip=None, max_res_l=None):
        if k_warm is not None:
            self.k_warm = k_warm
        if k_cold is not None:
            self.k_cold = k_cold
        if t_warm is not None:
            self.t_warm = t_warm
        if t_cold is not None:
            self.t_cold = t_cold
        if clip is not None:
            self.clip = clip
        if max_res_l is not None:
            self.max_res_l = max_res_l
        _LOGGER.info("Options: k_warm=%.2f, k_cold=%.2f, t_warm=%.1f°C, t_cold=%.1f°C",
                     self.k_warm, self.k_cold, self.t_warm, self.t_cold)
    
    async def _persist_options(self, new_opts: dict):
        """Optionen im ConfigEntry speichern."""
        data = dict(self.entry.data)
        options = dict(self.entry.options)
        options.update(new_opts)
        self.entry = self.entry.async_replace(data=data, options=options)
        self.hass.config_entries.async_update_entry(self.entry)
    
    async def async_set_k_warm(self, new_k: float):
        self.k_warm = new_k
        await self._persist_options({CONF_K_WARM: new_k})
        _LOGGER.info("K-Warm geändert → %.2f", new_k)
    
    async def async_set_k_cold(self, new_k: float):
        self.k_cold = new_k
        await self._persist_options({CONF_K_COLD: new_k})
        _LOGGER.info("K-Cold geändert → %.2f", new_k)
    
    @property
    def residuum_l(self) -> float:
        raw = self._volume_l - self._offset_l
        return max(0.0, min(raw, self.max_res_l))
    
    @property
    def volume_l(self) -> float:
        return self._volume_l
    
    @property
    def offset_l(self) -> float:
        return self._offset_l
    
    @property
    def volume_uncertainty(self) -> float:
        return self._volume_uncertainty

    def register_entity_listener(self, cb) -> None:
        """Sensoren/Numbers registrieren sich hier, um Updates zu bekommen."""
        self.__dict__.setdefault("_entity_listeners", []).append(cb)
        
    @property
    def last_flow_l_min(self) -> float | None:
        return self._last_flow
    
    @property
    def last_dt_k_per_min(self) -> float | None:
        return self._last_dt_used
    
    @property
    def last_k_eff(self) -> float | None:
        return self._last_k_used

    @property
    def night_mode_active(self) -> bool:
        """Gibt zurück ob Nacht-Modus aktiv ist."""
        return self._night_mode_active

    @property
    def deep_sleep_active(self) -> bool:
        """Gibt zurück ob Deep-Sleep-Modus aktiv ist."""
        return self._is_deep_sleep_mode()
    
    def _integrate(self, flow_l_min: float, dt_s: float):
        if dt_s <= 0:
            return
        delta_volume = flow_l_min * (dt_s / 60.0)
        self._volume_l += delta_volume
        self._volume_uncertainty += abs(delta_volume * 0.12)
        if self._volume_l < 0:
            _LOGGER.debug("Volume negativ, reset auf 0")
            self._volume_l = 0.0
    
    def _convert_total_to_l(self, val: float) -> float:
        return _m3_to_l(val) if self.total_unit == "m3" else float(val)
    
    def _guard_offset(self):
        """Offset darf höchstens 10 L über aktuellem Hydrus-Total liegen."""
        if self._last_hydrus_total is None:
            return
        max_offset = self._last_hydrus_total + 10.0
        if self._offset_l > max_offset:
            self._offset_l = max_offset
    
    @callback
    def _on_total_entity_changed(self, event: Event) -> None:
        if event.data.get("entity_id") != self.total_entity:
            return
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        try:
            now_total_l = self._convert_total_to_l(float(new_state.state))
        except (ValueError, TypeError):
            return
        
        # Erste Initialisierung
        if self._last_hydrus_total is None:
            # Wenn Volume vom Sensor bereits restauriert wurde, NICHT überschreiben.
            if getattr(self, "_restored_volume", False):
                self._last_hydrus_total = now_total_l  # nur Referenz setzen
                self._guard_offset()
                _LOGGER.info(
                    "Init: verwende restauriertes Volume %.1f L (Hydrus=%.1f L)",
                    self._volume_l, now_total_l
                )
            else:
                rounded_volume = (now_total_l // 10) * 10
                self._volume_l = rounded_volume
                self._offset_l = rounded_volume
                self._guard_offset()
                _LOGGER.info(
                    "Late Init: Hydrus %.1f L → Volume %.1f L",
                    now_total_l, self._volume_l
                )

        
        # 10L-Tick Erkennung mit Auto-Kalibrierung
        if self._last_hydrus_total is not None:
            delta_l = now_total_l - self._last_hydrus_total
            if 9.5 <= delta_l <= 10.5:
                thermal_measured = self.residuum_l

                # Auto-Kalibrierung: Nur bei plausiblen Werten, begrenzte Änderung
                if thermal_measured > 1.0 and len(self._temp_history_since_tick) > 0:
                    avg_temp = np.mean(self._temp_history_since_tick)

                    if 4.0 <= thermal_measured <= 16.0:
                        raw_correction = 10.0 / thermal_measured
                        correction = max(0.7, min(1.3, raw_correction))  # Max ±30%

                        def _smooth_k(old_k: float, corr: float, kmax_local: float) -> float:
                            target_k = old_k * corr
                            new_k = old_k + K_ADAPT_MAX_STEP * (target_k - old_k)  # Max 25% pro Tick
                            return max(KMIN, min(kmax_local, new_k))

                        if avg_temp >= self.t_warm:
                            old = self.k_warm
                            self.k_warm = _smooth_k(old, correction, KMAX)
                            _LOGGER.info(
                                "K-warm auto-korrigiert: %.2f → %.2f bei %.1f°C "
                                "(thermal: %.1f L, corr=%.3f)",
                                old, self.k_warm, avg_temp, thermal_measured, correction
                            )
                            self.hass.async_create_task(
                                self._persist_options({CONF_K_WARM: self.k_warm})
                            )

                        elif avg_temp <= self.t_cold:
                            old = self.k_cold
                            self.k_cold = _smooth_k(old, correction, KMAX_COLD)
                            _LOGGER.info(
                                "K-cold auto-korrigiert: %.2f → %.2f bei %.1f°C "
                                "(thermal: %.1f L, corr=%.3f, limit=%.1f)",
                                old, self.k_cold, avg_temp, thermal_measured, correction, KMAX_COLD
                            )
                            self.hass.async_create_task(
                                self._persist_options({CONF_K_COLD: self.k_cold})
                            )
                    else:
                        _LOGGER.info(
                            "Auto-Kalibrierung übersprungen: thermal_measured=%.2f L "
                            "(zu weit weg vom 10L-Tick)", thermal_measured
                        )

                _LOGGER.info("Hydrus 10L-Tick: +%.1f L, Thermal %.3f L → Reset",
                            delta_l, thermal_measured)

                # Reset Residuum und Tracking
                self._offset_l = self._volume_l
                self._volume_uncertainty = 0.0
                self._last_hydrus_change_time = time.time()
                self._temp_history_since_tick = []

            elif delta_l > 10.5:
                _LOGGER.warning("Hydrus Sprung %.1f L, kein Auto-Reset", delta_l)
            elif delta_l < -0.1:
                _LOGGER.warning("Hydrus Rückwärts: %.3f → %.3f", 
                               self._last_hydrus_total, now_total_l)
        
        self._last_hydrus_total = now_total_l
        self._notify_entities()
    
    @callback
    def _on_temp_entity_changed(self, event: Event) -> None:
        if event.data.get("entity_id") != self.temp_entity:
            return
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        try:
            raw_temp = float(new_state.state)
        except (ValueError, TypeError):
            return
        
        now_ts = time.time()
        self._last_temp = raw_temp
        
        if self._kalman is None:
            self._kalman = SimpleKalman(init_temp=raw_temp)
            self._last_ts = now_ts
            self._last_temp_relative = 0.0
            _LOGGER.info("Kalman init bei %.2f °C", raw_temp)
            self._notify_entities()
            return
        
        dt_s = now_ts - self._last_ts
        if dt_s < 1.0:
            return
        
        self._kalman.predict(dt_s)
        self._kalman.update(raw_temp)
        filt_temp, dt_per_min = self._kalman.get_state()

        # Speichere für Baseline und Auto-Kalibrierung
        self._temp_history_6h.append(filt_temp)
        self._temp_history_since_tick.append(filt_temp)

        # Baseline-Korrektur
        baseline = self._calculate_baseline()
        temp_relative = filt_temp - baseline

        # Baseline-korrigierter Gradient
        if self._last_temp_relative is not None:
            dt_baseline_corrected = (temp_relative - self._last_temp_relative) / (dt_s / 60.0)
        else:
            dt_baseline_corrected = 0.0
            self._last_temp_relative = temp_relative

        # Gradient-Geschwindigkeit (d²T/dt²)
        dt_gradient = None
        if self._last_dt_baseline_corrected is not None:
            dt_gradient = (dt_baseline_corrected - self._last_dt_baseline_corrected) / (dt_s / 60.0)
            self._dt_gradient_history.append(dt_gradient)

        self._last_dt_baseline_corrected = dt_baseline_corrected
        self._last_ts = now_ts
        self._last_dt_used = dt_baseline_corrected
        
        # Historie für MAD-Clipping
        self._dt_history.append(dt_baseline_corrected)
        if len(self._dt_history) >= 5:
            median_dt = statistics.median(self._dt_history)
            mad = statistics.median([abs(x - median_dt) for x in self._dt_history]) or 0.0001
            z_score = (dt_baseline_corrected - median_dt) / (1.4826 * mad)
            if abs(z_score) > 6.0:
                _LOGGER.debug(
                    "dT/dt-Ausreißer verworfen: %.4f K/min (median=%.4f, MAD=%.4f, z=%.2f)",
                    dt_baseline_corrected, median_dt, mad, z_score
                )
                return
        
        # Adaptive Schwellwerte basierend auf Tageszeit und Sleep-Mode
        threshold_enter = -0.006
        threshold_exit = -0.002

        # Nacht-Modus: 5x strengerer Schwellwert
        if self._is_night_time():
            threshold_enter *= 5.0
            self._night_mode_active = True
        else:
            self._night_mode_active = False

        # Deep-Sleep: weitere 3x Verschärfung
        if self._is_deep_sleep_mode():
            threshold_enter *= 3.0

        flow_detected = dt_baseline_corrected < threshold_enter

        # Flow-Konsistenz: Mindestens 3 aufeinanderfolgende Messungen
        if flow_detected:
            self._flow_confirmation_counter += 1
        else:
            self._flow_confirmation_counter = 0

        flow_confirmed = self._flow_confirmation_counter >= 3

        if (flow_detected and flow_confirmed) or self._flow_active:
            if not self._flow_active and flow_confirmed:
                self._flow_active = True
                _LOGGER.info("Flow gestartet (dT/dt=%.5f K/min, Nacht=%s, Sleep=%s)",
                            dt_baseline_corrected, self._night_mode_active, self._is_deep_sleep_mode())

            if not flow_detected and dt_baseline_corrected > threshold_exit:
                self._flow_active = False
                self._flow_confirmation_counter = 0
                _LOGGER.info("Flow beendet (dT/dt=%.5f K/min)", dt_baseline_corrected)

            if self._flow_active and self._should_accept_thermal_flow(dt_baseline_corrected, dt_gradient):
                if dt_baseline_corrected < -self.clip:
                    dt_clipped = -self.clip
                else:
                    dt_clipped = dt_baseline_corrected
            else:
                dt_clipped = 0.0
        else:
            dt_clipped = 0.0
            if flow_detected and not flow_confirmed:
                _LOGGER.debug("Flow-Kandidat ignoriert (nicht konsistent, Zähler=%d)", self._flow_confirmation_counter)
        
        if dt_clipped < 0.0:
            self._last_flow_time = now_ts
            
            k_adaptive = self._get_interpolated_k(filt_temp)
            self._last_k_used = k_adaptive
            
            flow_l_min = k_adaptive * (-dt_clipped)
            
            MAX_FLOW = 25.0
            if flow_l_min > MAX_FLOW:
                _LOGGER.warning("Flow %.1f L/min > Maximum, cappe auf %.1f", 
                               flow_l_min, MAX_FLOW)
                flow_l_min = MAX_FLOW
            
            self._last_flow = flow_l_min

            _LOGGER.debug(
                "Flow: %.3f L/min (K=%.2f @ %.1f°C, dT_corr=%.4f K/min, baseline=%.2f°C, d²T/dt²=%.6f, Nacht=%s)",
                flow_l_min, k_adaptive, filt_temp, dt_baseline_corrected, baseline,
                dt_gradient if dt_gradient else 0.0, self._night_mode_active
            )
            
            self._integrate(flow_l_min, dt_s)
        else:
            self._last_flow = 0.0
            self._last_k_used = self._get_interpolated_k(filt_temp)
        
        self._last_temp_relative = temp_relative
        
        self._notify_entities()
    
    def _notify_entities(self) -> None:
        """Informiert alle Entities über Zustandsänderungen."""
        self.hass.data[DOMAIN][self.entry.entry_id][DATA_CTRL] = self
        for cb in self.__dict__.get("_entity_listeners", []):
            try:
                cb()
            except Exception as e:
                _LOGGER.exception("Entity-Listener Fehler: %s", e)
    
    async def async_start(self):
        @callback
        def temp_listener(event: Event):
            self._on_temp_entity_changed(event)
        
        @callback
        def total_listener(event: Event):
            self._on_total_entity_changed(event)
        
        self._remove_temp_listener = self.hass.bus.async_listen(EVENT_STATE_CHANGED, temp_listener)
        self._remove_total_listener = self.hass.bus.async_listen(EVENT_STATE_CHANGED, total_listener)
        
        _LOGGER.info("WasserResiduumController gestartet für %s / %s", self.temp_entity, self.total_entity)
    
    async def async_stop(self):
        if self._remove_temp_listener:
            self._remove_temp_listener()
            self._remove_temp_listener = None
        if self._remove_total_listener:
            self._remove_total_listener()
            self._remove_total_listener = None
        _LOGGER.info("WasserResiduumController gestoppt")
    

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    ctrl = WasserResiduumController(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_CTRL: ctrl}
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await ctrl.async_start()
    
    entry.add_update_listener(_async_update_listener)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        ctrl = hass.data[DOMAIN][entry.entry_id][DATA_CTRL]
        await ctrl.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)
