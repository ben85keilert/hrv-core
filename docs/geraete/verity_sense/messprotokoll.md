# Verity Sense — Messprotokoll

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Datierte Befunde am echten Gerät. Referenz ist immer der **Polar H10**,
gleichzeitig getragen, aufgenommen im Mehrgerätebetrieb
(→ [`../mehrgeraetebetrieb.md`](../mehrgeraetebetrieb.md)) und ausgewertet mit
`tools/ble_pruefbericht.py`
(→ [`../ble_uebertragung_pruefen.md`](../ble_uebertragung_pruefen.md)).

Gerät: Polar Sense 1AB84530 · Referenz: Polar H10 158D1F38 · Rechner: Linux,
BlueZ 5.87, bleak 3.0.1

---

## 1. Probelauf — 19.09.2026, 17:10

Erster Kontakt mit der Hardware. Verbindung kam zustande, riss aber nach
Sekunden wieder ab; ein paar Herzfrequenzwerte, keine Intervalle.

| Befund | Ursache | Behebung |
|---|---|---|
| Trennung wenige Sekunden nach „PMD-Service verfügbar", bei jedem Versuch | Gerät verlangt Bonding; BlueZ hatte keinen Agenten (`No agent available for request type 2`) | Profilfeld `kopplung_noetig`, `pair=True`, eigener BlueZ-Agent |
| Nur Herzfrequenz, keine Intervalle | `PPI_START_CMD` wurde nirgends gesendet | Worker startet PPI nach jedem (Re-)Connect |
| PMD-Steuerantwort hätte „FEHLER" gemeldet | Fehlerbyte an der falschen Stelle gelesen (`data[2]` ist der Messtyp) | `pmd.parse_control` |
| X-Achse lief im Sekundentakt, Intervallkurve zog gerade Linien | RR-lose HF-Pakete zählten als Schlag und schrieben `rr_ms = 0`-Zeilen | Lebenszeichen-Regel für Geräte mit `pmd_ppi` |
| Schlagzeiten nach einem verworfenen Intervall zu spät | Rückrechnung nur über die brauchbaren Intervalle | Rückrechnung über alle Intervalle des Pakets |

Erste Einzelmessung (18:36): ~5 Intervalle je Paket, etwa alle 5 s. Zwei Pakete
kamen 11 ms nacheinander an, dazwischen lag ein 966-ms-Schlag — erster Hinweis,
dass die Paketankunft nicht der Schlagzeitpunkt ist.

---

## 2. Doppelmessung 1 — 19.09.2026, 19:14 (5 min Ruhe, ohne Rohmitschnitt)

Erster gleichzeitiger Lauf H10 + Verity Sense in einer Sitzung.

| | |
|---|---|
| Schläge | Verity 256 · H10 329 |
| Zugeordnet (über die Intervallfolge) | 246 von 256 (**96,1 %**) |
| Differenz je Schlag | Bias **+0,4 ms** · SD **12,8 ms** · mittlerer Betrag 8,9 ms · ein Ausreißer > 50 ms |
| Korrelation | r = **0,984** |
| RMSSD | 84,2 ms · H10 84,8 ms |
| SDNN | 72,5 ms · H10 72,5 ms |
| Zeitversatz je Schlag | Median +5,05 s · SD 789 ms |
| Vom Armband nicht geliefert | ~57 s von 298 s, davon ein Loch von 40 s |

**Lehre für die Methode:** Über die *Zeitstempel* zugeordnet fanden nur 65 % der
Schläge einen Partner, oft den falschen — beide Achsen sind Ankunftszeiten (Gurt
1-s-Raster, Armband 5-s-Raster), der Versatz je Schlag schwankt um mehr als
einen halben Herzschlag. Der Bericht ordnet seither über die **Intervallfolge**
zu; die Zeit dient nur als grobes Band.

---

## 3. Doppelmessung 2 — 19.09.2026, 20:48 (5 min Ruhe, mit Rohmitschnitt)

**A — Datenblöcke** (147 PPI-Pakete, 543 HF-Pakete, 542 s Mitschnitt)

| Prüfpunkt | Ergebnis |
|---|---|
| Rahmenlänge Vielfaches von 6, Frame-Typ `0x00`, PPI-Start bestätigt | ✓ |
| Byte-Layout: HF-Byte ≈ 60000 / Intervall | ✓ Abweichung Median 1,2 bpm — **PPI-Layout an Hardware bestätigt** |
| PMD-Kopf-Zeitstempel | 0 — als Zeitquelle unbrauchbar |
| Intervalle je Paket | Median 5 (1 … 5) |
| Vom Gerät blockiert | 60 von 576 (**10,4 %**) |
| Fehlerschätzung der brauchbaren Intervalle | Median 7 ms (4 … 16) |
| Hautkontakt | durchgehend |
| Doppelspeisung (HF-Pakete mit RR) | keine |

**B — Zeitstempel**

| Prüfpunkt | Ergebnis |
|---|---|
| Ankunftsabstand der PPI-Pakete | Median 4,92 s |
| Alter des ältesten Intervalls bei Ankunft | Median 4,56 s |
| Zustellverzögerung je Paket (gegen die Kontinuitätsuhr) | Median 550 ms · p95 1301 ms → **Ankunft taugt nicht als Schlagzeitpunkt** |
| Zeit, die der Herzuhr durch Blocker fehlt | 53,4 s von 525 s |

**C — Kette und Rechnung:** alles ✓ — die 293 Schläge der Datei stehen exakt im
Mitschnitt, `t_wall_s` deckt sich auf 0,95 ms mit der Paketankunft, `tw_src` und
Herzuhr stimmen, RMSSD/SDNN der App gleich der unabhängigen Kontrollrechnung,
keine `rr_ms = 0`-Zeilen.

**D — Goldstandard**

| | |
|---|---|
| Schläge | Verity 293 · H10 326 |
| Zugeordnet | 287 von 293 (**98,0 %**) |
| Differenz je Schlag | Bias **−0,3 ms** · SD **8,8 ms** · mittlerer Betrag 6,6 ms · kein Ausreißer > 50 ms |
| Korrelation | r = **0,980** |
| RMSSD | 33,2 ms · H10 30,2 ms (+2,9) |
| SDNN | 44,6 ms · H10 44,1 ms (+0,5) |
| Zeitversatz je Schlag, wie aufgezeichnet | Median +5,11 s · SD 773 ms · robust 434 ms |
| … auf der Kontinuitätsuhr (beide Geräte) | Median +5,01 s · SD 582 ms · robust **195 ms** |

In ungestörten 25-Schlag-Blöcken streute der Versatz auf der Kontinuitätsuhr mit
90–150 ms; die Blockmittel wanderten zwischen +4,76 und +5,21 s.

**Nachtrag (selber Tag, verbesserter Anker):** Das Wandern kam zu einem guten Teil aus
der Rechnung, nicht vom Gerät — die erste Fassung hielt drei verzögerte Pakete
hintereinander für einen Paketverlust und verankerte neu. Mit dem Anker „Minimum
über die folgenden Pakete" sinkt die robuste Streuung derselben Messung auf
**124 ms** (Zustellverzögerung je Paket: Median 779 ms, p95 1496 ms).

Anmerkung: der H10 riss in diesem Lauf dreimal ab (Oberkörperdehnen) — ohne
Einfluss auf das Ergebnis, die Zuordnung überbrückt das.

---

## 4. Doppelmessung 3 — 20.09.2026, 00:04 (Ruhe, erste Messung mit `ppi_pakete`)

Erste Aufnahme mit dem neuen Programmstand: eigene Kurvenliste je Gerät, beide
Geräte im Aufnahmefenster, `ppi_pakete` in der Messdatei.

| | |
|---|---|
| A — Datenblöcke | alles ✓; 21 von 301 Intervallen vom Gerät verworfen (**7,0 %**), Fehlerschätzung Median 6 ms, kein Verbindungsabbruch |
| C — Kette | alles ✓, neu: **`ppi_pakete` deckt sich Paket für Paket mit dem Mitschnitt** (37 Pakete, 16 verworfene Intervalle) |
| Schläge | Verity 158 · H10 174 |
| Zugeordnet | 150 von 158 (**94,9 %**) |
| Differenz je Schlag | Bias **−0,5 ms** · SD **7,5 ms** · mittlerer Betrag 5,7 ms · kein Ausreißer > 50 ms |
| Korrelation | r = **0,992** |
| RMSSD | 45,2 ms · H10 42,1 ms (+3,1) |
| SDNN | 59,7 ms · H10 58,4 ms (+1,4) |

**Zeitachse — die Kontinuitätsuhr kommt jetzt allein aus der Datei:**

| | Median | lokal (90. Perzentil der Änderung je Schlag) | Sprünge > 100 ms |
|---|---|---|---|
| wie aufgezeichnet (Ankunft) | +5,22 s | **893 ms** | 50 |
| Kontinuitätsuhr | +5,00 s | **21 ms** | 7 |

Im Verlauf: auf der Kontinuitätsuhr liegt der Versatz über lange Strecken bei
+5,00 s, innerhalb eines Pakets auf 0–20 ms genau; dazwischen einzelne Stufen
(+0,16 s, −0,39 s), fast alle an Stellen mit verworfenen Intervallen. Auf der
Ankunftsachse springt er von Paket zu Paket zwischen +5,2 und +6,4 s.

**Lehre für die Methode:** Die Gesamtstreuung (robust 237 gegen 322 ms) zeigte
den Gewinn nicht — sie wird von den wenigen Stufen bestimmt. Entscheidend für
Frequenzanalyse und Lücken ist die *lokale* Genauigkeit; der Bericht weist sie
seither eigens aus. Geprüft und verworfen: die Vermutung, das Gerät melde die
Dauer verworfener Intervalle systematisch zu lang (Σ Intervalle lag 2,3 s über
der verstrichenen Zeit). Gegen den H10 stimmten die gemeldeten Dauern auf
−7 / +18 / 0 ms; die Differenz in der Bilanz kommt aus der unterschiedlichen
Zustellverzögerung des ersten und letzten Pakets.

---

## 5. Bei der Arbeit — 14.10.2026, 11:30 (73 min, nur Verity, aufgenommen mit der trainingsapp)

**Bedingungen:** Messung während einer Behandlung (Hände und Arme in
Bewegung), Armband fest (Abdrücke auf der Haut). Ohne H10-Referenz.
Aufgenommen und ausgewertet mit der trainingsapp (Build 76, `raw-v1` mit
`ppi_pakete`).

| | |
|---|---|
| Intervalle | 5536 in 1629 Paketen; Summe aller Intervalle 73,6 min = Wanduhr 73,5 min |
| Übertragung | Paket im Median alle 4,8 s, keine Pause über 6 s |
| Vom Gerät blockiert | **62 %**, je 10 min zwischen 18 und 97 % |
| Hautkontakt | durchgehend 1 — laut Polar ohne Aussage (Abschnitt 4a) |
| Fehlerschätzung, behaltene Intervalle | Median 9 ms; 93 % bis 20 ms, 3,8 % über 50 ms (davon mehr als die Hälfte über 120 ms) |
| Fehlerschätzung, blockierte Intervalle | Median 16 ms; 22 % über 50 ms |
| Abweichung vom Median sauberer Nachbarn über 20 % | behalten: 0–0,6 % je Fehlerklasse bis 50 ms · blockiert: 1 % (bis 10 ms), 6 % (10–20), 19 % (20–30), 53 % (30–50) |
| Nachbarn weichen um mehr als 20 % ab | behalten 0,5 % · blockiert 17 % |
| RMSSD aus Paaren echter Nachbarn | beide behalten, Fehler ≤ 20 ms: **30 ms** · beide blockiert, Fehler ≤ 20 ms: **98 ms** |

**Lehre:** In Bewegung hat das Blocker-Bit recht, auch bei kleiner
Fehlerschätzung. Wer die blockierten Intervalle wieder aufnimmt, verdreifacht
RMSSD. Die trainingsapp folgt seither wieder dem Blocker-Bit (dort
ALGO_VERSION 6, `docs/korrektur.md`), wie praxis_gui es immer getan hat. Die
Fehlerschwelle (30, 50 oder 150 ms) änderte am Ergebnis kaum etwas: 36–38 %
der Zeit gewertet, RMSSD 30–31 ms.

---

## Vorlage für weitere Läufe

Bedingungen (Haltung, Dauer, Sitz des Armbands) · Bericht A–D in Stichworten ·
was sich gegenüber dem letzten Lauf geändert hat (Programmstand, Gerät,
Umgebung).
