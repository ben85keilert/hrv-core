"""hrv-core — gemeinsame HRV-Bibliothek von praxis_gui und trainingsapp.

Regeln:
- Laufzeit nur numpy und Standardbibliothek. Kein scipy, kein neurokit2, kein
  Qt, kein flet, nichts aus den Anwendungen (tests/test_import_regel.py).
- scipy/neurokit2 nur in tests/referenz/ (Gruppe ``referenz``) als Referenz.
- Keine Patientendaten im Repo. Testdaten nur unter tests/fixtures/ (synthetisch
  oder eigene, de-identifizierte Aufnahmen) und lokal unter daten/ (gitignoriert,
  Personenordner mit neutralen Codes, vorher scripts/pruefe_daten.py).
"""

__version__ = "0.0.1"
