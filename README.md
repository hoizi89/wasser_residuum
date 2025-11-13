# Wasser-Residuum (ΔT→L Kalman)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/yourusername/wasser_residuum.svg)](https://github.com/yourusername/wasser_residuum/releases)
[![License](https://img.shields.io/github/license/yourusername/wasser_residuum.svg)](LICENSE)

Misst den Wasserverbrauch **zwischen 10L-Zählerticks** (0-9.9999L) in Echtzeit durch Temperaturüberwachung.

## Was macht die Integration?

Dein Wasserzähler zählt nur in 10L-Schritten? Diese Integration zeigt dir den **aktuellen Verbrauch bis zum nächsten Tick** an!

**Prinzip**: Wasserfluss → Temperaturabfall → Durchflussberechnung

**Genauigkeit**: 0-9.9999 Liter zwischen den fixen 10L-Ticks

## 🆕 Version 0.3.0 - Anti-Nacht-Drift

**Problem gelöst**: Keine falschen Zapfungen mehr durch Nacht-Abkühlung!
- 🌙 Nacht-Modus (22:00-06:00) - 5x strengere Schwellwerte
- 😴 Deep-Sleep (>2h Ruhe) - 3x strengere Schwellwerte
- ✅ Flow-Konsistenz - 3 aufeinanderfolgende Messungen nötig

## 🎯 Features

- **Echtzeit**: Sofortige Anzeige, keine Wartezeit auf Zählerticks
- **Auto-Kalibrierung**: Lernt bei jedem 10L-Tick automatisch
- **Dual-K**: Unterscheidet zwischen warmem und kaltem Wasser
- **Nacht-sicher**: Keine falschen Zapfungen durch Temperatur-Drift

## 📋 Voraussetzungen

- Home Assistant 2024.1.0 oder neuer
- Ein **Temperatursensor** in der Wasserleitung (z.B. DS18B20)
- Ein **Wasserzähler** mit Smart Meter Auslesen (z.B. Hydrus mit ESPHome/wMBus)
- Python-Paket `numpy` (wird automatisch installiert)

## 🔧 Installation

### Via HACS (empfohlen)

1. Öffne HACS in Home Assistant
2. Klicke auf "Integrations"
3. Klicke auf die drei Punkte oben rechts und wähle "Custom repositories"
4. Füge die Repository-URL hinzu: `https://github.com/yourusername/wasser_residuum`
5. Kategorie: "Integration"
6. Klicke auf "Hinzufügen"
7. Suche nach "Wasser-Residuum" und klicke auf "Download"
8. Starte Home Assistant neu

### Manuelle Installation

1. Lade die neueste Version von [Releases](https://github.com/yourusername/wasser_residuum/releases) herunter
2. Entpacke das Archiv
3. Kopiere den Ordner `custom_components/wasser_residuum` nach `<config>/custom_components/`
4. Starte Home Assistant neu

## ⚙️ Konfiguration

1. **Einstellungen** → **Geräte & Dienste** → **+ Integration hinzufügen**
2. Suche nach **Wasser-Residuum**
3. Wähle:
   - **Temperatursensor** (z.B. DS18B20 in der Leitung)
   - **Wasserzähler** (z.B. Hydrus)
   - **Einheit**: m³ oder L

4. **Fertig!** Die Kalibrierung läuft automatisch.

### Optionale Anpassung

Die Standardwerte funktionieren gut. Bei Bedarf über **Optionen** anpassen:

| Parameter | Standard | Beschreibung |
|-----------|----------|--------------|
| **K-Warm** | 4.0 | Umrechnungsfaktor warm (≥16°C) - **lernt automatisch!** |
| **K-Cold** | 8.0 | Umrechnungsfaktor kalt (≤12°C) - **lernt automatisch!** |
| **T-Warm/T-Cold** | 16°C / 12°C | Temperatur-Grenzen für Interpolation |
| **Max. Residuum** | 10.0 L | Obergrenze (sollte bei 10L bleiben) |

## 📊 Wichtigste Sensoren

### Was du ansehen solltest:
- **`sensor.wasser_residuum_residuum`** → **0-9.9999L bis nächster Tick** 🎯
- `sensor.wasser_residuum_last_flow` → Aktueller Durchfluss (L/min)
- `sensor.wasser_residuum_night_mode` → Nacht-Modus Status
- `sensor.wasser_residuum_k_active` → Aktiver K-Faktor + Attribute (K-Warm/K-Cold Werte)

### Diagnose (falls was nicht stimmt):
- `sensor.wasser_residuum_last_dt_dt` → Temperaturgradient + Schwellwert
- `sensor.wasser_residuum_deep_sleep` → Sleep-Modus Status
- `sensor.wasser_residuum_temp_filtered` → Gefilterte Temperatur
- `sensor.wasser_residuum_uncertainty` → Messunsicherheit

### Anpassbar:
- `number.wasser_residuum_k_warm` / `k_cold` → Manuell ändern (oder Auto-Kalibrierung nutzen!)
- `button.wasser_residuum_reset` → Reset bei Problemen

## 🎯 Wie funktioniert's?

1. **Temperatur fällt** bei Wasserfluss → Kalman-Filter erkennt Gradient
2. **Baseline-Korrektur** → Kompensiert natürliche Nacht-Abkühlung
3. **K-Faktor** → Rechnet Temperatur-Gradient in L/min um (warm vs. kalt)
4. **Integration** → Summiert auf bis 10L
5. **10L-Tick** → Automatische Kalibrierung, Reset auf 0

**Auto-Kalibrierung**:
```
Bei jedem 10L-Tick: K_neu = K_alt × (10.0 / Thermal_gemessen)
```
→ System lernt automatisch die richtigen Werte!

## 📈 Beispiel-Dashboard

```yaml
type: gauge
entity: sensor.wasser_residuum_residuum
min: 0
max: 10
name: Liter bis 10L-Tick
needle: true
segments:
  - from: 0
    color: "#0da035"
  - from: 7
    color: "#e0b400"
  - from: 9
    color: "#db4437"
```

## 🔍 Troubleshooting

### Residuum steigt nachts ohne Zapfung
✅ **Gelöst in v0.3.0!** Nacht-Modus und Deep-Sleep verhindern das automatisch.
- Prüfe: `sensor.wasser_residuum_night_mode` und `deep_sleep`
- Falls noch Probleme: Nacht-Zeitfenster in `__init__.py:143` anpassen

### K-Faktoren passen nicht
🤖 **Auto-Kalibrierung läuft!** Warte 5-10 Ticks (50-100L), dann sollten die Werte stimmen.
- Manuell anpassen: `number.wasser_residuum_k_warm` / `k_cold`
- Typische Werte: K-Warm 3-5, K-Cold 6-9

### Flow wird nicht erkannt
🔧 **Sensor-Position prüfen!** Muss direkten Wasserkontakt haben.
- Prüfe: `sensor.wasser_residuum_last_dt_dt` (sollte < -0.03 K/min bei Flow)
- Sensor-Rate: Mindestens 1x/Minute

## 📝 Logs

Aktiviere Debug-Logging für detaillierte Ausgaben:

```yaml
logger:
  default: info
  logs:
    custom_components.wasser_residuum: debug
```

## 📋 Changelog

### v0.3.0 - Anti-Nacht-Drift
- Nacht-Modus + Deep-Sleep mit adaptiven Schwellwerten
- Flow-Konsistenz-Check (3x aufeinanderfolgend)
- Gradient-Geschwindigkeit (d²T/dt²) Filter
- Neue Diagnose-Sensoren: Night Mode, Deep Sleep
- Code-Aufräumung: Idle-Boost, Alpha, Window_s entfernt

### v0.2.0 - Auto-Kalibrierung
- Dual-K Interpolation (warm/kalt)
- Auto-Kalibrierung bei 10L-Ticks
- Baseline-Korrektur (12h-Fenster)

### v0.1.0 - Initial
- Kalman-Filter Flow-Detektion
- Config Flow UI

---

**Hinweis**: Experimentelles Projekt für Hobby-Nutzung. Für Abrechnungen nur geeichte Zähler verwenden!
