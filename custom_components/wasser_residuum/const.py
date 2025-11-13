from __future__ import annotations

from typing import Final, Literal
from homeassistant.const import Platform

# --- Domain / Platforms -------------------------------------------------------
DOMAIN: Final[str] = "wasser_residuum"
DATA_CTRL: Final[str] = "ctrl"

PLATFORMS: Final[tuple[Platform, ...]] = (
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
)

# --- Config keys --------------------------------------------------------------
CONF_NAME: Final[str] = "name"
CONF_TEMP_ENTITY: Final[str] = "temp_entity"
CONF_TOTAL_ENTITY: Final[str] = "total_entity"
CONF_LASTSYNC_ENTITY = "lastsync_entity"
CONF_RSSI_ENTITY = "rssi_entity"
CONF_TOTAL_UNIT: Final[str] = "total_unit"
TotalUnit = Literal["m3", "L"]

# --- Option keys --------------------------------------------------------------
CONF_K: Final[str] = "k"
CONF_K_WARM: Final[str] = "k_warm"  # NEU
CONF_K_COLD: Final[str] = "k_cold"  # NEU
CONF_T_WARM: Final[str] = "t_warm"  # NEU
CONF_T_COLD: Final[str] = "t_cold"  # NEU
CONF_CLIP: Final[str] = "clip"
CONF_ALPHA: Final[str] = "alpha"
CONF_WINDOW_S: Final[str] = "window_s"
CONF_MAX_RES_L: Final[str] = "max_residuum_l"

# --- Defaults -----------------------------------------------------------------
DEFAULT_NAME: Final[str] = "Wasser Residuum"
DEFAULT_K: Final[float] = 8.0  # Legacy, wird durch K_WARM ersetzt
DEFAULT_K_WARM: Final[float] = 4.0  # K-Faktor bei warmer Leitung
DEFAULT_K_COLD: Final[float] = 8.0  # K-Faktor bei kalter Leitung
DEFAULT_T_WARM: Final[float] = 16.0  # Referenztemperatur warm (°C)
DEFAULT_T_COLD: Final[float] = 12.0  # Referenztemperatur kalt (°C)
DEFAULT_CLIP: Final[float] = 2.5
DEFAULT_ALPHA: Final[float] = 0.5
DEFAULT_WINDOW_S: Final[int] = 8
DEFAULT_MAX_RES_L: Final[float] = 10.0
DEFAULT_TOTAL_UNIT: Final[str] = "L"

# Hysterese-Schwellwerte
DEADBAND_ENTER_KPMIN: Final[float] = 0.015
DEADBAND_EXIT_KPMIN: Final[float] = 0.006

# --- Ranges für Config Flow / Options -----------------------------------------
# K-Bereich reduziert, damit die Auto-Kalibrierung nicht mehr bis 15 L/K hochdreht
RANGE_K: Final[dict] = {"min": 0.5, "max": 10.0, "step": 0.1}
RANGE_T: Final[dict] = {"min": 5.0, "max": 35.0, "step": 0.5}  # NEU
RANGE_CLIP: Final[dict] = {"min": 0.5, "max": 5.0, "step": 0.1}
RANGE_ALPHA: Final[dict] = {"min": 0.01, "max": 1.0, "step": 0.05}
RANGE_WINDOW: Final[dict] = {"min": 2, "max": 30, "step": 1}
RANGE_MAX_RES: Final[dict] = {"min": 5.0, "max": 50.0, "step": 1.0}
