# Polar Verity Sense — Abweichungen vom Polar H10

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Stand: 2026-10-14 · Status: **in Betrieb, Intervalle und Zeitachse gegen den H10 geprüft;
Herstellerangaben zu PPI und ein Befund in Bewegung ergänzt**

Dieses Dokument setzt die H10-Dokumentation voraus
([`../sensor_hrv.md`](../../../../praxis_gui/docs/sensor_hrv.md), `theory/`) und beschreibt **nur, was am
Armband anders ist**. Der H10 bleibt Standard und Goldstandard.

Code: Profil `VERITY_SENSE` in `src/praxislab/sensors/devices/profiles.py` ·
Protokoll `devices/pmd.py` · Kopplung `devices/bluez_agent.py`

---

## 1. Fazit vorweg

Das Armband liefert **Puls-zu-Puls-Intervalle (PPI)**, die in dieselbe Kette
laufen wie die RR-Intervalle des Gurts. Für die Zeitbereichs-HRV in Ruhe
(RMSSD, SDNN) sind sie dem H10 praktisch gleichwertig. Alles, was **genaue
Zeitpunkte** braucht, ist am Armband unsicherer (± 0,5 s), und was das Armband
an Intervallen verwirft, fehlt.

Wofür es taugt: bequeme Ruhemessung ohne Gurt, Verlaufsbeobachtung von
RMSSD/SDNN. Wofür nicht: EKG, Atem-/RSA-Analyse, Messungen unter Bewegung,
schlaggenaue Ereignisse.

**Polar sagt dasselbe:** Puls-zu-Puls-Intervalle sind viel störanfälliger als
RR-Intervalle und lassen sich bei Aktivität **nicht genau messen, nur in
völliger Ruhe** ([PPIData.md][polar-ppi]). Gemessen am 14.10.2026 (73 min bei
der Arbeit, → [`messprotokoll.md`](messprotokoll.md), Abschnitt 5): Das Armband
verwarf 62 % der Intervalle, und die verworfenen sind falsch, auch wo seine
Fehlerschätzung klein ist. Aus Paaren verworfener Nachbarn ergab sich RMSSD
98 ms, aus sauberen Paaren 30 ms.

---

## 2. Gegenüberstellung

| | **Polar H10 (Standard)** | **Verity Sense (Abweichung)** |
|---|---|---|
| Messprinzip | elektrisch (EKG), Brustgurt | optisch (PPG), Oberarm |
| Intervalle | RR, `intervall_quelle = ekg_rr` | PPI, `intervall_quelle = ppg_ppi` |
| Herkunft der Intervalle | HR-Profil `0x2A37` | PMD-Strom `0x03` — das HR-Profil trägt **keine** Intervalle |
| Paketstruktur | 1–2 RR je Paket, etwa jede Sekunde | ~5 PPI je Paket, etwa alle 5 s |
| Latenz | praktisch keine | ~5 s (Algorithmus), plus Bündelung |
| Anlauf | sofort bei Hautkontakt | ~25 s, bis die ersten Intervalle kommen |
| Zeitstempel | Paketankunft ≈ letzter Schlag (1-s-Raster) | Paketankunft **≠** letzter Schlag; PMD-Kopf-Zeitstempel ist 0 |
| Ausfall-Signal | `RR = 0` | **Blocker-Bit** je Intervall (Polar: Bewegung erkannt) + **Fehlerschätzung** in ms (Abschnitt 4a) |
| Herzfrequenzwert | laufend | im PPI-Betrieb nur alle 5 s aktualisiert und bei Bewegung **eingefroren** (Polar) |
| Hautkontakt-Angabe | – | je Intervall vorhanden, laut Polar **unzuverlässig** — nicht auswerten |
| Rohsignal | EKG 130 Hz (`_ecg.json`) | PPG delta-komprimiert — **kein Decoder**, kein Rohsignal |
| Bluetooth-Kopplung | nicht nötig | **Bonding nötig** (`kopplung_noetig`) |
| Watchdog, erstes Paket | 30 s | 45 s (`ersttelegramm_s`) |
| Hinweis „kein Signal" | Gurt anlegen und anfeuchten | Sitz des Armbands, kein Luftspalt |
| Ablage | `Messungen/PolarH10/` | `Messungen/VeritySense/` |
| Kurvenbeschriftung | „RR Gerät", „BPM aus RR" | „PPI Gerät", „BPM aus PPI", „Ø PPI" |
| Stand | erprobt | Intervalle am Gerät geprüft (→ [`messprotokoll.md`](messprotokoll.md)) |

Alles davon steuert das **Geräteprofil**, nicht der Gerätename
(→ [`../geraete.md`](../geraete.md), Abschnitt 3).

---

## 3. Verbindung und Kopplung

Der H10 verbindet ohne Kopplung. Das Armband schickt direkt nach dem Verbinden
eine Sicherheitsanfrage. Eine vom *Gerät* angestoßene Kopplung braucht unter
BlueZ einen **Agenten** zur Bestätigung; läuft keiner, steht im Journal

```
bluetoothd: src/device.c:new_auth() No agent available for request type 2
```

die Kopplung wird abgelehnt, und das Armband trennt wenige Sekunden nach
„PMD-Service verfügbar" — bei jedem Versuch. GNOME stellt seinen Agenten nur,
solange die Bluetooth-Einstellungen offen sind; deshalb klappte es genau dann.

Was das Programm tut (nur bei `kopplung_noetig`, der H10-Weg ist unberührt):

1. Für die Dauer des Verbindungsaufbaus meldet es einen eigenen **BlueZ-Agenten**
   an (`devices/bluez_agent.py`, über `dbus_fast`). Er bestätigt „Just Works"
   **ausschließlich für das Gerät, das gerade verbunden wird**, setzt
   „Vertrauen" und meldet sich danach wieder ab.
2. bleak verbindet mit `pair=True` (ruft `Pair` statt `Connect`).
3. Solange das Gerät ungekoppelt ist, entfällt der System-Connect-Fallback —
   er liefe in genau dasselbe Fehlerbild.

Das Profil muss dem Worker **vor** `connect_to()` bekannt sein
(`set_geraete_profil`). Diagnose bei Problemen:
`journalctl -u bluetooth --since "-1h"`.

---

## 4. Datenstrom

**PPI wird vom Worker gestartet** (`PPI_START_CMD`), nach jedem Connect und
Reconnect. Der Algorithmus im Gerät braucht rund 25 s Anlauf.

⚠ **RR-lose HF-Pakete sind am Armband nur Lebenszeichen.** Neben dem PPI-Strom
läuft der HF-Strom (`0x2A37`) im Sekundentakt **ohne Intervalle** weiter. Diese
Pakete stempeln den Watchdog und die BPM-Anzeige, erzeugen aber weder eine Zeile
in `messungen` noch einen Schritt auf der X-Achse „Messung". Gesteuert über die
Fähigkeit `pmd_ppi`; am H10 bleibt die `rr_ms = 0`-Zeile wie bisher.

⚠ **Blockierte Intervalle erreichen die HRV-Kette nicht.** Das Gerät kennzeichnet
unsichere Intervalle selbst; diese Angabe ist bei optischer Messung verlässlicher
als jede nachgelagerte Ausreißerheuristik. Ihre *Dauer* zählt trotzdem: die
Schlagzeitpunkte eines Pakets werden über **alle** Intervalle zurückgerechnet,
erst danach fallen die blockierten heraus.

⚠ **Bündelung.** Die Live-Kurve springt alle ~5 s um mehrere Punkte. Das ist
Geräteverhalten, kein Zeichenproblem — bewusst **kein** Ausspiel-Puffer, damit
die Anzeige so aktuell wie möglich bleibt. Labels und Frequenzkurven rechnen
einmal je Paket statt fünfmal hintereinander.

**Rohsignal:** „Rohsignal mitschreiben" startet am Armband keinen Strom. PPG
kommt delta-komprimiert (Frame-Typ-Bit 7); `pmd.parse_frame` verwirft solche
Rahmen, statt sie als Rohwerte zu lesen.

---

## 4a. Was Polar zu den Angaben je Intervall sagt

Zu jedem Intervall liefert das Armband drei Angaben; `ppi_pakete` speichert sie
unverändert (`fehler_ms`, `blocker`, `kontakt`). Polars Definitionen
([`PolarPpiData`][polar-kt], [PPIData.md][polar-ppi]):

| Angabe (Datei) | Polar SDK | Bedeutung laut Polar |
|---|---|---|
| `fehler_ms` | `errorEstimate` | **Fehlerschätzung**: erwarteter absoluter Fehler des Intervalls in ms. Unter 10 ms ist es „wahrscheinlich sehr genau“; über 30 ms deutet auf Bewegung oder zu lockeren Sitz |
| `blocker` | `blockerBit` | **Blocker-Bit**: ungültig, weil Bewegung (Beschleunigung) erkannt wurde, oder aus anderem Grund. Polar: verwerfen |
| `kontakt` | `skinContactStatus` | Hautkontakt — bei Verity Sense und OH1 laut Polar **unzuverlässig**; das Gerät kann sogar ungetragen eine Herzfrequenz melden |

Weitere Herstellerangaben zum PPI-Betrieb ([PolarVeritySense.md][polar-vs]):

- PPI ist ein **eigener Algorithmus**, getrennt von dem für die Herzfrequenz
  ohne PPI.
- Läuft PPI, kommt die Herzfrequenz nur **alle 5 s**, und bei Bewegung bleibt
  sie auf dem **letzten verlässlichen Wert** stehen.
- Die ersten Intervalle kommen nach **etwa 25 s** (deckt sich mit Abschnitt 4).
- Polar rät, bei mehreren Intervallen mit Blocker-Bit hintereinander um mehr
  Ruhe zu bitten.

**Herzfrequenz im Sport ist etwas anderes.** Ohne PPI misst das Armband mit
seinem gewöhnlichen, für Bewegung gemachten Algorithmus. Eine Studie (2025,
gegen den H10, 10-s-Mittel, Ruhe bis Intervalltraining) fand am Oberarm 95 %
der Werte innerhalb von ±6 Schlägen/min, am Unterarm −15 bis +13
([JMIR Cardio 2025][studie]). Für schlaggenaue Intervalle in Bewegung gilt das
nicht.

**Unsere Messwerte zur Fehlerschätzung:** In Ruhe lag sie im Median bei 6–7 ms
(Doppelmessungen 2 und 3), bei der Arbeit bei 9 ms für die behaltenen
Intervalle — aber zweigeteilt: 93 % bis 20 ms, 3,8 % über 50 ms, davon mehr als
die Hälfte über 120 ms (messprotokoll, Abschnitt 5).

---

## 5. Zeitachse

Beim H10 ist die Paketankunft ein guter Näherungswert für den letzten Schlag;
darauf beruht `t_wall_s` (→ [`../sensor_hrv.md`](../../../../praxis_gui/docs/sensor_hrv.md), Lückenmodell).
Am Armband gilt das nicht: es sendet in einem festen ~5-s-Takt, unabhängig vom
Herzzyklus, mit rund 5 s Algorithmus-Latenz. Der letzte Schlag eines Pakets ist
bei Ankunft 0 bis 1 s alt — zufällig.

| | bedeutet | am Armband |
|---|---|---|
| `t_s` (Herzuhr) | Summe der gültigen Intervalle | in sich genau, läuft aber um die Dauer der **verworfenen** Intervalle hinter der Rechneruhr her |
| `t_wall_s` | Paketankunft, frühere Schläge zurückgerechnet | streut gegen den H10 mit robust ~430 ms |
| `tw_src` | `m` gemessen / `r` zurückgerechnet | `m` heißt hier nur „letzter Schlag des Pakets", **nicht** „Schlagzeitpunkt" |

**Kontinuitätsuhr.** Die Summe *aller* gelieferten Intervalle (auch der
verworfenen) ist die Herzuhr des Geräts. Offen ist nur ihr Versatz zur
Rechneruhr — und für den gilt: ein Schlag kann nie *nach* seiner Zustellung
liegen. Der kleinste beobachtete Wert von (Ankunft − Summe) ist deshalb die beste
Schätzung; alles darüber war Wartezeit im Gerät. Weil Zustellverzögerung diesen
Wert nur **erhöhen** kann und ein Paketverlust ihn **dauerhaft** hebt, ist der
Anker eines Pakets das Minimum über die *folgenden* Pakete — ohne Schwelle, ohne
Abschnitte. Gemessen gegen den H10: von Schlag zu Schlag ändert sich der Versatz
auf der Kontinuitätsuhr um **~20 ms**, auf der Ankunftsachse um **~900 ms**
(90. Perzentil); über die ganze Messung bleiben einzelne Stufen von 0,2–0,4 s,
fast alle an Stellen mit verworfenen Intervallen.

(Eine erste Fassung suchte „dauerhafte Sprünge" mit einer Schwelle und kam auf
~195 ms: drei verzögerte Pakete hintereinander sahen für sie wie ein Verlust aus
— bei im Median 0,5 s Verzögerung passierte das ständig.)

**Live** (Mehrgerätebetrieb, Chart-X des Begleiters) läuft dieselbe Uhr ohne
Blick nach vorn: `LiveKontinuitaetsuhr` nimmt das Minimum über die letzten 60
Pakete und lässt die Schlagzeit nie zurückgehen (→
[`../mehrgeraetebetrieb.md`](../mehrgeraetebetrieb.md), „Zeitrichtiges X"). Die
Datei bekommt davon nichts; dort entsteht die Uhr erst in der Analyse.

**Was betroffen ist:** Lückenerkennung, Abdeckungsquote, Zeitachse der
Frequenzanalyse, Uhrzeit von Notizen, jeder Zeitvergleich zwischen Geräten.
**Was nicht betroffen ist:** die Intervalle selbst — RMSSD, SDNN, mittlere HF.

**Stand der Umsetzung.** `t_wall_s` / `tw_src` in `messungen` bleiben die
Ankunftsachse — bewusst: Notizen werden live darauf verankert, das Crash-Backup
muss dieselbe Achse tragen, und „beim Stoppen nur Rohdaten" gilt auch hier.
Stattdessen schreibt die Aufnahme die **Zutaten** mit: der Block `ppi_pakete`
enthält jedes Paket roh, samt verworfener Intervalle, Ankunftszeit und
Fehlerschätzung (Feldreferenz → [`../sensor_hrv.md`](../../../../praxis_gui/docs/sensor_hrv.md)).
`devices/zeitachse.py::schlagzeiten_aus_paketen` bildet daraus die Zeit je Zeile
von `messungen` — streng monoton, mit Rückfall auf die Ankunftsachse, wenn der
Block fehlt oder nicht zur Schlagfolge passt. Dasselbe Muster wie bei den
`frame_offsets` des EKG: Rohdaten speichern, Rekonstruktion später.

**In der Analyse.** Trägt die Datei den Block, nimmt `AnalysisSession` die
Kontinuitätsuhr als Anzeige- und Lückenachse (`t_axis == "kontinuitaet"`,
`raw_t_true()`): Lückenerkennung, Lückendauer und Abdeckungsquote. Die
Spektren selbst rechnen seit hrv-core (2026-10-16) auf der Herzuhr je
lückenfreiem Teilstück (`effective_rr_analyse()`); die Nähte dafür — Messlücken
und vom Gerät verworfene Läufe — kommen aus `hrv_core.ppi` auf der Herzuhr
**aller** Intervalle, auch der verworfenen. Deshalb springt die Divergenz genau
dort, wo wirklich etwas fehlt — und um genau diesen Betrag —, statt im Takt der
Zustellung zu rauschen. **Nicht** umgestellt sind Notiz-Anker und
Uhrzeit-Anzeige: sie bleiben auf der Ankunftsachse, auf der sie erfasst wurden.
Der Compute-Log vermerkt die Rechenachse als `t_axis` (`herzuhr`).

Ältere Messungen (bis einschließlich der Doppelmessungen vom 19.09.2026) haben
den Block nicht; für sie gilt unverändert die Ankunftsachse. Ein Zuschneiden der
Datei (`crop_file_inplace`) führt die Pakete mit.

---

## 6. Vergleichbarkeit der Kennzahlen mit dem H10

PPI ist nicht RR: die Pulswellenlaufzeit schwankt mit Blutdruck, Gefäßtonus und
Atmung. Das ist kein Messfehler, sondern andere Physiologie.

| Kennzahl | vergleichbar? | Anmerkung |
|---|---|---|
| mittlere HF, Ø Intervall | ja | |
| SDNN | ja | gemessen: 44,6 gegen 44,1 ms |
| RMSSD | ja, leicht erhöht | am PPG in Ruhe systematisch etwas höher (gemessen +2,9 ms) |
| pNN50 | nein | Schwellenmaß, reagiert auf das zusätzliche Rauschen |
| Frequenzbänder | mit Vorsicht | hängen an der Zeitachse (Abschnitt 5) und an den Lücken |
| DFA α1 | nein | |
| RSA-Amplitude, Atemfrequenz | nein | die Pulswellenlaufzeit trägt ein eigenes Atemsignal |

Deshalb zeigt der Vergleich hinter jeder Messung das Kürzel `EKG` / `PPG` und
warnt, wenn beide gemischt werden (→ [`../geraete.md`](../geraete.md), Abschnitt 2).

---

## 7. Was offen ist

- **Stufen an verworfenen Intervallen.** Die Kontinuitätsuhr ist lokal auf
  ~20 ms genau, springt aber an einzelnen Stellen um 0,2–0,4 s. Die gemeldete
  Dauer verworfener Intervalle stimmte im Abgleich meist auf wenige ms — woher
  die Stufen genau kommen (Gerät oder Referenz), ist nicht geklärt.
- **Workbench-Sichtprüfung.** Lücken und PSD einer Verity-Messung mit
  `ppi_pakete` gegen die H10-Messung derselben Sitzung ansehen.
- **Fehlerschätzung wird gespeichert, aber nicht genutzt.** Sie steht je
  Intervall in `ppi_pakete`; kein Filter und keine Anzeige greift bisher darauf zu.
  Polar nennt Werte über 30 ms verdächtig (Abschnitt 4a). Die trainingsapp
  wertet sie bereits aus: Intervalle über 50 ms gelten dort als Artefakt
  (trainingsapp `docs/korrektur.md`).
- **`ausreisser_schwelle` (0,30) ist ohne Wirkung.** Das Profilfeld liest keine
  Codestelle; gefiltert wird überall nur 300–2000 ms.
- **PPG-Decoder** für die delta-komprimierten Rahmen — bis dahin kein Rohsignal.
- **Kein PPI-Modus im Generator.** Synthetisches Testmaterial für Bündelung,
  Zustellverzögerung und verworfene Intervalle gibt es nur in
  `tests/test_ble_pruefbericht.py`.

---

## 8. Quellen

Abgerufen am 14.10.2026.

- Polar BLE SDK, [*PPI Data in Polar devices*][polar-ppi] — Blocker-Bit,
  Kontakt, „nur in völliger Ruhe“
- Polar BLE SDK, [*Polar Verity Sense*][polar-vs] — eigener PPI-Algorithmus,
  Herzfrequenz alle 5 s und bei Bewegung eingefroren, ~25 s Anlauf, Kontakt
  unzuverlässig
- Polar BLE SDK, [`PolarPpiData`][polar-kt] — Definition von `errorEstimate`
- [Validierungsstudie Verity Sense gegen H10][studie], Ruhe bis HIIT (JMIR
  Cardio 2025; Herzfrequenz, nicht Intervalle)

[polar-ppi]: https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/PPIData.md
[polar-vs]: https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/products/PolarVeritySense.md
[polar-kt]: https://github.com/polarofficial/polar-ble-sdk/blob/master/sources/Android/android-communications/library/src/sdk/java/com/polar/sdk/api/model/PolarPpiData.kt
[studie]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11951816/
