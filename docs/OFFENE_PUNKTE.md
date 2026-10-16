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
| R10 | praxis_gui `analysis_service.py:284-286` | liest `r.get("mean_bpm")`, `respiration_summary` liefert `resp_rate_mean` → `resp_rate_bpm` im Neuberechnungspfad nie gesetzt | Bug; nach Umzug |

## Dateien und Formate

| # | Ort | Befund | Vorschlag |
|---|---|---|---|
| F1 | praxis_gui `widget.py:8093-8121`, `main.py:2286` | Crash-Backup trägt `hrv`-Block (`_scope: live_window`); die Wiederherstellung schreibt ihn unverändert in die Messdatei — Doku sagt „raw-v1 ohne hrv“ | Wiederherstellung soll den Block entfernen |
| F2 | praxis_gui `widget.py:7057` | fünfter raw-v1-Schreiber (Begleitgerät): Herkunftsfelder nicht über `_herkunft_felder`, `simulation` fest False; CLAUDE.md und `tests/test_geraete_provenienz.py:6` zählen „vier“ | Doku/Test nachziehen; Phase 3: alle Schreiber über `hrv_core.recording` |
| F3 | praxis_gui `analysis.py:1346-1410` | schreibt Titel/Notiz/Ereignisse in die Rohdatei ohne Sidecar-SHA, nicht atomar | Phase 3 |
| F4 | praxis_gui `analysis_io.py:653` `crop_file_inplace` | verankert Ereignisse nicht neu; im Programm unbenutzt | entfernen oder reparieren |
| F5 | praxis_gui / trainingsapp | Dateinamen: lokale Stoppzeit vs. UTC-Start; Backup in praxis_gui nach UTC mit `_1` bei Doppelung | **entschieden 2026-10-16: UTC-Start** (wie trainingsapp); praxis_gui in Phase 3 |
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
| T4 | praxis_gui `pyproject.toml` | `astropy` im Extra `hrv`, nirgends importiert | entfernen |

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
