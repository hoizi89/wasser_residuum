# Wasser-Residuum (wMBus Water Flow Detection)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/hoizi89/wasser_residuum.svg)](https://github.com/hoizi89/wasser_residuum/releases)
[![License](https://img.shields.io/github/license/hoizi89/wasser_residuum.svg)](LICENSE)

Home Assistant integration that estimates water consumption **between 10L meter ticks** (0-9.999 L) in real time using temperature data from a wMBus water meter and Kalman filtering.

## How It Works

1. The **Diehl Hydrus** water meter measures the pipe temperature and transmits it via **wMBus** (868 MHz) every ~16 seconds
2. An **RTL-SDR dongle** + **wmbusmeters** receives the data and publishes it to Home Assistant via MQTT
3. When water flows, the pipe temperature **drops** — the rate of change (dT/dt) correlates with flow rate
3. A **Kalman filter** smooths the temperature signal and extracts the gradient
4. A **baseline correction** (12h window) compensates for natural ambient temperature drift
5. The gradient is converted to flow rate using a **K-factor** (dual-K: separate values for warm and cold water, interpolated based on current temperature)
6. Flow rate is integrated over time to calculate **volume** (liters)
7. At every **10L tick** from the water meter, the integration auto-calibrates its K-factors and resets

### Anti-Drift Protection

- **Night mode** (22:00-06:00): 5x stricter thresholds to prevent false detections from overnight cooling
- **Deep sleep** (>2h idle): 3x stricter thresholds
- **Flow consistency**: Requires 3 consecutive measurements above threshold before counting
- **Variance detection**: Additional cold-weather flow detection via temperature variance analysis

### Auto-Calibration Formula

At every 10L tick from the water meter:
```
K_new = K_old * (10.0 / thermal_volume_measured)
```
The system learns the correct K-factors automatically over time (5-10 ticks / 50-100 L).

## Hardware

### Tested Setup

| Component | Model | Notes |
|-----------|-------|-------|
| Water Meter | **Diehl Hydrus** (wMBus 868 MHz) | Provides temperature + total volume via wMBus |
| wMBus Receiver | **RTL-SDR v3** USB dongle | Receives 868 MHz wMBus telegrams |
| wMBus Host | Any Linux box / VM | Runs wmbusmeters + the MQTT script |
| MQTT Broker | **Mosquitto** (on Home Assistant) | Bridges meter data to HA |

The Hydrus meter has a built-in temperature sensor and transmits the water temperature along with the total consumption. No additional temperature sensor is needed.

The RTL-SDR dongle can be attached to any machine on your network (e.g., a Proxmox VM with USB passthrough). It does not need to be on the same device as Home Assistant.

### Alternative Receivers

Any receiver supported by [wmbusmeters](https://github.com/wmbusmeters/wmbusmeters) works: CUL, IM871A-USB, AMB8465-M, or RTL-SDR.

## Prerequisites

- Home Assistant 2024.1.0+
- A **Diehl Hydrus** water meter (or any wMBus meter that reports temperature + total volume)
- A **wMBus receiver** (RTL-SDR v3 or similar) — see [wMBus Setup](#wmbus-setup)
- **Mosquitto MQTT** broker (or any MQTT broker connected to HA)
- Python `numpy` (installed automatically)

## Installation (HACS)

1. Open HACS → Integrations
2. Three-dot menu → Custom repositories
3. URL: `https://github.com/hoizi89/wasser_residuum`, Category: Integration
4. Install "Wasser-Residuum"
5. Restart Home Assistant

### Manual Installation

Copy `custom_components/wasser_residuum` to your HA `custom_components/` directory and restart.

## Configuration

1. Settings → Devices & Services → Add Integration
2. Search for "Wasser-Residuum"
3. Select your **temperature sensor** entity and **water meter total** entity
4. Optionally select Last Sync and RSSI entities (from wMBus)
5. Choose unit (m³ or L)

### Options

Adjustable via integration options (defaults work well, auto-calibration adjusts over time):

| Option | Default | Description |
|--------|---------|-------------|
| K-Warm | 4.0 | Conversion factor for warm water (>=16°C) — auto-learns |
| K-Cold | 8.0 | Conversion factor for cold water (<=12°C) — auto-learns |
| T-Warm / T-Cold | 16°C / 12°C | Temperature boundaries for K interpolation |
| Clip | 2.5 | Maximum dT/dt clipping value |
| Max Residuum | 10.0 L | Reset interval (matches meter resolution) |

## Sensors

| Sensor | Description |
|--------|-------------|
| Residuum | Volume since last reset, 0-10 L (main sensor) |
| Flow | Current estimated flow rate (L/min) |
| Volume | Cumulative total volume (L), persists across restarts |
| K Active | Currently used K-factor with warm/cold values in attributes |
| Night Mode | Whether night mode is active |
| Deep Sleep | Whether deep sleep mode is active |
| Temp Filtered | Kalman-filtered pipe temperature |
| dT Used | Current temperature gradient used for calculation |
| Uncertainty | Current measurement uncertainty estimate |

## wMBus Setup

The included `wmbus_pub.sh` script reads data from a **Diehl Hydrus** water meter via [wmbusmeters](https://github.com/wmbusmeters/wmbusmeters) and publishes it to Home Assistant via MQTT auto-discovery.

### What It Does

1. Receives JSON data from wmbusmeters (called as a shell hook on each telegram)
2. Extracts: total consumption (m³), water temperature, battery life, RSSI
3. Parses additional data from wmbusmeters log: historical billing volume, billing date, error flags
4. Publishes everything to MQTT with Home Assistant auto-discovery config
5. Rate-limits updates: publishes only on significant changes (temperature >0.05°C or volume >0.001 m³) or every 60s heartbeat

### Step 1: Hardware Setup

Plug the **RTL-SDR dongle** into a Linux machine. The dongle receives 868 MHz wMBus telegrams from the Hydrus meter — it broadcasts automatically every ~16 seconds.

Any Linux host works: a Raspberry Pi, a dedicated mini-PC, or a VM. If using **Proxmox**, create a Debian 12 VM and pass through the RTL-SDR USB device:

```
Proxmox UI → VM → Hardware → Add → USB Device → select "Realtek RTL2838" (0bda:2838)
```

Verify the dongle is detected inside the VM:

```bash
lsusb | grep RTL
# Should show: Realtek Semiconductor Corp. RTL2838
```

### Step 2: Install wmbusmeters

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y rtl-sdr mosquitto-clients jq
sudo snap install wmbusmeters

# Or build from source: https://github.com/wmbusmeters/wmbusmeters
```

Verify the RTL-SDR works:

```bash
rtl_test -t
# Should show "Found 1 device(s)" and "No E4000 tuner found, using default"
# Press Ctrl+C to stop
```

### Step 3: Find Your Meter

Run wmbusmeters in listen mode to discover nearby meters:

```bash
wmbusmeters --listento=t1 auto:t1
```

Look for your Hydrus meter in the output. Note the **meter ID** (8-digit number printed on the meter).

Many Hydrus meters transmit **unencrypted** — no AES key needed. If the data in Step 3 shows readable values (temperature, total volume), you're good. If the output shows encrypted/empty data, contact your water utility and ask for the wMBus AES decryption key.

### Step 4: Configure wmbusmeters

Create a meter config file:

```bash
sudo nano /etc/wmbusmeters.d/hydrus
```

```ini
name=hydrus
driver=hydrus
id=YOUR_METER_ID
# key=YOUR_AES_KEY  # Only needed if meter data is encrypted. Omit this line if unencrypted.
```

Configure the main wmbusmeters settings:

```bash
sudo nano /etc/wmbusmeters.conf
```

```ini
loglevel=normal
device=auto:t1
logtelegrams=false
format=json
shell=/path/to/wmbus_pub.sh "$METER_JSON" "$METER_NAME" "$METER_ID"
```

### Step 5: Set Up MQTT Publishing

1. Copy `wmbus_pub.sh` to your wmbusmeters host (e.g., `/opt/wmbus_pub.sh`)
2. Make it executable: `chmod +x /opt/wmbus_pub.sh`
3. Edit the script — set your MQTT broker address and credentials:
   ```bash
   BROKER="-h YOUR_HA_IP -u YOUR_MQTT_USER -P YOUR_MQTT_PASSWORD -q 1"
   ```

### Step 6: Start and Verify

```bash
sudo systemctl restart wmbusmeters
sudo journalctl -u wmbusmeters -f
```

You should see JSON telegrams arriving every ~16 seconds. The script auto-creates sensors in Home Assistant via MQTT discovery — check Settings → Devices & Services → MQTT for the new device.

### Troubleshooting wMBus

- **No telegrams**: Check RTL-SDR connection (`rtl_test`), ensure 868 MHz reception (T1 mode)
- **Encrypted data**: You need the correct AES key from your water utility
- **No MQTT sensors**: Verify mosquitto_pub works: `mosquitto_pub -h YOUR_HA_IP -u USER -P PASS -t test -m hello`
- **Weak signal**: The Hydrus transmits at low power — keep the RTL-SDR within ~10-20m of the meter

### Created MQTT Sensors

| Sensor | Unit | Description |
|--------|------|-------------|
| Total | m³ | Total water consumption |
| Total Liters | L | Same in liters |
| Water Temperature | °C | Current pipe temperature |
| Battery Life | years | Remaining meter battery |
| Signal Strength | dBm | wMBus RSSI |
| Last Billing Reading | m³ | Historical volume at billing date |
| Consumption Since Billing | m³ | Current - historical |
| Billing Date | — | Date of last billing reading |
| Meter Status | — | Error flags (OK or error code) |
| Last Sync | — | Timestamp of last received telegram |

## Related

Pairs well with [wasser_vibration](https://github.com/hoizi89/wasser_vibration) which uses vibration-based flow detection as an alternative/complementary approach.

## Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.wasser_residuum: debug
```

---

Experimental hobby project. Use calibrated meters for billing purposes.
