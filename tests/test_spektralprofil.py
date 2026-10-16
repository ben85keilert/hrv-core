"""Spektrogramm und Spektralprofil — gegen den praxis_gui-Vorher-Stand.

``tests/golden/praxis_gui/`` enthält, was praxis_gui mit scipy auf derselben
korrigierten Reihe (``automatik.rr_ms``) gerechnet hat. Das Spektrogramm muss
auf 1e-9 gleich sein (reiner Umzug, Welch in numpy). Die Formmaße des
Spektralprofils sind reine Funktionen des Spektrums: gefüttert mit dem
praxis_gui-Spektrum (``psd_lomb``) liefern sie dessen Werte (dort auf drei
Nachkommastellen gerundet).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hrv_core import atmung
from hrv_core.frequency import spektrogramm
from hrv_core.spektralprofil import peak_merkmale, spektrale_form, spektralprofil

GOLDEN = Path(__file__).parent / "golden" / "praxis_gui"
DATEIEN = sorted(p.name for p in GOLDEN.glob("*.json"))


def _golden(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))["automatik"]


@pytest.mark.parametrize("name", DATEIEN)
def test_spektrogramm_wie_praxis_gui(name: str) -> None:
    g = _golden(name)
    soll = g.get("spektrogramm") or {}
    ist = spektrogramm(g["rr_ms"])
    if not soll.get("time_s"):
        assert ist["time_s"].size == 0
        return
    np.testing.assert_allclose(ist["time_s"], soll["time_s"], rtol=1e-9)
    np.testing.assert_allclose(ist["freq_hz"], soll["freq_hz"], rtol=1e-9)
    p_soll = np.asarray(soll["power_ms2"], dtype=float)
    np.testing.assert_allclose(ist["power_ms2"], p_soll, rtol=1e-9, atol=1e-9 * p_soll.max())


@pytest.mark.parametrize("name", DATEIEN)
def test_formmasse_wie_praxis_gui(name: str) -> None:
    g = _golden(name)
    psd = g.get("psd_lomb") or {}
    profil = g.get("spektralprofil") or {}
    if not psd.get("freqs") or profil.get("status") != "ok":
        pytest.skip("kein praxis_gui-Spektrum in der Golden-Datei")
    f, p = np.asarray(psd["freqs"]), np.asarray(psd["psd"])
    pm = peak_merkmale(f, p)
    form = spektrale_form(f, p)
    assert pm is not None and form is not None
    for k in ("peak_hz", "peak_breite_hz", "peak_q", "peak_anteil"):
        assert pm[k] == pytest.approx(profil[k], abs=1e-3), k
    for k in ("spektral_entropie", "spektral_flatness"):
        assert form[k] == pytest.approx(profil[k], abs=1e-3), k
    assert form["form_bins"] == profil["form_bins"]


def test_profil_auf_golden_reihe() -> None:
    """Das Profil rechnet durch und trägt die Bandwerte von `frequenzbereich`."""
    g = _golden(DATEIEN[0])
    rr = g["rr_ms"]
    t = g["t_herz_s"]
    profil = spektralprofil(rr, t, g["breaks"], nichtlinear=True, sampen_max_beats=300)
    assert profil["status"] == "ok"
    assert profil["profil_version"] == 2
    assert profil["lf"] is not None and profil["ln_lf"] == pytest.approx(np.log(profil["lf"]))
    assert profil["peak_hz"] is not None
    assert "coherence_index" not in profil
    assert profil["sampen_n"] == 300


def test_profil_zu_kurz() -> None:
    p = spektralprofil([800.0] * 10)
    assert p["status"] == "zu_kurz" and p["n"] == 10


def test_atmung_median_kurze_reihe_ist_ein_fenster() -> None:
    t = np.cumsum(np.full(45, 1000.0)) / 1000.0
    rr = 1000 + 25 * np.sin(2 * np.pi * 0.2 * t)
    m = atmung.median(t, rr)
    assert m.n_fenster == 1
    assert m.gueltig and m.rate_pro_min == pytest.approx(12.0, abs=0.5)
