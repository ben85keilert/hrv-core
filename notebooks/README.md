# Notebooks

Exploration und Begründung algorithmischer Änderungen (Vergleich gegen Golden
Master und Referenzdaten). Regeln:

- Daten nur aus `tests/fixtures/` oder dem lokalen, gitignorierten Ordner
  `daten/` (vorher `python scripts/pruefe_daten.py`). Nie Patientenordner
  der Praxis öffnen.
- Ausgaben mit Messwerten vor dem Commit löschen (`*.ipynb` ist nicht
  gitignoriert, Ausgaben zählen als Daten).
- Die Rechnung macht `hrv_core`; ein Notebook rechnet nichts nach, es ruft auf
  und vergleicht.
