# Dateiformate, die hrv-core liest und schreibt

Stand 19.10.2026. Die maßgeblichen Verträge liegen bei den Apps:
`praxis_gui/docs/sensor_hrv.md` (Feldreferenz `raw-v1`, Schreiber) und
`trainingsapp/docs/kompatibilitaet.md` (Abgleich beider Apps, Erweiterungen).
Diese Seite ist der Index aus Sicht der Bibliothek: welches Modul welches Format
anfasst und welche Felder hrv-core selbst setzt. Die maschinenlesbare Fassung
ist die Weißliste `hrv_core.deid.REGELN` — sie muss jedes Feld kennen, das hier
steht; was sie nicht kennt, entfernt `deid.deidentifizieren` und lehnt
`deid.pruefen` ab (Befund F12).

> Eine Formatänderung ist eine neue Schema-Version oder ein zusätzliches,
> optionales Feld — nie ein stilles Umdeuten (CLAUDE.md). Neue Felder zuerst im
> Vertrag der trainingsapp eintragen, dann hier und in `deid.REGELN`.

## `raw-v1` — Messdatei `sensor_<UTC-Start>.json`

Modul `recording` (`Recording.to_dict`/`from_dict`, `laden`, `speichern`), Schreiber
während der Aufnahme `aufnahme.Aufnahme`. Feldfolge wie der Schreiber von praxis_gui.

| Feld | Von hrv-core gesetzt | Anmerkung |
|---|---|---|
| `behandlung_id`, `patient_id` | ja (vom Aufrufer, sonst `null`) | Personenfelder — `deid` leert sie |
| `datum` | ja | **Ortsdatum** des Starts (Vertrag §7) |
| `geraet`, `geraet_profil`, `intervall_quelle` | ja | `geraet` = BLE-Name, meist mit Seriennummer (`deid.geraet_modell` kürzt; eine Adresse als Name wird `Unbekannt`) |
| `adresse` | nur wenn bekannt (seit 19.10.2026) | BLE-Adresse des Geräts (MAC, auf macOS/iOS UUID), getrennt vom Namen — Pseudo-Identifikator, `deid` leert sie; Dateien ohne Adresse haben den Schlüssel nicht |
| `datenqualitaet` | ja | Erweiterung der trainingsapp: `rr_ekg`, `ppi_optisch`, `bpm_only` (`Recording.effektive_qualitaet`) |
| `simulation`, `generator_config` | ja | Synthetik liegt unter `Messungen/Generator` (`messordner`) |
| `schema`, `analyzed` | wie gelesen; neu `raw-v1`/`false` | Altdateien ohne `schema` bleiben ohne (F16) |
| `start_utc` | ja | `YYYY-MM-DDTHH:MM:SSZ`; bestimmt den Dateinamen (`messdatei_name`) |
| `batterie_prozent`, `ecg_aufzeichnung`, `ppg_aufzeichnung` | ja | |
| `ppi_pakete` | nur Geräte mit PPI | Vertrag 3b; `ppi.py` leitet daraus Zeitachse, Nähte, Wiederaufnahme ab |
| `titel`, `notiz` | ja | Freitext; `ereignisse.metadaten_schreiben` darf nur diese und `ereignisse` ändern |
| `ereignisse[]` | ja | Notizanker (`ereignisse.py`): `beat_index`, `dt_s`, `t_wall_s`, `t_s`, `wall_time`, `text`; Erweiterungen `uebungen[]` (Kurzcodes) und `marke` (`MARKE_FELDER`: `quelle`, `art`, `spur`, `einheit`, `name`, `runde`, `von`, `zaehlt`, `soll_s`, `profil`, seit 19.10.2026 `feld` und `wert` für `person/leistung`); alt: `chart_x` |
| `messungen[]` | ja | `t_s` (Herzuhr), `t_wall_s`/`tw_src` (Wanduhr, `m`/`r`/`g`), `hf_bpm`, `rr_ms` |
| `hrv`, `quality` | nein (alte praxis_gui-Dateien) | bleiben über `extra` erhalten |

Unbekannte Felder überleben einen Round-Trip (`Recording.extra`). Beim Schreiben
wird eine vorhandene Datei nie ersetzt (`recording.freier_pfad`: `_1`, `_2` …).
Dateinamen mit `_analyzed`, `_ecg`, `_ppg`, `_truth` und `__cNN` sind keine
Messdateien (`ist_messdatei`).

## Crash-Backup `.backup_<UTC-Start>.json`

`aufnahme.Aufnahme.backup` / `backup_lesen`: eine `raw-v1`-Datei plus den Block
`_wiederherstellung` (App-Zusatz: `subject_id`, `grenzen`, `spuren`), den
`backup_lesen` wieder entfernt. Nur `.backup_*`-Dateien tragen ihn; `deid`
entfernt ihn ganz.

## `corrected-v1` — `sensor_<ts>__cNN.json`

Nur gelesen (`Recording.from_dict`, ohne `t_wall_s`). Wird von hrv-core nicht geschrieben.

## `analysis-v1` — Sidecar `sensor_<ts>_analyzed.json`

`korrektur.analyse_speichern`/`analyse_lesen`, `ausschnitte.zusatz_speichern`/`zusatz_lesen`,
`ereignisse.metadaten_schreiben` (frischt nur `source_file_sha1` auf). Ein
vorhandenes Sidecar wird **fortgeschrieben**, fremde Felder (praxis_gui) bleiben.

| Feld | Von hrv-core gesetzt | Anmerkung |
|---|---|---|
| `schema`, `source_file`, `source_file_sha1`, `updated_utc` | ja | Prüfsumme der Messdatei; `korrektur.sidecar_veraltet` / `Sidecar.veraltet` sagen, ob sie noch passt (R16) |
| `corrections[]` | ja | `op` (`interpolate`, `delete`, `exclude_range`; gelesen auch `set_value`, `split`, `merge`), `beat_index`, `t_s`, `original_value_ms`, `unsicher`, `beat_index_end` … — Indizes der **Rohdatei** |
| `corrections_meta` | ja | `malik_threshold`, `corrections_total`, `corrections_by_op`, `rr_min_ms`, `rr_max_ms`, `interpolate_zeros`; Erweiterung `regeln` (`Korrekturregeln.als_dict`) |
| `corrections_ppi[]` | nur bei Wiederaufnahme | Erweiterung: Korrekturen in der Analysebasis (`sensor_verwerfung = "selbst"`) |
| `rr_corrected[]` | ja | `t_s`, `rr_ms`, `flag` |
| `active_crop` | ja | `t_start_s`, `t_end_s` auf der Herzuhr der Rohdatei |
| `segments[]` | ja | `id`, `name`, `t_start_s`, `t_end_s` (bei Crop relativ zu dessen Anfang), `color`, `metrics`, `computed_utc`, `active`, `visible`; `gesamt` legt praxis_gui an; je Segment wird das gelesene Objekt fortgeschrieben (F11) |
| `metric_selection`, `rolling_*`, `frequency_summary`, `nonlinear_summary`, `neurokit2_hrv_*`, `ecg_qualitaet`, `ecg_morphologie` | nein (praxis_gui) | bleiben erhalten |

## Nur gelesen oder nur geprüft

| Format | Datei | hrv-core |
|---|---|---|
| `truth-v1` | `sensor_*_truth.json` | Sollwerte des Generators — `deid.TRUTH_REGELN`, Golden-Tests |
| EKG | `sensor_*_ecg.json` | `sample_rate_hz`, `uv[]`, `gaps`, `frame_offsets`, `frame_sample_counts` — nur `deid` |
| PPG | `sensor_*_ppg.json` | `sample_rate_hz`, `kanaele`, `kanal_namen`, `werte[]`, … — nur `deid` |
| `sitzung-v1` | `Messungen/Sitzungen/sitzung_*.json` | Mehrgeräte-Sitzung aus praxis_gui: `teilnehmer[]` mit `geraet`, `adresse` (BLE-MAC, `deid` leert), `geraet_profil`, `intervall_quelle`, `ordner`, `datei`, `n_schlaege` — nur `deid` |

## Offen (D10)

Die Feldreferenz in `praxis_gui/docs/sensor_hrv.md` kennt `datenqualitaet`,
`uebungen`, `marke` und `corrections_ppi` noch nicht; die Kompatibilität ist
gegeben (optionale, flache Felder, praxis_gui behält sie beim Bearbeiten). Der
Nachtrag dort gehört in das praxis_gui-Repo.
