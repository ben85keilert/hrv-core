"""Atem-Beiwerk `atem.py` (`atem-v1`): sammeln, Journal, schreiben, lesen (trainingsapp A3)."""

from __future__ import annotations

import json

import pytest

import hrv_core
from hrv_core import atem, deid
from hrv_core.recording import ist_messdatei


def _sammler() -> atem.AtemSammler:
    s = atem.AtemSammler("sensor", "polar_h10", 50, prototyp="hrv_core.prototyp.atemzuege")
    s.lauf_beginn(10.0)
    s.phase(12.3456, "ein")
    s.phase(14.5, "aus")
    s.phase(16.7, "ein")
    s.fenster(40.0, 12.345, True)
    s.fenster(45.0, None, False, "bewegung")
    s.lauf_ende(50.0)
    return s


def test_rundreise_dokument_und_datei(tmp_path) -> None:
    s = _sammler()
    assert not s.leer and not s.offen
    messdatei = tmp_path / "sensor_2026-11-05_061500.json"
    pfad = s.schreiben(messdatei)
    assert pfad.name == "sensor_2026-11-05_061500_atem.json" and not ist_messdatei(pfad)
    assert atem.atem_pfad(messdatei) == pfad
    doc = json.loads(pfad.read_text(encoding="utf-8"))
    assert list(doc) == [
        "schema",
        "art",
        "prototyp",
        "hrv_core",
        "quelle",
        "geraet",
        "rate_hz",
        "erfasst",
        "phasen",
        "fenster",
    ]
    assert doc["schema"] == "atem-v1" and doc["art"] == "prototyp"
    assert doc["prototyp"] == "hrv_core.prototyp.atemzuege"
    assert doc["hrv_core"] == hrv_core.__version__
    assert doc["quelle"] == "sensor" and doc["geraet"] == "polar_h10" and doc["rate_hz"] == 50
    assert doc["erfasst"] == [[10.0, 50.0]]
    assert doc["phasen"] == [[12.346, "ein"], [14.5, "aus"], [16.7, "ein"]]  # 3 Nachkommastellen
    assert doc["fenster"] == [[40.0, 12.35, True, ""], [45.0, None, False, "bewegung"]]
    assert "rate_hz" in doc and not any(k in doc for k in ("proben", "xyz", "lat", "lon"))

    a = atem.atem_laden(pfad)
    assert a.quelle == "sensor" and a.geraet == "polar_h10" and a.rate_hz == 50
    assert a.art == "prototyp" and a.prototyp == "hrv_core.prototyp.atemzuege"
    assert a.hrv_core == hrv_core.__version__
    assert a.erfasst == [(10.0, 50.0)] and a.dauer_erfasst_s == 40.0
    assert a.phasen == [(12.346, "ein"), (14.5, "aus"), (16.7, "ein")]
    assert a.fenster == [(40.0, 12.35, True, ""), (45.0, None, False, "bewegung")]
    assert a.ist_erfasst(30.0) and not a.ist_erfasst(5.0)
    assert a.phasen_zwischen(14.0, 16.7) == [(14.5, "aus")]
    assert a.raten() == [(40.0, 12.35)]
    # Zweite Rundreise ist byteidentisch
    s2 = atem.AtemSammler(a.quelle, a.geraet, a.rate_hz, prototyp=a.prototyp, hrv_core=a.hrv_core)
    for von, bis in a.erfasst:
        s2.lauf_beginn(von)
        s2.lauf_ende(bis)
    for t, art in a.phasen:
        s2.phase(t, art)
    for t, rate, gueltig, grund in a.fenster:
        s2.fenster(t, rate, gueltig, grund)
    assert s2.dokument() == doc
    # Atomares Schreiben hinterlässt keine .tmp-Datei
    assert sorted(p.name for p in tmp_path.iterdir()) == [pfad.name]


def test_offener_lauf_wird_beim_schreiben_geschlossen_und_phasen_sortiert() -> None:
    s = atem.AtemSammler()
    assert s.leer and s.dokument()["erfasst"] == []
    s.lauf_beginn(10.0)
    assert s.offen and not s.leer
    assert s.dokument()["erfasst"] == [[10.0, 10.0]]  # nichts bekannt: von_s
    s.phase(20.0, "ein")
    assert s.dokument()["erfasst"] == [[10.0, 20.0]]
    s.fenster(35.0, 10.0, True)
    assert s.dokument()["erfasst"] == [[10.0, 35.0]]
    s.phase(18.0, "aus")  # kommt nach, liegt aber davor
    assert s.dokument()["phasen"] == [[18.0, "aus"], [20.0, "ein"]]
    assert s.laeufe == [[10.0, None]]  # der Sammler selbst bleibt offen
    # Zweiter Beginn schließt den offenen Lauf an seiner Stelle, kein Ende ohne Lauf
    s.lauf_beginn(40.0)
    assert s.laeufe == [[10.0, 40.0], [40.0, None]]
    s.lauf_ende(30.0)  # vor dem Beginn: auf den Beginn gezogen
    assert s.laeufe == [[10.0, 40.0], [40.0, 40.0]]
    s.lauf_ende(99.0)  # kein offener Lauf: nichts
    assert s.laeufe == [[10.0, 40.0], [40.0, 40.0]]
    with pytest.raises(ValueError):
        s.phase(1.0, "halten")


def test_journal_nur_neues_halbe_zeile_und_neuer_pfad(tmp_path, monkeypatch) -> None:
    """Wie das EKG-Journal (Diagnosemodus V6): fsync, nur Neues, eine halbe Zeile wird
    abgeschlossen statt fortgesetzt, ein anderer oder verschwundener Pfad bekommt alles samt
    Kopf."""
    aufrufe: list[int] = []
    echt = atem.os.fsync
    monkeypatch.setattr(atem.os, "fsync", lambda fd: (aufrufe.append(fd), echt(fd)))
    s = atem.AtemSammler("sensor", "polar_h10", 50, prototyp="p")
    s.lauf_beginn(1.0)
    s.phase(2.0, "ein")
    backup = tmp_path / ".backup_2026-11-05_061500.json"
    a = atem.atem_journal_pfad(backup)
    assert a.name == ".backup_2026-11-05_061500_atem.jsonl"
    s.journal_anhaengen(a)
    assert len(aufrufe) == 1
    zeilen = a.read_text(encoding="utf-8").splitlines()
    assert [json.loads(z)[0] for z in zeilen] == ["k", "e", "p"]
    assert json.loads(zeilen[0])[1] == {
        "schema": "atem-v1",
        "art": "prototyp",
        "prototyp": "p",
        "hrv_core": hrv_core.__version__,
        "quelle": "sensor",
        "geraet": "polar_h10",
        "rate_hz": 50,
    }
    s.journal_anhaengen(a)  # nichts Neues: hängt nichts an
    assert len(aufrufe) == 1 and a.read_text(encoding="utf-8").splitlines() == zeilen
    # Nur Neues: Phase, Fenster, Lauf zu, neuer Lauf auf
    s.phase(4.0, "aus")
    s.fenster(30.0, 15.0, True)
    s.lauf_ende(31.0)
    s.lauf_beginn(40.0)
    s.journal_anhaengen(a)
    zeilen = a.read_text(encoding="utf-8").splitlines()
    assert [json.loads(z)[0] for z in zeilen] == ["k", "e", "p", "x", "e", "p", "f"]
    assert json.loads(zeilen[3]) == ["x", 31.0] and json.loads(zeilen[4]) == ["e", 40.0]
    w = atem.AtemSammler.aus_journal(a)
    assert w.laeufe == [[1.0, 31.0], [40.0, None]] and w.offen  # im Journal bleibt er offen
    assert w.phasen == s.phasen and w.fenster_liste == s.fenster_liste
    assert w.geraet == "polar_h10" and w.rate_hz == 50 and w.prototyp == "p"
    assert w.dokument() == s.dokument()

    # Anderer Pfad: alles noch einmal, mit Kopf
    b = tmp_path / "b_atem.jsonl"
    s.fenster(45.0, None, False, "bewegung")
    s.journal_anhaengen(b)
    assert atem.AtemSammler.aus_journal(b).dokument() == s.dokument()
    assert sum(1 for z in b.read_text(encoding="utf-8").splitlines() if z.startswith('["k"')) == 1
    # Verschwunden: wieder alles
    b.unlink()
    s.phase(42.0, "ein")
    s.journal_anhaengen(b)
    assert atem.AtemSammler.aus_journal(b).dokument() == s.dokument()
    # Halbe Zeile: der Anhang beginnt mit einem Zeilenumbruch, die halbe Zeile fällt weg
    with open(b, "a", encoding="utf-8") as f:
        f.write('["p", 43.0, "au')
    s.phase(44.0, "aus")
    s.lauf_ende(50.0)
    s.journal_anhaengen(b)
    w = atem.AtemSammler.aus_journal(b)
    assert w.dokument() == s.dokument() and w.laeufe == [[1.0, 31.0], [40.0, 50.0]]
    # Nach dem Wiederaufbau geht es im selben Journal weiter, ohne zweiten Kopf
    w.lauf_beginn(60.0)
    w.journal_anhaengen(b)
    zeilen = b.read_text(encoding="utf-8").splitlines()
    assert sum(1 for z in zeilen if z.startswith('["k"')) == 1
    assert json.loads(zeilen[-1]) == ["e", 60.0]
    assert atem.AtemSammler.aus_journal(b).laeufe == [[1.0, 31.0], [40.0, 50.0], [60.0, None]]


def test_aus_journal_uebergeht_unlesbares(tmp_path) -> None:
    j = tmp_path / "x_atem.jsonl"
    j.write_text(
        "\n".join(
            [
                '["k", {"quelle": "sensor", "geraet": "verity_sense", "rate_hz": 52.0}]',
                "kaputt",
                '["p", 1.0, "ein"]',
                '["p", 2.0, "halten"]',  # unbekannte Phase
                '["p", "x", "aus"]',  # keine Zahl
                '["x", 5.0]',  # Lauf zu ohne offenen Lauf
                '["e", 3.0]',
                '["f", 30.0, 12.0, true]',  # ohne Grund
                '["f", 35.0, null, false, "bewegung"]',
                '{"art": "n"}',  # kein Listeneintrag
                "[]",
                '["z", 1]',  # unbekannte Art
                '["p", 4.0, "aus"',  # halbe Zeile am Ende
            ]
        ),
        encoding="utf-8",
    )
    w = atem.AtemSammler.aus_journal(j)
    assert w.geraet == "verity_sense" and w.rate_hz == 52 and w.quelle == "sensor"
    assert w.phasen == [(1.0, "ein")]
    assert w.laeufe == [[3.0, None]]
    assert w.fenster_liste == [(30.0, 12.0, True, ""), (35.0, None, False, "bewegung")]
    assert w.dokument()["erfasst"] == [[3.0, 35.0]]


def test_laden_tolerant_und_fremdes_schema(tmp_path) -> None:
    pfad = tmp_path / "sensor_x_atem.json"
    pfad.write_text(json.dumps({"schema": "atem-v1"}), encoding="utf-8")
    a = atem.atem_laden(pfad)
    assert a.erfasst == [] and a.phasen == [] and a.fenster == [] and a.rate_hz is None
    assert a.quelle == "sensor" and a.geraet == "" and a.dauer_erfasst_s == 0.0
    pfad.write_text(
        json.dumps(
            {
                "schema": "atem-v1",
                "rate_hz": "50",
                "erfasst": [[1.0, None], [2.0], "x", [5.0, 4.0]],
                "phasen": [[3.0, "aus"], [1.5, "ein"], [2.0, "halten"], ["x", "ein"]],
                "fenster": "nein",
            }
        ),
        encoding="utf-8",
    )
    a = atem.atem_laden(pfad)
    assert a.rate_hz == 50
    assert a.erfasst == [(1.0, 1.0), (5.0, 5.0)]  # offen → geschlossen, rückwärts → leer
    assert a.phasen == [(1.5, "ein"), (3.0, "aus")]  # sortiert, Unbekanntes weg
    assert a.fenster == []
    pfad.write_text(json.dumps({"sample_rate_hz": 130, "uv": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        atem.atem_laden(pfad)
    pfad.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        atem.atem_laden(pfad)


def test_beiwerk_haengt_am_stamm_und_bleibt_bei_deid_vollstaendig(tmp_path) -> None:
    doc = _sammler().dokument()
    messdatei = tmp_path / "sensor_2026-11-05_061500.json"
    pfad = atem.AtemSammler.schreiben(_sammler(), messdatei)
    assert deid.stamm(pfad) == "sensor_2026-11-05_061500"
    assert deid.format_erkennen(doc, pfad.name) == "atem-v1"
    assert deid.format_erkennen({}, pfad.name) == "atem-v1"
    neu, meldungen = deid.deidentifizieren_dict(doc, pfad.name)
    assert neu == doc and meldungen == []


# ---------------------------------------------------------------------------
# Soll-Phasen des Taktgebers: Feld `takt` (P141, 5.11.2026)
# ---------------------------------------------------------------------------


def _sammler_mit_takt() -> atem.AtemSammler:
    s = _sammler()
    s.takt_beginn(10.0, "Box 4-4", 7.5)
    s.takt_phase(10.0, "ein")
    s.takt_phase(14.0, "aus")
    s.takt_phase(18.0, "ein")
    s.takt_ende(22.0)
    # Zweiter Lauf nach Tempoänderung: andere Rate, dieselbe Phasenliste
    s.takt_beginn(30.0, "Box 4-4", 10.0)
    s.takt_phase(30.0, "ein")
    s.takt_phase(33.123456, "aus")
    s.takt_ende(36.0)
    return s


def test_takt_rundreise_und_ohne_takt_unveraendert(tmp_path) -> None:
    """Mit Soll-Phasen steht `takt` hinten als letztes Feld; ohne bleibt die Datei wie vor
    0.13.0 (Rundreise ohne `takt` prüft `test_rundreise_dokument_und_datei`)."""
    assert "takt" not in _sammler().dokument() and _sammler().takt() is None
    s = _sammler_mit_takt()
    assert not s.takt_offen
    doc = s.dokument()
    assert list(doc)[-2:] == ["fenster", "takt"]
    assert doc["takt"] == {
        "name": "Box 4-4",
        "rate_pro_min": 10.0,  # der letzte Lauf
        "phasen": [
            [10.0, "ein"],
            [14.0, "aus"],
            [18.0, "ein"],
            [30.0, "ein"],
            [33.123, "aus"],  # 3 Nachkommastellen
        ],
        "laeufe": [[10.0, 22.0, "Box 4-4", 7.5], [30.0, 36.0, "Box 4-4", 10.0]],
    }
    # Sensor-Teil unverändert
    assert doc["phasen"] == [[12.346, "ein"], [14.5, "aus"], [16.7, "ein"]]
    assert doc["erfasst"] == [[10.0, 50.0]]

    pfad = s.schreiben(tmp_path / "sensor_2026-11-05_061500.json")
    a = atem.atem_laden(pfad)
    assert a.takt is not None
    assert a.takt.name == "Box 4-4" and a.takt.rate_pro_min == 10.0
    assert a.takt.phasen == [(t, art) for t, art in doc["takt"]["phasen"]]
    assert a.takt.laeufe == [(10.0, 22.0, "Box 4-4", 7.5), (30.0, 36.0, "Box 4-4", 10.0)]
    assert a.takt.ist_getaktet(20.0) and not a.takt.ist_getaktet(25.0)
    assert a.takt_phasen_zwischen(14.0, 30.0) == [(14.0, "aus"), (18.0, "ein")]
    assert a.phasen_zwischen(14.0, 30.0) == [(14.5, "aus"), (16.7, "ein")]  # Ist bleibt getrennt
    # Zweite Rundreise ist byteidentisch
    s2 = atem.AtemSammler(a.quelle, a.geraet, a.rate_hz, prototyp=a.prototyp, hrv_core=a.hrv_core)
    for von, bis in a.erfasst:
        s2.lauf_beginn(von)
        s2.lauf_ende(bis)
    for t, art in a.phasen:
        s2.phase(t, art)
    for t, rate, gueltig, grund in a.fenster:
        s2.fenster(t, rate, gueltig, grund)
    for von, bis, name, rate in a.takt.laeufe:
        s2.takt_beginn(von, name, rate)
        s2.takt_ende(bis)
    for t, art in a.takt.phasen:
        s2.takt_phase(t, art)
    assert s2.dokument() == doc


def test_takt_allein_lohnt_ein_beiwerk_und_offener_takt_wird_geschlossen() -> None:
    s = atem.AtemSammler("sensor", "polar_h10", None)
    s.takt_beginn(5.0, "Metronom", 6.0)
    assert s.leer  # ein Takt ohne Soll-Phase: nichts zu schreiben
    assert s.dokument().get("takt") is None
    s.takt_phase(5.0, "ein")
    assert not s.leer and s.takt_offen
    assert s.dokument()["takt"]["laeufe"] == [[5.0, 5.0, "Metronom", 6.0]]
    s.takt_phase(15.0, "aus")
    s.takt_phase(12.0, "ein")  # kommt nach, liegt davor: sortiert, der Lauf endet bei 15
    doc = s.dokument()
    assert doc["takt"]["phasen"] == [[5.0, "ein"], [12.0, "ein"], [15.0, "aus"]]
    assert doc["takt"]["laeufe"] == [[5.0, 15.0, "Metronom", 6.0]]
    assert doc["erfasst"] == [] and doc["phasen"] == [] and doc["fenster"] == []
    assert s.takt_laeufe == [[5.0, None, "Metronom", 6.0]]  # der Sammler bleibt offen
    # Zweiter Beginn schließt den offenen Lauf an seiner Stelle; Ende ohne Lauf tut nichts
    s.takt_beginn(20.0, "Metronom", 8.0)
    assert s.takt_laeufe == [[5.0, 20.0, "Metronom", 6.0], [20.0, None, "Metronom", 8.0]]
    s.takt_ende(19.0)  # vor dem Beginn: auf den Beginn gezogen
    s.takt_ende(99.0)
    assert s.takt_laeufe[-1] == [20.0, 20.0, "Metronom", 8.0]
    assert s.dokument()["takt"]["rate_pro_min"] == 8.0
    with pytest.raises(ValueError):
        s.takt_phase(1.0, "halten")
    # Soll-Phasen ohne Lauf: Name leer, Rate None
    t = atem.AtemSammler()
    t.takt_phase(1.0, "ein")
    assert t.takt() == {"name": "", "rate_pro_min": None, "phasen": [[1.0, "ein"]], "laeufe": []}


def test_takt_im_journal_nur_neues_und_wiederaufbau(tmp_path) -> None:
    s = atem.AtemSammler("sensor", "polar_h10", 50, prototyp="p")
    s.lauf_beginn(1.0)
    s.takt_beginn(1.0, "Box 4-4", 7.5)
    s.takt_phase(1.0, "ein")
    j = tmp_path / ".backup_x_atem.jsonl"
    s.journal_anhaengen(j)
    zeilen = [json.loads(z) for z in j.read_text(encoding="utf-8").splitlines()]
    assert zeilen[1:] == [["e", 1.0], ["t", 1.0, "Box 4-4", 7.5], ["q", 1.0, "ein"]]
    s.journal_anhaengen(j)  # nichts Neues
    assert len(j.read_text(encoding="utf-8").splitlines()) == 4
    s.takt_phase(5.0, "aus")
    s.takt_ende(9.0)
    s.takt_beginn(20.0, "Box 4-4", 10.0)
    s.phase(6.0, "aus")
    s.journal_anhaengen(j)
    zeilen = [json.loads(z) for z in j.read_text(encoding="utf-8").splitlines()]
    assert [z[0] for z in zeilen] == ["k", "e", "t", "q", "p", "u", "t", "q"]
    assert zeilen[5] == ["u", 9.0] and zeilen[6] == ["t", 20.0, "Box 4-4", 10.0]
    w = atem.AtemSammler.aus_journal(j)
    assert w.takt_laeufe == [[1.0, 9.0, "Box 4-4", 7.5], [20.0, None, "Box 4-4", 10.0]]
    assert w.takt_offen and w.takt_phasen == [(1.0, "ein"), (5.0, "aus")]
    assert w.dokument() == s.dokument()
    # Weiter im selben Journal ohne zweiten Kopf, auch nach dem Wiederaufbau
    w.takt_phase(21.0, "ein")
    w.takt_ende(25.0)
    w.journal_anhaengen(j)
    zeilen = [json.loads(z) for z in j.read_text(encoding="utf-8").splitlines()]
    assert sum(1 for z in zeilen if z[0] == "k") == 1
    assert zeilen[-2:] == [["u", 25.0], ["q", 21.0, "ein"]]
    assert atem.AtemSammler.aus_journal(j).dokument() == w.dokument()
    # Unlesbares im Takt-Teil fällt weg
    j.write_text(
        "\n".join(
            [
                '["t", 1.0]',  # ohne Name und Rate
                '["t", "x", "a", 1]',  # keine Zahl
                '["q", 2.0, "ein"]',
                '["q", 3.0, "halten"]',
                '["u", "x"]',
                '["u", 4.0]',
                '["t", 5.0, null, "nan"]',
            ]
        ),
        encoding="utf-8",
    )
    w = atem.AtemSammler.aus_journal(j)
    assert w.takt_laeufe == [[1.0, 4.0, "", None], [5.0, None, "", None]]
    assert w.takt_phasen == [(2.0, "ein")]


def test_laden_ohne_und_mit_kaputtem_takt(tmp_path) -> None:
    pfad = tmp_path / "sensor_x_atem.json"
    # Datei vor 0.13.0: kein Feld → None, nichts sonst ändert sich
    pfad.write_text(json.dumps({"schema": "atem-v1", "phasen": [[1.0, "ein"]]}), encoding="utf-8")
    a = atem.atem_laden(pfad)
    assert a.takt is None and a.takt_phasen_zwischen(0.0, 10.0) == []
    assert a.phasen == [(1.0, "ein")]
    # Tolerant: kaputte Teile sind leer, kein Objekt ist wie kein Feld
    pfad.write_text(
        json.dumps(
            {
                "schema": "atem-v1",
                "takt": {
                    "name": None,
                    "rate_pro_min": "7.5",
                    "phasen": [[3.0, "aus"], [1.0, "ein"], [2.0, "halten"], "x"],
                    "laeufe": [[1.0, None, "A"], [5.0, 4.0, None, "nan"], [2.0], "x"],
                },
            }
        ),
        encoding="utf-8",
    )
    a = atem.atem_laden(pfad)
    assert a.takt == atem.Takt(
        name="",
        rate_pro_min=7.5,
        phasen=[(1.0, "ein"), (3.0, "aus")],
        laeufe=[(1.0, 1.0, "A", None), (5.0, 5.0, "", None)],
    )
    assert a.takt_phasen_zwischen(1.0, 3.0) == [(1.0, "ein")]
    pfad.write_text(json.dumps({"schema": "atem-v1", "takt": [1, 2]}), encoding="utf-8")
    assert atem.atem_laden(pfad).takt is None


def test_takt_bleibt_bei_deid_vollstaendig(tmp_path) -> None:
    doc = _sammler_mit_takt().dokument()
    pfad = _sammler_mit_takt().schreiben(tmp_path / "sensor_2026-11-05_061500.json")
    neu, meldungen = deid.deidentifizieren_dict(doc, pfad.name)
    assert neu == doc and meldungen == [] and neu["takt"]["laeufe"] == doc["takt"]["laeufe"]
