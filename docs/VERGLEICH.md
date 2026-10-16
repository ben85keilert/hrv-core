# Vergleich praxis_gui ↔ trainingsapp (Grundlage für Phase 2)

Stand 2026-10-16, aus `praxis_gui/HRV_INVENTAR.md` und `trainingsapp/HRV_INVENTAR.md`.

## Leitsatz (Ben, 2026-10-16)

Beide Apps verwenden **dieselben Algorithmen** aus hrv-core — für Vergleichbarkeit und identische
Ergebnisse. Die Bibliothek entsteht aus `trainingsapp.hrv_core` (numpy); praxis_gui wird darauf
umgestellt. scipy/neurokit2 dienen in hrv-core nur der Referenztestung (`tests/referenz/`).

Es gibt **keine algorithmischen Profile** (`profil="praxis"/"training"`). Was sich unterscheidet,
ist die Bedienung, und die bleibt in den Apps:

| | trainingsapp | praxis_gui |
|---|---|---|
| Zielgruppe | Therapeuten, Sportler, Leistungssportler, Laien | Therapeuten |
| Vorgabe | **Automatik**: Korrektur läuft mit den `Korrekturregeln`-Vorgaben vollautomatisch | **Expertenmodus** sichtbar: alle Schwellen und Regeln einstellbar, jede Kette einzeln |
| Zuschaltbar | Expertenmodus (Regeln sichtbar, Ketten einzeln) | Automatik (Vorschläge auf einmal anwenden) |
| Träger in hrv-core | `Korrekturregeln` (regeln.py) + `automatisch()`/`anwenden()` (korrektur.py) — beide Modi nutzen dieselben Funktionen, der Expertenmodus zeigt nur die Parameter | dto. |

Folge für Phase 2: `Korrekturregeln` ist die einzige Stelle, an der ein Parameter „nach App“ gesetzt
wird — und zwar in der App, nicht in der Bibliothek.

## Spalten

**Vorschlag** = Vorgehen beim Umzug. Entscheidung Ben = leer, bis freigegeben.

Kürzel: TA = `trainingsapp/src/trainingsapp/hrv_core/`, PG = `praxis_gui/src/praxislab/sensors/polar_h10/`.

## A. Identisch (Umzug 1:1 aus TA, Golden 1e-9 für TA; praxis_gui bekommt dieselben Zahlen)

| Funktion | TA | PG | Bemerkung | Entscheidung |
|---|---|---|---|---|
| Atemfrequenz-Prüfkette | `atmung.py` | `atmung.py` | byteidentisch | |
| Zeitbereich (SDNN ddof 0, pNN strikt >, Naht-Skip, ≥ 2) | `time_domain.py` | `hrv_compute.py:435-469` | gleich; TA liefert `rmssd=0.0` statt None bei nur Nähten (OFFENE_PUNKTE) | |
| Poincaré SD1/SD2 | `nonlinear.py` | `hrv_compute.py:1303-1324` | gleich | |
| Bänder, Mindestdauern, Bandpolitik (50 %, Lücken 300/60/10/2, Ausfall 20/15/10/5) | `constants.py`, `frequency.py:601-666` | `hrv_compute.py:58, 483-524` | gleich | |
| Ketten-Parameter (merge 2, auto 2, unsicher 5, 3 s), Rampe zwischen gültigen Ankern | `korrektur.py` | `analysis_session.py:1375-1563` | gleich; 9 Ketten/RMSSD 44,816 auf der Golden-Datei in beiden | |
| DFA α1 (200, Skalen 4–16, Boxen s//2) | `nonlinear.py:80-152` | `nk.fractal_dfa` | TA = NK2 auf 1e-12 — **ohne** Kubios-Vorkorrektur (siehe C) | |
| SampEn (m 2, r 0,2·SD, Chebyshev; A über n−m, B über n−m+1) | `nonlinear.py:155-199` | `hrv_compute.py:1327-1365` | gleich (gleicher Zählfehler in beiden, OFFENE_PUNKTE) | |
| Lückenerkennung (Divergenz ±5 Schläge > 5 s) | `segments.py:154` | `analysis_session.py:1224` | gleich | |
| Kontinuitätsuhr (Schlagzeiten aus `ppi_pakete`) | `zeitachse.py`, `ppi.py` | `devices/zeitachse.py` | Prinzip gleich; TA verankert neu ab 3 s, PG MAX_VERZUG 2,0 s/60 Pakete — Golden-Vergleich in Phase 2 | |
| Notiz-Anker (`beat_index` + `dt_s`) | `ereignisse.py` | `event_anchor.py` | Portierung; gemeinsames Datenmodell möglich (PG `EventTimeContext` bleibt App) | |

## B. Gleich gemeint, numerisch ppm-nah (TA-Fassung wird Standard)

| Funktion | TA | PG | Abweichung | Vorschlag | Entscheidung |
|---|---|---|---|---|---|
| Lomb-Scargle (Intervallmitten, Mittelwertabzug, ·2T/N, df = 1/T, Deckel 2000) | `frequency.py` numpy | `spectrum.py` scipy | 2e-5 relativ (Rundung in PG-Sollwerten), Spektrum auf alle Stellen | TA-Fassung; Referenztest gegen scipy in `tests/referenz/` | |
| Welch (4 Hz linear, 256, 50 %, Hann) | `frequency.py` numpy | `spectrum.py` scipy | ppm | TA-Fassung; Referenztest | |
| Periodogramm | numpy | scipy | ppm | TA-Fassung | |
| Teilspektren an Nähten, längengewichtet | `frequency.py` | `spectrum.py:357-382` | gleich bis auf Nullen (C) | TA-Fassung | |

## C. Bewusst verschieden (dokumentiert in `trainingsapp/docs/hrv_algorithmen.md`, `korrektur.md`)

TA ist der neue Standard; praxis_gui ändert sich an diesen Stellen. Vorher/Nachher wird in Phase 2
über `tests/golden/praxis_gui/` beziffert.

| Punkt | TA (Standard) | PG (bisher) | Wirkung auf praxis_gui | Entscheidung |
|---|---|---|---|---|
| Nullen (`rr_ms = 0`) | kein Artefakt, keine Naht im Spektrum (`ohne_nullen`); Zeitbereich: Naht | Null = fehlend → Interpolationskandidat; Naht im Spektrum | weniger erfundene Schläge; bei Ruhe < 60 bpm werden Bänder nicht mehr gesperrt | |
| Malik-Basis | auf der Reihe, in der Grenz-/Nullkandidaten schon überbrückt sind | auf der effektiven (korrigierten) Reihe | bei Einzelnullen identisch, bei Nullfolgen anders | |
| Malik-Schwelle optisch | 0,30 (`malik_threshold(intervall_quelle)`) | 0,20 überall | Verity-Messungen: weniger Fehlmarkierungen | |
| Fehlerschätzung Verity | `fehler_ms > 50` → Kandidat vor Malik | nicht ausgewertet | neu in praxis_gui | |
| `sensor_verwerfung` | `sensor` (Vorgabe) / `selbst` | nur `sensor` | neue Option (Expertenmodus) | |
| Nullen interpolieren | `nullen=False` Vorgabe; `True` = PG-Verhalten | immer | Option bleibt (`Korrekturregeln.nullen`) | |
| Fensterspektrum (Kurven, Live) | ein Lomb über alle guten Schläge des Fensters (≥ 30, ≥ 70 %) | Teilstücke je ≥ 60 Schläge | Fenster mit Artefakt fallen nicht mehr aus | |
| Lange Messungen ≥ 4000 s | drei Wege (LF/HF 5 min, VLF 30 min Hann, ULF) | Deckel 2000 Bins → Trapez überschätzt | Kurzmessungen unverändert | |
| Live-Grenzen | 250–2000 (über Regeln) | 300–2000 im Live-Puffer | Angleichung auf 250 | |
| RR-Grenze in Nebenpfaden | — | 300 ms in `poincare_widget`, `nk2_analysis`, Prüfbericht, Generator | über den Adapter vereinheitlichen | |
| Dateiname | UTC-Start | lokale Stoppzeit | Format-Frage, nicht Algorithmus; Phase 3 praxis_gui? | |
| `__cNN` in Messungsliste | nicht gelistet | gelistet | App-Frage | |
| Expertenmodus live | Regeln wirken live (`LiveFenster.regeln_setzen`) | feste Grenzen | praxis_gui-Live nutzt `LiveFenster`? | |

## D. Nur praxis_gui — braucht Entscheidung

| Funktion | PG | Abhängigkeit | Vorschlag | Entscheidung |
|---|---|---|---|---|
| Kubios-Vorkorrektur vor DFA | `hrv_compute.py:344-376` | NK2 `signal_fixpeaks` | **entfällt** — Standard wird Malik/Ketten (TA kennzeichnet). Referenztest hält die Differenz fest | |
| `compute_nonlinear` (NK2 `hrv_nonlinear`: SD1/SD2/SampEn/DFA u. a.) | `hrv_compute.py:900-934` | NK2 | entfällt; Werte kommen aus `nonlinear.py` (SD1/SD2 < 2 %, SampEn < 10 % laut Smoke-Test) | |
| RSA Peak-to-Trough (kubischer Spline 16 Hz, Butterworth filtfilt, Hilbert, Fragmentfilter, Median) | `respiration.py:367-481` | scipy | **nach numpy portieren** (Spline: `np.interp` reicht nicht — eigener kubischer Spline oder Catmull-Rom; Butterworth/filtfilt: IIR in numpy; Hilbert: FFT). Referenztest gegen scipy ±3 % wie `test_rsa_amplitude.py`. TA hat `_schwankung` (Spannweite 10-s-Fenster) als einfache Näherung — Ben: RSA-Hüllkurve behalten? | |
| Kontinuierliche Atemrate (`resp_rate_continuous`) | `respiration.py:286-334` | scipy | wie RSA portieren oder durch `trends.atmung_aktuell` (Fenster) ersetzen | |
| Kohärenz-Index (`coherence_index`) | `respiration.py:484-507` | scipy Welch | numpy-Welch vorhanden → portieren oder entfallen (praxis_gui zeigt „ohne Urteil“) | |
| EDR aus EKG (`edr_from_ecg`), `nk2_analysis.py` (EKG-R-Zacken, `nk.hrv`) | `nk2_analysis.py` | NK2 | in praxis_gui belassen als optionaler NK2-Zusatz (EKG-Rohsignal gibt es nur dort) — **nicht** nach hrv-core | |
| Spektrogramm (120 s / 30 s Welch) | `spectrum.py:385-464` | scipy Welch | numpy-Welch → portieren | |
| Spektralprofil (Peak, Halbwertsbreite, Entropie, Flatness) | `spektralprofil.py` | numpy | 1:1 übernehmen | |
| Rolling/Segment/Overlap-Fensterung (`compute_rolling`, `compute_segmented`, `compute_segments_overlap`, `compute_chunk_metric`) | `hrv_compute.py:1000-1300` | numpy | TA hat `trends.verlauf` (gleitend/Blöcke, Cache). Zusammenführen: Golden-Vergleich beider auf den Fixtures; Vorschlag `trends` als Standard, PG-Schritt/Fensterparameter abbilden | |
| Korrektur-Ops `set_value`, `split`, `merge` | `analysis_session.py:196-363` | — | TA liest und wendet sie an (`korrektur.anwenden`); Erzeugung im Expertenmodus → in hrv-core ergänzen (reiner Umzug) | |
| Undo/Redo, Sitzungszustand, Segmente mit Farben | `AnalysisSession` | — | App | |
| `analysis-v3`-Store (CSV-Serien, Compute-Log, `region_hash`) | `analysis_store.py` | — | App (praxis_gui-eigenes Cache-Format) | |
| Generator (IPFM, Artefakte, EKG, Szenarien) | `generator/` | numpy | eigenes Paket `hrv_core.generator` später; Kalibriermodi eingefroren | |
| Prüfbericht (`ordne_zu`, `schaetze_versatz`) | `devices/pruefbericht.py` | numpy | Werkzeug; `ordne_zu` als Referenzhelfer nach hrv-core denkbar | |
| `tw_src="g"`, Generator-Widget-Schreiber | `generator/widget.py` | — | App | |

## E. Nur trainingsapp (kommt nach hrv-core, praxis_gui gewinnt sie dazu)

| Funktion | TA | Für praxis_gui | Entscheidung |
|---|---|---|---|
| `Korrekturregeln` (regeln.py) | Träger Automatik/Experte | ersetzt `[hrv]`/`[hrv_gaps]`/`metric_params.malik` als Rechenparameter; Expertenpanel bindet daran | |
| `ppi.py` (Verity: Zuordnung `ppi_pakete` ↔ Zeilen, `ohne_verwerfung`, `corrections_ppi`) | | neu; praxis_gui hat nur die Kontinuitätsuhr | |
| `live.py::LiveFenster` (Puffer, Live-Kennzahlen, Schwankung) | | kann `widget.py`-Live-Rechnung (`_kachel_werte`, `_rolling_rmssd`) ersetzen | |
| `trends.py` (Verlaufskurven mit Cache) | Katalog `KENNZAHLEN` UI-nah | siehe D Fensterung | |
| `ausschnitte.py` (Abschnitte, `achsen_umrechnung`) | | entspricht Segmenten/Regionen | |
| `recording.py`/`aufnahme.py` (raw-v1 lesen/schreiben, atomar, Backup) | | praxis_gui-Schreiber (5 Stellen) könnten darauf umziehen — Phase 3, eigene Entscheidung | |
| `export.py` | Diagnose | App | |
| `training.py` | GPX | App | |

## F. Vorgehen Phase 2 (nach Freigabe)

1. `trainingsapp/scripts/export_referenz.py`: je Fixture Kennzahlen (`kennzahlen`), Ketten
   (`automatisch` mit Vorgabe-Regeln und mit `nullen=True`), korrigierte Reihe, Spektrum/Bänder
   (lomb, welch), Fensterspektrum, DFA, SampEn, Atmung, `trends.verlauf` für RMSSD/SDNN/LF/HF,
   `ppi`-Zuordnung bei Verity → `tests/golden/trainingsapp/<fixture>.json`. Toleranz 1e-9.
2. `praxis_gui/scripts/export_referenz.py`: dieselben Größen mit dem heutigen Code →
   `tests/golden/praxis_gui/`. Dient als **Vorher-Stand**; Differenz zu hrv-core wird je Zeile
   in C/D beziffert und ist die Grundlage für Bens Entscheidung.
3. Umzug `trainingsapp.hrv_core` → `hrv_core` Modul für Modul (constants, artifacts, segments,
   time_domain, frequency, nonlinear, atmung, ppi, zeitachse, regeln, korrektur, live, trends,
   ausschnitte, recording, aufnahme, ereignisse), mit Tests; `tests/referenz/` gegen scipy/NK2.
4. Ergänzungen aus D, die als „portieren“ oder „übernehmen“ entschieden sind (Spektralprofil,
   Spektrogramm, Korrektur-Ops, RSA).
5. Tag `v0.1.0`.
