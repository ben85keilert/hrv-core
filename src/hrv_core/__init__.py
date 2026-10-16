"""hrv-core — gemeinsame HRV-Bibliothek von praxis_gui und trainingsapp.

Regeln:
- Laufzeit nur numpy und Standardbibliothek. Kein scipy, kein neurokit2, kein
  Qt, kein flet, nichts aus den Anwendungen (tests/test_import_regel.py).
- scipy/neurokit2 nur in tests/referenz/ (Gruppe ``referenz``) als Referenz.
- Keine Patientendaten im Repo (es wird öffentlich). Testdaten nur unter
  tests/fixtures/ (synthetisch, PhysioNet, eigene Aufnahmen ohne Personenbezug);
  de-identifizierte Messungen liegen im privaten Repo hrv-research
  ($HRV_TESTDATA, vorher scripts/pruefe_daten.py).
"""

__version__ = "0.0.1"
