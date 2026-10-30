"""Herzfrequenz: Reihe auf der Wanduhr, Rollfenster, Ruhe/Nacht/HFmax, Bereiche, Erholung,
Last, Bouts, Wertehierarchie — gegen Handrechnung und naive Schleifen."""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest

from hrv_core import herzfrequenz as hz
from hrv_core.recording import Beat


def _reihe_aus_hf(hf: list[float], *, geraet: bool = False) -> hz.HfReihe:
    """Eine Reihe mit einem Schlag je Sekunde (Mitte der Zelle) und gegebener HF."""
    t = np.arange(len(hf)) + 0.5
    if geraet:
        return hz.hf_reihe(t, [0] * len(hf), hf)
    return hz.hf_reihe(t, [60000.0 / h for h in hf])


def _rollmittel_naiv(x: np.ndarray, n: int, min_anteil: float) -> np.ndarray:
    out = np.full(x.size, np.nan)
    for i in range(n - 1, x.size):
        w = x[i - n + 1 : i + 1]
        g = w[~np.isnan(w)]
        if g.size >= max(1, math.ceil(min_anteil * n - 1e-9)):
            out[i] = g.mean()
    return out


# -- Reihe ------------------------------------------------------------------


def test_reihe_mittelt_schlaege_je_sekunde_und_fuellt_kurze_luecken() -> None:
    # Zwei Schläge in Sekunde 0 (75 und 80 bpm), keiner in 1 und 2, einer in 3
    r = hz.hf_reihe([0.2, 0.7, 3.4], [800, 750, 1000])
    assert r.t.tolist() == [0.0, 1.0, 2.0, 3.0]
    assert r.hf[0] == pytest.approx((75 + 80) / 2)
    # linear zwischen Zelle 0 und 3
    assert r.hf[1] == pytest.approx(r.hf[0] + (60 - r.hf[0]) / 3)
    assert r.hf[3] == 60.0
    assert r.quelle.tolist() == [1, 1, 1, 1]
    assert r.n_rr.tolist() == [2, 0, 0, 1]


def test_reihe_laesst_lange_luecken_offen_und_nimmt_dort_das_geraet() -> None:
    t = [0.5, 1.5, 2.5, 9.5, 10.5]
    rr = [1000, 1000, 1000, 1000, 1000]
    hf = [60, 60, 0, 0, 60]
    r = hz.hf_reihe(t, rr, hf)
    assert np.isnan(r.hf[3:9]).all()
    assert (r.quelle[3:9] == hz.QUELLE_KEINE).all()
    # Gerät füllt, wo RR fehlen: Pakete ohne RR nur mit Geräte-HF
    r2 = hz.hf_reihe([0.5, 1.5, 2.5, 3.5], [1000, 0, 0, 1000], [60, 70, 72, 60])
    assert r2.quelle.tolist() == [1, 1, 1, 1]  # RR-Lücke von 3 s wird aus RR interpoliert
    r3 = hz.hf_reihe([0.5, 3.5, 6.5, 9.5, 12.5], [1000, 0, 0, 0, 1000], [60, 70, 72, 74, 60])
    assert r3.quelle[6] == hz.QUELLE_GERAET and r3.hf[6] == 72.0
    assert r3.quelle[0] == hz.QUELLE_RR


def test_reihe_ignoriert_artefakte_und_zaehlt_sie() -> None:
    r = hz.hf_reihe([0.5, 1.5, 2.5], [1000, 300, 1000], artefakt=[False, True, False])
    assert r.hf.tolist() == [60.0, 60.0, 60.0]
    assert r.n_rr.tolist() == [1, 1, 1] and r.n_artefakt.tolist() == [0, 1, 0]
    assert r.artefaktanteil() == pytest.approx(1 / 3)
    # implausible RR (> 2000) zählt nicht als RR-Schlag
    r2 = hz.hf_reihe([0.5, 1.5], [1000, 2600])
    assert r2.n_rr.tolist() == [1, 0]


def test_reihe_aus_beats_reiner_pulsgeber_laeuft_auf_der_wanduhr() -> None:
    beats = [Beat(0.0, 0, 70 + i % 3, float(i) + 0.3) for i in range(20)]
    r = hz.reihe_aus_beats(beats)
    assert r.n == 20 and r.dauer_s == 20.0
    assert (r.quelle == hz.QUELLE_GERAET).all()
    assert r.abgedeckt_s() == 20.0


def test_reihe_leer_und_fester_bereich() -> None:
    assert hz.hf_reihe([], []).n == 0
    r = hz.hf_reihe([], [], anfang=0.0, ende=9.0)
    assert r.n == 10 and np.isnan(r.hf).all()
    with pytest.raises(ValueError):
        hz.hf_reihe([0.5], [800, 800])


def test_auf_raster_mittelt_und_fuellt() -> None:
    r = _reihe_aus_hf([60.0] * 6)
    w = hz.auf_raster([0.1, 0.9, 5.5], [2.0, 4.0, 9.0], r)
    assert w[0] == 3.0 and w[5] == 9.0
    assert w[1] == pytest.approx(3.0 + 6.0 / 5)


# -- Rollfenster ------------------------------------------------------------


@pytest.mark.parametrize("min_anteil", [1.0, 0.8, 0.5])
def test_rollmittel_wie_naive_schleife(min_anteil: float) -> None:
    zufall = np.random.default_rng(7)
    x = zufall.normal(70, 5, 500)
    x[zufall.random(500) < 0.2] = np.nan
    for n in (3, 10, 30):
        erwartet = _rollmittel_naiv(x, n, min_anteil)
        ist = hz.rollmittel(x, float(n), min_anteil=min_anteil)
        assert np.allclose(np.nan_to_num(ist, nan=-1), np.nan_to_num(erwartet, nan=-1), atol=1e-9)


def test_rollmittel_fehler_und_kurze_reihe() -> None:
    with pytest.raises(ValueError):
        hz.rollmittel(np.ones(5), 0.1)
    assert np.isnan(hz.rollmittel(np.ones(3), 5.0)).all()


# -- Ruhe, Nacht, Tag, HFmax ---------------------------------------------------


def test_ruhe_hf_morgen_findet_das_tiefste_30s_fenster() -> None:
    hf = [62.0] * 360
    hf[200:230] = [55.0] * 30  # 30 s Senke
    r = _reihe_aus_hf(hf)
    w = hz.ruhe_hf_morgen(r)
    assert w.gueltig and w.wert == pytest.approx(55.0)
    assert (w.t_von, w.t_bis) == (200.0, 230.0)
    assert w.quelle == hz.QUELLE_RR


def test_ruhe_hf_morgen_ungueltig_bei_zu_kurz_oder_artefakten() -> None:
    kurz = hz.ruhe_hf_morgen(_reihe_aus_hf([60.0] * 120))
    assert not kurz.gueltig and kurz.wert == 60.0 and "zu wenig" in kurz.gruende[0]
    t = np.arange(400) + 0.5
    art = np.zeros(400, dtype=bool)
    art[::10] = True  # 10 % markiert
    r = hz.hf_reihe(t, [1000] * 400, artefakt=art)
    w = hz.ruhe_hf_morgen(r)
    assert not w.gueltig and any("Artefakt" in g for g in w.gruende)
    assert w.artefaktanteil == pytest.approx(0.1)


def test_nacht_hf_und_tagesminimum() -> None:
    n = 6 * 3600
    hf = np.full(n, 58.0)
    hf[3 * 3600 : 5 * 3600] = 50.0
    r = hz.hf_reihe(np.arange(n) + 0.5, 60000.0 / hf)
    w = hz.nacht_hf(r, 0.0, float(n))
    assert w.gueltig and w.wert == pytest.approx(50.0)
    assert w.t_von == pytest.approx(3 * 3600.0) and w.t_bis == pytest.approx(5 * 3600.0)
    zu_kurz = hz.nacht_hf(r, 0.0, 3 * 3600.0)
    assert not zu_kurz.gueltig
    tag = hz.tagesminimum(r)
    assert not tag.gueltig  # 6 h < 10 h
    assert tag.wert == pytest.approx(50.0)


def test_hfmax_kandidat_verlangt_plateau_und_wenig_artefakte() -> None:
    # 10 min Rampe 100 → 180, dann 30 s Spitze 200 aus dem Nichts
    hf = list(np.linspace(100, 180, 600))
    hf += [120.0] * 120 + [200.0] * 30 + [120.0] * 60
    r = _reihe_aus_hf(hf)
    k = hz.hfmax_kandidat(r)
    assert k.gueltig
    assert 176 < k.wert < 180.1  # das letzte Rampenfenster, nicht die Spitze
    assert k.t_bis <= 600.0
    # ohne die Rampe zählt die Spitze nicht: gültig ist das höchste Fenster mit Plateau (120)
    spitze = hz.hfmax_kandidat(_reihe_aus_hf([120.0] * 120 + [200.0] * 30 + [120.0] * 60))
    assert spitze.gueltig and spitze.wert == pytest.approx(120.0)
    # nur die Spitze allein, ohne 30 s davor: ungültig, mit Begründung
    allein = hz.hfmax_kandidat(_reihe_aus_hf([200.0] * 30 + [120.0] * 20))
    assert not allein.gueltig and allein.wert == pytest.approx(200.0)
    assert any("Plateau" in g for g in allein.gruende)


def test_hfmax_kandidat_bei_reinem_pulsgeber_und_leer() -> None:
    hf = list(np.linspace(100, 170, 300)) + [170.0] * 60
    r = _reihe_aus_hf(hf, geraet=True)
    k = hz.hfmax_kandidat(r)
    assert k.gueltig and k.quelle == hz.QUELLE_GERAET and k.artefaktanteil is None
    leer = hz.hfmax_kandidat(hz.hf_reihe([], [], anfang=0, ende=10))
    assert leer.wert is None and not leer.gueltig


# -- Formeln, Reserve, Schwellen -------------------------------------------------


def test_formeln_und_reserve() -> None:
    assert hz.formel_hfmax(40, "tanaka").wert == pytest.approx(180.0)
    assert hz.formel_hfmax(40, "gulati").wert == pytest.approx(170.8)
    with pytest.raises(ValueError):
        hz.formel_hfmax(40, "fox")
    assert hz.prozent_hrr(np.array([60.0, 120.0, 180.0]), 60, 180).tolist() == [0.0, 50.0, 100.0]
    assert hz.hf_aus_prozent(42, 55, 185) == pytest.approx(109.6)
    with pytest.raises(ValueError):
        hz.prozent_hrr(100, 180, 60)


def test_milani_entspricht_etwa_42_und_77_prozent() -> None:
    s = hz.schwellen_milani(185, 55)
    assert s.vt1 == pytest.approx(4.866 + 0.405 * 185 + 0.542 * 55)
    assert s.vt2 == pytest.approx(-2.606 + 0.773 * 185 + 0.254 * 55)
    assert 40 < s.vt1_prozent < 45 and 74 < s.vt2_prozent < 79
    assert s.unsicherheit_vt1 == pytest.approx(0.071 * s.vt1)


# -- Bereiche ---------------------------------------------------------------------


def test_bereiche_aller_modelle() -> None:
    drei = hz.bereiche("drei", 60, 180)
    assert [b.name for b in drei] == ["Bereich 1", "Bereich 2", "Bereich 3"]
    assert drei[0].von_bpm == 60 and drei[-1].bis_bpm == 180
    assert drei[0].bis_bpm == pytest.approx(60 + 0.42 * 120)
    acsm = hz.bereiche("acsm", 60, 180)
    assert len(acsm) == 5 and acsm[2].name == "moderat"
    cluster = hz.bereiche("cluster", 60, 180)
    assert len(cluster) == 10 and cluster[3].von_prozent == 30.0
    eigen = hz.bereiche("eigen", 60, 180, eigene_bpm=[150, 120], namen=["ruhig", "zügig", "hart"])
    assert [b.name for b in eigen] == ["ruhig", "zügig", "hart"]
    assert eigen[0].bis_bpm == 120 and eigen[0].bis_prozent == pytest.approx(50.0)
    with pytest.raises(ValueError):
        hz.bereiche("drei", 180, 60)
    with pytest.raises(ValueError):
        hz.bereiche("drei", 60, 180, namen=["a"])
    with pytest.raises(ValueError):
        hz.grenzen_prozent("fuenf")


def test_unsicherheitsband_waechst_mit_formelfehler() -> None:
    ohne = hz.bereiche("drei", 55, 185, unsicherheit_grenze_prozent=6)
    mit = hz.bereiche("drei", 55, 185, unsicherheit_grenze_prozent=6, unsicherheit_hfmax_bpm=10.8)
    assert mit[1].unsicherheit_bpm > ohne[1].unsicherheit_bpm > 0
    assert mit[1].unsicherheit_bpm == pytest.approx(math.hypot(0.06 * 130, 0.77 * 10.8))
    assert mit[2].unsicherheit_bpm == 0.0  # offenes Ende
    je = hz.bereiche("drei", 55, 185, unsicherheit_grenze_prozent=[5, 6])
    assert je[0].unsicherheit_bpm == pytest.approx(0.05 * 130)
    with pytest.raises(ValueError):
        hz.bereiche("drei", 55, 185, unsicherheit_grenze_prozent=[5])


def test_bereich_index_und_zeit_je_bereich_mit_luecken() -> None:
    hf = [100.0] * 10 + [np.nan] * 5 + [130.0] * 20
    t = np.arange(35) + 0.5
    rr = [60000 / h if not np.isnan(h) else 0 for h in hf]
    r = hz.hf_reihe(t, rr)
    z = hz.zeit_je_bereich(r, [110.0, 120.0])
    assert z == [10.0, 0.0, 20.0]
    assert hz.zeit_je_bereich(r, [110.0, 120.0], von=15.0) == [0.0, 0.0, 20.0]
    assert hz.bereich_index(np.array([np.nan]), [100.0]).tolist() == [-1]


# -- Zusammenfassung, Erholung, Last ----------------------------------------------


def test_trimp_banister_und_zusammenfassung() -> None:
    r = _reihe_aus_hf([120.0] * 3600)  # 60 min bei 50 % HRR
    erwartet = 60 * 0.5 * 0.64 * math.exp(1.92 * 0.5)
    assert hz.trimp_banister(r, 60, 180) == pytest.approx(erwartet, rel=1e-9)
    frauen = 60 * 0.5 * 0.86 * math.exp(1.67 * 0.5)
    assert hz.trimp_banister(r, 60, 180, geschlecht="w") == pytest.approx(frauen, rel=1e-9)
    assert hz.trimp_banister(hz.hf_reihe([], [], anfang=0, ende=5), 60, 180) is None
    z = hz.zusammenfassung(r, ruhe=60, hfmax=180, grenzen_bpm=[110.0, 152.0])
    assert z["dauer_s"] == 3600.0 and z["gueltig_s"] == 3600.0
    assert z["mittel_bpm"] == 120.0 and z["gipfel_bpm"] == 120.0 and z["minimum_bpm"] == 120.0
    assert z["mittel_prozent"] == pytest.approx(50.0)
    assert z["sekunden_je_bereich"] == [0.0, 3600.0, 0.0]
    assert z["trimp"] == pytest.approx(erwartet)
    assert z["quelle_rr_anteil"] == 1.0
    leer = hz.zusammenfassung(hz.hf_reihe([], [], anfang=0, ende=5))
    assert leer["mittel_bpm"] is None and leer["dauer_s"] == 6.0


def test_gipfel_ist_ein_fuenf_sekunden_mittel() -> None:
    hf = [120.0] * 60
    hf[30] = 190.0  # Einzelsekunde
    z = hz.zusammenfassung(_reihe_aus_hf(hf))
    assert z["gipfel_bpm"] == pytest.approx((4 * 120 + 190) / 5)


def test_trimp_zonen_gewichte() -> None:
    assert hz.trimp_zonen([60, 60, 60], [1, 2, 3]) == pytest.approx(6.0)
    with pytest.raises(ValueError):
        hz.trimp_zonen([60, 60], [1])


def test_erholung_none_wo_daten_fehlen() -> None:
    hf = [150.0] * 10 + [140.0 - i for i in range(50)]  # nur 50 s Erholung
    r = _reihe_aus_hf(hf)
    e = hz.hrr_erholung(r, 10.0, kontext="satz", haltung="steht")
    assert e.hf_ende == pytest.approx(150.0)
    # Zellen 38…42 (Mitte um t0 + 30 = 40): HF 112 … 108
    assert e.hrr[30] == pytest.approx(150 - np.mean([140 - (i - 10) for i in range(38, 43)]))
    assert e.hrr[60] is None and e.hrr[120] is None
    assert e.kontext == "satz" and e.als_dict()["hrr"]["30"] == e.hrr[30]
    assert hz.hrr_erholung(r, 3.0).hf_ende is not None  # 3 von 5 s reichen …
    assert hz.hrr_erholung(r, 2.0).hf_ende is None  # … 2 von 5 nicht (auch vor dem Anfang)


def test_drift_und_entkopplung() -> None:
    hf = [130.0] * 300 + [140.0] * 300
    r = _reihe_aus_hf(hf)
    d = hz.drift(r, 0, 600)
    assert d.differenz_bpm == pytest.approx(10.0) and d.entkopplung_prozent is None
    leistung = np.full(600, 3.0)
    d2 = hz.drift(r, 0, 600, leistung=leistung)
    assert d2.entkopplung_prozent == pytest.approx((140 / 130 - 1) * 100)
    with pytest.raises(ValueError):
        hz.drift(r, 0, 600, leistung=np.ones(5))


# -- Bouts, Ruhe, Schlaf -------------------------------------------------------------


def test_bouts_tolerieren_kurze_einbrueche_und_enden_nach_zwei_minuten() -> None:
    hf = [70.0] * 60 + [140.0] * 200 + [90.0] * 60 + [140.0] * 200 + [70.0] * 200
    r = _reihe_aus_hf(hf)
    b = hz.bouts(r, 110)
    assert [(p.von_s, p.bis_s) for p in b] == [(60.0, 520.0)]
    assert b[0].art == "belastung" and b[0].dauer_s == 460.0
    # zu kurz (2 min) zählt nicht
    assert hz.bouts(_reihe_aus_hf([70.0] * 60 + [140.0] * 120 + [70.0] * 60), 110) == []


def test_ruhephasen_und_schlafkandidat() -> None:
    n = 10 * 3600
    hf = np.full(n, 75.0)
    hf[2 * 3600 : 7 * 3600] = 52.0  # 5 h Ruhe
    hf[8 * 3600 : 8 * 3600 + 900] = 55.0  # 15 min Ruhe
    r = hz.hf_reihe(np.arange(n) + 0.5, 60000.0 / hf)
    ph = hz.ruhephasen(r, 60.0)
    assert len(ph) == 2 and ph[0].dauer_s == 5 * 3600.0
    s = hz.schlaf_kandidat(ph, 0.0, 9 * 3600.0)
    assert s is not None and s.art == "schlaf" and s.von_s == 2 * 3600.0
    assert hz.schlaf_kandidat(ph, 7.5 * 3600.0, 9 * 3600.0) is None
    assert hz.schwelle_belastung(None, None) is None


def test_aktivitaetsprofil_und_baseline() -> None:
    hf = [80.0] * 1800 + [130.0] * 1800
    r = _reihe_aus_hf(hf)
    a = hz.aktivitaetsprofil(r, 60, 180)
    assert len(a.sekunden_je_cluster) == 10 and sum(a.sekunden_je_cluster) == 3600.0
    assert a.sekunden_je_cluster[1] == 1800.0 and a.sekunden_je_cluster[5] == 1800.0
    assert not a.gueltig
    b = hz.baseline([50, 52])
    assert b.median == 51.0 and b.unten is None and b.n == 2
    assert hz.baseline([]).median is None
    assert hz.baseline(list(range(20)), n=7).n == 7


# -- Wertehierarchie ----------------------------------------------------------------


def test_hierarchie_fest_schlaegt_alles_und_messung_schlaegt_eintrag() -> None:
    e = [
        hz.ProfilEintrag("ruhe_hf", 60, "eintrag", date(2026, 10, 28)),
        hz.ProfilEintrag("ruhe_hf", 54, "messung_morgen_5", date(2026, 10, 27)),
        hz.ProfilEintrag("ruhe_hf", 56, "messung_morgen_5", date(2026, 10, 20)),
    ]
    g = hz.geltender_wert(e, "ruhe_hf", date(2026, 10, 29))
    assert g is not None and g.wert == 54  # jüngste Messung der genauesten Quelle
    fest = [*e, hz.ProfilEintrag("ruhe_hf", 58, "tagesfeld", date(2026, 9, 1), fest=True)]
    assert hz.geltender_wert(fest, "ruhe_hf", date(2026, 10, 29)).wert == 58
    assert hz.geltender_wert(e, "hf_max", date(2026, 10, 29)) is None


def test_hierarchie_abgelaufen_nimmt_den_juengsten() -> None:
    e = [
        hz.ProfilEintrag("hf_max", 190, "ergometrie", date(2024, 1, 1)),
        hz.ProfilEintrag("hf_max", 186, "feldmaximum", date(2025, 1, 1)),
    ]
    g = hz.geltender_wert(e, "hf_max", date(2026, 10, 29))
    assert g is not None and g.quelle == "feldmaximum"  # beide abgelaufen → jüngster
    formel = [*e, hz.ProfilEintrag("hf_max", 185.4, "formel_nes", date(2026, 10, 29))]
    assert hz.geltender_wert(formel, "hf_max", date(2026, 10, 29)).quelle == "formel_nes"
    assert hz.gueltig_am(formel[-1], date(2030, 1, 1))
    assert not hz.gueltig_am(e[0], date(2026, 1, 1))
    assert hz.ProfilEintrag("hf_max", 1, "formel_nes", date(2026, 1, 1)).unsicherheit == 10.8


def test_hierarchie_am_stichtag_zaehlt_nichts_spaeteres() -> None:
    """Entscheidung 19: Ruhe-HF vom 5.10. und 15.10. — eine Messung vom 1.10. rechnet mit dem
    Wert vom 5.10., eine vom 10.10. mit dem vom 5.10., eine vom 20.10. mit dem vom 15.10."""
    e = [
        hz.ProfilEintrag("ruhe_hf", 56, "messung_morgen_5", date(2026, 10, 5)),
        hz.ProfilEintrag("ruhe_hf", 52, "messung_morgen_5", date(2026, 10, 15)),
    ]
    assert hz.geltender_wert(e, "ruhe_hf", date(2026, 10, 1)).wert == 56
    assert hz.geltender_wert(e, "ruhe_hf", date(2026, 10, 10)).wert == 56
    assert hz.geltender_wert(e, "ruhe_hf", date(2026, 10, 20)).wert == 52
    # beide abgelaufen (14 Tage): der jüngste bis zum Stichtag, nicht ein späterer
    spaeter = [*e, hz.ProfilEintrag("ruhe_hf", 49, "messung_morgen_5", date(2026, 12, 1))]
    assert hz.geltender_wert(spaeter, "ruhe_hf", date(2026, 11, 10)).wert == 52
    assert hz.ProfilEintrag("hf_max", 1, "ergometrie", date(2026, 1, 1)).misst


def test_hierarchie_deckt_alle_quellen_mit_gueltigkeit_und_unsicherheit() -> None:
    for folge in hz.RANGFOLGE.values():
        for q in folge:
            assert q in hz.GUELTIG_TAGE and q in hz.UNSICHERHEIT_BPM
    assert hz.rang("hf_vt1", "talk_test") < hz.rang("hf_vt1", "schaetzung_milani")
    assert hz.median_letzter([]) is None
    assert hz.nenner_fortschreiben(None, 55.0) == 55.0
