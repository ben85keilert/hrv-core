# hrv-core

Gemeinsame HRV-Bibliothek von praxis_gui und trainingsapp: Einlesen `raw-v1`/`analysis-v1`,
Artefaktkorrektur, Kennzahlen, Segmentierung — ohne GUI, nur numpy.

## Installation

```bash
uv sync                      # Entwicklung (dev: pytest, ruff)
uv sync --group referenz     # zusätzlich scipy/neurokit2 für Vergleichstests (tests/referenz/)
uv run pytest
```

Einbindung in die Apps (uv): `[tool.uv.sources] hrv-core = { path = "../hrv-core", editable = true }`;
fester Stand: `{ git = "https://github.com/ben85keilert/hrv-core.git", tag = "v0.2.0" }`.

## Aufbau

- `src/hrv_core/` — die Bibliothek (aus `trainingsapp.hrv_core`, ALGO_VERSION 7): `recording`/`aufnahme`
  (raw-v1), `regeln`/`korrektur` (Automatik und Expertenkorrektur, Sidecar analysis-v1), `segments`,
  `time_domain`, `frequency` (samt Spektrogramm), `nonlinear`, `atmung`, `spektralprofil`, `trends`,
  `ausschnitte`, `ppi`/`zeitachse` (Verity Sense), `live`, `ereignisse`, `referenz` (alles auf einmal), `deid`.
- `tests/fixtures/` Messdateien ohne Personenbezug · `tests/golden/trainingsapp/` Golden Master
  (`test_golden_trainingsapp.py`, 1e-9) · `tests/golden/praxis_gui/` Vorher-Stand von praxis_gui
  (scipy/NK2) für `docs/VERGLEICH_ZAHLEN.md` · `tests/referenz/` Vergleich gegen scipy/neurokit2.
- `docs/` — `hrv_algorithmen.md`, `korrektur.md` (Regeln), `VERGLEICH.md` (Entscheidungen),
  `VERGLEICH_ZAHLEN.md`, `OFFENE_PUNKTE.md`.
- `scripts/golden_erneuern.py` nur nach begründeter Algorithmusänderung; `scripts/vergleich_praxis_gui.py`.

Beide Apps rechnen mit denselben Funktionen. Unterschiede gibt es nur in der Bedienung: die
trainingsapp korrigiert standardmäßig automatisch (`Korrekturregeln`-Vorgaben) mit zuschaltbarem
Expertenmodus, praxis_gui zeigt den Expertenmodus und kann die Automatik.

## Datenschutz

Dieses Repo ist öffentlich. Deshalb:

- Keine Patientendaten, auch nicht de-identifiziert. Versioniert sind nur `tests/fixtures/`
  (synthetisch, PhysioNet, eigene Aufnahmen von Ben ohne Personenbezug) und `tests/golden/`.
- De-identifizierte Messungen für Forschung liegen im privaten Repo **hrv-research**, ein Ordner
  je Person mit neutralem Code (`p001`, `selbst`); Zuordnung Code ↔ Person außerhalb jedes Repos.
  Der Pfad dorthin steht in `$HRV_TESTDATA`. Die Werkzeuge dafür liefert hrv-core:
  `python scripts/deid_export.py <messdatei> --ziel $HRV_TESTDATA/p001` (entfernt nur
  `patient_id`/`behandlung_id`, führt nur Ben lokal aus) und vor jeder Sitzung mit Testdaten
  `python scripts/pruefe_daten.py` (prüft `$HRV_TESTDATA`).
- Nachbarrepos: `hrv-research` (privat, Exploration, Notebooks, Modelle), `trainingsapp`,
  `trainingsapp-praxis` (privat), `trainingsapp-inhalte` (privat), `praxis_gui`. Öffentliche Repos
  hängen nie von privaten ab.

## Lizenz

[AGPL-3.0](LICENSE). Nutzen, ändern und weitergeben ist frei — auch in der eigenen Praxis oder
für den Eigenbedarf. Wer die Bibliothek in ein Produkt einbaut oder als Dienst betreibt, muss
dessen Quelltext unter der AGPL offenlegen; wer das nicht möchte, braucht eine kommerzielle
Lizenz des Projektinhabers (auf Anfrage). Beiträge unterliegen der CLA in
[CONTRIBUTING.md](CONTRIBUTING.md), die dem Projektinhaber diese Dual-Lizenzierung offenhält.
