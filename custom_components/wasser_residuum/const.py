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
CONF_K_WARM: Final[str] = "k_warm"
CONF_K_COLD: Final[str] = "k_cold"
CONF_T_WARM: Final[str] = "t_warm"
CONF_T_COLD: Final[str] = "t_cold"
CONF_CLIP: Final[str] = "clip"
CONF_MAX_RES_L: Final[str] = "max_residuum_l"

# --- Defaults -----------------------------------------------------------------
DEFAULT_NAME: Final[str] = "Wasser Residuum"
DEFAULT_K_WARM: Final[float] = 4.0
DEFAULT_K_COLD: Final[float] = 8.0
DEFAULT_T_WARM: Final[float] = 16.0
DEFAULT_T_COLD: Final[float] = 12.0
DEFAULT_CLIP: Final[float] = 2.5
DEFAULT_MAX_RES_L: Final[float] = 10.0
DEFAULT_TOTAL_UNIT: Final[str] = "L"

# --- Ranges für Config Flow / Options -----------------------------------------
RANGE_K: Final[dict] = {"min": 0.5, "max": 10.0, "step": 0.1}
RANGE_T: Final[dict] = {"min": 5.0, "max": 35.0, "step": 0.5}
RANGE_CLIP: Final[dict] = {"min": 0.5, "max": 5.0, "step": 0.1}
RANGE_MAX_RES: Final[dict] = {"min": 5.0, "max": 50.0, "step": 1.0}
