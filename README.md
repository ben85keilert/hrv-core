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
fester Stand: `{ git = "ssh://git@github.com/ben85keilert/hrv-core.git", tag = "v0.1.0" }`.

## Datenschutz

- Keine Patientendaten im Repo. `daten/` ist gitignoriert: ein Ordner je Person mit neutralem
  Code (`p001`, `selbst`), befüllt nur von Ben über `python scripts/deid_export.py … --ziel daten/p001`
  (entfernt nur `patient_id`/`behandlung_id`). Zuordnung Code ↔ Person liegt außerhalb des Repos.
- Vor jeder Sitzung mit Testdaten: `python scripts/pruefe_daten.py` (oder `$HRV_TESTDATA`).
- Versioniert sind nur `tests/fixtures/` (synthetisch, PhysioNet, eigene Aufnahmen von Ben,
  de-identifiziert) und `tests/golden/` (Referenzergebnisse).
