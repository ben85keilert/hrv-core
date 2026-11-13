# Offene Punkte (beim Umzug aufgefallen, bewusst nicht jetzt behoben — Regel 4)

Stand 2026-10-16. Je Punkt: Ort, Befund, Vorschlag. Behebung erst nach dem Umzug, mit Golden-Vergleich.

## Rechnung

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| R1 | praxis_gui `hrv_compute.py:1327-1365`, trainingsapp `nonlinear.py:155-199` | SampEn zählt A über n−m Vorlagen, B über n−m+1 (Richman/Moorman: beide n−m). Beide Repos gleich → kein Umzugsproblem | nach Umzug korrigieren, `ALGO_VERSION` hoch |
| R2 | trainingsapp `time_domain.py:54` | `rmssd = 0.0` statt `None`, wenn alle Differenzen durch Nähte wegfallen — widerspricht „None statt 0“ | nach Umzug |
| R3 | praxis_gui `hrv_compute.compute_frequency_domain` | `interpolation_rate` wird nie an `spectrum` gereicht; Resampling immer 4 Hz | mit dem Umzug entfällt der Parameter |
| R4 | praxis_gui `spectrum.py:234` | ohne scipy liefert `lomb` still kein Spektrum (kein Rückfall) | erledigt sich durch numpy-Lomb |
| R5 | praxis_gui, sechs Stellen | RR-Grenze 300 ms statt 250 (`widget.py` Live-Puffer, `poincare_widget.py:43`, `nk2_analysis.py:54`, `pruefbericht.py:34`, `generator/artifacts.py:36`) | Phase 3 über den Adapter |
| R6 | praxis_gui `hrv_compute.compute_poincare_points` | überspringt keine Nähte | Phase 3 |
| R7 | praxis_gui `spectrum.py` MAX_GRID_BINS, trainingsapp vor ALGO 5 | Deckel 2000 Bins macht df gröber als 1/T → Trapez überschätzt schmale Gipfel bei > 67 min | TA-„langer Weg“ wird Standard |
| R8 | trainingsapp `constants.py` | ungenutzt: `WELCH_OVERLAP` (Overlap fest `n−n//2`), `DFA_DETREND_BOX`, `RECOMMENDED_BEATS_FREQUENCY`, `SAMPEN_MAX_BEATS_LIVE` (nur Docstring; UI deckelt bei 3000) | beim Umzug bereinigen (keine Zahl ändert sich) — **erledigt** (2026-10-19, 8f640b3: WELCH_OVERLAP, DFA_DETREND_BOX, RECOMMENDED_BEATS_FREQUENCY entfernt; SAMPEN_MAX_BEATS_LIVE bleibt (spektralprofil)) |
| R9 | trainingsapp `ui/views/messung_detail.py` | Rechenlogik in der UI: `_Zustand`, Atem-Median (doppelt zu `ausschnitte.py:192`), SampEn-Deckel, DFA ganze Reihe (Befund H11) | Phase 3 trainingsapp |
| R11 | praxis_gui `effective_rr_true()` als PSD-Stützstellen (CLAUDE.md, `sensor_hrv.md` „Echte Zeitachse“) | Die Wanduhr ist die Paketankunft (H10: 1-s-Takt, `r`-Stempel zurückgerechnet) — als Lomb-Stützstellen ein Zeitjitter, der HF hebt: Generator Kohärenzatmung Wahrheit 67,5 ms², praxis_gui 670, hrv-core (Herzuhr je Teilstück) 44,6; Ruhe liegend +19 %. Die Doku warnte nur vor `r`-Stempeln (+9–10 %) | erledigt sich mit dem Umstieg: hrv-core trennt an Lücken (Wanduhr) und rechnet auf der Herzuhr; praxis_gui-Doku in Phase 3 korrigieren (`docs/VERGLEICH_ZAHLEN.md`) |
| R12 | praxis_gui `nk2_analysis.py`, `respiration.edr_from_ecg` | EKG-Auswertung hängt an NK2 | **entfällt** (Ben 2026-10-16); EKG-Rohsignal bleibt; Ersatz später aus hrv-research |
| R13 | praxis_gui `AnalysisSession` | `Korrekturregeln.sensor_verwerfung = "selbst"` (Verity: vom Sensor Verworfenes wieder aufnehmen) ist in praxis_gui fest `"sensor"`: die Sitzung rechnet auf den Zeilen der Rohdatei, die Analysebasis mit zusätzlichen Zeilen (`korrektur.analysebasis`, `corrections_ppi`) bräuchte einen eigenen Index-Raum für Korrekturen, Anker und Segmente | später, wenn Verity-Messungen in der Praxis eine Rolle spielen; der Dialog zeigt den Schalter nicht |
| R14 | praxis_gui `widget.py` (Live) | Die Live-Anzeige führt ihren eigenen Puffer (Kacheln, Kurven, Kontinuitätsuhr `devices/zeitachse.py`) und ruft hrv-core nur je Fenster (`compute_chunk_metric`, `compute_time_domain`); `live.LiveFenster` (Malik live, Verworfenes nach Regeln) wird nicht benutzt | Angleichung bei der nächsten Überarbeitung des Live-Tabs; Zahlen der Kacheln sind bereits hrv-core |
| R10 | praxis_gui `analysis_service.py:284-286` | liest `r.get("mean_bpm")`, `respiration_summary` liefert `resp_rate_mean` → `resp_rate_bpm` im Neuberechnungspfad nie gesetzt | **erledigt** (Phase 3 praxis_gui, 2026-10-16) |

## Dateien und Formate

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| F1 | praxis_gui `widget.py:8093-8121`, `main.py:2286` | Crash-Backup trägt `hrv`-Block (`_scope: live_window`); die Wiederherstellung schreibt ihn unverändert in die Messdatei — Doku sagt „raw-v1 ohne hrv“ | Wiederherstellung soll den Block entfernen |
| F2 | praxis_gui `widget.py:7057` | fünfter raw-v1-Schreiber (Begleitgerät): Herkunftsfelder nicht über `_herkunft_felder`, `simulation` fest False; CLAUDE.md und `tests/test_geraete_provenienz.py:6` zählen „vier“ | Doku/Test nachziehen; Phase 3: alle Schreiber über `hrv_core.recording` |
| F3 | praxis_gui `analysis.py:1346-1410` | schreibt Titel/Notiz/Ereignisse in die Rohdatei ohne Sidecar-SHA, nicht atomar | Phase 3 |
| F4 | praxis_gui `analysis_io.py:653` `crop_file_inplace` | verankert Ereignisse nicht neu; im Programm unbenutzt | entfernen oder reparieren |
| F5 | praxis_gui / trainingsapp | Dateinamen: lokale Stoppzeit vs. UTC-Start; Backup in praxis_gui nach UTC mit `_1` bei Doppelung | **erledigt**: UTC-Start in beiden Apps (praxis_gui Phase 3, 2026-10-16) — seit 2026-11-13 Start in **Ortszeit** in beiden Apps, siehe F24 |
| F24 | praxis_gui `sensors/polar_h10/widget.py` (Backup- und Messdateiname), `main.py` (`_restore_sensor_backup`), `devices/sitzung.py`, `generator/widget.py`, `dokumentation/widget.py` (Uhrzeit im Titel des Doku-Eintrags); hrv-core `recording.dateistempel` | **Zeitstempel in Dateinamen: Start in Ortszeit, in beiden Apps** (Ben, 13.11.2026 — hebt F5 „UTC-Start“ auf). Anlass: In der trainingsapp trug die Messung UTC, die Strecke Ortszeit. hrv-core benennt Messdatei und Backup über `dateistempel`, die trainingsapp ihre Streckendatei ebenso; praxis_gui nutzt dieselbe Funktion an allen fünf Stellen und liest die Uhrzeit für den Titel des Doku-Eintrags aus `start_utc` statt aus dem Namen (vorher stand dort die UTC-Stunde). Altdateien behalten ihren Namen. | **erledigt** (2026-11-13, hrv-core 0.15.0; praxis_gui `tests/test_messdatei_name.py`) |
| F6 | trainingsapp `docs/kompatibilitaet.md` §6a (uncommittet) | „praxis_gui liest Backups nicht“ ist falsch (`main.py:2167`); ein Backup mit `_wiederherstellung` würde samt Block zur Messdatei | Doku korrigieren; F1 |
| F7 | trainingsapp `001_init.sql:245` | `hrv_metrics_cache` ohne Code; `measurement.source='hrv'` nie geschrieben; CLAUDE.md beschreibt den Cache als tragend | klären |
| F8 | trainingsapp `tests/golden/rr/README.md` | sagt „entfernt“, Felder sind vorhanden (null); Kopie 46 B größer als das Original | README präzisieren |
| F9 | praxis_gui `sensor_hrv.md:640` | `tw_src="g"` liest niemand; entsteht nur im Generator-Widget | dokumentieren oder entfernen |

## Tests und Regeln

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| T1 | trainingsapp `tests/test_import_regel.py:41` | relative Importe werden übersprungen; `hrv_core → devices/data/core` nicht verboten | hrv-core hat einen geschärften Test (`tests/test_import_regel.py`) |
| T2 | praxis_gui `tests/test_live_compute_smoke.py` | keine `test_`-Funktion, läuft unter pytest nicht | in Referenztests überführen |
| T3 | praxis_gui | keine festen Sollwerte für Kennzahlen (nur Toleranzen) | Phase 2 Golden |
| T4 | praxis_gui `pyproject.toml` | `astropy` im Extra `hrv`, nirgends importiert | **erledigt** (Extra `hrv` gestrichen) |

## Doku

| # | Ort | Befund |
|---|---|---|
| D1 | praxis_gui `docs/sensor_hrv.md:545-612` | Atem-Abschnitt beschreibt „PSD-Peak + Prominenz“, Code ruft `atmung` |
| D2 | praxis_gui `docs/sensor_hrv.md:24` | „NK2-Frequenzanalyse“ laut Z. 878 überholt |
| D3 | praxis_gui `analysis_io.py:13` | Docstring nennt `analysis-v2`, Store schreibt v3 |
| D4 | praxis_gui `widget.py:13-26`, `generator/artifacts.py:461` | Kopfbeispiel ohne `tw_src`; Zeilenverweis veraltet |
| D5 | trainingsapp `CLAUDE.md:139` | nennt `datenqualitaet`-Werte als `intervall_quelle` |
| D6 | trainingsapp `docs/kompatibilitaet.md:12-19, 598` | Zeilenverweise ~3 Zeilen daneben; „eine Golden-Datei“ sind vier |
| D7 | trainingsapp `docs/hrv_algorithmen.md:510` | 16-Hz-Tachogramm kubisch: im TA-Code nicht vorhanden (meint praxis_gui) |
| D8 | praxis_gui CLAUDE.md:59 | „Python 3.10+“, pyproject ≥ 3.11, venv 3.14 |

## Durchsicht 2026-10-19

Nach den Änderungen vom 15.–18.10. (Marken, `messdatei_name`, Spuren, `atmung.fenster/median`,
`spektrogramm`, `spektralprofil`). Stand: 347 Tests und 16 Referenztests (scipy 1.18.1,
neurokit2 0.2.12) grün; die Änderungen seit 14.10. sind additiv, Golden und `ALGO_VERSION`
unverändert, Doku-Einträge vorhanden. Mathematik gegen `hrv_algorithmen.md`/`korrektur.md`
geprüft (Welch, Lomb, DFA, SampEn, Malik, Ketten, Bänder) — stimmt. Grenzfälle (leer, 1, 2,
konstant, NaN, Inf, None, 0, negativ) liefern überall `None` bzw. Gründe ohne Ausnahme.
Schwere: **hoch** = Datenverlust/Datenschutz/Absturz im Normalgebrauch, **mittel** = falscher
Wert, Leak, Last, **niedrig** = Wartung. „Bestätigt“ = nachgestellt.

### Rechnung

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| R15 | `frequency.py:860-905` `fensterspektrum` | **Kein Längendeckel:** 8-h-Fenster (34 000 Schläge) → `_lombscargle` legt N×256-Matrizen an, 488 MB Spitze, 16 s (bestätigt, tracemalloc) — am Handy OOM. Zudem greift dort `MAX_GRID_BINS` (df gröber als 1/T), genau der Fehler, den ALGO 5 für die Gesamtmessung behob (R7). Die App leitet heute „Alles“ und Abschnitte > `LANG_AB_S` über `frequenzbereich`/`abschnitt_spektrum` um, der Live-Puffer ist 30 min — die Bibliothek selbst schützt nicht. **mittel** | ab `LANG_AB_S` auf `frequenzbereich(mindestdauer=False)` umleiten oder `None` — **erledigt** (2026-10-19, 67673ca: langer Weg ab LANG_AB_S) |
| R16 | `korrektur.py:877, 900-926` (`analyse_laden`), `ausschnitte.py:318`, `ereignisse.py:423` | `source_file_sha1` wird geschrieben und aufgefrischt, aber **nirgends geprüft** (hrv-core und trainingsapp, grep). Ein Sidecar einer anderen oder nachträglich veränderten Messdatei wird per `beat_index` angewandt: Indizes ≥ n fallen still weg (`anwenden`:588), kleinere treffen falsche Schläge (bestätigt: `interpolate 42` aus fremdem Sidecar ersetzt einen gesunden Schlag). **mittel** | in `analyse_laden` Hash vergleichen; bei Abweichung Sidecar als veraltet melden (wie praxis_gui) — **erledigt** (2026-10-19, 4da0444: analyse_lesen → Sidecar.veraltet, sidecar_veraltet) |
| R17 | `time_domain.py:261-264` | Ergänzung zu R2, wirksam: `compute_time_domain([800, 810], breaks=[1])` → `rmssd 0.0, pnn 0.0, n_diffs 0`; `ausschnitte.abschnitt_werte:465` zeigt für einen kurzen Abschnitt mit Naht RMSSD 0. `trends._wert` und `live._zeitbereich` sind per `min_diffs` geschützt. **mittel** | `None` bei `n_diffs == 0`, `ALGO_VERSION` hoch — **erledigt** (2026-10-19, 67673ca: None bei n_diffs 0) |
| R18 | `frequency.py:463` `_mittelreihe` | NaN in `t` → `astype(int)` → `np.bincount` wirft `ValueError` (bestätigt). Erreichbar über `vlf_fenster:932` (Maske prüft nur `rr`, nicht `t`) und `_teilspektrum_lang`; `Beat.from_dict` lässt NaN durch (Pythons `json.loads` akzeptiert `NaN`). Nur bei kaputter Datei. **niedrig** | Maske auch auf `t` — **erledigt** (2026-10-19, 67673ca: Maske auch auf t, _mittelreihe filtert) |
| R19 | `nonlinear.py:345` `sd1_sd2` | `sd2` als Rundungsrest (8,4·10⁻⁸) → Verhältnis 8,4·10⁷ (bestätigt mit Wechselfolge [800, 810]·60). Schwelle `sd2 > 0` ohne Toleranz; praktisch nur bei künstlich regelmäßigen Reihen. **niedrig** | `sd2 > eps·sdnn` — **erledigt** (2026-10-19, 67673ca: None bei sd2 ≤ 1e-6·sdnn) |
| R20 | `frequency.py:531-532` `_teilspektrum_lang` | fehlt ULF- oder VLF-Teilspektrum, werden Nullen eingesetzt → `integriere_band` 0,0 statt `None`; durch Bandpolitik und Mindestlänge kaum erreichbar (plausibel). **niedrig** | `None` durchreichen — **erledigt** (2026-10-19, 67673ca: NaN statt Nullen, mittel je Bin) |
| R21 | `korrektur.py:511-514` `_interpolationswerte` | Artefakt am Anfang/Ende mit nur einem Anker → Plateau-Kopie des Nachbarn (bestätigt: 3000 ms an Index 0 → 800); ohne Anker bleibt der Rohwert mit Flag `interp` (bestätigt `[3000,3000,3000]`) und wird erst vom Plausibilitätsfilter verworfen — ein Malik-Ausreißer innerhalb 250–2000 ms zählte mit. praxis_gui-gleich; „lieber Lücke“ wäre `delete`. **niedrig** | mit praxis_gui entscheiden — **erledigt** (2026-10-19, 67673ca: ausschließen statt Plateau, ohne Anker ebenso) |
| R22 | `trends.py:463-468` `verlauf` | filtert implausible Werte nicht selbst (bestätigt: 100×0 ms → RMSSD 0,0; −800 → 0,0); verlässt sich auf `trends.reihe`/`live.verlaufsreihe`. **niedrig** | Vorbedingung dokumentieren oder filtern — **erledigt** (2026-10-19, 67673ca: verlauf/aktuell filtern selbst) |
| R23 | `frequency.py:544-546` | Rasterkanten fließkommaempfindlich: 0,15 Hz liegt im 1/300-Raster bei 0,15000000000000002 (zählt zu HF), 0,4 bei 0,4000000000000001 (fällt aus HF). Kein Fehler, dokumentiert. **niedrig** | `np.isclose` an den Kanten — **erledigt** (2026-10-19, 67673ca: KANTE_HZ 1e-9) |

### Dateien und Formate

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| F10 | `recording.py:364-372` `speichern`, `aufnahme.py:237-249` | **Vorhandene `sensor_<ts>.json` wird stillschweigend ersetzt** (`os.replace`); praxis_gui hängt bei Namensgleichheit `_1` an. Zwei Aufnahmen mit gleicher UTC-Startsekunde im selben Geräteordner (Simulator/Generator, zweiter Start nach Fehler mit übernommenem `start_utc`) → die erste Messung ist weg, ohne Fehler (bestätigt). `backup_wiederherstellen` in der App schützt sich selbst mit `exists()`, die Bibliothek nicht. **hoch** | Zähler wie praxis_gui oder `FileExistsError` — **erledigt** (2026-10-19, 3908eb9) |
| F11 | `ausschnitte.py:327-343` `zusatz_speichern` | Ersetzt alle `segments` außer `gesamt` und schreibt feste `metrics: None, computed_utc: None, active: True, visible: True`; praxis_gui wertet `active`/`visible` aus (`analysis_session.py:215`, `workbench.py:2540`). In praxis_gui einen Abschnitt deaktiviert, danach in der trainingsapp Crop gespeichert (`messung_detail.py:1080`) → Abschnitt wieder aktiv und sichtbar, praxis_gui-`metrics` und jedes weitere Segmentfeld weg (bestätigt). Verschärft trainingsapp H5. **mittel** | je Segment das gelesene Dict fortschreiben, nur `name/t_start_s/t_end_s/color` setzen — **erledigt** (2026-10-19, 4da0444: je Segment fortgeschrieben; bei verschobenen Grenzen metrics/computed_utc geleert) |
| F12 | `deid.py:239-241, 281-288, 346-351` | **De-Identifizierung nicht vollständig gegenüber dem Schreibpfad:** ohne Ablehnung oder Hinweis passieren `ereignisse[].marke.name` (Freitext aus dem Timerprofil), `geraet` (BLE-Name mit Seriennummer — Pseudo-Identifikator über Dateien hinweg), `_wiederherstellung.subject_id` (Profil-ID in `.backup_*.json`, die `rglob("*.json")` mit erfasst), verschachtelte `teilnehmer[].patient_id`/`adresse` (BLE-MAC) in `sitzung-v1`, jedes unbekannte Top-Level-Feld (`extra` wird durchgereicht). `deidentifizieren` leert nur Top-Level `patient_id`/`behandlung_id` (bestätigt: Datei mit allen Feldern → 0 Ablehnungen, 0 Hinweise). **hoch** | Weißliste je Feld statt Schwarzliste; `extra` und verschachtelte Strukturen rekursiv prüfen; `geraet` auf Modell kürzen — **erledigt** (2026-10-19, f415963: Weißliste REGELN, rekursiv, geraet_modell, pruefen lehnt Unbekanntes ab) |
| F13 | `deid.py:212-219`, `scripts/deid_export.py:9` | `start_utc`, `datum`, `wall_time` und der Dateiname (UTC-Startsekunde) bleiben bewusst erhalten — zusammen mit dem Praxiskalender re-identifizierend. Dokumentiert, kein Codefehler. **mittel** | als Risiko in `pruefen` benennen; Zeitversatz je Person erwägen — **erledigt** (2026-10-19, f415963: nichts geändert, bewusst — im Modul und in deid_export dokumentiert) |
| F14 | `recording.py:80-89, 237`, `aufnahme.py:290-298` | `Beat.from_dict`: `d["t_s"]` → `KeyError`, Eintrag `None`/String → `AttributeError`, `"x"` → `ValueError`; `laden()` wirft vier Ausnahmetypen statt eines Formatfehlers; `backup_lesen` fängt nur `JSONDecodeError` → Backup mit kaputtem Messwert bricht die Wiederherstellung ab (bestätigt). **mittel** | `FormatFehler` in `laden`/`backup_lesen` — **erledigt** (2026-10-19, 3908eb9) |
| F15 | `recording.py:262` | `list(doc.get("ereignisse") or [])`: ist `ereignisse` ein dict oder String, entsteht eine Liste von Schlüsseln/Zeichen, die beim nächsten Speichern zurückgeschrieben wird — Korruption statt Fehler (bestätigt, unwahrscheinlich). **niedrig** | Typ prüfen — **erledigt** (2026-10-19, 3908eb9) |
| F16 | `recording.py:188-189, 214-235` | `analyzed` und `schema` gelten als bekannt, werden aber nicht übernommen; `to_dict` schreibt immer `schema: raw-v1`, `analyzed: False`. Round-Trip einer Altdatei (Fixture `sensor_2026-04-24_204808.json`) behauptet `raw-v1` und trägt den Legacy-`hrv`-Block; `test_round_trip_verliert_nichts` prüft nur Messwerte (bestätigt). Heute nur über `backup_wiederherstellen` erreichbar. **niedrig** | Kopf übernehmen, Test auf den Kopf ausdehnen — **erledigt** (2026-10-19, 3908eb9) |
| F17 | `recording.py:177-181, 372`, `aufnahme.py:106` | `start_utc=None`: `dateiname()` und `to_dict()` nehmen zwei `datetime.now(UTC)` (Sekundengrenze → Dateiname ≠ Kopf); `to_dict` leitet `datum` aus dem UTC-Datum ab, `Aufnahme` aus dem Ortsdatum (Vertrag §7: Ortsdatum). **niedrig** | einmal `jetzt` ziehen, Ortsdatum — **erledigt** (2026-10-19, 3908eb9) |
| F18 | `ereignisse.py:97-101` `marke_bereinigen`, `recording.py:326-330` | NaN/Infinity passieren; `json.dump` schreibt `NaN`/`Infinity` — kein gültiges JSON für strikte Parser (bestätigt). **niedrig** | `allow_nan=False` in `json_atomar_schreiben`, `math.isfinite` in `marke_bereinigen` — **erledigt** (2026-10-19, 3908eb9) |
| F19 | `recording.py:333` | kein `fsync` des Verzeichnisses nach `os.replace`; auf Android/ext4 kann der Rename bei Stromausfall verloren gehen (Inhalt der `.tmp` ist gesichert). **niedrig** | `os.fsync` auf den Ordner — **erledigt** (2026-10-19, 3908eb9) |
| F20 | `recording.py:29` | `DATEINAME_MUSTER` ungenutzt und würde praxis_guis `sensor_<ts>_1.json` ablehnen, die `ist_messdatei` korrekt akzeptiert. **niedrig** | entfernen — **erledigt** (2026-10-19, 3908eb9) |
| F21 | `ereignisse.py:411-413` | Fehlt `titel` in einer Altdatei, landet es nach `metadaten_schreiben` hinter `messungen` — wie praxis_gui, kosmetisch. **niedrig** | — — **erledigt** (2026-10-19, 3908eb9) |

### Tests und Regeln

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| T5 | Repo | **Kein CI-Workflow** (`.github/` enthält nur `dependabot.yml`); der Stand auf main ist nicht ruff-sauber (16 Meldungen: EXE001 ×4 in `scripts/`, RUF100 ×3, TRY004 ×2, I001 ×2, F401, C401, C408, ISC004, RUF046; 12 Dateien unformatiert), obwohl CLAUDE.md `ruff check` und `ruff format --check` verlangt. **mittel** | Workflow wie trainingsapp `ci.yml` (ruff, pytest, Referenz als eigene Matrix), einmal `ruff format`— **erledigt** (2026-10-19, 8dfaa97: `.github/workflows/ci.yml`, Regelauswahl in pyproject wie trainingsapp, Shebangs entfernt) |
| T6 | `tests/golden/`, `tests/test_frequenz.py:275` | Kein Golden für den langen Weg (ALGO 5): längste Fixture 2640 s < `LANG_AB_S` 4000 s; `_spektrum_lang`, `_lomb_hann`, `_mittelreihe`, `vlf_fenster`, ULF nur mit 10 % Toleranz gedeckt. Ohne Golden auch `spektrogramm`, `spektralprofil`, `live.LiveFenster`, `zeitachse.Kontinuitaetsuhr`, trends `vlf_power`/`gipfel`/`rsa`/`hf_rr`, `atmung.median` direkt. **mittel** | synthetische > 4000-s-Fixture ins Golden — **erledigt** (2026-10-19, ad86a3a: scripts/fixture_synth_lang.py, tests/fixtures/synthetisch/) |
| T7 | `tests/referenz/` | fehlen: Zeitbereich/Poincaré gegen nk2 `hrv_time` (Abweichungen ddof/pNN50 als Beleg), `_lomb_hann` gegen `scipy.signal.lombscargle` mit gefensterten Werten; Malik und Atmung haben kein Pendant. SampEn-Referenz bewusst 2 % (R1). **niedrig** | ergänzen — **erledigt** (2026-10-19, 8f640b3: Zeitbereich gegen nk2 hrv_time, _lomb_hann gegen scipy) |
| T8 | `scripts/vergleich_praxis_gui.py:227-228`, `golden_erneuern.py` | `a['n_beats']`, `a['roh']` ohne Absicherung; `golden_erneuern` schreibt nicht atomar (Dev-Skripte). **niedrig** | — **erledigt** (2026-10-19, 8dfaa97, 67673ca: vergleich_praxis_gui ohne KeyError, golden_erneuern atomar) |

### Doku

| # | Ort | Befund |
|---|---|---|
| D9 | `docs/hrv_algorithmen.md:109, 386-388, 575, 658-662, 695` | verweist auf `tests/test_korrektur_regeln.py` (gibt es hier nicht), auf `test_atmung_byteidentisch` (nur im Docstring, keine Testfunktion, `PRAXIS_GUI_PFAD` nirgends), auf einen Deckel „höchstens 2000 Minutenfenster“ (in `atmung.fenster/median` nicht vorhanden; 8 h → 1922 Fenster, 2,1 s; 24 h ≈ 5800), auf `tests/golden/rr/` (hier `tests/fixtures` + `tests/golden/trainingsapp`) und auf einen nk2-Vergleich in `tests/test_nichtlinear.py` (liegt in `tests/referenz`). — **erledigt** (2026-10-19, 8f640b3) |
| D10 | `praxis_gui/docs/sensor_hrv.md`, hrv-core `docs/` | Feldreferenz raw-v1 kennt weder `uebungen`, `marke`, `datenqualitaet` noch `corrections_ppi`; hrv-core hat keinen eigenen Formatvertrag. Kompatibilität selbst ist gegeben (Felder optional, flach, praxis_gui behält sie; trainingsapp `kompatibilitaet.md` §4/§6a/§9b aktuell). — **erledigt** (2026-10-19, 8f640b3: docs/formate.md; Nachtrag in praxis_gui/docs/sensor_hrv.md am 19.10. abends, dort committet) |
| D11 | `constants.py` | R8 weiter offen: `WELCH_OVERLAP`, `DFA_DETREND_BOX`, `RECOMMENDED_BEATS_FREQUENCY` ungenutzt; `SAMPEN_MAX_BEATS_LIVE` inzwischen in `spektralprofil.py:33` genutzt. — **erledigt** (2026-10-19, 8f640b3: drei Konstanten entfernt) |

## Durchsicht 2026-10-22

Nach den Commits `04e6110..5a3c97f` (Marken `person`/`leistung`/`abschluss`, Feld `adresse`,
De-Identifizierung mit Adresserkennung, `korrektur_laden`/`korrekturstand`, Gerätedoku
Decathlon/Beurer, `scripts/ble_erkundung.py`). Stand: 388 Tests grün (Golden 1e-9,
Doctests), ruff sauber, kein ALGO-Sprung nötig (nur Komposition vorhandener Funktionen).
Schwere wie am 19.10. „Bestätigt“ = nachgestellt (Skript lag im Scratchpad der Sitzung).
Nichts behoben — Ben entscheidet. Gegenstück in trainingsapp `docs/offene_fragen.md` § 9.

### Rechnung

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| R24 | `korrektur.py:1074-1080` (`Korrekturstand.korrekturen/anwenden`), `:1083-1098` (`auswahl_aus`) | **`anwenden()` rechnet nicht die gespeicherten Korrekturen, sondern die Vorschläge der Ketten, die ein gespeicherter `beat_index` berührt.** Bestätigt: 100 Schläge, Artefakte bei 30 und 60, Sidecar `set_value 10→700`, `interpolate 30`, `exclude_range 55–70` → praxis_gui-Weg (`anwenden(rec, corrections)`, `analysis_session.py:244`) RMSSD 20,5 ms, `Korrekturstand.anwenden()` 127,8 ms — das 1700-ms-Artefakt bleibt roh, rr[10] 800 statt 700. `set_value` auf einem Schlag ohne Kette fällt weg, `exclude_range` zählt nur mit seinem Startindex (Ketten innerhalb bleiben roh), ein `delete` außerhalb einer Kette ebenso. Für die Auswertungsansicht der trainingsapp ist das der alte `_Zustand`-Weg (deren Sidecars entstehen aus Ketten), aber `ausdauer._hrv_laden` wandte bis trainingsapp 610b4b8 die Sidecar-Korrekturen direkt an — dort ein Rückschritt —, und `korrektur.md:367` verspricht „beide Apps lesen dieselbe Reihe“. **hoch** | `korrekturen()` = gespeicherte Korrekturen **plus** Vorschläge der übernommenen, nicht gespeicherten Ketten (oder gespeicherte unverändert durchreichen, Ketten nur zur Anzeige); Test mit praxis_gui-Sidecar (`set_value`, `exclude_range`) |
| R25 | `korrektur.py:1142-1143` (`korrektur_laden`) | Bei veraltetem Sidecar (R16) werden dessen Korrekturen verworfen, seine **Regeln** (`analyse_regeln` ohne Prüfsummenblick: Malik, Grenzen, `sensor_verwerfung`, `vorauswahl`) bestimmen aber Basis und Vorschläge — der Test schreibt das fest (`alt.uebernommen == vorauswahl(alt.ketten, "sicher")`). Wie der alte App-Weg, aber inkonsequent gegenüber R16. **niedrig** | veraltet → auch Regeln aus der Vorgabe, oder bewusst dokumentieren |

### Dateien und Formate

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| F22 | `docs/geraete/decathlon/hrm_belt/erkundung_2026-10-19_befund.json:3`, `…_roh.jsonl:1`, `runbook_app_mitschnitt.md:49,60`; `docs/geraete/beurer_po60/*.md` (8× `C9:49:AC:1E:4B:00`); `docs/geraete/geraete.md:219` (`24:AC:AC:15:8D:1F`); Doctests `deid.py:270`, `recording.py:691`, trainingsapp `hrv_export.py:51`; `scripts/ble_erkundung.py:358,367` | Mit dem Umzug der Gerätedoku aus dem **privaten** praxis_gui ins **öffentliche** hrv-core stehen reale BLE-Adressen von Praxis-/Testgeräten im Netz; die Bibliothek nennt `adresse` selbst einen Pseudo-Identifikator und leert ihn in `deid`. Die Decathlon-MAC ist zudem das Beispiel in den Doctests. `ble_erkundung.py` schreibt die Adresse in Befund und Rohmitschnitt ohne Hinweis, sie vor dem Ablegen unter `docs/` zu streichen. Gerätekennung, keine Person — Bens Entscheidung. **mittel** | Adressen in der Doku maskieren (`AA:BB:…:00`), Doctest-Beispiele erfinden, Hinweis im Runbook und in `ble_erkundung.py` |
| F23 | `deid.py:277-283` (`geraet_modell`) | Adresse wird nur als letztes Wort erkannt: `"E2:B4:CC:3F:08:44 HRM"` und eine MAC ohne Trenner als einziges Wort (`"E2B4CC3F0844"`, `_SERIENNUMMER` verlangt ≥ 2 Wörter) passieren ungemeldet (nachgestellt). Realistisch selten. Dazu: die trainingsapp ruft `deid` nirgends — ihr Export entfernt nur den Schlüssel `adresse`, Messdateien von vor dem 19.10. mit der MAC in `geraet` und Polar-Geräte-IDs („Polar H10 A1B2C3D4“) verlassen das Gerät (trainingsapp S16/P78). **niedrig** hier | Muster an jeder Wortposition; trainingsapp bindet `geraet_modell` im Export an |

### Tests und Regeln

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| T9 | `deid.py:355`, `ereignisse.py:452/459/464`, `korrektur.py:986/994/995` | mypy meldet 10 Fehler in 3 Dateien — alle aus Commits **vor** dem Bereich (f415963, 4da0444); mypy ist weder in `pyproject.toml` konfiguriert noch in `ci.yml`. Nur Stand. **niedrig** | mypy wie in trainingsapp konfigurieren und in die CI |

### Doku

| # | Ort | Befund |
|---|---|---|
| D12 | `docs/korrektur.md:360-366`; `korrektur.py:1018-1021` (`analyse_regeln`-Docstring), `:1109-1111` (`korrekturstand`-Docstring) | „ohne gespeicherte Regeln (praxis_gui) gilt die Vorauswahl“ stimmt nicht mehr: praxis_gui schreibt seit c306d68 `corrections_meta.regeln` immer, und `analyse_regeln` baut auch aus einem alten `corrections_meta` ohne `regeln` einen `Korrekturregeln`. Ein praxis_gui-Sidecar zählt nie als „ohne Regeln“; mit `corrections: []` gilt „Keine“ → roh. Ergebnis stimmig (praxis_gui rechnet dann ebenfalls roh), nur die Beschreibung ist falsch. **niedrig** |
| D13 | `korrektur.py:519-521` (`_interpolationswerte`-Docstring: „praxis_gui tut das weiter“), `docs/VERGLEICH.md:82` („praxis_gui zeigt … ein Plateau“) | Widerspricht 5a3c97f (`korrektur.md:96-99`: praxis_gui rechnet über `anwenden`, kein Plateau mehr — stimmt, `analysis_session.py:244`). Der Code ist stimmig (`am_rand`, `_interpolationswerte` löscht ohne zwei Anker). **niedrig** |

Geprüft und in Ordnung: raw-v1 `adresse` abwärtskompatibel (`to_dict` schreibt den
Schlüssel nur, wenn gesetzt; alte Dateien byteidentisch; praxis_gui behält ihn beim
Rückschreiben), Marken additiv (`marke_bereinigen` nur `MARKE_FELDER`, endliche Zahlen),
`metadaten_schreiben` ersetzt nur `titel/notiz/ereignisse`; `docs/formate.md`,
trainingsapp `kompatibilitaet.md` und praxis_gui `sensor_hrv.md` nachgezogen. deid:
Weißliste je Format, rekursiv, `adresse` NULL, Sidecar ohne Adressfelder, Unbekanntes
fällt weg; Meldungen `(art, pfad)` passen zu `deid_export.py`/`pruefe_daten.py`.
`korrektur_laden`: Reihenfolge Regeln → Basis → Vorschläge → Sidecar → Auswahl
zeilengleich mit dem alten `_Zustand`-Weg, „Keine“ = roh, veraltet → Vorauswahl, leere
Messung → `None` ohne Ausnahme, Sidecar ohne `malik_threshold` ohne Absturz. Paket
bleibt stdlib + numpy; `ble_erkundung.py` außerhalb, schreibt nur ins gitignorierte
`ausgaben/`, liest 0x2A25 bewusst nicht; HR-Paketzerlegung korrekt.

## Durchsicht 2026-11-10

Nach den Commits `5a3c97f..4abd64c` (Mitschnitt, De-Identifizierung des Mitschnitts, Prototypen
Atemzüge/Atem-HRV/Wiederholungen, Atemlage und Atemband, Zusammenfügen, abgelesene Erholung,
Backup-Journal). Teil der Durchsicht der ganzen trainingsapp (dort `docs/offene_fragen.md`
§ 10). Stand: CI auf `4abd64c` grün; der Commit `b5d870f`, auf den `hrv-core.ref` der App zeigt,
hatte rote CI (Doctest `WdhLive`). Die Tests wurden bei dieser Durchsicht nicht lokal gefahren.
Schwere wie zuvor. *Nachweis* nennt, wie der lesende Agent den Befund belegt hat; selbst erneut
ausgeführt wurde nur das Zusammenfügen überlappender Teile (250 statt 150 Schläge). Nichts
behoben — Ben entscheidet. Nummern nur für diese Durchsicht (1110-nn), keinem Kreis zugeordnet.

| # | Stelle | Befund | Schwere |
|---|---|---|---|
| 1110-01 | `src/hrv_core/frequency.py:379-405` (`atemband`), `:885-908` | **Atemband enthält die Atemfrequenz nicht mehr, wird aber ausgewiesen.** Bei Atemraten über 30/min (f > `F_MAX_HZ` 0,5 Hz; bis 46/min) oder über der halben Schlagfrequenz wird das Band auf `[0,65 f, 0,5]` gekappt: für 40/min `(0,433; 0,5)` — f = 0,667 Hz liegt außerhalb. `hf_atem` ist dann nicht die Atemschwankung, `lf_hf_atem` kommt mit 113,6 heraus; die App zeigt beides als „HF (Atemband)“/„LF/HF (Atemband)“. Ebenso unten: 1,6–2,4/min → Band `(0,04; 1,5 f)` ohne f. Unter Belastung sind 30–46/min normal. Vorschlag: `None`, wenn f nach dem Schnitt nicht im Band liegt. — *Nachweis:* Ja — `freq.py`: `atemrate_pro_min=40` → `atem_band_hz (0.433, 0.5)`, `lf_hf_atem 113.637` | mittel |
| 1110-02 | `src/hrv_core/zusammenfuegen.py:60-116`; Aufrufer `trainingsapp/devices/messlauf.py:249-279` | **Überlappende oder doppelte Teile werden nicht erkannt.** Dieselbe Datei zweimal, ein `…_zusammen.json` zusammen mit einem seiner Teile (die Teile bleiben in der Liste) oder ein nach einem Absturz liegengebliebener Zwischenstand plus die ganze Messung: alle Schläge doppelt, `t_wall_s` springt zurück (nicht monoton), Herzuhr-Dauer verdoppelt. Die App prüft nur `intervall_quelle`. Vorschlag: ablehnen, wenn `start_utc` eines Teils vor dem Wanduhr-Ende des vorigen liegt. — *Nachweis:* Ja — `zus.py`: zwei Teile mit 40 s Versatz und 80 s Länge → Wanduhr nicht monoton, 200 Schläge, Dauer 160 s statt 120 s; `[a, a]` → 200 Schläge | mittel |
| 1110-03 | `src/hrv_core/aufnahme.py` `_journal_anhaengen` (Zähler erst nach `fsync`), `_journal_lesen` (Doppelte nur unmittelbar hintereinander) | **Ein Fehler nach dem Schreiben (fsync: ENOSPC/EIO) verdoppelt Schläge im Backup-Journal.** Die Zeilen stehen schon in der Datei, die Zähler rücken nicht vor; der nächste 15-s-Takt hängt dieselben Schläge noch einmal an. `_journal_lesen` überspringt nur eine Zeile, die der **vorigen** gleicht — ein Stapel ab zwei Schlägen kommt doppelt in die wiederhergestellte Messung (Herzuhr springt zurück). Die laufende Aufnahme und `speichern` sind nicht betroffen, nur die Wiederherstellung nach Absturz. Vorschlag: beim Lesen Schläge mit `t_wall_s` ≤ dem letzten verwerfen oder je Zeile eine laufende Nummer. — *Nachweis:* Ja — `journal.py` (fsync einmal mit `OSError(28)`): 12 Schläge in der Aufnahme, 17 aus dem Backup, `t_s` …8.0, 4.8, 5.6… | mittel |
| 1110-04 | `src/hrv_core/prototyp/atemzuege.py:459-463` (`AtemLive._probe`); App: `trainingsapp/devices/zaehlen.py:1299-1322` | **Nach einer Zeitlücke holt `AtemLive` alle ausgefallenen 5-s-Fenster nach** — `_naechstes_fenster` rückt je Probe nur um 5 s vor, jede der nächsten Proben rechnet ein Fenster (Lomb-Scargle). Die App füttert bewusst über Lücken hinweg; der Schub läuft in der Ereignisschleife und schreibt lauter ungültige Fenster (`zu_wenig_zyklen`) ins Beiwerk. Vorschlag: nach einer Lücke `_naechstes_fenster` auf `t − t_start + SCHRITT_S` vorziehen. — *Nachweis:* Ja (Teilagent, `num/t1.py`, am Rechner): 60 s Lücke → erster 1-s-Rahmen 13 Fenster/262 ms; 600 s → 25 Fenster/545 ms, dann 97 Fenster/2,2 s; 3600 s → 225 Fenster/4,8 s; normal 0,2 ms je Sekunde Daten. Am Handy nicht gemessen | mittel |
| 1110-05 | `src/hrv_core/ekg.py:148-150` (`luecken`), `:309-310` (`Ekg.zeit_s`) | Springt der Gerätezeitstempel zwischen zwei Rahmen zurück, meldet `luecken()` nichts, `zeit_s()` läuft rückwärts, `dauer_s` wird negativ, `ausschnitt` greift falsche Proben. Vorschlag: negativen Sprung als Lücke führen. — *Nachweis:* Rechnerisch ja (`num/t1.py`: `gaps []`, `dauer_s -8.446`); ob der H10 seine Uhr nach Kontaktverlust neu startet, **unbestätigt** | mittel |
| 1110-06 | `src/hrv_core/prototyp/wiederholungen.py:1006-1008` (`_gleitend`), `:1014-1016`; App: `trainingsapp/devices/messlauf.py:2093` | `np.convolve(mode="same")` liefert die Länge des längeren Operanden: ein Satzfenster kürzer als 2 s (2…199 Proben bei 100 Hz) → `zaehlen_fenster` wirft `ValueError` statt 0. Die App schluckt es (`suppress(Exception)`), der Sensor-Vergleichswert im Diagnose-Rückfall fehlt dann still. NaN im Fenster → `LinAlgError` (`:1019`). — *Nachweis:* Ja — selbst nachgestellt: n = 50, 199 → `ValueError operands could not be broadcast … (50,3) (200,3)`; n = 1, 200 → 0 | niedrig |
| 1110-07 | `src/hrv_core/live.py:324-364` (`LiveFenster.dfa_a1`) | Die letzten 200 guten Schläge werden über Nähte hinweg aneinandergehängt: nach einem Wiederverbinden trägt die Stufe zwischen den Stücken den Wert (α1 1,41 statt etwa 0,5 bei Rauschen); `docs/hrv_algorithmen.md:277` nennt nur Artefakte als Ausschluss. Geht an die Uhr (Live-DFA). — *Nachweis:* Ja (Teilagent, `num/t2.py`) | niedrig |
| 1110-08 | `src/hrv_core/herzfrequenz.py:1290-1291` (`intervall_erholung`) | „Letzte Stelle des Plateaus“ ist der letzte Index **irgendwo** im Intervall, der ≤ 0,5 bpm unter dem Höchstwert liegt, nicht der letzte zusammenhängende: zwei fast gleich hohe Spitzen (150 bei 20 s, 149,7 bei 108 s) → Bezug an der zweiten. — *Nachweis:* Ja (`num/t1.py`: `spitze_t 108.5`) | niedrig |
| 1110-09 | `src/hrv_core/herzfrequenz.py:252-254` (`hf_reihe`) | NaN/inf in `t_wall_s` (lässt `laden` durch) → `ValueError`/`OverflowError` aus `math.floor`; `reihe_aus_beats` bricht an einer kaputten Datei ab (wie das erledigte R18). — *Nachweis:* Ja (`num/t1.py`, `t2.py`) | niedrig |
| 1110-10 | `src/hrv_core/herzfrequenz.py:573-599` (`hfmax_kandidat`) | Je Kandidat ein `abgedeckt_s` (O(n)); besteht kein Fenster, quadratisch: 8 h 1,7 s, 24 h 12,5 s am Rechner. — *Nachweis:* Ja (`num/t1.py`) | niedrig |
| 1110-11 | `src/hrv_core/ekg.py:223-224` (`journal_anhaengen`), `:249-259` (`aus_journal`) | Kopf `["k", rate, t_wall_start_s]` wird nur einmal geschrieben — kommt ein Akkustand vor dem ersten Rahmen, bleibt `null` (EKG nach Wiederherstellung bei 0 s); `aus_journal` wirft bei gültigem JSON mit falschem Typ `TypeError`, den die App bei der Wiederherstellung nicht fängt (`messlauf.py:318`: nur `OSError, ValueError`). — *Nachweis:* Ja (`num/t1.py`) | niedrig |
| 1110-12 | `src/hrv_core/prototyp/atemzuege.py:261-267`, `prototyp/wiederholungen.py:447-452` | Eine NaN-Probe vergiftet die laufenden Summen dauerhaft (AtemLive/WdhLive zählen danach still nichts mehr); aus dem PMD-Parser kommen nur Ganzzahlen, also nur über fremde Aufrufer. `atemzuege.py:401`: ein Rücksprung von `t0_s` hält Fenster an, bis die Zeit aufholt (in der App nicht erreichbar). — *Nachweis:* Ja (`num/t1.py`, `t2.py`) | niedrig |
| 1110-13 | `src/hrv_core/prototyp/atemzuege.py:198` gegen `:630-631`; `herzfrequenz.py:1045-1047`; `atem.py:106, :327`, `ekg.py:181`; `geraete/treiber.py:88, :102`; `geraete/gatt.py:183-185` | Kleinigkeiten: `gleichmaessigkeit` rechnet nur über die letzten 8 Abstände statt „aller“ (App liest das Feld nicht); Doctest `trimp_banister` behauptet 60 min, hat eine gültige Sekunde; `json.dump` ohne `allow_nan=False` in `atem`/`ekg` (inf/NaN im Beiwerk); `erkennen("Fitcent CH10 0042")` → `polar_h10` (Teilstring, App ruft es nicht auf); 16-bit-HF mit abgeschnittenem Paket → HF aus einem Byte. — *Nachweis:* Ja (`num/t1.py`, `t2.py`) | niedrig |
| 1110-14 | `src/hrv_core/zusammenfuegen.py:109-116` (`replace(erster, …)`) | Kopf und `extra` kommen nur vom ersten Teil: `datenqualitaet` (steht in jeder gespeicherten Datei ausdrücklich) — ist Teil 1 `bpm_only` (noch kein RR), bleibt die ganze Datei `bpm_only`, obwohl Teil 2 RR hat; das Protokollfeld `atmung` (Teil 1 spontan, Teil 2 getaktet → „spontan“ für alles), `ecg_aufzeichnung`, `batterie_prozent`. Naive `start_utc` neben einer mit Zeitzone → `TypeError` statt `ValueError`. — *Nachweis:* Ja — `zus.py`: `qualitaet: bpm_only`, `extra {'atmung': {'modus': 'spontan'}}`; `naiv: TypeError`. **Teil behoben 11.11.2026:** `atmung` nur bei Gleichstand aller Teile, `ecg_aufzeichnung` immer `false`; **Rest behoben 11.11.2026 (Ben: nur gleiche Aufnahmen):** `datenqualitaet` aus den Schlägen aller Teile, `batterie_prozent` vom letzten Teil, verschiedene `intervall_quelle` und gemischte Zeitzonen → `ValueError`. | niedrig |
| 1110-15 | `src/hrv_core/deid.py` `MITSCHNITT_REGELN` (`kopf.geraet.info`, `dienste`, `stroeme`, `marken`, `kontext.wert`: `KEEP`), `_anwenden` (Regeln `ADRESSE`/`PROTOKOLL`: Nicht-Text unverändert zurück) | **Die Weißliste ist an Behälterfeldern keine:** `KEEP` lässt ganze Objekte ungeprüft durch — ein `info.seriennummer`, ein Wert im Dienste-Abbild, ein Objekt unter `kontext.wert` oder ein Objekt statt Text in `v.text`/`grund`/`fehler` verlassen das Gerät, obwohl der Modultext „jedes unbekannte Feld fällt weg (rekursiv)“ verspricht. Heute schreibt die App dort nichts Kritisches (`GERAETEINFO` ohne Seriennummer) — latent. Dazu: `c` als Kurzform (`"2A25"`) wird nicht als Kennungsmerkmal erkannt (nur volle UUID). Vorschlag: `info` als Weißliste der fünf Schlüssel, `dienste` auf `uuid/name/merkmale/eigenschaften`, bei `ADRESSE`/`PROTOKOLL` Nicht-Text verwerfen. — *Nachweis:* Ja — `deid1.py`: `info.seriennummer`, `dienste[].merkmale[].wert`, `v.text = {"lat":…}`, `kontext.wert = {"gps":…}`, `r` mit `c="2A25"` kommen unverändert heraus | niedrig |
| 1110-16 | `src/hrv_core/deid.py:84-89` (`ADRESSE_IM_TEXT`) | Adressen ohne Doppelpunkt/Bindestrich bleiben im Protokolltext stehen: BlueZ-Pfad `dev_E2_B4_CC_3F_08_44` (bleak unter Linux, Fehlertexte) und `e2b4cc3f0844`. Für den Gerätenamen als F23 bekannt, für `v.text`/`fehler` neu. Nur Desktop. — *Nachweis:* Regex bestätigt (`deid1.py`); ob bleak den Pfad in Fehlertexte schreibt, unbestätigt | niedrig |
| 1110-17 | `src/hrv_core/mitschnitt.py:287-297` (`_anhaengen`) | „Ein Fehler beim Schreiben geht nie an den Aufrufer“ gilt nur für `OSError`/`ValueError`: ein nicht serialisierbarer Wert (`np.int64`, `bytes`) wirft `TypeError` aus `json.dumps` in den Aufrufer (Ereignisschleife der App), `fehler` bleibt 0. Nach einem halb geschriebenen Stück (Platte voll) hängt die nächste Zeile ohne Zeilenumbruch an — beide verloren. — *Nachweis:* Ja — `deid1.py`: `kontext(wert=np.int64(3))` → `TypeError`, `s.fehler == 0` | niedrig |
| 1110-18 | `src/hrv_core/ausschnitte.py` `Abschnitt.rechenbereich` | Ein negativer Kopf, der länger ist als der Abschnitt (`Abschnitt(600, 1800, kopf_s=-1500)`), wird nicht „gekappt“, sondern schiebt den Rechenbereich **hinter** den Abschnitt (`von = 2100`, `bis = von + MIN`). — *Nachweis:* Nachgerechnet am Code, nicht ausgeführt | niedrig |
