"""Prototyp Wiederholungszähler (`hrv_core.prototyp.wiederholungen`) an Kunstsignalen."""

from __future__ import annotations

import numpy as np

from hrv_core.prototyp import KENNZEICHEN
from hrv_core.prototyp import wiederholungen as wh


def _satz(n: int, periode_s: float, rate: float = 200.0, rauschen: float = 30.0, seed: int = 1):
    rng = np.random.default_rng(seed)
    dauer = n * periode_s
    t = np.arange(0, dauer, 1 / rate)
    # Absenken und Aufrichten, ungleich schnell (unten kurz verweilen), dazu Atmung und Rauschen
    phase = 2 * np.pi * t / periode_s
    bewegung = 250 * np.sin(phase) + 80 * np.sin(2 * phase)
    atmung = 40 * np.sin(2 * np.pi * t / 4.5)
    achsen = np.column_stack([0.3 * bewegung, -980 + bewegung + atmung, 0.2 * bewegung])
    return achsen + rng.normal(0, rauschen, achsen.shape), rate


def test_zaehlt_saetze_verschiedener_tempi() -> None:
    for n, periode in ((10, 3.9), (15, 2.1), (20, 1.8), (30, 1.0)):
        xyz, rate = _satz(n, periode)
        z = wh.zaehlen(xyz, rate)
        assert abs(z.anzahl - n) <= 1, (n, periode, z)
        assert z.periode_s is not None and abs(z.periode_s - periode) < 0.15 * periode


def test_ruhe_ergibt_keine_wiederholung() -> None:
    rng = np.random.default_rng(2)
    xyz = np.column_stack([np.zeros(4000), -1000 + rng.normal(0, 5, 4000), np.zeros(4000)])
    assert wh.zaehlen(xyz, 200.0).anzahl == 0


def test_ergebnis_ist_als_prototyp_gekennzeichnet() -> None:
    xyz, rate = _satz(8, 2.0)
    assert wh.zaehlen(xyz, rate).art == KENNZEICHEN == "prototyp"
