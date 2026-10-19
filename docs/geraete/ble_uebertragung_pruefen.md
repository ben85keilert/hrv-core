# BLE-Übertragung prüfen

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Für **jedes neue Gerät** — und nach jeder Änderung am Empfangspfad — gibt es
eine wiederholbare Prüfung in vier Ebenen: kommen die Datenblöcke sauber, passen
die Zeitstempel, stimmt die Rechnung, und *misst* das Gerät richtig? Referenz für
die letzte Frage ist der **Polar H10**.

Code: `src/praxislab/sensors/devices/rohlog.py` (Mitschnitt) ·
`devices/pruefbericht.py` (Auswertung) · `tools/ble_pruefbericht.py`
(Kommandozeile) · Tests `tests/test_ble_pruefbericht.py`

## Ablauf

```bash
PRAXIS_BLE_ROHLOG=1 .venv/bin/python main.py        # Rohmitschnitt einschalten
```

1. Für den Goldstandard: **H10 als Hauptgerät** verbinden, das Prüfgerät
   „＋ Zusätzlich" (→ [`mehrgeraetebetrieb.md`](mehrgeraetebetrieb.md)).
2. 5 min ruhig sitzend aufzeichnen, speichern.
3. Die Messdateien nach `Logs/ble_pruefung/` kopieren — **je Gerät ein
   Unterordner**, weil beide Dateien gleich heißen (`PolarH10/`, `VeritySense/`).
   `Logs/` ist von Git ignoriert: dort landet nichts in einem Commit, und
   niemand muss in Patientenordnern nach Pfaden suchen.
4. `tools/ble_pruefbericht.py` — ohne Argumente. Das Werkzeug nimmt die jüngste
   Aufnahme (Zeitstempel im Dateinamen), behandelt das optische Gerät als
   Prüfling und das EKG als Referenz und **findet die passenden Mitschnitte
   selbst** (Profil + Aufnahmezeit, im Mitschnitt-Ordner der App). Ausdrücklich
   geht es auch: `--ordner`, `--neueste --messung <datei>`, `--referenz <datei>`.

## Rohmitschnitt

`devices/rohlog.py`: der Worker schreibt jedes empfangene
Paket roh (Hex + `time.monotonic()` der Ankunft) nach
`<daten-root>/config/hosts/<rechner>/ble_roh/*.jsonl`, dazu seine
Konsolenmeldungen als Ereignisse. Dieselben Pakete laufen unverändert durch die
App — geprüft wird die echte Kette, kein Nachbau. Ohne die Umgebungsvariable
entsteht nichts, der Live-Pfad ist der alte.

## Die vier Ebenen

| Ebene | Frage | Prüfpunkte |
|---|---|---|
| **A Datenblöcke** | Sendet das Gerät, was die Spezifikation sagt? | Rahmenlänge (Vielfaches von 6), Frame-Typ, Kopf-Zeitstempel, Blocker-/Hautkontakt-Anteil, Fehlerschätzung, HF-Byte ≈ 60000/Intervall (entlarvt ein verschobenes Byte-Layout), Doppelspeisung, Steuerantworten |
| **B Zeitstempel** | Kommt alles an, und rechtzeitig? | Residuum je Paket (ΔAnkunft − Σ Intervalle), verlorene Intervalle über die laufende Zeitbilanz, Drift in ms/min, Bündel-Latenz, Zeitverlust der Herzuhr durch Blocker |
| **C Kette** | Macht die App daraus nichts Falsches? | `ppi_pakete` der Datei deckt sich Paket für Paket mit dem Mitschnitt (samt verworfener Intervalle), Schlagfolge der Messdatei steht exakt im Mitschnitt, `t_wall_s` deckt sich mit der Paketankunft, `tw_src`, Herzuhr `t_s`, RMSSD/SDNN der App gegen unabhängige Formeln |
| **D Goldstandard** | *Misst* das Gerät richtig? | gleichzeitige Aufnahme mit dem H10 (Mehrgerätebetrieb): Zeitversatz per Kreuzkorrelation, schlagweise Zuordnung, Bland-Altman, Korrelation, Drift der Zeitachse, RMSSD/SDNN nebeneinander |

## Zwei Zeitachsen

Ein optisches Gerät stellt gebündelt *und verzögert* zu —
die Paketankunft ist nicht der Zeitpunkt des letzten Schlags (erste
Verity-Messung: zwei Pakete 11 ms nacheinander, dazwischen ein 966-ms-Schlag).
Der Bericht bildet deshalb eine zweite Achse, die **Kontinuitätsuhr**: die
laufende Summe aller Intervalle ist die Herzuhr des Geräts; ihr Versatz zur
Rechneruhr ist der *kleinste* beobachtete Wert von (Ankunft − Summe), denn ein
Schlag kann nie nach seiner Zustellung liegen. Nach Paketverlust setzt sie neu
auf. B meldet, ob die Ankunft als Schlagzeitpunkt taugt; D nennt den Versatz
je Schlag auf beiden Achsen — mit Referenzmitschnitt auf der Kontinuitätsuhr
**beider** Geräte. Maßgeblich ist die **lokale** Genauigkeit (90. Perzentil der
Änderung des Versatzes von Schlag zu Schlag, dazu die Zahl der Sprünge
> 100 ms): das spüren Frequenzanalyse und Lückenerkennung. Die Gesamtstreuung
(SD, robust/MAD) steht daneben, taugt aber nicht zum Vergleich — wenige Stufen
an verworfenen Intervallen bestimmen sie und verdecken den Gewinn. Die *Intervalle* — und
damit RMSSD/SDNN — sind von der Zustellverzögerung nicht betroffen, wohl aber
`t_wall_s`, Lückenerkennung und jeder Zeitvergleich.

## Zuordnung über die Intervallfolge

Abschnitt D ordnet die Schläge **nicht über die Zeitstempel** zu. Beide Achsen
sind Ankunftszeiten (Gurt 1-s-Raster, Armband 5-s-Raster mit ~5 s Latenz); je
Schlag schwankt der Versatz um mehr als einen halben Herzschlag, und ein
Nachbarschlag liegt dann näher als der richtige — so fanden in der ersten
Doppelmessung nur 65 % einen Partner. `ordne_zu` sucht stattdessen die Zuordnung
mit der kleinsten Summe |Δ Intervall| (das Prüfgerät liefert die Folge der
Referenz mit Auslassungen); die Zeit dient nur als grobes Band (± 4 s um den
per Kreuzkorrelation geschätzten Versatz). Nicht 100 % eindeutig: fällt ein
Intervall zwischen zwei fast gleich langen Nachbarn aus, ist nicht entscheidbar,
welcher fehlt — für die Kennzahlen belanglos.

Ergebnisse am Verity Sense → [`verity_sense/messprotokoll.md`](verity_sense/messprotokoll.md).

Die Kontinuitätsuhr braucht **alle** Intervalle, auch die verworfenen — in
`messungen` fehlen sie, ihre Summe hat Löcher. Neuere Messdateien tragen sie im
Block `ppi_pakete`; der Bericht rechnet dann allein aus der Datei, mit derselben
Funktion wie die Analyse (`devices/zeitachse.py`). Nur für ältere Aufnahmen ohne
Block greift er dafür auf den Rohmitschnitt zurück.

## Was die Ebenen leisten

A bis C zeigen nur, dass nichts verloren geht oder verfälscht wird. Ob die
Intervalle *stimmen*, zeigt allein D. Dafür den H10 als Hauptgerät verbinden und
das Prüfgerät „zusätzlich verbinden"; der Bericht findet die Geschwisterdatei
über die Sitzung selbst (`--referenz` überschreibt das).

## Tests

`tests/test_ble_pruefbericht.py` schickt synthetische Pakete durch die
echten Worker-Callbacks und das echte `_on_hr_received` und verlangt, dass der
Bericht den sauberen Strom durchwinkt und jede eingebaute Störung findet
(Paketverlust, Blocker, Doppelspeisung, falsches Byte-Layout, veränderte Datei).
