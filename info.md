# Wasser-Residuum (ΔT→L Kalman)

Präzise Wasserverbrauchsmessung zwischen Zählerticks mittels thermischer Analyse und Kalman-Filter.

## Was macht diese Integration?

Misst den Wasserverbrauch in **Echtzeit** durch Temperaturüberwachung - ohne auf Zählerticks warten zu müssen!

### Prinzip
```
Wasserfluss → Temperaturabfall → dT/dt → Durchflussberechnung
```

## Features

✅ **Kalman-Filter**: Präzise Temperatur-Gradientenerkennung
✅ **Dual-K Interpolation**: Automatische Anpassung für warmes/kaltes Wasser
✅ **Auto-Kalibrierung**: Selbstlernend bei jedem 10L-Tick
✅ **Baseline-Korrektur**: Kompensiert natürliche Temperaturabkühlung
✅ **Hydrus-Fusion**: Korreliert mit physischen Zählerticks
✅ **Niedrige Latenz**: Echtzeit-Anzeige

## Voraussetzungen

- Temperatursensor in der Wasserleitung (z.B. DS18B20)
- Wasserzähler mit Smart Meter Auslesen (z.B. Hydrus)
- Home Assistant 2024.1.0+

## Konfiguration

Nach Installation über UI:
1. **Einstellungen** → **Geräte & Dienste**
2. **+ Integration hinzufügen**
3. **Wasser-Residuum** suchen
4. Temperatursensor und Wasserzähler auswählen

### Wichtige Parameter

- **K-Warm** (4.0): Umrechnungsfaktor bei warmer Leitung
- **K-Cold** (8.0): Umrechnungsfaktor bei kalter Leitung
- **T-Warm** (16°C): Referenztemperatur warm
- **T-Cold** (12°C): Referenztemperatur kalt

Diese werden durch Auto-Kalibrierung automatisch optimiert!

## Entitäten

Nach Setup verfügbar:
- `sensor.wasser_residuum_residuum` - Verbrauch seit letztem Tick (L)
- `sensor.wasser_residuum_last_flow` - Aktueller Durchfluss (L/min)
- `sensor.wasser_residuum_last_dt_dt` - Temperaturgradient (K/min)
- `number.wasser_residuum_k_warm` - Anpassbar
- `number.wasser_residuum_k_cold` - Anpassbar

## Quick Start Dashboard

```yaml
type: gauge
entity: sensor.wasser_residuum_residuum
min: 0
max: 10
name: Wasser bis Tick
needle: true
```

## Support

Für Fragen und Issues: [GitHub Repository](https://github.com/yourusername/wasser_residuum)

---

**Hinweis**: Experimentelles Projekt für Forschung und Hobby. Für Abrechnungszwecke nur geeichte Zähler verwenden!
