# Wasser-Residuum (ΔT→L Kalman)

Zeigt **0-9.9999 Liter** zwischen 10L-Zählerticks in Echtzeit an!

## Was macht das?

Dein Wasserzähler zählt nur in 10L-Schritten? Diese Integration zeigt dir **sofort** den aktuellen Verbrauch!

**Prinzip**: Wasserfluss → Temperaturabfall → Durchflussberechnung

## 🆕 v0.3.0 - Keine Nacht-Drift mehr!

- 🌙 Nacht-Modus (22:00-06:00) - 5x strengere Schwellwerte
- 😴 Deep-Sleep (>2h Ruhe) - 3x strengere Schwellwerte
- ✅ Flow-Konsistenz - 3 Messungen erforderlich
- 🤖 Auto-Kalibrierung - Lernt automatisch!

## Brauchst du

- DS18B20 Temperatursensor in der Wasserleitung
- Smart Meter Wasserzähler (z.B. Hydrus)
- Home Assistant 2024.1.0+

## Installation

1. HACS → Integrations → Custom Repository hinzufügen
2. Nach **Wasser-Residuum** suchen → Installieren
3. HA neu starten
4. Integration hinzufügen → Sensor & Zähler wählen
5. **Fertig!** Auto-Kalibrierung läuft automatisch

## Wichtigste Sensoren

- **`sensor.wasser_residuum_residuum`** → **0-9.9999L** 🎯
- `sensor.wasser_residuum_last_flow` → Durchfluss
- `sensor.wasser_residuum_night_mode` → Nacht-Status
- `sensor.wasser_residuum_k_active` → K-Faktoren (lernt automatisch!)

## Dashboard

```yaml
type: gauge
entity: sensor.wasser_residuum_residuum
min: 0
max: 10
name: Liter bis Tick
needle: true
```

---

**Hinweis**: Hobby-Projekt. Für Abrechnungen nur geeichte Zähler!
