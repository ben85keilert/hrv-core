# Mehrgerätebetrieb: mehrere Sensoren in einer Sitzung

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Mehrere Geräte zeichnen gleichzeitig in **dieselbe** Sitzung — mit einem
gemeinsamen Zeit-Nullpunkt. Gebaut für den Abgleich eines Zusatzgeräts gegen den
Polar H10 (→ [`verity_sense/messprotokoll.md`](verity_sense/messprotokoll.md));
auf demselben Weg kommen später weitere Vitalsensoren dazu.

Das **Hauptgerät** (★) speist Livechart-Achse, Kennzahlen und Analyse — im
Normalfall der H10. Alle weiteren sind **Begleiter**.

Code: `src/praxislab/sensors/polar_h10/widget.py` (`geraet_hinzufuegen`,
`_BegleiterRelay`, `_on_begleiter_*`) · `devices/sitzung.py` ·
`devices/pairing_dialog.py` · Tests `tests/test_mehrgeraete.py`,
`tests/test_kopplung.py`

Gerätekatalog und Profile → [`geraete.md`](geraete.md)

---

## Verbinden

Steht schon ein Hauptgerät, wird der **Hauptknopf jeder anderen Zeile zu
„＋ Zusätzlich"** — er nimmt das Gerät dazu, das Hauptgerät bleibt verbunden.
„Stattdessen verbinden (ersetzt das Hauptgerät)" liegt dann im Menü ⋮. Die
Zeile des Hauptgeräts trägt „★ Hauptgerät", ein Begleiter „✓ zusätzlich
verbunden"; ob der Verbindungsaufbau klappt, zeigt der Chip in der Geräteleiste
(„verbindet… / Fehler"). Lehnt das Widget ab, steht der Grund im Dialog-Log.

Vorher war „Verbinden" der naheliegende Knopf — und der ruft `connect_to` auf
dem Worker des Hauptgeräts, ersetzt es also. Der Weg über ⋮ brach zudem an
einem Methodenaufruf ab, den es nicht gab (`g.zuletzt_benutzt()`): über die
Oberfläche ließ sich nie ein zweites Gerät dazunehmen.

Ein Gerät **während** einer laufenden Aufnahme dazuzunehmen ist bewusst gesperrt: sein Strom hätte einen anderen Anfang als
alle übrigen, und die Sitzungsdatei behauptete einen gemeinsamen Nullpunkt, den
es nie gab.

Ein **Autoconnect gibt es nicht und ist nicht vorgesehen.** Verbunden wird von
Hand.

## Ein Worker je Gerät

Jedes Gerät bekommt einen eigenen `BleakWorker` mit eigenem asyncio-Loop. Der
Gerätebezug entsteht über ein `_BegleiterRelay` (QObject im GUI-Thread, hält die
Adresse) — **keine Signatur ändert sich**, und `VirtualPolarWorker` bleibt ein
gültiger Ersatz.

⚠ **Nie eine Lambda als Slot eines Worker-Signals.** Genau so war es zuerst
gebaut: die Lambda hat kein Empfänger-QObject, Qt ruft sie direkt im
Worker-Thread auf. Dort schrieben die Handler in Puffer, die der Render-Tick
gleichzeitig liest, und `_on_begleiter_batterie` baute Widgets. `cleanup()` und
„Trennen" stoppen jetzt auch die Begleit-Worker.

Der ursprüngliche Entwurf sah stattdessen einen gemeinsamen `BleHub` mit je
einer `BleConnection` pro Gerät vor. Dagegen sprach die Praxis: der
Verbindungscode ist rund 900 Zeilen und am H10 erprobt; ihn für mehrere
Verbindungen umzubauen wäre der riskanteste denkbare Eingriff in den
Live-Aufnahmepfad gewesen. Ein leerlaufender asyncio-Loop kostet bei zwei bis
drei Geräten praktisch nichts.

## Gemeinsame Zeitachse

Sie entsteht **ohne Synchronisation**: alle Pakete stammen aus demselben
Prozess und derselben `time.monotonic()`-Uhr, und `t_wall_s` ist die Differenz
zu **einem** gemeinsamen `_record_start_monotonic`. Die Herzuhr `t_s` bleibt je
Gerät — an ihrem Auseinanderlaufen mit `t_wall_s` hängt die Lückenerkennung.

## Zeitrichtiges X für Begleiter

Die X-Achse des Livecharts zählt die Schläge des **Hauptgeräts**. Ein Begleiter
bekam früher schlicht den aktuellen Zählerstand — ein PPI-Bündel (fünf Schläge,
im selben Moment zugestellt) landete fünfmal auf demselben X, die History
überschreibt gleiche X, übrig blieb ein Schlag am falschen Ort. Jetzt führt das
Hauptgerät eine Spur `(t_capture, x)`; `_begleiter_x` hängt jeden Begleiter-
Schlag über seinen **Zeitpunkt** ein (gebrochene X, auch links vom Rand). Beim
Verbinden werden die Intervallkurve und die Herzfrequenz des Begleiters
angelegt — RR des Gurts und PPI des Armbands liegen schlagweise übereinander.

**Welcher Zeitpunkt** (seit 2026-10-12): Bei Geräten mit `pmd_ppi` nicht die aus
der Paketankunft zurückgerechnete Zeit — Pakete kommen mit 0–1,3 s Streuung an,
und so lag der erste Schlag eines Pakets regelmäßig *vor* dem letzten des
vorigen; die Verity-Kurve lief auf der X-Achse zurück. Stattdessen führt jeder
Begleiter live eine `LiveKontinuitaetsuhr` (`devices/zeitachse.py`): Anker =
Minimum von (Ankunft − Intervallsumme) über die letzten 60 Pakete, Schlagzeit =
Summe + Anker, streng steigend. `_on_begleiter_ppi_paket` rechnet die Zeiten
des Pakets, `_on_begleiter_hr` holt sie der Reihe nach ab (passt die
Intervallfolge nicht, gilt die Ankunft). Zwei Wächter obendrauf: die Spur des
Hauptgeräts bleibt monoton, und ein Begleiter-X ist nie kleiner als sein
Vorgänger. **Nur Anzeige** — `t_wall_s` in der Datei bleibt die Ankunftsachse.

## Kurvenmanager im Mehrgerätebetrieb

Liegen Kurven von mehr als einem Gerät in der Liste, bekommt **jedes Gerät seine
eigene Liste unter einer Kopfzeile** („★ Polar H10 · EKG (5)", „Polar Sense · PPG
(5)") — Hauptgerät zuerst; die Reihenfolge innerhalb eines Geräts bleibt, wie man
sie gelegt hat, und ▲/▼ verschiebt nur innerhalb dieser Liste. Bis zu **zehn
Kurven** lassen sich einblenden (`LiveCurvesPanel.MAX_CURVES` =
`PolarH10Widget.MAX_SLOTS`); der Kurvenbereich scrollt. ⚠ Die Kacheln haben dafür
eine feste Wunschhöhe — ohne sie drückte die Scrollfläche zehn Kacheln in die
sichtbare Höhe zusammen, statt zu scrollen.

Sind mehrere Geräte verbunden, zeigt das Hinzufügen-Formular eine **Gerätewahl**.
Jedes Gerät bietet an, was es liefern kann, in seiner eigenen Sprache: am Gurt
„RR Gerät", am optischen Sensor „PPI Gerät" / „BPM aus PPI" / „Ø PPI"
(`metric_label(key, quelle)`, Quelle = `intervall_quelle` des Profils; die Spec
trägt sie als `geraet_quelle`). Ein EKG gibt es nur, wo das Profil `hat_ekg`
sagt — das regelt wie bisher der EKG-Bereich, nicht die Kurvenliste.

Begleiter können **Gerätewerte und alle je Schlag fensterbaren Kennzahlen**
zeichnen (RMSSD, SDNN, pNN50, Frequenzbänder, SD1/SD2 …) — gerechnet aus ihrem
*eigenen* Intervallstrom über ihre eigene Herzuhr
(`_begleiter_kurven_erweitern`, derselbe Rechenweg wie `_kurven_live_erweitern`).
Nicht angeboten werden DFA α1, Sample Entropy, Atemfrequenz und RSA: sie
entstehen in Hintergrundrechnungen, die nur der Hauptstrom speist
(`live_curves_panel.BEGLEITER_METRIKEN`). Der „Ber."-Neuaufbau gilt nur für
Kurven des Hauptgeräts.

Das **Aufnahmefenster** (Anzeigemodus „Analyse") hing früher allein am Worker
des Hauptgeräts — ein zweites Gerät zeichnete auf, war dort aber unsichtbar.
Sein Mini-Chart läuft jetzt auf einer Zeitachse (60-s-Fenster) mit einer Kurve
je Gerät samt Legende; RR-lose Lebenszeichen eines optischen Hauptgeräts zählen
dort nicht mehr als Ausreißer.

## Geräteleiste

Über dem Chart erscheint — nur bei mehr als einem Gerät — je Gerät ein Chip mit
Name, Akku und einem Schalter „nimmt auf". Der Schalter nimmt ein Gerät
**während** der Aufnahme heraus und wieder hinein; der Strom bekommt dabei eine
Lücke, die die vorhandene Lückenmaschinerie ohnehin behandelt. Fällt ein Gerät
aus, passiert dasselbe von selbst — Watchdog und Reconnect arbeiten je
Verbindung, die Sitzung läuft weiter. Das Hauptgerät ist mit ★ markiert; es
speist die Kennzahlen und die Analyse.

## Live-Kurven je Gerät

Die Kurvenspec trägt drei Felder dafür: `geraet` (Adresse, leer = Hauptgerät),
`geraet_kurz` (Kürzel für die Beschriftung) und `geraet_quelle`
(Intervallquelle, steuert „RR“ ↔ „PPI“ in der Beschriftung). Der Chart holt die Punkte
eines Begleitgeräts unter dem Schlüssel `<adresse>::<metrik>` aus derselben
`_metric_history` — Achsentitel, Y-Vorgaben und Crosshair hängen weiterhin an
der reinen Metrik. Beim Verbinden werden die Intervallkurve und die
Herzfrequenz des neuen Geräts angelegt; mehr fügt man über die Gerätewahl im
Kurvenmanager selbst hinzu. Im ⋮-Menü stehen dann „Nach Gerät
sortieren" und „Nach Gerät gruppieren". `MAX_SLOTS` ist von 6 auf 10 gestiegen;
die Serien werden weiterhin ausschließlich beim Aufbau angelegt.

## Ablage

```
Messungen/
  PolarH10/     sensor_2026-08-06_101500.json  + _ecg.json
  VeritySense/  sensor_2026-08-06_101500.json  + _ppg.json
  Sitzungen/    sitzung_2026-08-06_101500.json
```

Jedes Gerät schreibt **seine gewohnte `raw-v1`** in seinen Profilordner, unter
demselben Dateinamen. Eine kleine `sitzung-v1` klammert sie und steht in jeder
Messdatei als `sitzung_id`. Der Gewinn: die gesamte Analysekette — Workbench,
Korrektur, Sidecar, Smart-Cache, Vergleich, Verlauf — arbeitet **ohne eine
einzige Änderung** weiter, und eine Aufnahme mit einem Gerät ist byteweise wie
zuvor.

Die Sitzungsdatei entsteht **nur**, wenn wirklich mehrere Geräte Daten
geliefert haben. Ein verbundenes, aber stummes Gerät erzwingt keine.

## Im Workbench

Gehört die offene Messung zu einer Sitzung, erscheint in der Werkzeugleiste
**◫ Sitzung (n)**; dahinter liegen die Geschwisterströme mit Gerätename und
Modalitätskürzel. Jeder Strom bleibt eine eigenständige Messung mit eigener
Korrektur und eigenem Sidecar — hier wird nur zwischen ihnen gewechselt.

---

## Was noch offen ist

- **Gemeinsame Darstellung zweier Ströme in einem Analysechart** (nicht nur
  Wechseln). Dafür müsste die Overlay-Maschinerie fremde Dateien annehmen.
- **DFA α1, Sample Entropy, Atemfrequenz und RSA für Begleiter** — ihre
  Hintergrundrechnungen speist bisher nur der Hauptstrom.
