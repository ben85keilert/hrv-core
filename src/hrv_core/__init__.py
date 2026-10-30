"""hrv-core — gemeinsame HRV-Bibliothek von praxis_gui und trainingsapp.

Reines numpy — **kein scipy, kein neurokit2**: Auf Android und iOS gibt es sie
nicht, und beide Apps sollen dieselben Zahlen liefern. scipy/neurokit2 dienen
nur der Referenztestung (Gruppe ``referenz``, tests/referenz/). Importiert nie
Qt, flet oder etwas aus den Anwendungen (tests/test_import_regel.py).

Keine Patientendaten im Repo (es wird öffentlich). Testdaten nur unter
tests/fixtures/; de-identifizierte Messungen liegen im privaten Repo
hrv-research ($HRV_TESTDATA, vorher scripts/pruefe_daten.py).
Algorithmen: docs/hrv_algorithmen.md, Korrekturregeln: docs/korrektur.md.
"""

__version__ = "0.5.1"

from .artifacts import clean_rr
from .aufnahme import Aufnahme
from .constants import ALGO_VERSION, RR_MAX_MS, RR_MIN_MS
from .korrektur import (
    Kette,
    Korrektur,
    Korrigiert,
    analyse_laden,
    analyse_pfad,
    analyse_speichern,
    anwenden,
    automatisch,
    kennzahlen,
)
from .live import LiveFenster, LiveKennzahlen, LivePunkt
from .recording import (
    Beat,
    Recording,
    ist_messdatei,
    json_atomar_schreiben,
    laden,
    messordner,
    speichern,
)
from .segments import segment_diffs, segmentieren
from .time_domain import compute_time_domain

__all__ = [
    "ALGO_VERSION",
    "RR_MAX_MS",
    "RR_MIN_MS",
    "Aufnahme",
    "Beat",
    "Kette",
    "Korrektur",
    "Korrigiert",
    "LiveFenster",
    "LiveKennzahlen",
    "LivePunkt",
    "Recording",
    "analyse_laden",
    "analyse_pfad",
    "analyse_speichern",
    "anwenden",
    "automatisch",
    "clean_rr",
    "compute_time_domain",
    "ist_messdatei",
    "json_atomar_schreiben",
    "kennzahlen",
    "laden",
    "messordner",
    "segment_diffs",
    "segmentieren",
    "speichern",
]
