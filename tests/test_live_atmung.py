"""Live-Atemfrequenz und -Artefaktanteil (`LiveFenster`): Vorschau für die Uhr, Gurt-Warnung."""

from __future__ import annotations

import numpy as np

from hrv_core.atmung import ATEMUEBUNG, RUHE, atemfrequenz
from hrv_core.live import LiveFenster


def _atmend(hz: float, n: int = 120, hf: int = 60) -> tuple[LiveFenster, list[float], list[float]]:
    f = LiveFenster()
    t, ts, rrs = 0.0, [], []
    for _ in range(n):
        rr = 1000 + 40 * np.sin(2 * np.pi * hz * t)
        t += rr / 1000
        f.hinzufuegen(t, int(rr), hf)
        ts.append(t)
        rrs.append(int(rr))
    return f, ts, rrs


def test_gleiche_zahl_wie_die_auswertung() -> None:
    f, ts, rrs = _atmend(0.1)
    live = f.atemfrequenz()
    soll = atemfrequenz(ts, rrs, ts[-1] - 60.0, ts[-1], modus=ATEMUEBUNG)
    assert live is not None and soll.gueltig
    assert abs(live - soll.rate_pro_min) < 1e-9
    assert abs(live - 6.0) < 0.3


def test_modus_ruhe_verwirft_langsames_atmen() -> None:
    f, _, _ = _atmend(0.1)  # 6/min: unter 8/min
    assert f.atemfrequenz() is not None
    assert f.atemfrequenz(modus=RUHE) is None


def test_unter_belastung_kein_wert() -> None:
    f = LiveFenster()
    t = 0.0
    for _ in range(200):
        rr = 450 + 10 * np.sin(2 * np.pi * 0.4 * t)
        t += rr / 1000
        f.hinzufuegen(t, int(rr), 133)
    assert f.atemfrequenz() is None


def test_artefaktanteil_im_fenster() -> None:
    f = LiveFenster()
    assert f.artefaktanteil() is None
    for i in range(1, 4):
        f.hinzufuegen(i * 0.8, 800, 75)
    assert f.artefaktanteil() is None  # zu wenige Schläge
    for i in range(4, 41):
        f.hinzufuegen(i * 0.8, 800, 75)
    assert f.artefaktanteil() == 0.0
    # Zehn implausible Schläge in den letzten 60 s von 40 + 10 → 20 %
    for i in range(41, 51):
        f.hinzufuegen(i * 0.8, 200, 75)
    anteil = f.artefaktanteil()
    assert anteil is not None and abs(anteil - 0.2) < 1e-9
    # Enges Fenster: nur die letzten Schläge zählen
    assert f.artefaktanteil(dauer_s=5.0) == 1.0
