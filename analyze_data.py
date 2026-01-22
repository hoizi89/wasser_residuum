"""
Analyse der ADXL345 Vibrationsdaten
Vergleicht Wasser AUS vs Wasser EIN
"""
import re
import statistics

def parse_data(filename):
    """Parst die Log-Datei und extrahiert X, Y, Z, Mag Werte"""
    data = {'x': [], 'y': [], 'z': [], 'mag': []}

    with open(filename, 'r') as f:
        for line in f:
            # Format: [timestamp][W][DATA:xxx]: X,Y,Z,Mag
            match = re.search(r'DATA:\d+\]: ([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)', line)
            if match:
                data['x'].append(float(match.group(1)))
                data['y'].append(float(match.group(2)))
                data['z'].append(float(match.group(3)))
                data['mag'].append(float(match.group(4)))

    return data

def analyze(data, name):
    """Berechnet Statistiken für die Daten"""
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    print(f"  Anzahl Samples: {len(data['mag'])}")

    for axis in ['x', 'y', 'z', 'mag']:
        values = data[axis]
        if len(values) > 1:
            mean = statistics.mean(values)
            std = statistics.stdev(values)
            min_v = min(values)
            max_v = max(values)
            variance = statistics.variance(values)

            print(f"\n  {axis.upper():3}: Mean={mean:.4f}  Std={std:.4f}  Min={min_v:.4f}  Max={max_v:.4f}  Range={max_v-min_v:.4f}")

def compare(data_off, data_on):
    """Vergleicht die beiden Datensätze"""
    print(f"\n{'='*50}")
    print(f"  VERGLEICH: Unterschiede")
    print(f"{'='*50}")

    for axis in ['x', 'y', 'z', 'mag']:
        if len(data_off[axis]) > 1 and len(data_on[axis]) > 1:
            mean_off = statistics.mean(data_off[axis])
            mean_on = statistics.mean(data_on[axis])
            std_off = statistics.stdev(data_off[axis])
            std_on = statistics.stdev(data_on[axis])

            delta_mean = mean_on - mean_off
            delta_std = std_on - std_off

            # Prozentuale Änderung der Standardabweichung
            if std_off > 0:
                pct_change = ((std_on - std_off) / std_off) * 100
            else:
                pct_change = 0

            print(f"\n  {axis.upper():3}:")
            print(f"      Mean:  AUS={mean_off:.4f}  EIN={mean_on:.4f}  Delta={delta_mean:+.4f}")
            print(f"      Std:   AUS={std_off:.4f}  EIN={std_on:.4f}  Delta={delta_std:+.4f} ({pct_change:+.1f}%)")

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  ADXL345 Datenanalyse")
    print("="*50)

    # Daten laden
    try:
        data_off = parse_data("D:/ProjektePrivat/wasserAus.csv")
        data_on = parse_data("D:/ProjektePrivat/wasserEin.csv")

        # Einzelne Analysen
        analyze(data_off, "WASSER AUS")
        analyze(data_on, "WASSER EIN")

        # Vergleich
        compare(data_off, data_on)

        print("\n" + "="*50)
        print("  FAZIT")
        print("="*50)

        # Berechne ob signifikanter Unterschied
        if len(data_off['mag']) > 1 and len(data_on['mag']) > 1:
            std_off = statistics.stdev(data_off['mag'])
            std_on = statistics.stdev(data_on['mag'])
            mean_off = statistics.mean(data_off['mag'])
            mean_on = statistics.mean(data_on['mag'])

            # Effektgröße (Cohen's d)
            pooled_std = ((std_off**2 + std_on**2) / 2) ** 0.5
            if pooled_std > 0:
                cohens_d = abs(mean_on - mean_off) / pooled_std
            else:
                cohens_d = 0

            print(f"\n  Cohen's d (Effektgröße): {cohens_d:.3f}")
            if cohens_d < 0.2:
                print("  → Kein messbarer Unterschied (d < 0.2)")
            elif cohens_d < 0.5:
                print("  → Kleiner Unterschied (0.2 < d < 0.5)")
            elif cohens_d < 0.8:
                print("  → Mittlerer Unterschied (0.5 < d < 0.8)")
            else:
                print("  → Großer Unterschied (d > 0.8)")

            std_ratio = std_on / std_off if std_off > 0 else 1
            print(f"\n  Std-Verhältnis (EIN/AUS): {std_ratio:.3f}")
            if std_ratio > 1.2:
                print("  → Wasser EIN hat MEHR Varianz (+20%)")
            elif std_ratio < 0.8:
                print("  → Wasser EIN hat WENIGER Varianz (-20%)")
            else:
                print("  → Kein signifikanter Unterschied in der Varianz")

    except FileNotFoundError as e:
        print(f"Fehler: Datei nicht gefunden - {e}")
    except Exception as e:
        print(f"Fehler: {e}")
