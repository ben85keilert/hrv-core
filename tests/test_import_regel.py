"""Die eine Architekturregel: hrv_core importiert nur numpy und die Standardbibliothek.

scipy und neurokit2 gibt es auf Android/iOS nicht; Qt, flet und die beiden
Anwendungen gehören nicht in eine Bibliothek. Geprüft per AST-Scan über alle
Module unter src/hrv_core — auch relative Importe werden aufgelöst.
"""

import ast
from pathlib import Path

PAKET = Path(__file__).resolve().parents[1] / "src" / "hrv_core"
VERBOTEN = {
    "scipy",
    "neurokit2",
    "sklearn",
    "pandas",
    "PySide6",
    "PyQt5",
    "PyQt6",
    "flet",
    "flet_ble",
    "trainingsapp",
    "praxislab",
    "matplotlib",
}


def _importe(datei: Path):
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for alias in knoten.names:
                yield alias.name.split(".")[0]
        elif isinstance(knoten, ast.ImportFrom):
            if knoten.level:  # relativ: bleibt im Paket
                yield "hrv_core"
            elif knoten.module:
                yield knoten.module.split(".")[0]


def test_hrv_core_importiert_nichts_verbotenes():
    verstoesse = []
    for datei in sorted(PAKET.rglob("*.py")):
        for name in _importe(datei):
            if name in VERBOTEN:
                verstoesse.append(f"{datei.relative_to(PAKET.parent)}: {name}")
    assert not verstoesse, "\n".join(verstoesse)


def test_paket_hat_module():
    assert (PAKET / "__init__.py").is_file()
    assert (PAKET / "deid.py").is_file()
