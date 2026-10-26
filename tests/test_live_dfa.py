"""Live-DFA α1 (`LiveFenster.dfa_a1`): Vorschau für die Uhr, Rechnung wie in der Aufzeichnung."""

from __future__ import annotations

import numpy as np

from hrv_core.constants import DFA_WINDOW_N
from hrv_core.live import LiveFenster
from hrv_core.nonlinear import compute_dfa_alpha1


def _fenster(rr_liste, hf: int = 75) -> LiveFenster:
    f = LiveFenster()
    t = 0.0
    for rr in rr_liste:
        t += rr / 1000
        f.hinzufuegen(t, int(rr), hf)
    return f


def test_gleiche_zahl_wie_die_aufzeichnung() -> None:
    rng = np.random.default_rng(7)
    rr = (800 + rng.normal(0, 25, 320)).round()
    f = _fenster(rr)
    live = f.dfa_a1()
    assert live is not None
    # Ohne Artefakte sind die guten Rohwerte die Rohwerte: dieselbe Zahl wie die Aufzeichnung
    soll = compute_dfa_alpha1(rr, window_n=DFA_WINDOW_N)
    assert soll is not None and abs(live - soll["dfa_alpha1"]) < 1e-12


def test_zu_wenig_schlaege_oder_zu_viele_artefakte() -> None:
    rng = np.random.default_rng(7)
    rr = (800 + rng.normal(0, 25, DFA_WINDOW_N - 1)).round()
    assert _fenster(rr).dfa_a1() is None
    # 4 % Ausreißer im Fenster: markiert → über der Grenze → None
    rr = (800 + rng.normal(0, 25, 300)).round()
    rr[::25] = 1600
    assert _fenster(rr).dfa_a1() is None
    # 1 % Ausreißer: markiert, aber unter der Grenze → Wert aus den guten Schlägen
    rr = (800 + rng.normal(0, 25, 300)).round()
    rr[::100] = 1600
    wert = _fenster(rr).dfa_a1()
    assert wert is not None and 0.2 < wert < 1.5


def test_nur_die_letzten_sekunden() -> None:
    rng = np.random.default_rng(3)
    rr = (800 + rng.normal(0, 25, 300)).round()
    f = _fenster(rr)
    # 300 Schläge à 0,8 s = 240 s; mit 100 s Rückblick liegen keine 200 Schläge darin
    assert f.dfa_a1(dauer_s=100.0) is None
    assert f.dfa_a1(dauer_s=240.0) is not None
