"""Live-Wiederholungszähler (`hrv_core.prototyp.wiederholungen.WdhLive`, Entscheidung 26) an
Kunstsignalen: Takt, Tempowechsel, Pause, halbe, Abbruch, Übergang, Kausalität (Rahmengröße,
50/200 Hz), Vorlagen, Offline-Hülle, Rechenlast."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from hrv_core.prototyp import KENNZEICHEN
from hrv_core.prototyp import wiederholungen as wl


def _kniebeugen(
    perioden_s: list[float],
    rate_hz: float = 50.0,
    *,
    hub_mg: float | list[float] = 600.0,
    ruhe_vor_s: float = 1.0,
    ruhe_nach_s: float = 2.0,
    rauschen: float = 8.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Kniebeugen auf der Brust: Beginn oben, je Wiederholung eine Periode ``1 − cos``; z fällt
    nach vorn, x wippt mit. Liefert ``xyz`` und die Zeiten der unteren Umkehrpunkte."""
    hube = [hub_mg] * len(perioden_s) if isinstance(hub_mg, int | float) else list(hub_mg)
    teile = [np.zeros(int(ruhe_vor_s * rate_hz))]
    unten: list[float] = []
    t_lauf = ruhe_vor_s
    for per, hub in zip(perioden_s, hube, strict=True):
        n = round(per * rate_hz)
        teile.append(hub * (1 - np.cos(2 * np.pi * np.arange(n) / n)) / 2)
        unten.append(t_lauf + per / 2)
        t_lauf += per
    teile.append(np.zeros(int(ruhe_nach_s * rate_hz)))
    weg = np.concatenate(teile)
    rng = np.random.default_rng(seed)
    xyz = np.column_stack([-1000 + 0.15 * weg, 60 + 0 * weg, 120 - weg])
    return xyz + rng.normal(0, rauschen, xyz.shape), np.array(unten)


def _drehen(xyz: np.ndarray, grad: float, achse: str) -> np.ndarray:
    """Die Proben um ``grad`` um eine Geräteachse gedreht — ein anders sitzender Gurt."""
    c, s = math.cos(math.radians(grad)), math.sin(math.radians(grad))
    if achse == "x":
        r = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    elif achse == "y":
        r = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    else:
        r = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return np.asarray(xyz, dtype=np.float64) @ r.T


def _lauf(xyz: np.ndarray, rate_hz: float, vorlage="auto", rahmen_s: float = 0.18, t0: float = 0.0):
    live = wl.WdhLive(rate_hz, vorlage)
    schritt = max(1, round(rahmen_s * rate_hz))
    ereignisse: list = []
    for i in range(0, xyz.shape[0], schritt):
        ereignisse += live.rahmen(xyz[i : i + schritt], t0 + i / rate_hz)
    ereignisse += live.abschluss()
    return live, ereignisse


def _zeiten(ereignisse) -> np.ndarray:
    return np.array([w.t_s for w in wl.gueltige(ereignisse)])


@pytest.mark.parametrize("rate_hz", [50.0, 52.0, 200.0])
def test_zaehlt_im_takt_wenn_es_geschieht(rate_hz) -> None:
    xyz, unten = _kniebeugen([2.5] * 12, rate_hz)
    live, er = _lauf(xyz, rate_hz)
    wdh = wl.gueltige(er)
    assert len(wdh) == 12 and live.stand().anzahl == 12 and live.stand().halbe == 0
    assert np.allclose(_zeiten(er), unten, atol=0.2)
    verzug = np.array([w.gemeldet_s - w.t_s for w in wdh])
    assert verzug.max() < 1.25 and verzug.min() > 0  # unter einer halben Periode, nie vorher
    assert all(w.nr == i + 1 for i, w in enumerate(wdh))
    assert live.stand().periode_s == pytest.approx(2.5, abs=0.1)
    assert live.stand().art == KENNZEICHEN


def test_tempowechsel_und_hub_wechsel() -> None:
    perioden = [3.0] * 5 + [1.5] * 8 + [4.0] * 3
    xyz, unten = _kniebeugen(perioden, 50.0, hub_mg=[700] * 5 + [450] * 8 + [800] * 3)
    _, er = _lauf(xyz, 50.0)
    assert len(wl.gueltige(er)) == 16
    assert np.allclose(_zeiten(er), unten, atol=0.25)


def test_pause_im_satz_beendet_nichts() -> None:
    a, unten_a = _kniebeugen([2.0] * 6, 50.0, ruhe_nach_s=12.0)
    b, unten_b = _kniebeugen([2.0] * 6, 50.0, ruhe_vor_s=0.0, seed=1)
    xyz = np.vstack([a, b])
    _, er = _lauf(xyz, 50.0)
    assert len(wl.gueltige(er)) == 12
    assert not any(isinstance(e, wl.Ruecknahme) for e in er)
    erwartet = np.concatenate([unten_a, unten_b + a.shape[0] / 50.0])
    assert np.allclose(_zeiten(er), erwartet, atol=0.25)


def test_rahmengroesse_aendert_nichts() -> None:
    xyz, _ = _kniebeugen([2.2] * 8, 50.0)
    laeufe = [_lauf(xyz, 50.0, rahmen_s=r)[1] for r in (0.02, 0.18, 1.0, 3.0)]
    bezug = [(round(w.t_s, 6), w.nr, w.art) for w in wl.gueltige(laeufe[0])]
    for er in laeufe[1:]:
        assert [(round(w.t_s, 6), w.nr, w.art) for w in wl.gueltige(er)] == bezug


def test_50_und_200_hz_zaehlen_gleich() -> None:
    xyz200, unten = _kniebeugen([2.0] * 10, 200.0)
    xyz50 = xyz200.reshape(-1, 4, 3).mean(axis=1)
    _, er200 = _lauf(xyz200, 200.0)
    _, er50 = _lauf(xyz50, 50.0)
    assert len(wl.gueltige(er200)) == len(wl.gueltige(er50)) == 10
    assert np.allclose(_zeiten(er200), _zeiten(er50), atol=0.1)
    assert np.allclose(_zeiten(er200), unten, atol=0.2)


def test_ruhe_und_wackler_zaehlen_nicht() -> None:
    rng = np.random.default_rng(3)
    xyz = np.column_stack(
        [-1000 + rng.normal(0, 5, 3000), 60 + rng.normal(0, 5, 3000), 120 + rng.normal(0, 5, 3000)]
    )
    # dazu Atmung (Neigung ~ 15 mG) und ein kleiner Ruck
    t = np.arange(3000) / 50.0
    xyz[:, 2] += 15 * np.sin(2 * np.pi * t / 4.0)
    xyz[1000:1010, 2] -= 60
    live, er = _lauf(xyz, 50.0)
    assert wl.gueltige(er) == [] and live.stand().anzahl == 0


def test_halbe_wiederholung_wird_erkannt() -> None:
    xyz, unten = _kniebeugen([2.0] * 10, 50.0, hub_mg=[600] * 5 + [300] + [600] * 4)
    live, er = _lauf(xyz, 50.0)
    wdh = wl.gueltige(er)
    assert len(wdh) == 10 and live.stand().anzahl == 9 and live.stand().halbe == 1
    assert wdh[5].art == wl.ART_HALB and wdh[5].t_s == pytest.approx(unten[5], abs=0.2)


def test_uebergang_am_anfang_wird_nachtraeglich_zurueckgenommen() -> None:
    # Hinstellen: ein Ausschlag von 160 mG, dann Kniebeugen mit 900 mG
    xyz, unten = _kniebeugen([1.5] + [2.0] * 8, 50.0, hub_mg=[160] + [900] * 8)
    live, er = _lauf(xyz, 50.0)
    rn = [e for e in er if isinstance(e, wl.Ruecknahme)]
    assert len(rn) == 1 and rn[0].grund == wl.GRUND_UEBERGANG and rn[0].nr == 1
    assert len(wl.gueltige(er)) == 8 and live.stand().anzahl == 8
    assert np.allclose(_zeiten(er), unten[1:], atol=0.2)


def test_strom_beginnt_mitten_in_der_ersten_wiederholung() -> None:
    xyz, unten = _kniebeugen([2.0] * 8, 50.0, ruhe_vor_s=0.0, ruhe_nach_s=3.0)
    # der Tipp lag 0,5 s vor dem ersten Rahmen: mitten im Abstieg — unten zählt
    ab = int(0.5 * 50)
    live, er = _lauf(xyz[ab:], 50.0, t0=ab / 50.0)
    assert live.stand().anzahl == 8 and not any(isinstance(e, wl.Ruecknahme) for e in er)
    assert np.allclose(_zeiten(er), unten, atol=0.25)
    # 1,4 s danach: mitten im Aufstieg — die Rollen sind vertauscht, gezählt wird oben (eine
    # halbe Periode später), die Ruhe am Ende (in der Ausgangslage) holt die letzte nach
    ab = int(1.4 * 50)
    live, er = _lauf(xyz[ab:], 50.0, t0=ab / 50.0)
    assert live.stand().anzahl == 8
    assert np.allclose(_zeiten(er), unten + 1.0, atol=0.3)


def test_abbruch_nimmt_unbestaetigte_zurueck() -> None:
    rate = 50.0
    a, _ = _kniebeugen([2.0] * 4, rate, ruhe_nach_s=0.0)
    # hinunter (−600 auf z), gut 40 % wieder hoch, dann 3 s stehen bleiben
    n = int(0.8 * rate)
    runter = 120 - 600 * np.linspace(0, 1, n)
    hoch = 120 - 600 + 260 * np.linspace(0, 1, int(0.4 * rate))
    stehen = np.full(int(3 * rate), hoch[-1])
    z = np.concatenate([runter, hoch, stehen])
    b = np.column_stack([-1000 + 0 * z, 60 + 0 * z, z])
    live, er = _lauf(np.vstack([a, b]), rate)
    rn = [e for e in er if isinstance(e, wl.Ruecknahme)]
    assert len(rn) == 1 and rn[0].grund == wl.GRUND_STILLSTAND and rn[0].nr == 5
    assert live.stand().anzahl == 4 and not live.stand().unbestaetigt


def test_umkehr_oben_zaehlt_die_rueckkehr_auch_die_letzte() -> None:
    xyz, unten = _kniebeugen([2.0] * 6, 50.0, ruhe_nach_s=3.0)
    v = wl.Vorlage(
        "t", "t", wl.SIGNAL_HAUPTACHSE, wl.ZAEHLTYP_PERIODISCH, (0.8, 8.0), wl.UMKEHR_OBEN, 100.0
    )
    live = wl.WdhLive(50.0, v)
    er: list = []
    for i in range(0, xyz.shape[0], 9):
        er += live.rahmen(xyz[i : i + 9], i / 50.0)
    # die letzte kommt in Ruhe (Stillstand), nicht erst mit abschluss()
    assert live.stand().anzahl == 6
    assert np.allclose(_zeiten(er), unten + 1.0, atol=0.25)


def test_feste_achse_und_neigung_mit_tal() -> None:
    xyz, unten = _kniebeugen([2.0] * 8, 50.0)
    for schluessel in ("kniebeuge", "rudern"):
        live, er = _lauf(xyz, 50.0, schluessel)
        assert live.stand().anzahl == 8, schluessel
        assert live.stand().signal == wl.SIGNAL_NEIGUNG_ZX  # kein Rückfall: Schwerkraft auf x
        assert np.allclose(_zeiten(er), unten, atol=0.25)
    live, er = _lauf(xyz, 50.0, wl.mit_signal(wl.VORLAGEN["auto"], wl.SIGNAL_Z))
    assert live.stand().anzahl == 8
    # gedreht um x (Gurt schief): Neigung z–x und Hauptachse zählen weiter
    gedreht = _drehen(xyz, 25.0, "x")
    for schluessel in ("auto", "kniebeuge"):
        assert _lauf(gedreht, 50.0, schluessel)[0].stand().anzahl == 8


def test_neigung_ohne_schwerkraft_in_der_ebene_faellt_auf_die_hauptachse_zurueck() -> None:
    # Schwerkraft auf y (Sensor anders getragen): in der Ebene z–x liegt fast nichts
    xyz, unten = _kniebeugen([2.0] * 8, 50.0)
    xyz = xyz[:, [1, 0, 2]]
    live, er = _lauf(xyz, 50.0, "kniebeuge")
    st = live.stand()
    assert st.signal == wl.SIGNAL_HAUPTACHSE and st.umkehr == wl.UMKEHR_UNTEN
    assert live.vorlage.min_hub == wl.MIN_HUB_MG and live.vorlage.geraet is None
    assert st.anzahl == 8 and np.allclose(_zeiten(er), unten, atol=0.25)


def test_vorlagen_katalog() -> None:
    assert wl.vorlage("unbekannt").schluessel == "auto" and wl.vorlage(None).schluessel == "auto"
    assert wl.vorlage(wl.VORLAGEN["rudern"]) is wl.VORLAGEN["rudern"]
    assert set(wl.VORLAGEN) >= {"auto", "kniebeuge", "liegestuetz", "rudern", "burpee"}
    for v in wl.VORLAGEN.values():
        assert v.signal in wl.SIGNALE and v.periode_s[0] < v.periode_s[1]
        assert (v.geraet is not None) == (v.signal in wl.ACHSENSIGNALE)
    assert wl.VORLAGEN["auto"].geraet is None and wl.VORLAGEN["auto"].umkehr == wl.UMKEHR_UNTEN
    assert not wl.VORLAGEN["burpee"].verfuegbar and wl.VORLAGEN["burpee"].zustaende
    with pytest.raises(ValueError):
        wl.WdhLive(50.0, "burpee")
    with pytest.raises(ValueError):
        wl.WdhLive(0.0)


def test_offline_huelle_und_ergebnis() -> None:
    xyz, _ = _kniebeugen([2.0] * 10, 50.0)
    z = wl.zaehlen(xyz, 50.0, 100.0)
    assert z.anzahl == 10 and z.art == KENNZEICHEN and z.gleichmaessigkeit > 0.95
    assert z.zeiten_s[0] > 100.0 and len(z.verzug_s) == 10 and z.ruecknahmen == 0
    assert z.periode_s == pytest.approx(2.0, abs=0.1) and z.hub is not None
    assert z.halbe_s == ()


def test_zaehlung_bleibt_rueckwaertskompatibel() -> None:
    # Die Felder von 0.8.0 (Satzfenster) heißen und stehen, wie sie waren; neue haben Vorgaben
    alt = wl.Zaehlung(3, (1.0, 2.0, 3.0), 1.0, 0.9)
    assert alt.art == KENNZEICHEN and alt.halbe_s == () and alt.hub is None
    assert alt.verzug_s == () and alt.ruecknahmen == 0
    xyz, _ = _kniebeugen([2.0] * 10, 50.0)
    zf = wl.zaehlen_fenster(xyz, 50.0, 100.0)
    assert zf.anzahl == 10 and zf.periode_s == pytest.approx(2.0, abs=0.15)
    assert zf.zeiten_s[0] > 100.0 and zf.art == KENNZEICHEN and zf.halbe_s == ()


def test_rechenlast_klein_und_unabhaengig_von_der_satzlaenge() -> None:
    kurz, _ = _kniebeugen([2.0] * 10, 200.0)
    lang, _ = _kniebeugen([2.0] * 150, 200.0)
    zeiten = []
    for xyz in (kurz, lang):
        live = wl.WdhLive(200.0)
        beginn = time.perf_counter()
        for i in range(0, xyz.shape[0], 36):
            live.rahmen(xyz[i : i + 36], i / 200.0)
        zeiten.append((time.perf_counter() - beginn) * 1000.0 / (xyz.shape[0] / 200.0))
    assert zeiten[0] < 20.0 and zeiten[1] < 20.0
    assert zeiten[1] < 3 * zeiten[0] + 2.0  # je Sekunde Daten gleich teuer, nicht wachsend
