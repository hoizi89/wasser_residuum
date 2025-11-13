# Wasser-Residuum (ΔT→L Kalman)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/yourusername/wasser_residuum.svg)](https://github.com/yourusername/wasser_residuum/releases)
[![License](https://img.shields.io/github/license/yourusername/wasser_residuum.svg)](LICENSE)

Eine Home Assistant Integration zur präzisen Messung des Wasserverbrauchs zwischen Zählerticks mittels thermischer Analyse und Kalman-Filter.

## 🌟 Features

- **Kalman-Filter basierte Temperaturanalyse**: Präzise Erkennung von Temperaturgradienten zur Durchflusserkennung
- **Dual-K Interpolation**: Automatische Anpassung des Umrechnungsfaktors basierend auf Wassertemperatur (warm/kalt)
- **Auto-Kalibrierung**: Selbstlernende K-Faktoren bei jedem 10L-Tick des Hauptzählers
- **Baseline-Korrektur**: Kompensiert natürliche Temperaturabkühlung über 12h-Fenster
- **Hydrus-Fusion**: Korreliert thermische Messungen mit physischen Zählerticks für höhere Genauigkeit
- **Niedrige Latenz**: Echtzeit-Verbrauchsanzeige ohne Wartezeit auf Zählerticks
- **Robust**: MAD-basiertes Outlier-Filtering und adaptive Schwellwerte

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

### Über die UI

1. Gehe zu **Einstellungen** → **Geräte & Dienste**
2. Klicke auf **+ Integration hinzufügen**
3. Suche nach **Wasser-Residuum**
4. Folge dem Konfigurationsassistenten:
   - **Name**: Ein beschreibender Name (z.B. "Küchen-Wasser")
   - **Temperatursensor**: Wähle deinen DS18B20 Sensor
   - **Wasserzähler**: Wähle deinen Hydrus/Hauptzähler
   - **Einheit**: m³ oder L (je nach Zähler)

### Erweiterte Optionen

Nach der Einrichtung kannst du die Integration über **Optionen** konfigurieren:

| Parameter | Standard | Bereich | Beschreibung |
|-----------|----------|---------|--------------|
| **K-Warm** | 4.0 | 0.5 - 10.0 | Umrechnungsfaktor bei warmer Leitung (≥16°C): `L/min = K × ΔT` |
| **K-Cold** | 8.0 | 0.5 - 10.0 | Umrechnungsfaktor bei kalter Leitung (≤12°C) |
| **T-Warm** | 16.0°C | 5.0 - 35.0 | Referenztemperatur für warme Leitung |
| **T-Cold** | 12.0°C | 5.0 - 35.0 | Referenztemperatur für kalte Leitung |
| **Clip** | 2.5 K/min | 0.5 - 5.0 | Maximaler Gradient (verhindert Überschwingen) |
| **Max. Residuum** | 10.0 L | 5.0 - 50.0 | Maximales Residuum (Plausibilitätsgrenze) |

## 📊 Entitäten

Die Integration erstellt folgende Entitäten:

### Sensoren
- **Residuum (L)**: Geschätzter Verbrauch seit letztem Zählertick
- **Volume (L)**: Absolutes internes Volumen
- **Offset (L)**: Referenzpunkt des letzten Zählerticks
- **Unsicherheit (L)**: Kumulative Messunsicherheit
- **Letzter Flow (L/min)**: Aktueller Durchfluss (thermisch)
- **Letztes dT/dt (K/min)**: Temperatur-Gradient (baseline-korrigiert)
- **K-Effektiv**: Aktuell verwendeter K-Faktor

### Numbers (anpassbar)
- **K-Warm**: K-Faktor für warme Leitung
- **K-Cold**: K-Faktor für kalte Leitung

### Buttons
- **Reset Volume**: Setzt Residuum auf 0 zurück (bei Störungen)

## 🎯 Funktionsweise

### 1. Thermische Durchflusserkennung
```
Wasserfluss → Temperaturabfall → dT/dt < 0 → Flow erkannt
```

Die Integration nutzt einen **Kalman-Filter**, um Temperaturgradienten präzise zu schätzen:
- Predict-Phase: Extrapoliert Temperatur basierend auf bisheriger Dynamik
- Update-Phase: Korrigiert Schätzung mit neuer Messung
- Ergebnis: Gefilterte Temperatur `T` und Gradient `dT/dt`

### 2. Baseline-Korrektur (NEU in v0.2.0)
```
Baseline = 5. Perzentil der letzten 12h
Temperatur (relativ) = T - Baseline
```

Kompensiert natürliche Abkühlung über Nacht. Nur Gradienten **relativ zur Baseline** werden als Flow interpretiert.

### 3. Dual-K Interpolation
```
K(T) = K_cold    wenn T ≤ T_cold
K(T) = K_warm    wenn T ≥ T_warm
K(T) = linear interpoliert    dazwischen
```

**Warum?** Warmes Wasser hat höhere Wärmekapazität und Strömungsviskosität → anderer K-Faktor.

### 4. Auto-Kalibrierung bei 10L-Tick
```
Hydrus: +10L → K_neu = K_alt × (10.0 / Thermal_gemessen)
```

Gleicht systematische Fehler automatisch aus. Begrenzt auf ±30% pro Tick (Stabilitätsschutz).

### 5. Hydrus-Fusion
```
Zeit seit letztem Tick | Schwellwert
0-5 min               | -0.001 K/min (hohe Konfidenz)
5-30 min              | -0.05 K/min  (mittlere Konfidenz)
>30 min               | -0.15 K/min  (niedrige Konfidenz)
```

**Idee**: Kurz nach einem Zählertick ist thermische Messung besonders zuverlässig (Wasser floss kürzlich).

## 📈 Beispiel-Dashboard

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Wasser-Residuum
    entities:
      - entity: sensor.wasser_residuum_residuum
        name: Residuum
        icon: mdi:water
      - entity: sensor.wasser_residuum_last_flow
        name: Durchfluss
        icon: mdi:water-pump
      - entity: sensor.wasser_residuum_last_dt_dt
        name: Temperaturgradient
        icon: mdi:thermometer

  - type: history-graph
    title: Durchfluss Historie
    entities:
      - entity: sensor.wasser_residuum_last_flow
    hours_to_show: 2

  - type: gauge
    entity: sensor.wasser_residuum_residuum
    min: 0
    max: 10
    name: Residuum bis Tick
    needle: true
```

## 🔍 Troubleshooting

### Problem: Residuum steigt bei Stillstand

**Ursache**: Natürliche Temperaturabkühlung wird als Flow interpretiert.

**Lösung**:
- Warte 12h, damit Baseline-Korrektur greift
- Erhöhe `T_cold` (z.B. auf 13°C), damit mehr Gradienten als "kalt = normal" klassifiziert werden

### Problem: Auto-Kalibrierung schießt hoch

**Ursache**: Thermischer Flow zu niedrig (z.B. durch schlechten Sensorpositionierung).

**Lösung**:
- Überprüfe Sensor-Position (muss im direkten Wasserkontakt sein)
- Setze `K-Cold` manuell auf realistischen Wert (6.0 - 9.0)
- Logs prüfen: `custom_components.wasser_residuum`

### Problem: Flow wird nicht erkannt

**Ursache**: Schwellwerte zu streng oder Sensor zu träge.

**Lösung**:
- Reduziere `Clip` (z.B. auf 1.5 K/min)
- Prüfe Sensor-Aktualisierungsrate (sollte >1/min sein)
- Erhöhe `K-Warm` (mehr Sensitivität bei warmer Leitung)

## 📝 Logs

Aktiviere Debug-Logging für detaillierte Ausgaben:

```yaml
logger:
  default: info
  logs:
    custom_components.wasser_residuum: debug
```

## 🤝 Beitragen

Contributions sind willkommen! Bitte öffne ein Issue oder Pull Request auf GitHub.

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE)

## 🙏 Credits

Entwickelt mit ❤️ für die Home Assistant Community.

Basiert auf:
- Kalman-Filter Theorie (Rudolf E. Kalman, 1960)
- Thermischer Durchflussmessung (Prinzip: Heiß-/Kaltdrahtanemometrie)
- Home Assistant Integration Best Practices

---

**Hinweis**: Diese Integration ist ein experimentelles Projekt zur Forschung und Hobby-Nutzung. Für offizielle Abrechnungszwecke verwende ausschließlich geeichte Wasserzähler.
