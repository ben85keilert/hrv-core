# Notebooks

Hier liegen nur Notebooks, die eine **Änderung in hrv-core begründen** (Vergleich gegen
Golden Master, Referenztests) — und zwar ausschließlich auf `tests/fixtures/`.

Exploration, Literaturarbeit, Prototypen und Modelle gehören in das private Repo
**hrv-research** (Schwesterordner `../hrv-research`): Dort liegen die de-identifizierten
Messungen (`$HRV_TESTDATA`), dort sind scipy/neurokit2/pandas/torch erlaubt, und von dort
ziehen Algorithmen nach `docs/UEBERNAHME.md` hierher um.

Regeln für Notebooks in diesem Repo:

- Daten nur aus `tests/fixtures/`. Nie `$HRV_TESTDATA`, nie Patientenordner der Praxis —
  dieses Repo ist öffentlich, und Notebook-Ausgaben zählen als Daten.
- Ausgaben vor dem Commit löschen (`*.ipynb` ist nicht gitignoriert).
- Die Rechnung macht `hrv_core`; ein Notebook rechnet nichts nach, es ruft auf und vergleicht.
