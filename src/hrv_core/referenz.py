"""Vollständige Referenzrechnung einer Messdatei — Grundlage der Golden-Master-Tests.

``referenz(pfad)`` rechnet alles, was die Bibliothek aus einer ``raw-v1``-Datei
macht: Nähte und Zeitachse, Rohkennzahlen, Atmung, und je Korrekturvariante
Ketten, korrigierte Reihe, Zeit-/Frequenzbereich, nichtlineare Werte,
Verlaufskurven und Abschnitte. Das Ergebnis ist JSON-tauglich.

Die Dateien unter ``tests/golden/trainingsapp/`` entstanden mit genau dieser
Rechnung im alten ``trainingsapp.hrv_core`` (``trainingsapp/scripts/export_referenz.py``);
``tests/test_golden_trainingsapp.py`` verlangt Gleichheit auf 1e-9. Wer eine
Zahl hier ändert, ändert bewusst einen Algorithmus — mit Begründung und neuen
Golden-Dateien.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from . import ausschnitte, korrektur, nonlinear, ppi, trends
from .atmung import ATEM_VERSION, ATEMUEBUNG, RUHE, atemfrequenz
from .constants import ALGO_VERSION
from .frequency import fensterspektrum, frequenzbereich
from .recording import Recording, laden
from .regeln import Korrekturregeln
from .time_domain import compute_time_domain

BEIWERK = ("_analyzed.json", "_ecg.json", "_ppg.json", "_truth.json")
#: Verlaufskurven mit ihrem Vorgabefenster (Kennzahl, Fenster s, Block?)
VERLAUF: list[tuple[str, int, bool]] = [
    ("rmssd", 30, False),
    ("sdnn", 60, False),
    ("mean_rr", 10, False),
    ("pnnx", 30, False),
    ("sd1", 60, False),
    ("sd2", 180, False),
    ("lf_power", 120, False),
    ("hf_power", 120, False),
    ("lf_hf", 120, True),
    ("dfa_alpha1", 120, False),
    ("atemfrequenz", 60, False),
]


def json_tauglich(x: Any) -> Any:
    """numpy → Python, NaN/Inf → None, Dataclasses über ihre Felder."""
    if isinstance(x, dict):
        return {str(k): json_tauglich(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_tauglich(v) for v in x]
    if isinstance(x, np.ndarray):
        return json_tauglich(x.tolist())
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if hasattr(x, "__dataclass_fields__"):
        return json_tauglich({k: getattr(x, k) for k in x.__dataclass_fields__})
    if callable(x):
        raise TypeError(f"nicht serialisierbar: {x!r}")
    return x


def ist_rohdatei(p: Path) -> bool:
    n = p.name
    return (
        n.startswith("sensor_")
        and n.endswith(".json")
        and not any(n.endswith(s) for s in BEIWERK)
        and "__c" not in n
    )


def _korrigiert_dict(korr: korrektur.Korrigiert) -> dict[str, Any]:
    return {
        "t_s": korr.t_s,
        "rr_ms": korr.rr_ms,
        "flag": korr.flag,
        "breaks": korr.breaks,
        "entfernt": korr.entfernt,
        "interpoliert": korr.interpoliert,
        "roh_index": korr.roh_index,
    }


def _frequenz(korr: korrektur.Korrigiert) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, kw in (
        ("lomb", {}),
        ("welch", {"methode": "welch"}),
        ("lomb_nullen_trennen", {"nullen_trennen": True}),
        ("lomb_ohne_mindestdauer", {"mindestdauer": False}),
    ):
        out[name] = frequenzbereich(korr.rr_ms, korr.t_s, korr.breaks, **kw)  # type: ignore[arg-type]
    return out


def variante(rec: Recording, regeln: Korrekturregeln, achse: list[float]) -> dict[str, Any]:
    """Eine Korrekturvariante: Automatik mit ``regeln``, dann alles auf der korrigierten Reihe."""
    basis = korrektur.analysebasis(rec, regeln)
    ketten = korrektur.vorschlaege(basis.rec, regeln)
    korrekturen = [k for kette in ketten for k in kette.vorschlag]
    korr = korrektur.anwenden(basis.rec, korrekturen)
    rr = korr.rr_ms
    out: dict[str, Any] = {
        "regeln": regeln.als_dict(),
        "basis_zeile": basis.zeile,
        "aufgenommen": basis.aufgenommen,
        "ketten": [
            {
                "start": k.start,
                "ende": k.ende,
                "art": k.art,
                "unsicher": k.unsicher,
                "grund": k.grund,
                "luecke_s": k.luecke_s,
                "vorschlag": [v.to_dict() for v in k.vorschlag],
            }
            for k in ketten
        ],
        "korrekturen": [k.to_dict() for k in korrekturen],
        "korrigiert": _korrigiert_dict(korr),
        "kennzahlen": korrektur.kennzahlen(korr),
        "kennzahlen_pnn20": compute_time_domain(rr, pnn_threshold_ms=20.0, breaks=korr.breaks),
        "frequenz": _frequenz(korr),
        "poincare": nonlinear.compute_poincare(rr, korr.breaks),
        "dfa_alpha1": nonlinear.compute_dfa_alpha1(rr),
        "sampen": nonlinear.compute_sampen(rr),
    }
    if len(basis.zeile) == len(rec.beats):  # Identität: Achse der Rohzeilen passt
        zeiten = korrektur.korr_zeiten(korr, achse)
        t, rrk, naht = trends.reihe(zeiten, rr, korr.breaks)
        out["zeiten"] = zeiten
        out["verlauf"] = {
            f"{k}_{f}s{'_block' if b else ''}": trends.verlauf(t, rrk, naht, k, f, block=b)
            for k, f, b in VERLAUF
        }
        out["aktuell"] = {
            k: trends.aktuell(t, rrk, naht, k, f) for k, f, _ in VERLAUF if k != "atemfrequenz"
        }
        out["atmung_aktuell_60s"] = trends.atmung_aktuell(t, rrk, 60.0).als_dict()
        t0, t1 = float(t[0]), float(t[-1])
        out["fensterspektrum_gesamt"] = fensterspektrum(t, rrk, t0 - 1e-6, t1)
        mitte = (t0 + t1) / 2
        von, bis = max(t0, mitte - 90.0), min(t1, mitte + 90.0)
        out["abschnitt_mitte"] = ausschnitte.abschnitt_werte(korr, zeiten, von, bis, frequenz=True)
        out["abschnitt_mitte_spektrum"] = ausschnitte.abschnitt_spektrum(korr, zeiten, von, bis)
    return out


def referenz(pfad: Path | str) -> dict[str, Any]:
    """Alles, was die Bibliothek aus einer Messdatei rechnet — JSON-tauglich."""
    pfad = Path(pfad)
    rec = laden(pfad)
    rr_roh = rec.rr_ms
    achse = ppi.schlagzeiten(rec)
    naehte = korrektur.naehte(rec)
    out: dict[str, Any] = {
        "quelle": pfad.name,
        "algo_version": ALGO_VERSION,
        "atem_version": ATEM_VERSION,
        "n_beats": len(rec.beats),
        "intervall_quelle": rec.intervall_quelle,
        "datenqualitaet": rec.effektive_qualitaet()
        if callable(rec.effektive_qualitaet)
        else rec.effektive_qualitaet,
        "dauer_s": rec.dauer_s() if callable(rec.dauer_s) else rec.dauer_s,
        "hat_ppi": rec.ppi_pakete is not None,
        "schlagzeiten": achse,
        "messluecken": ppi.messluecken(rec),
        "ppi_naehte": ppi.ppi_naehte(rec),
        "naehte": naehte,
        "ppi_verworfen": ppi.ppi_verworfen(rec),
        "rohfolge": korrektur.rohfolge(rec),
        "roh_kennzahlen": compute_time_domain(rr_roh, breaks=naehte),
        "roh_kennzahlen_ohne_naht": compute_time_domain(rr_roh, breaks=naehte, skip_seams=False),
        "roh_frequenz_lomb": frequenzbereich(rr_roh, [b.t_s for b in rec.beats], naehte),
        "roh_poincare": nonlinear.compute_poincare(rr_roh, naehte),
        "roh_poincare_punkte": nonlinear.poincare_punkte(rr_roh),
        "roh_dfa_alpha1": nonlinear.compute_dfa_alpha1(rr_roh),
        "roh_sampen": nonlinear.compute_sampen(rr_roh),
        "atmung_gesamt": {
            modus: atemfrequenz(achse, [float(x) for x in rr_roh], modus=modus).als_dict()
            for modus in (RUHE, ATEMUEBUNG)
        },
        "varianten": {},
    }
    varianten = {
        "vorgabe": Korrekturregeln(),
        "nullen": Korrekturregeln(nullen=True),
        "sicher": Korrekturregeln(vorauswahl="sicher"),
        "ohne_malik": Korrekturregeln(malik_an=False, fehler_an=False),
    }
    if rec.ppi_pakete is not None:
        varianten["selbst"] = Korrekturregeln(sensor_verwerfung="selbst")
    for name, regeln in varianten.items():
        out["varianten"][name] = variante(rec, regeln, achse)
    return json_tauglich(out)
