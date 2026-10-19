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
| R8 | trainingsapp `constants.py` | ungenutzt: `WELCH_OVERLAP` (Overlap fest `n−n//2`), `DFA_DETREND_BOX`, `RECOMMENDED_BEATS_FREQUENCY`, `SAMPEN_MAX_BEATS_LIVE` (nur Docstring; UI deckelt bei 3000) | beim Umzug bereinigen (keine Zahl ändert sich) |
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
| F5 | praxis_gui / trainingsapp | Dateinamen: lokale Stoppzeit vs. UTC-Start; Backup in praxis_gui nach UTC mit `_1` bei Doppelung | **erledigt**: UTC-Start in beiden Apps (praxis_gui Phase 3, 2026-10-16) |
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
| R15 | `frequency.py:860-905` `fensterspektrum` | **Kein Längendeckel:** 8-h-Fenster (34 000 Schläge) → `_lombscargle` legt N×256-Matrizen an, 488 MB Spitze, 16 s (bestätigt, tracemalloc) — am Handy OOM. Zudem greift dort `MAX_GRID_BINS` (df gröber als 1/T), genau der Fehler, den ALGO 5 für die Gesamtmessung behob (R7). Die App leitet heute „Alles“ und Abschnitte > `LANG_AB_S` über `frequenzbereich`/`abschnitt_spektrum` um, der Live-Puffer ist 30 min — die Bibliothek selbst schützt nicht. **mittel** | ab `LANG_AB_S` auf `frequenzbereich(mindestdauer=False)` umleiten oder `None` |
| R16 | `korrektur.py:877, 900-926` (`analyse_laden`), `ausschnitte.py:318`, `ereignisse.py:423` | `source_file_sha1` wird geschrieben und aufgefrischt, aber **nirgends geprüft** (hrv-core und trainingsapp, grep). Ein Sidecar einer anderen oder nachträglich veränderten Messdatei wird per `beat_index` angewandt: Indizes ≥ n fallen still weg (`anwenden`:588), kleinere treffen falsche Schläge (bestätigt: `interpolate 42` aus fremdem Sidecar ersetzt einen gesunden Schlag). **mittel** | in `analyse_laden` Hash vergleichen; bei Abweichung Sidecar als veraltet melden (wie praxis_gui) |
| R17 | `time_domain.py:261-264` | Ergänzung zu R2, wirksam: `compute_time_domain([800, 810], breaks=[1])` → `rmssd 0.0, pnn 0.0, n_diffs 0`; `ausschnitte.abschnitt_werte:465` zeigt für einen kurzen Abschnitt mit Naht RMSSD 0. `trends._wert` und `live._zeitbereich` sind per `min_diffs` geschützt. **mittel** | `None` bei `n_diffs == 0`, `ALGO_VERSION` hoch |
| R18 | `frequency.py:463` `_mittelreihe` | NaN in `t` → `astype(int)` → `np.bincount` wirft `ValueError` (bestätigt). Erreichbar über `vlf_fenster:932` (Maske prüft nur `rr`, nicht `t`) und `_teilspektrum_lang`; `Beat.from_dict` lässt NaN durch (Pythons `json.loads` akzeptiert `NaN`). Nur bei kaputter Datei. **niedrig** | Maske auch auf `t` |
| R19 | `nonlinear.py:345` `sd1_sd2` | `sd2` als Rundungsrest (8,4·10⁻⁸) → Verhältnis 8,4·10⁷ (bestätigt mit Wechselfolge [800, 810]·60). Schwelle `sd2 > 0` ohne Toleranz; praktisch nur bei künstlich regelmäßigen Reihen. **niedrig** | `sd2 > eps·sdnn` |
| R20 | `frequency.py:531-532` `_teilspektrum_lang` | fehlt ULF- oder VLF-Teilspektrum, werden Nullen eingesetzt → `integriere_band` 0,0 statt `None`; durch Bandpolitik und Mindestlänge kaum erreichbar (plausibel). **niedrig** | `None` durchreichen |
| R21 | `korrektur.py:511-514` `_interpolationswerte` | Artefakt am Anfang/Ende mit nur einem Anker → Plateau-Kopie des Nachbarn (bestätigt: 3000 ms an Index 0 → 800); ohne Anker bleibt der Rohwert mit Flag `interp` (bestätigt `[3000,3000,3000]`) und wird erst vom Plausibilitätsfilter verworfen — ein Malik-Ausreißer innerhalb 250–2000 ms zählte mit. praxis_gui-gleich; „lieber Lücke“ wäre `delete`. **niedrig** | mit praxis_gui entscheiden |
| R22 | `trends.py:463-468` `verlauf` | filtert implausible Werte nicht selbst (bestätigt: 100×0 ms → RMSSD 0,0; −800 → 0,0); verlässt sich auf `trends.reihe`/`live.verlaufsreihe`. **niedrig** | Vorbedingung dokumentieren oder filtern |
| R23 | `frequency.py:544-546` | Rasterkanten fließkommaempfindlich: 0,15 Hz liegt im 1/300-Raster bei 0,15000000000000002 (zählt zu HF), 0,4 bei 0,4000000000000001 (fällt aus HF). Kein Fehler, dokumentiert. **niedrig** | `np.isclose` an den Kanten |

### Dateien und Formate

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| F10 | `recording.py:364-372` `speichern`, `aufnahme.py:237-249` | **Vorhandene `sensor_<ts>.json` wird stillschweigend ersetzt** (`os.replace`); praxis_gui hängt bei Namensgleichheit `_1` an. Zwei Aufnahmen mit gleicher UTC-Startsekunde im selben Geräteordner (Simulator/Generator, zweiter Start nach Fehler mit übernommenem `start_utc`) → die erste Messung ist weg, ohne Fehler (bestätigt). `backup_wiederherstellen` in der App schützt sich selbst mit `exists()`, die Bibliothek nicht. **hoch** | Zähler wie praxis_gui oder `FileExistsError` |
| F11 | `ausschnitte.py:327-343` `zusatz_speichern` | Ersetzt alle `segments` außer `gesamt` und schreibt feste `metrics: None, computed_utc: None, active: True, visible: True`; praxis_gui wertet `active`/`visible` aus (`analysis_session.py:215`, `workbench.py:2540`). In praxis_gui einen Abschnitt deaktiviert, danach in der trainingsapp Crop gespeichert (`messung_detail.py:1080`) → Abschnitt wieder aktiv und sichtbar, praxis_gui-`metrics` und jedes weitere Segmentfeld weg (bestätigt). Verschärft trainingsapp H5. **mittel** | je Segment das gelesene Dict fortschreiben, nur `name/t_start_s/t_end_s/color` setzen |
| F12 | `deid.py:239-241, 281-288, 346-351` | **De-Identifizierung nicht vollständig gegenüber dem Schreibpfad:** ohne Ablehnung oder Hinweis passieren `ereignisse[].marke.name` (Freitext aus dem Timerprofil), `geraet` (BLE-Name mit Seriennummer — Pseudo-Identifikator über Dateien hinweg), `_wiederherstellung.subject_id` (Profil-ID in `.backup_*.json`, die `rglob("*.json")` mit erfasst), verschachtelte `teilnehmer[].patient_id`/`adresse` (BLE-MAC) in `sitzung-v1`, jedes unbekannte Top-Level-Feld (`extra` wird durchgereicht). `deidentifizieren` leert nur Top-Level `patient_id`/`behandlung_id` (bestätigt: Datei mit allen Feldern → 0 Ablehnungen, 0 Hinweise). **hoch** | Weißliste je Feld statt Schwarzliste; `extra` und verschachtelte Strukturen rekursiv prüfen; `geraet` auf Modell kürzen |
| F13 | `deid.py:212-219`, `scripts/deid_export.py:9` | `start_utc`, `datum`, `wall_time` und der Dateiname (UTC-Startsekunde) bleiben bewusst erhalten — zusammen mit dem Praxiskalender re-identifizierend. Dokumentiert, kein Codefehler. **mittel** | als Risiko in `pruefen` benennen; Zeitversatz je Person erwägen |
| F14 | `recording.py:80-89, 237`, `aufnahme.py:290-298` | `Beat.from_dict`: `d["t_s"]` → `KeyError`, Eintrag `None`/String → `AttributeError`, `"x"` → `ValueError`; `laden()` wirft vier Ausnahmetypen statt eines Formatfehlers; `backup_lesen` fängt nur `JSONDecodeError` → Backup mit kaputtem Messwert bricht die Wiederherstellung ab (bestätigt). **mittel** | `FormatFehler` in `laden`/`backup_lesen` |
| F15 | `recording.py:262` | `list(doc.get("ereignisse") or [])`: ist `ereignisse` ein dict oder String, entsteht eine Liste von Schlüsseln/Zeichen, die beim nächsten Speichern zurückgeschrieben wird — Korruption statt Fehler (bestätigt, unwahrscheinlich). **niedrig** | Typ prüfen |
| F16 | `recording.py:188-189, 214-235` | `analyzed` und `schema` gelten als bekannt, werden aber nicht übernommen; `to_dict` schreibt immer `schema: raw-v1`, `analyzed: False`. Round-Trip einer Altdatei (Fixture `sensor_2026-04-24_204808.json`) behauptet `raw-v1` und trägt den Legacy-`hrv`-Block; `test_round_trip_verliert_nichts` prüft nur Messwerte (bestätigt). Heute nur über `backup_wiederherstellen` erreichbar. **niedrig** | Kopf übernehmen, Test auf den Kopf ausdehnen |
| F17 | `recording.py:177-181, 372`, `aufnahme.py:106` | `start_utc=None`: `dateiname()` und `to_dict()` nehmen zwei `datetime.now(UTC)` (Sekundengrenze → Dateiname ≠ Kopf); `to_dict` leitet `datum` aus dem UTC-Datum ab, `Aufnahme` aus dem Ortsdatum (Vertrag §7: Ortsdatum). **niedrig** | einmal `jetzt` ziehen, Ortsdatum |
| F18 | `ereignisse.py:97-101` `marke_bereinigen`, `recording.py:326-330` | NaN/Infinity passieren; `json.dump` schreibt `NaN`/`Infinity` — kein gültiges JSON für strikte Parser (bestätigt). **niedrig** | `allow_nan=False` in `json_atomar_schreiben`, `math.isfinite` in `marke_bereinigen` |
| F19 | `recording.py:333` | kein `fsync` des Verzeichnisses nach `os.replace`; auf Android/ext4 kann der Rename bei Stromausfall verloren gehen (Inhalt der `.tmp` ist gesichert). **niedrig** | `os.fsync` auf den Ordner |
| F20 | `recording.py:29` | `DATEINAME_MUSTER` ungenutzt und würde praxis_guis `sensor_<ts>_1.json` ablehnen, die `ist_messdatei` korrekt akzeptiert. **niedrig** | entfernen |
| F21 | `ereignisse.py:411-413` | Fehlt `titel` in einer Altdatei, landet es nach `metadaten_schreiben` hinter `messungen` — wie praxis_gui, kosmetisch. **niedrig** | — |

### Tests und Regeln

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| T5 | Repo | **Kein CI-Workflow** (`.github/` enthält nur `dependabot.yml`); der Stand auf main ist nicht ruff-sauber (16 Meldungen: EXE001 ×4 in `scripts/`, RUF100 ×3, TRY004 ×2, I001 ×2, F401, C401, C408, ISC004, RUF046; 12 Dateien unformatiert), obwohl CLAUDE.md `ruff check` und `ruff format --check` verlangt. **mittel** | Workflow wie trainingsapp `ci.yml` (ruff, pytest, Referenz als eigene Matrix), einmal `ruff format` |
| T6 | `tests/golden/`, `tests/test_frequenz.py:275` | Kein Golden für den langen Weg (ALGO 5): längste Fixture 2640 s < `LANG_AB_S` 4000 s; `_spektrum_lang`, `_lomb_hann`, `_mittelreihe`, `vlf_fenster`, ULF nur mit 10 % Toleranz gedeckt. Ohne Golden auch `spektrogramm`, `spektralprofil`, `live.LiveFenster`, `zeitachse.Kontinuitaetsuhr`, trends `vlf_power`/`gipfel`/`rsa`/`hf_rr`, `atmung.median` direkt. **mittel** | synthetische > 4000-s-Fixture ins Golden |
| T7 | `tests/referenz/` | fehlen: Zeitbereich/Poincaré gegen nk2 `hrv_time` (Abweichungen ddof/pNN50 als Beleg), `_lomb_hann` gegen `scipy.signal.lombscargle` mit gefensterten Werten; Malik und Atmung haben kein Pendant. SampEn-Referenz bewusst 2 % (R1). **niedrig** | ergänzen |
| T8 | `scripts/vergleich_praxis_gui.py:227-228`, `golden_erneuern.py` | `a['n_beats']`, `a['roh']` ohne Absicherung; `golden_erneuern` schreibt nicht atomar (Dev-Skripte). **niedrig** | — |

### Doku

| # | Ort | Befund |
|---|---|---|
| D9 | `docs/hrv_algorithmen.md:109, 386-388, 575, 658-662, 695` | verweist auf `tests/test_korrektur_regeln.py` (gibt es hier nicht), auf `test_atmung_byteidentisch` (nur im Docstring, keine Testfunktion, `PRAXIS_GUI_PFAD` nirgends), auf einen Deckel „höchstens 2000 Minutenfenster“ (in `atmung.fenster/median` nicht vorhanden; 8 h → 1922 Fenster, 2,1 s; 24 h ≈ 5800), auf `tests/golden/rr/` (hier `tests/fixtures` + `tests/golden/trainingsapp`) und auf einen nk2-Vergleich in `tests/test_nichtlinear.py` (liegt in `tests/referenz`). |
| D10 | `praxis_gui/docs/sensor_hrv.md`, hrv-core `docs/` | Feldreferenz raw-v1 kennt weder `uebungen`, `marke`, `datenqualitaet` noch `corrections_ppi`; hrv-core hat keinen eigenen Formatvertrag. Kompatibilität selbst ist gegeben (Felder optional, flach, praxis_gui behält sie; trainingsapp `kompatibilitaet.md` §4/§6a/§9b aktuell). |
| D11 | `constants.py` | R8 weiter offen: `WELCH_OVERLAP`, `DFA_DETREND_BOX`, `RECOMMENDED_BEATS_FREQUENCY` ungenutzt; `SAMPEN_MAX_BEATS_LIVE` inzwischen in `spektralprofil.py:33` genutzt. |
