# Wasser-Residuum

Estimates water consumption **between 10L meter ticks** (0-9.999 L) in real time using temperature data from a wMBus water meter (e.g., Diehl Hydrus) and Kalman filtering.

## How It Works

The Hydrus meter transmits water temperature via wMBus. Water flow causes a temperature drop — a Kalman filter extracts the gradient, which is converted to flow rate using auto-calibrating K-factors (separate for warm/cold water). Volume is integrated and resets at each 10L meter tick.

## Key Features

- Real-time flow estimation between coarse meter ticks
- Auto-calibration at every 10L tick
- Night mode and deep sleep to prevent false detections
- Dual-K interpolation for warm/cold water accuracy

## Prerequisites

- Diehl Hydrus water meter (or any wMBus meter with temperature)
- RTL-SDR dongle + wmbusmeters for wMBus reception
- Home Assistant 2024.1.0+

## Installation

1. HACS → Integrations → Custom Repository → `https://github.com/hoizi89/wasser_residuum`
2. Install, restart HA
3. Add integration → select temperature and water meter entities from MQTT
