"""Golden Master: hrv-core rechnet auf jeder Fixture genau das, was trainingsapp.hrv_core rechnete.

Die Dateien unter tests/golden/trainingsapp/ entstanden vor dem Umzug mit
``trainingsapp/scripts/export_referenz.py`` (ALGO_VERSION 7). Toleranz 1e-9
relativ für Gleitkommazahlen, sonst Gleichheit. Eine bewusste
Algorithmusänderung erneuert die Golden-Dateien mit ``scripts/golden_erneuern.py``
und begründet das in docs/ (Notebook unter notebooks/).
"""

import json
import math
from pathlib import Path

import pytest

from hrv_core.referenz import referenz

GOLDEN = Path(__file__).parent / "golden" / "trainingsapp"
FIXTURES = Path(__file__).parent / "fixtures"
TOLERANZ = 1e-9


def _vergleiche(a, b, pfad: str, fehler: list[str]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            fehler.append(f"{pfad}: Schlüssel {sorted(set(a) ^ set(b))}")
            return
        for k in a:
            _vergleiche(a[k], b[k], f"{pfad}.{k}", fehler)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            fehler.append(f"{pfad}: Länge {len(a)} ≠ {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _vergleiche(x, y, f"{pfad}[{i}]", fehler)
    elif isinstance(a, bool) or isinstance(b, bool):
        if a != b:
            fehler.append(f"{pfad}: {a!r} ≠ {b!r}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if not math.isclose(a, b, rel_tol=TOLERANZ, abs_tol=TOLERANZ):
            fehler.append(f"{pfad}: {a!r} ≠ {b!r}")
    elif a != b:
        fehler.append(f"{pfad}: {a!r} ≠ {b!r}")


def _golden_dateien() -> list[Path]:
    return sorted(GOLDEN.glob("*.json"))


@pytest.mark.parametrize("golden", _golden_dateien(), ids=lambda p: p.stem)
def test_golden_master(golden: Path) -> None:
    ordner, _, name = golden.stem.partition("__")
    fixture = FIXTURES / ordner / f"{name}.json"
    assert fixture.is_file(), fixture
    soll = json.loads(golden.read_text(encoding="utf-8"))
    ist = referenz(fixture)
    fehler: list[str] = []
    _vergleiche(soll, ist, name, fehler)
    assert not fehler, "\n".join(fehler[:20]) + (f"\n… {len(fehler)} Abweichungen" if len(fehler) > 20 else "")


def test_golden_deckt_alle_fixtures_ab() -> None:
    erwartet = {
        f"{p.parent.name}__{p.stem}" for p in FIXTURES.rglob("sensor_*.json")
        if not any(p.name.endswith(s) for s in ("_analyzed.json", "_ecg.json", "_ppg.json", "_truth.json"))
    }
    assert erwartet == {p.stem for p in _golden_dateien()}
