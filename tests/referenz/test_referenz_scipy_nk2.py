"""Referenztests: die numpy-Implementierungen gegen scipy und neurokit2.

Laufen nur mit der Gruppe ``referenz`` (``uv sync --group referenz``); ohne die
Bibliotheken werden sie übersprungen. Sie sind der Beleg, dass hrv-core dieselbe
Mathematik rechnet wie die Referenzen, die praxis_gui bis Oktober 2026 benutzte
(scipy 1.18, neurokit2 0.2.12) — ohne dass die Apps sie brauchen.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hrv_core.frequency import (
    lomb_psd,
    periodogramm_psd,
    resample_tachogramm,
    spektrogramm,
    welch_psd,
)
from hrv_core.nonlinear import compute_dfa_alpha1

scipy_signal = pytest.importorskip("scipy.signal")
nk = pytest.importorskip("neurokit2")

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "trainingsapp"


def _rr(name: str) -> np.ndarray:
    m = json.loads((FIXTURES / name).read_text(encoding="utf-8"))["messungen"]
    rr = np.asarray([x["rr_ms"] for x in m], dtype=float)
    return rr[(rr >= 250) & (rr <= 2000)]


def _reihe(name: str) -> tuple[np.ndarray, np.ndarray]:
    rr = _rr(name)
    t = np.cumsum(rr) / 1000.0
    return t - rr / 2000.0, rr  # Intervallmitten wie `frequency`


DATEIEN = [
    "sensor_2026-05-23_125422.json",
    "sensor_synth_ruhe_sitzend_11.json",
    "sensor_synth_kohaerente_atmung_7.json",
]


@pytest.mark.parametrize("name", DATEIEN)
def test_lomb_wie_scipy(name: str) -> None:
    t, rr = _reihe(name)
    spanne = float(t[-1] - t[0])
    f = np.arange(1.0 / spanne, 0.5, 1.0 / spanne)
    ist = lomb_psd(t, rr, f)
    y = rr - rr.mean()
    soll = scipy_signal.lombscargle(t, y, 2 * np.pi * f, normalize=False) * 2.0 * spanne / y.size
    np.testing.assert_allclose(ist, soll, rtol=1e-9, atol=1e-9 * soll.max())


@pytest.mark.parametrize("name", DATEIEN)
def test_welch_wie_scipy(name: str) -> None:
    t, rr = _reihe(name)
    _, y = resample_tachogramm(t, rr, 4.0)
    nper = min(256, y.size)
    f_ist, p_ist = welch_psd(y, 4.0, nper)
    f_soll, p_soll = scipy_signal.welch(y, 4.0, nperseg=nper, noverlap=nper // 2)
    np.testing.assert_allclose(f_ist, f_soll, rtol=1e-12)
    np.testing.assert_allclose(p_ist, p_soll, rtol=1e-9, atol=1e-9 * p_soll.max())


@pytest.mark.parametrize("name", DATEIEN)
def test_periodogramm_wie_scipy(name: str) -> None:
    t, rr = _reihe(name)
    _, y = resample_tachogramm(t, rr, 4.0)
    f_ist, p_ist = periodogramm_psd(y, 4.0)
    f_soll, p_soll = scipy_signal.periodogram(y, 4.0)
    np.testing.assert_allclose(f_ist, f_soll, rtol=1e-12)
    np.testing.assert_allclose(p_ist, p_soll, rtol=1e-9, atol=1e-9 * p_soll.max())


@pytest.mark.parametrize("name", DATEIEN)
def test_dfa_alpha1_wie_neurokit2(name: str) -> None:
    rr = _rr(name)
    rr = rr[(rr >= 300) & (rr <= 2000)][-200:]
    ist = compute_dfa_alpha1(rr, window_n=200)
    assert ist is not None
    soll = nk.fractal_dfa(rr, scale=np.arange(4, 17), overlap=True, integrate=True, order=1)
    alpha = soll[0] if isinstance(soll, tuple) else soll
    alpha = float(np.asarray(alpha).ravel()[0]) if not isinstance(alpha, float) else alpha
    assert ist["dfa_alpha1"] == pytest.approx(alpha, rel=1e-10)


def test_sampen_nahe_neurokit2() -> None:
    """Richman/Moorman-Zählung: neurokit2 zählt beide Dimensionen über n−m Vorlagen,
    hrv-core (wie praxis_gui) B über n−m+1 — Abweichung klein, aber kein Bit-Gleichstand
    (docs/OFFENE_PUNKTE.md R1)."""
    from hrv_core.nonlinear import compute_sampen

    rr = _rr("sensor_2026-05-23_125422.json")
    ist = compute_sampen(rr)
    soll, _ = nk.entropy_sample(rr, dimension=2, tolerance=0.2 * float(np.std(rr)))
    assert ist == pytest.approx(float(soll), rel=0.02)


@pytest.mark.parametrize("name", DATEIEN)
def test_spektrogramm_wie_scipy(name: str) -> None:
    """Jedes Fenster des Spektrogramms ist ein scipy-Welch (256, 50 %) auf 4 Hz."""
    rr = _rr(name)
    sg = spektrogramm(rr)
    t_rs, y = resample_tachogramm((np.cumsum(rr) - rr) / 1000.0, rr, 4.0)
    n = 120 * 4
    for j, s in enumerate(range(0, t_rs.size - n + 1, 120)):
        stueck = y[s : s + n]
        stueck = stueck - stueck.mean()
        f, p = scipy_signal.welch(stueck, 4.0, nperseg=256, noverlap=128, scaling="density")
        maske = f <= 0.5
        np.testing.assert_allclose(sg["freq_hz"], f[maske], rtol=1e-12)
        np.testing.assert_allclose(sg["power_ms2"][:, j], p[maske], rtol=1e-9, atol=1e-9 * p.max())
