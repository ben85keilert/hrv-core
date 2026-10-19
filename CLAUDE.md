# CLAUDE.md

Hinweise für Claude Code in diesem Repository.

## Was dieses Repo ist

**hrv-core** ist die gemeinsame HRV-Bibliothek von praxis_gui (Praxisverwaltung, PySide6) und
trainingsapp (Flet, Android/iOS): Einlesen `raw-v1`/`analysis-v1`, Artefaktkorrektur,
Kennzahlen, Spektren, Atmung, Verlaufskurven. Beide Apps rechnen mit **denselben Funktionen**
und liefern dieselben Zahlen; sie unterscheiden sich nur in der Bedienung (trainingsapp:
Automatik, Expertenmodus zuschaltbar; praxis_gui: Expertenmodus sichtbar, Automatik dazu).
Träger der Bedienung ist `regeln.Korrekturregeln`, gesetzt in der App — hier gibt es keine
Profile und keine App-Sonderfälle.

Das Repo ist **öffentlich** (AGPL-3.0, CLA in `CONTRIBUTING.md`). Nachbarn:

- `../hrv-research` (privat): Literatur, de-identifizierte Messungen (`$HRV_TESTDATA`),
  Notebooks, Prototypen mit scipy/neurokit2, Modelle, der Auswertungs-Skill. Von dort ziehen
  Algorithmen hierher um (`hrv-research/docs/UEBERNAHME.md`); dieses Repo verweist auf
  hrv-research nur als Name und `$HRV_TESTDATA`, nie als Abhängigkeit.
- `../praxis_gui` und `../trainingsapp`: binden hrv-core editierbar als Schwesterordner ein
  (`[tool.uv.sources]`, trainingsapp zusätzlich `[tool.flet.dev_packages]`). Fester Stand für
  andere Rechner: Git-Tag `vX.Y.Z`.
- `trainingsapp-praxis`, `trainingsapp-inhalte` (privat): hängen von trainingsapp ab, nicht
  umgekehrt. Öffentliche Repos hängen nie von privaten ab.

## Sprache

Code und Bezeichner englisch, wenn es die verbreitete Schreibweise ist (`compute_time_domain`,
`rr_ms`), sonst deutsch wie im Bestand (`korrektur`, `atemfrequenz`, `Korrekturregeln`);
Kommentare, Docstrings, Dokumentation, Antworten und Commit-Messages deutsch
(`CONTRIBUTING.md`). Feldnamen des Austauschformats bleiben, wie praxis_gui sie schreibt
(Feldreferenz `raw-v1` in `praxis_gui/docs/sensor_hrv.md`, Abgleich der Apps in
`trainingsapp/docs/kompatibilitaet.md`).

## Befehle

```bash
uv sync                           # dev: pytest, ruff
uv sync --group referenz          # zusätzlich scipy/neurokit2 für tests/referenz/
uv run pytest                     # Tests, Doctests in src/, Golden Master (~2 min)
uv run pytest tests/referenz      # numpy-Fassungen gegen scipy/neurokit2
uv run ruff check . && uv run ruff format --check .
uv run python scripts/pruefe_daten.py              # $HRV_TESTDATA auf Personenbezug prüfen
uv run python scripts/pruefe_daten.py --ohne-ordnerregel tests/fixtures
uv run python scripts/deid_export.py <messdatei> --ziel $HRV_TESTDATA/p001   # nur Ben, lokal
uv run python scripts/golden_erneuern.py           # nur nach begründeter Algorithmusänderung
uv run python scripts/fixture_synth_lang.py       # synthetische 5000-s-Fixture neu erzeugen (Seed fest)
uv run python scripts/vergleich_praxis_gui.py      # docs/VERGLEICH_ZAHLEN.md neu erzeugen
uv run --with bleak python scripts/ble_erkundung.py ADRESSE   # Dienste und RR-Strom eines Gurts (Hardware, nur Ben)
```

## Regeln

- **Nur numpy zur Laufzeit.** Kein scipy, neurokit2, pandas, sklearn, Qt, flet, kein Import
  aus einer App (`tests/test_import_regel.py`, AST-Scan). scipy/neurokit2 nur in
  `tests/referenz/` (Gruppe `referenz`) als Beleg, dass die numpy-Fassung dieselbe Mathematik
  rechnet. Grund: Android/iOS haben kein scipy, und beide Apps sollen dieselben Zahlen liefern.
- **Jede Änderung an einer Rechenvorschrift ist begründet.** Vergleich gegen Golden Master und
  Referenzdaten im Notebook (`notebooks/` hier nur die Begründung auf `tests/fixtures/`;
  Exploration in hrv-research), Eintrag in `docs/hrv_algorithmen.md` bzw. `docs/korrektur.md`
  mit Formel, Parameter und Quelle. Ändert sich eine Zahl auf bisherigen Messungen:
  `constants.ALGO_VERSION` hochzählen, Golden Master mit `scripts/golden_erneuern.py` erneuern,
  Diff im Commit beschreiben. Die Apps halten ihre Caches an `ALGO_VERSION` fest.
- **Golden Master ist der Maßstab.** `tests/golden/trainingsapp/` (1e-9,
  `tests/test_golden_trainingsapp.py`) und die Referenztests müssen grün sein, bevor ein Tag
  gesetzt wird. `tests/golden/praxis_gui/` ist der **Vorher-Stand** von praxis_gui (scipy,
  Wanduhr) — Dokumentation der Abweichung (`docs/VERGLEICH_ZAHLEN.md`), kein Ziel.
- **Unterschiede nie stillschweigend vereinheitlichen.** Was in `docs/VERGLEICH.md` als
  bewusst verschieden steht, bleibt es, bis Ben entscheidet; neue Abweichungen und Befunde
  nach `docs/OFFENE_PUNKTE.md`, nicht nebenbei fixen.
- **Keine Patientendaten — auch nicht de-identifiziert.** Versioniert sind nur
  `tests/fixtures/` (synthetisch, PhysioNet, eigene Aufnahmen von Ben ohne Personenbezug) und
  `tests/golden/`. Nie Patientenordner der Praxis öffnen, durchsuchen oder kopieren. Testdaten
  für Forschung liegen unter `$HRV_TESTDATA` (hrv-research, Ordner `p001`, `selbst` …, Zuordnung
  Code ↔ Person außerhalb jedes Repos); vor jeder Sitzung mit solchen Daten
  `scripts/pruefe_daten.py`. `*.json` ist gitignoriert außer unter `tests/`. Keine Messwerte
  aus `$HRV_TESTDATA` in Doku, Kommentare oder Commit-Messages; Notebook-Ausgaben vor dem
  Commit löschen.
- **Rückwärtskompatibel lesen.** `recording.Recording.from_dict` und `korrektur.analyse_laden`
  müssen Altdateien beider Apps lesen (ohne `schema`, ohne `t_wall_s`, Sidecars mit
  `set_value`/`split`/`merge`, `corrections_ppi`). Unbekannte Felder bleiben erhalten (`extra`).
  Eine Formatänderung ist eine neue Schema-Version, nie ein stilles Umdeuten.
- **Zeitachsen.** Spektren rechnen auf der Herzuhr je lückenfreiem Teilstück; die Wanduhr
  bestimmt nur die Nähte (`korrektur.naehte`: Messlücken, Verworfenes). Nie die Paketankunft
  als Lomb-Stützstelle (`docs/OFFENE_PUNKTE.md` R11). `rr_ms = 0` ist kein Artefakt und keine
  Naht im Spektrum (H10: kein Schlag in dieser Sekunde).
- **Keine Bewertung in der Bibliothek.** Kennzahlen sind beschreibend; Deutung (Belastung,
  Entlastung, Regulation) gehört in den Auswertungs-Skill in hrv-research und in die Apps.
- **Commit und Push nur auf Bens Wort.** Kleine Commits je Thema; Tag `vX.Y.Z` mit
  `__version__` in `src/hrv_core/__init__.py`, danach `STAND.md` in hrv-research nachziehen.

## Aufbau

`src/hrv_core/`: `constants` (Grenzen, Bänder, `ALGO_VERSION`), `recording`/`aufnahme`
(raw-v1, Backup), `regeln`/`korrektur` (Korrekturregeln, Ketten, Sidecar analysis-v1),
`segments`, `time_domain`, `frequency` (Lomb/Welch/Periodogramm, Teilspektren, langer Weg,
Fensterspektrum, Spektrogramm), `nonlinear` (Poincaré, DFA α1, SampEn), `atmung`
(Prüfkette, Fenster, Median), `spektralprofil`, `trends` (Verlaufskurven), `ausschnitte`
(Crop, Abschnitte), `ppi`/`zeitachse` (Verity Sense), `live`, `ereignisse` (Notiz-Anker),
`referenz` (alles auf einmal, Grundlage der Golden Master), `deid` (Weißliste je Format).
Formeln und Fallstricke: `docs/hrv_algorithmen.md`, `docs/korrektur.md`; welche Felder die
Bibliothek liest und schreibt: `docs/formate.md`.
Gerätewissen für beide Apps (H10 als Referenz, Verity Sense, Decathlon, Beurer PO60, Prüfmethode):
`docs/geraete/README.md` — aus praxis_gui hierher verschoben (19.10.2026), Codepfade dort meinen praxis_gui.
