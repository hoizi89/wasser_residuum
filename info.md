# Wasser-Residuum

Estimates water consumption **between 10L meter ticks** (0-9.999 L) in real time using pipe temperature monitoring and Kalman filtering.

## How It Works

Water flow causes a temperature drop in the pipe. A Kalman filter extracts the temperature gradient, which is converted to flow rate using auto-calibrating K-factors (separate for warm/cold water). Volume is integrated and resets at each 10L meter tick.

## Key Features

- Real-time flow estimation between coarse meter ticks
- Auto-calibration at every 10L tick
- Night mode and deep sleep to prevent false detections
- Dual-K interpolation for warm/cold water accuracy

## Prerequisites

- Temperature sensor on the water pipe (e.g., DS18B20)
- Smart water meter (e.g., Diehl Hydrus via wMBus)
- Home Assistant 2024.1.0+

## Installation

1. HACS → Integrations → Custom Repository → `https://github.com/hoizi89/wasser_residuum`
2. Install, restart HA
3. Add integration → select temperature sensor and water meter entity
