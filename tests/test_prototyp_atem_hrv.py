"""Prototyp Atem-HRV je Atemzug (`hrv_core.prototyp.atem_hrv`, Entscheidung 25 in
hrv-research): Kunstsignale mit bekannter Spanne und Phasenlage, Trend, Lücke und Artefakt, die
Gründe, Prüffenster, Live = Offline in jeder Reihenfolge, die Zusammenfassung.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from hrv_core.prototyp import KENNZEICHEN
from hrv_core.prototyp import atem_hrv as ah


def _schlaege(
    dauer_s: float,
    periode_s: float,
    *,
    rr0: float = 800.0,
    amplitude: float = 40.0,
    gipfel_anteil: float = 0.4,
    trend_ms_je_s: float = 0.0,
    seed: int = 0,
    rauschen: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Schläge, deren RR mit der Atmung schwingt: HF-Gipfel (kürzestes RR) bei
    ``gipfel_anteil`` der Periode nach jedem „ein“ (bei 0, Periode, 2·Periode …)."""
    rng = np.random.default_rng(seed)
    t_ende: list[float] = []
    rr: list[float] = []
    t = 0.0
    while t < dauer_s:
        mitte = t + rr0 / 2000.0
        wert = (
            rr0
            - amplitude * math.cos(2 * math.pi * (mitte / periode_s - gipfel_anteil))
            + trend_ms_je_s * mitte
            + rng.normal(0.0, rauschen)
        )
        t += wert / 1000.0
        t_ende.append(t)
        rr.append(wert)
    return np.array(t_ende), np.array(rr)


def _phasen(dauer_s: float, periode_s: float, ein_anteil: float = 0.4) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    t = 0.0
    while t <= dauer_s:
        out += [(t, ah.EIN), (t + ein_anteil * periode_s, ah.AUS)]
        t += periode_s
    return out


@pytest.mark.parametrize("periode_s", [10.0, 5.0, 4.0])
def test_spanne_und_phasenlage_eines_kunstsignals(periode_s: float) -> None:
    t, rr = _schlaege(300.0, periode_s, amplitude=40.0, gipfel_anteil=0.4)
    zuege = ah.atem_hrv(_phasen(300.0, periode_s, ein_anteil=0.4), t, rr)
    gueltig = [z for z in zuege if z.gueltig]
    assert len(gueltig) >= 0.9 * len(zuege) and len(zuege) >= 300 / periode_s - 2
    z = ah.zusammenfassen(zuege)
    assert z.art == KENNZEICHEN and zuege[0].art == KENNZEICHEN
    # Spanne: 2·Amplitude, nach unten nur durch die Abtastung mit Schlägen begrenzt
    assert z.spanne_ms_median is not None and 60.0 <= z.spanne_ms_median <= 81.0
    assert z.sinus_bpm_median is not None and z.spanne_bpm_median is not None
    assert abs(z.sinus_bpm_median - 2 * 40 * 60000 / 800**2) < 1.0  # ≈ 7,5 bpm
    # HF-Gipfel genau am Ende des Einatmens (0,4 der Periode): Phasenlage 0, Winkel 144°
    assert z.phasenlage_s_median is not None and abs(z.phasenlage_s_median) < 0.12 * periode_s
    assert z.winkel_grad is not None and abs(z.winkel_grad - 144.0) < 15.0
    assert z.ein_aus_median is not None and abs(z.ein_aus_median - 1.5) < 1e-6
    assert z.rate_pro_min == pytest.approx(60.0 / periode_s, abs=0.05)
    # Einatmen = kürzere Abstände: Differenz aus − ein positiv
    assert z.rr_differenz_ms_median is not None and z.rr_differenz_ms_median > 0.0
    assert z.ln_spanne_ms is not None and math.exp(z.ln_spanne_ms) == pytest.approx(
        z.spanne_ms_median, rel=0.1
    )


def test_phasenlage_folgt_dem_gipfel() -> None:
    # Gipfel 1 s nach dem Ende des Einatmens (ein 2 s von 5 s → Gipfel bei 0,6 der Periode)
    t, rr = _schlaege(200.0, 5.0, gipfel_anteil=0.6)
    z = ah.zusammenfassen(ah.atem_hrv(_phasen(200.0, 5.0, ein_anteil=0.4), t, rr))
    assert z.phasenlage_s_median == pytest.approx(1.0, abs=0.3)
    assert z.phasenlage_anteil_median == pytest.approx(0.2, abs=0.06)
    # Gipfel am Beginn des Einatmens: zirkulär nahe −2 s bzw. +3 s → Anteil um −0,4 / 0,6 …
    t, rr = _schlaege(200.0, 5.0, gipfel_anteil=0.0)
    z = ah.zusammenfassen(ah.atem_hrv(_phasen(200.0, 5.0, ein_anteil=0.4), t, rr))
    assert z.winkel_grad is not None and (z.winkel_grad < 20.0 or z.winkel_grad > 340.0)
    assert z.phasenlage_s_median is not None and -2.5 < z.phasenlage_s_median <= 2.5


def test_trend_wird_bereinigt() -> None:
    # 6 ms je Sekunde Drift (Erholung): ohne Bereinigung wüchse die Spanne eines 10-s-Atemzugs
    # um 60 ms — mit der Geraden durch die Mittel der Nachbarn bleibt sie bei ≈ 80 ms
    t, rr = _schlaege(300.0, 10.0, amplitude=40.0, trend_ms_je_s=6.0)
    zuege = ah.atem_hrv(_phasen(300.0, 10.0), t, rr)
    spaeter = [z for z in zuege[1:] if z.gueltig]
    assert spaeter and all(z.trend_ms_je_s == pytest.approx(6.0, abs=1.0) for z in spaeter)
    assert all(70.0 <= (z.spanne_ms or 0) <= 90.0 for z in spaeter)
    assert zuege[0].trend_ms_je_s == 0.0  # kein Vorgänger: Konstante
    assert 70.0 <= (zuege[0].spanne_ms or 0) <= 140.0


def test_luecke_artefakt_und_zu_wenig_schlaege() -> None:
    t, rr = _schlaege(100.0, 5.0)
    phasen = _phasen(100.0, 5.0)
    # Lücke: drei Schläge aus dem Atemzug 20–25 s entfernen
    im = (t > 21.0) & (t < 24.0)
    zuege = ah.atem_hrv(phasen, t[~im], rr[~im])
    (z,) = [z for z in zuege if z.ein_s == 20.0]
    assert not z.gueltig and ah.LUECKE in z.gruende
    assert all(zz.gueltig for zz in zuege if zz.ein_s not in (20.0,))
    # Artefakt: ein RR fehlt (NaN) im Atemzug 40–45 s
    rr2 = rr.copy()
    rr2[np.flatnonzero((t > 41.0) & (t < 44.0))[0]] = np.nan
    (z,) = [z for z in ah.atem_hrv(phasen, t, rr2) if z.ein_s == 40.0]
    assert not z.gueltig and z.gruende == (ah.ARTEFAKT,)
    assert z.spanne_ms is not None  # Zahlen zur Diagnose bleiben
    # Zu wenig Schläge: 40 bpm bei 20/min → zwei Schläge je Atemzug
    t3, rr3 = _schlaege(60.0, 3.0, rr0=1500.0, amplitude=30.0)
    zuege3 = ah.atem_hrv(_phasen(60.0, 3.0), t3, rr3)
    assert zuege3 and all(ah.ZU_WENIG_SCHLAEGE in z.gruende for z in zuege3)


def test_phase_ohne_schlag_und_dauer() -> None:
    # Einatmen 0,3 s lang bei 75 bpm: fast immer ohne Schlag
    t, rr = _schlaege(60.0, 5.0)
    phasen = [(5.0 * k + p, a) for k in range(13) for p, a in ((0.0, ah.EIN), (0.3, ah.AUS))]
    zuege = ah.atem_hrv(phasen, t, rr)
    assert sum(ah.PHASE_OHNE_SCHLAG in z.gruende for z in zuege) >= 0.6 * len(zuege)
    # zu lang (25 s) und zu kurz (1 s)
    lang = [(0.0, ah.EIN), (10.0, ah.AUS), (25.0, ah.EIN), (25.5, ah.AUS), (26.0, ah.EIN)]
    zl = ah.atem_hrv([*lang, (28.0, ah.AUS), (31.0, ah.EIN)], t, rr)
    assert [z.gruende[:1] for z in zl] == [(ah.ZU_LANG,), (ah.ZU_KURZ,), ()]


def test_verpasster_atemzug_ist_untypisch() -> None:
    t, rr = _schlaege(120.0, 5.0)
    phasen = _phasen(120.0, 5.0)
    # das „ein“ und „aus“ bei 50 s fehlen: der Atemzug ab 45 s dauert 10 s
    verdorben = [(x, a) for x, a in phasen if not (49.9 < x < 53.0)]
    zuege = ah.atem_hrv(verdorben, t, rr)
    (z,) = [z for z in zuege if z.ein_s == 45.0]
    assert z.dauer_s == 10.0 and z.gruende == (ah.DAUER_UNTYPISCH,)
    assert all(zz.gueltig for zz in zuege if zz.ein_s != 45.0)
    # vorher zu wenig gültige Atemzüge: die ersten drei dürfen nicht an der Regel scheitern
    kurz = ah.atem_hrv(
        [(0.0, ah.EIN), (2.0, ah.AUS), (10.0, ah.EIN), (12.0, ah.AUS), (15.0, ah.EIN)], t, rr
    )
    assert all(ah.DAUER_UNTYPISCH not in z.gruende for z in kurz)


def test_live_gleich_offline_in_jeder_reihenfolge() -> None:
    t, rr = _schlaege(120.0, 5.0, rauschen=5.0, seed=3)
    phasen = _phasen(120.0, 5.0)
    offline = ah.atem_hrv(phasen, t, rr)
    assert len(offline) >= 20
    # 1) alle Phasen im Voraus (Takt), dann die Schläge
    live = ah.AtemHrvLive()
    a: list[ah.Atemzug] = []
    for x, art in phasen:
        a += live.phase(x, art)
    for tk, rk in zip(t, rr, strict=True):
        a += live.schlag(tk, rk)
    assert a == offline
    # 2) Phasen zwei Sekunden nach ihrer Zeit (Sensor)
    live = ah.AtemHrvLive()
    b: list[ah.Atemzug] = []
    ereignisse = sorted(
        [(x + 2.0, 0, x, art) for x, art in phasen]
        + [(tk, 1, tk, rk) for tk, rk in zip(t, rr, strict=True)]
    )
    for _, nr, x, wert in ereignisse:
        b += live.phase(x, wert) if nr == 0 else live.schlag(x, wert)
    assert b == offline
    assert live.letzter == offline[-1]


def test_pairung_der_phasen() -> None:
    t, rr = _schlaege(40.0, 5.0)
    # zwei „ein“ hintereinander: das erste fällt weg; „aus“ ohne „ein“ wird übergangen
    phasen = [
        (1.0, ah.AUS),
        (5.0, ah.EIN),
        (6.0, ah.EIN),
        (8.0, ah.AUS),
        (11.0, ah.EIN),
        (13.0, ah.AUS),
    ]
    zuege = ah.atem_hrv(phasen, t, rr)
    assert [(z.ein_s, z.aus_s, z.ende_s) for z in zuege] == [(6.0, 8.0, 11.0)]
    assert zuege[0].ein_dauer_s == 2.0 and zuege[0].aus_dauer_s == 3.0
    # ohne Schlag bis zum Ende bleibt der letzte Atemzug offen
    assert ah.atem_hrv([(0.0, ah.EIN), (2.0, ah.AUS), (50.0, ah.EIN)], t, rr) == []


def test_zusammenfassung() -> None:
    t, rr = _schlaege(100.0, 5.0)
    zuege = ah.atem_hrv(_phasen(100.0, 5.0), t, rr)
    leer = ah.zusammenfassen([])
    assert leer.n == 0 and leer.anteil_gueltig is None and leer.rate_pro_min is None
    z = ah.zusammenfassen(zuege)
    assert z.n == len(zuege) and z.n_gueltig == len(zuege) and z.anteil_gueltig == 1.0
    assert z.gruende == ()
    kaputt = [
        zuege[0].__class__(**{**_felder(zuege[0]), "gueltig": False, "gruende": (ah.LUECKE,)})
    ]
    z2 = ah.zusammenfassen(kaputt + zuege[1:])
    assert z2.n_gueltig == len(zuege) - 1 and z2.gruende == (ah.LUECKE,)


def _felder(z: ah.Atemzug) -> dict:
    return {name: getattr(z, name) for name in z.__slots__}  # type: ignore[attr-defined]


def test_fenster_des_phasen_prototyps() -> None:
    t, rr = _schlaege(120.0, 5.0)
    phasen = _phasen(120.0, 5.0)
    # Fenster 30 s alle 5 s; 55–85 s ungültig (Bewegung)
    # Fenster enden bei 115: der letzte Atemzug (115–120) hat keins mehr nach sich
    fenster = [(bis - 30.0, bis, not (55.0 <= bis <= 85.0)) for bis in np.arange(30.0, 120.0, 5.0)]
    zuege = ah.atem_hrv(phasen, t, rr, fenster)
    ohne = ah.atem_hrv(phasen, t, rr)
    assert len(zuege) == len(ohne)
    schlecht = [z for z in zuege if not z.gueltig]
    # das erste Fenster, das nach dem Atemzug endet, entscheidet: Enden 55 … 85 → ende 55 … 85
    assert all(z.gruende == (ah.FENSTER_UNGUELTIG,) for z in schlecht)
    assert {z.ein_s for z in schlecht} == {50.0 + 5.0 * k for k in range(7)} | {115.0}
    # Zahlen bleiben gleich, nur die Gültigkeit nicht
    assert [z.spanne_ms for z in zuege] == [z.spanne_ms for z in ohne]
    # live, Fenster treffen nach ihrem Ende ein: dieselbe Antwort, auch für den Rest am Ende
    live = ah.AtemHrvLive()
    a: list[ah.Atemzug] = []
    ereignisse = sorted(
        [(x + 2.0, 0, x, art) for x, art in phasen]
        + [(tk, 1, tk, rk) for tk, rk in zip(t, rr, strict=True)]
        + [(bis + 1.0, 2, von, ok) for von, bis, ok in fenster]
    )
    for zeit, nr, x, wert in ereignisse:
        if nr == 0:
            a += live.phase(x, wert)
        elif nr == 1:
            a += live.schlag(x, wert)
        else:
            a += live.fenster(x, zeit - 1.0, bool(wert))
    assert len(a) < len(zuege)  # der letzte wartet auf sein Fenster
    a += live.abschluss()
    assert a == zuege
