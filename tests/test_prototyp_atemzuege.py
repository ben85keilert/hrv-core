"""Prototyp Atemzüge und Atemphasen live (`hrv_core.prototyp.atemzuege`, Entscheidung 24 in
hrv-research): Kunstsignale, Kausalität (Rahmengröße, Abtastrate), Bewegung, Rechenlast.

Die Kunstsignale atmen als Neigung mit dem Vorzeichen des echten Gurts: sitzend fällt z beim
Einatmen, liegend steigt x — die Täler von (x − z) sind der Beginn „ein“.
"""

from __future__ import annotations

import itertools
import time

import numpy as np
import pytest

from hrv_core.prototyp import KENNZEICHEN
from hrv_core.prototyp import atemzuege as al


def _welle(
    dauer_s: float,
    rate_pro_min: float,
    rate_hz: float,
    *,
    haltung: str = "sitzen",
    amplitude: float = 15.0,
    rauschen: float = 2.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Atemwelle als Neigung: Tal (Beginn „ein“) bei t = k·Periode, Gipfel in der Mitte.

    Sitzend fällt z beim Einatmen (Schwerkraft auf −x), liegend steigt x (Schwerkraft auf +z).
    Liefert ``t, xyz, tal_s``.
    """
    t = np.arange(0, dauer_s, 1 / rate_hz)
    periode = 60.0 / rate_pro_min
    dehnung = -amplitude * np.cos(2 * np.pi * t / periode)  # Tal bei 0, Periode, 2·Periode …
    rng = np.random.default_rng(seed)
    r = rng.normal(0, rauschen, (t.size, 3))
    if haltung == "sitzen":
        xyz = np.column_stack([-1000 + 0 * t, -20 + 0 * t, 20 - dehnung]) + r
    else:
        xyz = np.column_stack([-10 + dehnung, 40 + 0 * t, 980 + 0 * t]) + r
    return t, xyz, np.arange(periode, dauer_s, periode)


def _lauf(xyz: np.ndarray, rate_hz: float, rahmen_s: float = 0.18, t0: float = 0.0):
    live = al.AtemLive(rate_hz)
    schritt = max(1, round(rahmen_s * rate_hz))
    ereignisse: list = []
    for i in range(0, xyz.shape[0], schritt):
        ereignisse += live.rahmen(xyz[i : i + schritt], t0 + i / rate_hz)
    ereignisse += live.abschluss()
    return live, ereignisse


def _phasen(ereignisse, art: str) -> np.ndarray:
    return np.array([e.t_s for e in ereignisse if isinstance(e, al.Phase) and e.art == art])


def _fenster(ereignisse) -> list[al.Fenster]:
    return [e for e in ereignisse if isinstance(e, al.Fenster)]


@pytest.mark.parametrize(
    ("haltung", "rate_hz", "rate_pro_min"),
    [("sitzen", 50.0, 12.0), ("liegen", 200.0, 15.0), ("sitzen", 52.0, 8.0)],
)
def test_zaehlt_und_phasiert_ein_kunstsignal(haltung, rate_hz, rate_pro_min) -> None:
    _, xyz, taeler = _welle(120, rate_pro_min, rate_hz, haltung=haltung)
    live, er = _lauf(xyz, rate_hz)
    ein, aus = _phasen(er, al.EIN), _phasen(er, al.AUS)
    # alle Täler ab dem zweiten (das erste hat keinen Gipfel davor) — bis auf eines am Ende
    assert abs(ein.size - (taeler.size - 1)) <= 1, (ein.size, taeler.size)
    fehler = np.array([np.min(np.abs(taeler - z)) for z in ein])
    assert np.median(fehler) < 0.6 and fehler.max() < 1.0, fehler
    periode = 60.0 / rate_pro_min
    gipfel = taeler - periode / 2
    fehler_aus = np.array([np.min(np.abs(gipfel - z)) for z in aus])
    assert np.median(fehler_aus) < 0.6, fehler_aus
    # „ein“ und „aus“ wechseln sich ab, jeder Atemzug trägt seine Nummer
    phasen = sorted((e for e in er if isinstance(e, al.Phase)), key=lambda e: e.t_s)
    for a, b in itertools.pairwise(phasen):
        assert a.art != b.art and (b.nr == a.nr or b.nr == a.nr + 1)
    fenster = _fenster(er)
    gueltig = [f for f in fenster if f.gueltig]
    assert len(gueltig) >= len(fenster) - 3, [f.gruende for f in fenster]
    assert all(abs(f.rate_pro_min - rate_pro_min) < 0.7 for f in gueltig)
    assert live.stand().atemzuege == ein.size and live.stand().art == KENNZEICHEN


def test_vorzeichenregel_x_minus_z_steigt_beim_einatmen() -> None:
    """Die Täler der Richtung (x − z) sind der Beginn „ein“ — sitzend wie liegend."""
    for haltung in ("sitzen", "liegen"):
        _, xyz, taeler = _welle(90, 12.0, 50.0, haltung=haltung, rauschen=0.5)
        _, er = _lauf(xyz, 50.0)
        ein = _phasen(er, al.EIN)
        # die Gipfel (Beginn „aus“) liegen 2,5 s neben den Tälern — ein Vorzeichenfehler hieße
        # Fehler um 2,5 s
        assert np.all([np.min(np.abs(taeler - z)) < 1.0 for z in ein]), haltung


def test_kausal_rahmengroesse_aendert_nichts() -> None:
    _, xyz, _ = _welle(100, 10.0, 200.0, seed=3)
    laeufe = [_lauf(xyz, 200.0, rahmen_s=r)[1] for r in (0.18, 1.0, 5.0, 0.005)]

    def kern(er):
        phasen = sorted((e.art, e.nr, round(e.t_s, 6)) for e in er if isinstance(e, al.Phase))
        fenster = [(f.bis_s, f.rate_pro_min, f.gruende) for f in _fenster(er)]
        return phasen, fenster

    bezug = kern(laeufe[0])
    assert bezug[0] and bezug[1]
    for er in laeufe[1:]:
        assert kern(er) == bezug


def test_abtastrate_50_und_200_hz_zaehlen_gleich() -> None:
    _, xyz200, _ = _welle(100, 14.0, 200.0, seed=5)
    xyz50 = xyz200.reshape(-1, 4, 3).mean(axis=1)
    _, er200 = _lauf(xyz200, 200.0)
    _, er50 = _lauf(xyz50, 50.0)
    e200, e50 = _phasen(er200, al.EIN), _phasen(er50, al.EIN)
    assert abs(e200.size - e50.size) <= 1
    n = min(e200.size, e50.size)
    assert np.max(np.abs(e200[:n] - e50[:n])) < 0.15


def test_bewegung_unterbricht_und_nimmt_zurueck() -> None:
    t, xyz, _ = _welle(120, 12.0, 50.0, rauschen=1.0)
    xyz[:, 1] += 600 * (t > 60.0)  # Lagesprung bei 60 s, dann 15 s Unruhe
    rng = np.random.default_rng(1)
    unruhig = (t > 60.0) & (t < 75.0)
    xyz[unruhig] += rng.normal(0, 60, (int(unruhig.sum()), 3))
    _, er = _lauf(xyz, 50.0)
    ein = _phasen(er, al.EIN)
    # kein Ereignis im Rand um die Bewegung, davor und danach wird gezählt
    assert not np.any((ein > 59.0) & (ein < 77.0)), ein
    assert np.sum(ein < 59) >= 9 and np.sum(ein > 77) >= 6
    fenster = _fenster(er)
    um = [f for f in fenster if 60 <= f.von_s <= 65]  # weniger als 60 % ruhig
    assert um and all("bewegung" in f.gruende for f in um), [f.gruende for f in um]
    spaeter = [f for f in fenster if f.von_s > 80]
    assert spaeter and all(f.gueltig for f in spaeter[2:]), [f.gruende for f in spaeter]


def test_rauschen_ohne_atmung_nennt_keine_zahl() -> None:
    rng = np.random.default_rng(7)
    xyz = np.column_stack(
        [-1000 + rng.normal(0, 2, 5000), rng.normal(0, 2, 5000), rng.normal(0, 2, 5000)]
    )
    _, er = _lauf(xyz, 50.0)
    fenster = _fenster(er)
    assert fenster and not any(f.gueltig for f in fenster)
    assert all(f.rate_pro_min is None for f in fenster)


def test_luecke_in_der_zeitachse_ist_bewegung() -> None:
    _, xyz, _ = _welle(60, 12.0, 50.0, rauschen=0.5)
    live = al.AtemLive(50.0)
    er = live.rahmen(xyz[:1500], 0.0) + live.rahmen(xyz[1500:], 40.0)  # 10 s fehlen
    er += live.abschluss()
    ein = _phasen(er, al.EIN)
    assert not np.any((ein > 29.0) & (ein < 42.0)), ein


def test_stand_zeigt_vorlaeufige_phase() -> None:
    _, xyz, _ = _welle(30, 12.0, 50.0, rauschen=0.5)
    live = al.AtemLive(50.0)
    phasen = []
    for i in range(0, xyz.shape[0], 25):
        live.rahmen(xyz[i : i + 25], i / 50.0)
        phasen.append(live.stand().phase)
    assert al.EIN in phasen and al.AUS in phasen
    assert live.stand().gueltig is False or live.stand().rate_pro_min is not None


def test_offline_huelle_fasst_zusammen() -> None:
    _, xyz, _ = _welle(90, 12.0, 100.0)
    a = al.atemzuege(xyz, 100.0, t0_s=5.0)
    assert a.art == KENNZEICHEN and a.gueltig and a.rate_pro_min == pytest.approx(12.0, abs=0.6)
    assert a.gleichmaessigkeit > 0.9 and len(a.ein_s) >= 15 and len(a.aus_s) >= 15
    assert min(a.ein_s) >= 5.0  # Zeiten auf der Achse der Eingabe
    leer = al.atemzuege(np.zeros((400, 3)), 50.0)
    assert not leer.gueltig and leer.gruende == ("zu_kurz",)


def test_rechenlast_unter_20_ms_je_sekunde() -> None:
    _, xyz, _ = _welle(120, 12.0, 200.0)
    start = time.perf_counter()
    _lauf(xyz, 200.0)
    dauer = time.perf_counter() - start
    assert dauer / 120.0 < 0.020, dauer
