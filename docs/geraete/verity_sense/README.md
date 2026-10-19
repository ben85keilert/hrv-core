# Polar Verity Sense — Zusatzgerät

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Der **Polar H10 ist das Standardgerät** der Sensorik und der Goldstandard, an
dem sich alles misst. Die gesamte übrige Sensor-Dokumentation beschreibt ihn.
Der **Verity Sense** (optisches Armband, PPI statt RR) ist ein **Zusatz** — und
so ist er hier dokumentiert: als **Abweichung vom H10**. Was hier nicht steht,
gilt wie beim H10.

Stand: 2026-09-19 · Status: **am Gerät in Betrieb genommen, Intervalle gegen den
H10 geprüft; Zeitachse noch in Arbeit**

## Ergebnis in Kürze

- **Die Intervalle sind brauchbar.** Im gleichzeitigen Abgleich gegen den H10
  (5 min Ruhe): 98 % der Schläge zugeordnet, Bias −0,3 ms, SD 8,8 ms,
  r = 0,980; RMSSD 33,2 gegen 30,2 ms, SDNN 44,6 gegen 44,1 ms.
- **Die Zeitachse ist die Schwäche.** Das Armband stellt alle ~5 s gebündelt und
  rund **5 s verzögert** zu; die Paketankunft ist nicht der Schlagzeitpunkt.
  Betroffen sind Lückenerkennung, Frequenzanalyse und Zeitvergleiche — **nicht**
  RMSSD/SDNN.
- **Es verwirft selbst Intervalle** (Blocker-Bit), in Ruhe 10–20 %. Fester Sitz
  am Oberarm und ein ruhiger Arm sind die halbe Messung.
- **Nur in Ruhe.** Polar selbst: PPI ist bei Aktivität nicht genau messbar. Bei
  der Arbeit (14.10.2026) verwarf das Armband 62 %, und die verworfenen
  Intervalle waren falsch, auch bei kleiner Fehlerschätzung. Im PPI-Betrieb
  friert es außerdem die Herzfrequenz bei Bewegung ein. Herstellerangaben mit
  Quellen: `verity_sense.md`, Abschnitt 4a.
- **Es verlangt eine Bluetooth-Kopplung.** Das Programm erledigt sie selbst
  (BlueZ-Agent für die Dauer des Verbindungsaufbaus).
- **Kein Rohsignal.** PPG kommt delta-komprimiert; ein Decoder fehlt. Ein EKG
  gibt es am Armband nicht.
- **Nicht alle Kennzahlen sind mit dem H10 vergleichbar:** RMSSD und SDNN ja;
  pNN50, DFA α1, RSA-Amplitude und Atemfrequenz nicht.

## Die Dokumente

| Datei | Inhalt |
| --- | --- |
| [`verity_sense.md`](verity_sense.md) | **Das Hauptdokument.** Gegenüberstellung H10 ↔ Verity Sense, Kopplung, Datenstrom, Zeitachse, Vergleichbarkeit der Kennzahlen, offene Punkte. Hier zuerst lesen. |
| [`messprotokoll.md`](messprotokoll.md) | Datierte Befunde am echten Gerät: Probelauf und Doppelmessungen gegen den H10 mit den Zahlen des Prüfberichts. Wächst mit jeder Messung. |

Verwandt: Gerätekatalog und Profilvertrag → [`../geraete.md`](../geraete.md) ·
beide Geräte gleichzeitig → [`../mehrgeraetebetrieb.md`](../mehrgeraetebetrieb.md) ·
Prüfmethode für jedes neue Gerät →
[`../ble_uebertragung_pruefen.md`](../ble_uebertragung_pruefen.md)
