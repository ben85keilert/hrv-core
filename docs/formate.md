# Dateiformate, die hrv-core liest und schreibt

Stand 5.11.2026. Die maßgeblichen Verträge liegen bei den Apps:
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
| `atmung` | nein (trainingsapp, seit 5.11.2026) | Protokollfeld „Atmung“ (P125, Vertrag §3/§5 der trainingsapp): `{"art": "spontan" \| "getaktet" \| "uebung", "takt_pro_min": 6.0, "uebung": "<Kurzcode>"}` — `takt_pro_min` nur bei `getaktet`, `uebung` nur bei `uebung`; fehlt = unbekannt (Altdateien). Bleibt über `extra` erhalten, `deid` behält es als Ganzes |
| `titel`, `notiz` | ja | Freitext; `ereignisse.metadaten_schreiben` darf nur diese und `ereignisse` ändern |
| `ereignisse[]` | ja | Notizanker (`ereignisse.py`): `beat_index`, `dt_s`, `t_wall_s`, `t_s`, `wall_time`, `text`; Erweiterungen `uebungen[]` (Kurzcodes) und `marke` (`MARKE_FELDER`: `quelle`, `art`, `spur`, `einheit`, `name`, `runde`, `von`, `zaehlt`, `soll_s`, `profil`, seit 19.10.2026 `feld` und `wert` für `person/leistung`, seit 27.10.2026 `kopf_s`/`endteil_s` an der Start-Notiz eines Abschnitts — Rechenbereich über die Grenzen hinaus (positiv) oder innerhalb (negativ); ein eigener Abschnitt der Person ist ein Paar `person/abschnitt` + `person/ende` mit `spur` = Kennung `seg-…`, `ausschnitte.paare_aus_notizen`; seit 29.10.2026 `kontext`/`haltung` an `person/erholung` — Ende einer Belastung, woran und in welcher Haltung die Person sich erholt, `herzfrequenz.hrr_erholung`); alt: `chart_x` |
| `messungen[]` | ja | `t_s` (Herzuhr), `t_wall_s`/`tw_src` (Wanduhr, `m`/`r`/`g`), `hf_bpm`, `rr_ms` |
| `hrv`, `quality` | nein (alte praxis_gui-Dateien) | bleiben über `extra` erhalten |

Unbekannte Felder überleben einen Round-Trip (`Recording.extra`). Beim Schreiben
wird eine vorhandene Datei nie ersetzt (`recording.freier_pfad`: `_1`, `_2` …).
Dateinamen mit `_analyzed`, `_ecg`, `_ppg`, `_truth`, `_atem` und `__cNN` sind keine
Messdateien (`ist_messdatei`), Endungen außer `.json` ebenso (`_mitschnitt.jsonl`).

## Crash-Backup `.backup_<UTC-Start>.json` + `.jsonl`

`aufnahme.Aufnahme.backup` / `backup_lesen` / `backup_entfernen` — seit 28.10.2026 **Kopf
und Journal** (lange Aufnahmen: vorher wurde alle 15 s die ganze Datei neu geschrieben,
11 MB bei 36 h):

- **Kopf** `.backup_<Start>.json`: die `raw-v1`-Datei **ohne** `messungen` (und mit leerem
  `ppi_pakete`, wenn das Gerät PPI liefert), plus `_wiederherstellung` (App-Zusatz:
  `subject_id`, `grenzen`, `spuren`) und `_journal` (der Name des Journals). Atomar, nur
  bei Änderung neu geschrieben (Titel, Notizen).
- **Journal** `.backup_<Start>.jsonl`: eine Zeile je Eintrag, angehängt und mit `fsync`
  abgeschlossen — `["b", {Messung wie in messungen[]}]` bzw. `["p", {PPI-Paket}]`. Eine
  halbe Zeile (Absturz beim Schreiben) überspringt `backup_lesen`; eine doppelte Zeile
  direkt hintereinander ebenso.
- `backup_lesen` setzt beides zusammen; ein Kopf **mit** `messungen` (Backup von vor dem
  Journal, praxis_gui) wird weiter gelesen. `_wiederherstellung` und `_journal` tragen nur
  `.backup_*`-Dateien; `deid` entfernt sie.
- **Begleit-Journale** am Stamm des Kopfs: `.backup_<Start>_ecg.jsonl` (EKG, `ekg`),
  `.backup_<Start>_atem.jsonl` (Atemphasen, `atem`, seit 5.11.2026) und
  `.backup_<Start>_mitschnitt.jsonl` (Rohmitschnitt, `mitschnitt`). `backup_entfernen` löscht
  sie mit (seit 0.6.0) — wer eines behalten will, macht vorher daraus das Beiwerk der
  Messdatei. Das EKG-Journal schreibt seit 0.6.0 wie das der Schläge: `fsync`, eine halbe
  Zeile wird abgeschlossen, ein neuer Pfad bekommt alles samt Kopf.

## Zusammenfügen `sensor_<ts>_zusammen.json`

`zusammenfuegen.zusammenfuegen` / `python -m hrv_core.zusammenfuegen a.json b.json`: Teile
einer Aufnahme („Teil speichern & weiter“) als eine `raw-v1`-Datei. Wanduhr über den Start
des ersten Teils (Lücken bleiben Lücken), Herzuhr zählt weiter, Notizen rücken mit
(`beat_index`, `t_s`, `t_wall_s`), an jeder Naht eine Notiz „Teil n“ mit Marke
`{"quelle": "zusammenfuegen", "art": "teil", "teil": n}`.

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
| `segments[]` | ja | `id`, `name`, `t_start_s`, `t_end_s` (bei Crop relativ zu dessen Anfang), `color`, `metrics`, `computed_utc`, `active`, `visible`; `gesamt` legt praxis_gui an; je Segment wird das gelesene Objekt fortgeschrieben (F11); Erweiterung `rand` (`kopf_s`, `endteil_s`, nur wenn gesetzt — praxis_gui behält es nicht, die Wahrheit ist die Marke der Start-Notiz) |
| `metric_selection`, `rolling_*`, `frequency_summary`, `nonlinear_summary`, `neurokit2_hrv_*`, `ecg_qualitaet`, `ecg_morphologie` | nein (praxis_gui) | bleiben erhalten |

## `mitschnitt-v1` — Rohmitschnitt `sensor_<ts>_mitschnitt.jsonl`

`mitschnitt` (`Schreiber`, `lesen`, `laden`, `stroeme`, `zusammenfassen`), seit 0.6.0 (Plan
Diagnosemodus der trainingsapp, 4.11.2026). Jedes Bluetooth-Paket einer Aufnahme roh, dazu
Kommandos, Verbindungsereignisse, Uhrpaare, Zustandsproben, Diagnosemarken und Kontext.
Ein Format für die trainingsapp (Diagnosemodus), die Brustgurt-Diagnose in hrv-research und
später praxis_gui (`rohlog`). JSON Lines, nur angehängt, jede Zeile `{"art": …, "t": …}` mit
`t` = monotone Uhr der App in ns:

| `art` | Felder |
|---|---|
| `kopf` | `format` (`mitschnitt-v1`), `app`, `version`, `plattform`, `start_utc`, `wall_ns`, `messdatei`, `aufnahme` {`start_mono_ns`: Nullpunkt der Messung auf der Uhr der Zeilen, `t_wall_s = (t − start_mono_ns)/1e9`; `start_utc`} (seit 0.6.1), `geraet` {`name`, `id` (Adresse), `profil`, `art`, `info`}, `stroeme` (gewählt, mit Einstellungen, etwa `{"acc": {"rate_hz": 200, "bereich_g": 8}}`), `dienste` (Abbild), `marken` |
| `n` | Benachrichtigung: `c` Merkmal (Kürzel `hr`, `pmd_ctrl`, `pmd_data`, `akku`, `info_*` oder UUID), `x` Hex, vom Transport `s` (Folgenummer), `tm` (µs, monotone Uhr der Dart-Seite), `tw` (µs, Wanduhr der Dart-Seite) |
| `w` | Kommando: `c`, `x`, `a` (mit Antwort) |
| `r` | Lesen: `c`, `x` oder `fehler` |
| `v` | Verbindung und Protokoll: `text`, `q` (Quelle), wahlweise `zustand`, `grund`, `code` |
| `uhr` | alle 10 s: `utc`, `wall_ns` zur Zeit `t` (auch nach einem Neustart der App) |
| `probe` | `akku`, `akku_handy`, `laedt`, `bildschirm`, `verzug_ms`, `verzug_spitze_ms`, `pakete`, `mb` |
| `marke` | `id` (laufend je Datei), `typ` (`wdh`, `atem`, `stoerung`, `marke`), `quelle` (`handy`, `uhr`), `nr` (im Satz), `tm`, `kontext` {`uebung`, `uebung_id`, `satz`, `phase`, `feld`} |
| `marke_weg` | `id` — nimmt eine Marke zurück; gelöscht wird nie |
| `kontext` | `was` (`uebung_start`, `uebung_ende`, `timer_*`, `satz`, `pause`, `diagnose_start`, `diagnose_ende`), `uebung`, `uebung_id`, `satz`, `feld`, `wert`, `abschnitt`, `dauer_s`, `phase`, `art_marke`; seit 0.6.1 `plan`, `runde`, `von`, `profil`, `soll_s` (wie die Marke im Ereignis der Messdatei) |

- **Schreiben:** jede Zeile sofort geschrieben und geflusht, `fsync` höchstens alle 5 s;
  endet die Datei beim Öffnen mitten in einer Zeile, beginnt der Anhang mit einem
  Zeilenumbruch. Während der Aufnahme heißt die Datei `.backup_<ts>_mitschnitt.jsonl`
  (`journal_pfad`), beim Speichern wird sie umbenannt (`Schreiber.umbenennen`,
  `mitschnitt_pfad`). Ohne Messung (unbekanntes Gerät): `Diagnose/<ts>_<gerät>/mitschnitt.jsonl`.
- **Lesen:** `lesen` übergeht leere, halbe und kaputte Zeilen; `stroeme` entschlüsselt EKG
  (µV) und Beschleunigung (mG) aus `pmd_data` mit `geraete.pmd`, Probenzeiten nach Gerätezeit
  (letzte Probe je Rahmen, Rate aus der Gerätezeit), Lücken ab 1,5 Proben; komprimierte
  Rahmen werden gezählt, nie als Werte gelesen.
- **Nie im Mitschnitt:** Seriennummer (0x2A25) und Systemkennung (0x2A23) liest keine App;
  GPS gehört nicht hinein. `deid.mitschnitt_deidentifizieren` maskiert Adressen (der
  Herstellerteil bleibt), kürzt den Gerätenamen auf das Modell — auch in Protokollzeilen —,
  entfernt Zeilen der Merkmale 0x2A00/0x2A23/0x2A25 und alles, was `deid.MITSCHNITT_REGELN`
  nicht kennt; `deid.pruefen` lehnt einen Mitschnitt ab, an dem das noch etwas ändern würde.

## `atem-v1` — Beiwerk `sensor_<ts>_atem.json`

`atem` (`AtemSammler`, `atem_laden`, `atem_pfad`, `atem_journal_pfad`), seit 5.11.2026
(trainingsapp `docs/plan_beschleunigung.md` §7.4/§8: **Ergebnisse statt Rohdaten**, P123).
Das Ergebnis der Atemerfassung aus dem Beschleunigungssensor neben der Messdatei; der Inhalt
stammt aus einem Prototyp (`hrv_core.prototyp`, Kennzeichnung `art`/`prototyp`), das Format ist
stabil. Alle Zeiten in Sekunden auf der **Wanduhr der Messung** (`t_wall_s` wie die Schläge),
3 Nachkommastellen. Keine Rohproben, kein Ort, nichts vom Magnetometer, keine Korrekturen
(±1 steht in der Zeitleiste der Einheit).

| Feld | Von hrv-core gesetzt | Anmerkung |
|---|---|---|
| `schema` | ja | `atem-v1` |
| `art`, `prototyp` | ja | `prototyp` und der Modulname des Verfahrens (`hrv_core.prototyp.atemzuege`) — der Inhalt ist nie Grundlage gespeicherter Kennzahlen |
| `hrv_core` | ja | Version der Bibliothek beim Schreiben |
| `quelle` | ja (vom Aufrufer) | `sensor` (Beschleunigung); `takt` ist für den Taktgeber reserviert |
| `geraet` | ja (vom Aufrufer) | Profil-ID (`polar_h10`, `verity_sense`) — nie Name, Adresse oder Seriennummer |
| `rate_hz` | ja (vom Aufrufer) | Abtastrate der Beschleunigung, `null` wenn keine |
| `erfasst[]` | ja | `[von_s, bis_s]` je Lauf „Atmung erfassen“; ohne Eintrag ist eine Lücke „nicht gemessen“, nicht „kein Atemzug“. Ein beim Schreiben noch offener Lauf endet mit dem letzten bekannten Zeitpunkt (letzte Phase oder letztes Fenster, sonst `von_s`) |
| `phasen[]` | ja | `[t_s, "ein" \| "aus"]` — Beginn von Ein- bzw. Ausatmen, zeitlich sortiert |
| `fenster[]` | ja | `[t_ende_s, rate_pro_min, gueltig, grund]` je Prüffenster (alle 5 s, 30 s lang, Ende des Fensters); ungültig: `rate_pro_min = null` und `grund` als snake_case-Code aus dem Prototyp (`bewegung`, `amplitude_klein`, `unregelmaessig`, `zu_wenig_zyklen`, `kein_gipfel` …), sonst `""` |

- **Journal** `.backup_<ts>_atem.jsonl` neben dem Crash-Backup (`AtemSammler.journal_anhaengen`,
  `aus_journal`): JSON Lines, jede Zeile für sich abgeschlossen, zuletzt `fsync` — `["k", {kopf}]`,
  `["e", von_s]` (Lauf auf), `["x", bis_s]` (Lauf zu), `["p", t_s, "ein"|"aus"]`,
  `["f", t_ende_s, rate, gueltig, grund]`. Nur Neues wird angehängt; eine halbe Zeile wird
  abgeschlossen statt fortgesetzt, ein anderer oder verschwundener Pfad bekommt alles samt Kopf.
  Ein offener Lauf bleibt im Journal offen. `backup_entfernen` löscht das Journal mit.
- **Lesen:** `atem_laden` ist tolerant — fehlende oder kaputte Listen sind leer, unbekannte
  Phasen und unlesbare Zeilen fallen weg; nur ein fremdes `schema` ist ein Fehler.
- `deid.ATEM_REGELN` behält alle Felder (Listen als Ganzes); `deid.format_erkennen` erkennt
  `schema` und die Endung `_atem.json`.

## PMD-Dekoder `geraete.pmd`

Polar Measurement Data (H10, Verity Sense) ohne Transport: Kommandos (`ECG_START`,
`acc_start(rate, bereich, auflösung)`, `ACC_STOP`, `einstellungen_kommando`), Steuerantworten
(`parse_control_antwort` mit `mehr` und `parameter`; `parse_einstellungen` für die Antwort auf
„Einstellungen“), Merkmalsliste (`parse_feature_antwort`) und Rahmen (`parse_pmd_rahmen`,
`parse_ekg_proben`, `parse_ppi_proben`, `parse_acc_proben` für die Frame-Typen 0x00–0x02).
Bis 0.6.0 lag das in `trainingsapp/devices/pmd.py`; die App reicht es seitdem durch.

## Nur gelesen oder nur geprüft

| Format | Datei | hrv-core |
|---|---|---|
| `truth-v1` | `sensor_*_truth.json` | Sollwerte des Generators — `deid.TRUTH_REGELN`, Golden-Tests |
| EKG | `sensor_*_ecg.json` | `sample_rate_hz`, `uv[]`, `gaps`, `frame_offsets`, `frame_sample_counts` (praxis_gui); seit 30.10.2026 schreibt es auch die trainingsapp (`ekg.EkgSammler`, Polar H10 PMD 130 Hz, nur auf Wunsch) mit `frame_t_ns[]`, `t_wall_start_s`, `batterie[]`, `gaps[]` aus der Gerätezeit; `ekg.ekg_laden` liest beides; Journal `.backup_<ts>_ecg.jsonl` neben dem Crash-Backup |
| PPG | `sensor_*_ppg.json` | `sample_rate_hz`, `kanaele`, `kanal_namen`, `werte[]`, … — nur `deid` |
| `sitzung-v1` | `Messungen/Sitzungen/sitzung_*.json` | Mehrgeräte-Sitzung aus praxis_gui: `teilnehmer[]` mit `geraet`, `adresse` (BLE-MAC, `deid` leert), `geraet_profil`, `intervall_quelle`, `ordner`, `datei`, `n_schlaege` — nur `deid` |

## Abgleich mit praxis_gui (D10)

Die Feldreferenz in `praxis_gui/docs/sensor_hrv.md` nennt seit dem 19.10.2026
(praxis_gui c3ba778) auch `datenqualitaet`, `uebungen`, `marke`, `adresse` und
`corrections_ppi` und verweist für alles Weitere hierher. Die Kompatibilität ist
gegeben: optionale, flache Felder, praxis_gui behält sie beim Bearbeiten.
