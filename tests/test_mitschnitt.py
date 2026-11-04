"""Rohmitschnitt `mitschnitt.py`: Schreiber, Leser, Ströme, Zusammenfassung — und sein deid.

Alle Zeilen synthetisch; Adressen und Namen erfunden.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hrv_core import deid, mitschnitt
from hrv_core.geraete import pmd
from hrv_core.recording import ist_messdatei


class Uhr:
    """Monotone Uhr zum Weiterdrehen (ns)."""

    def __init__(self, t: int = 1_000_000_000) -> None:
        self.t = t

    def __call__(self) -> int:
        return self.t

    def weiter(self, s: float) -> None:
        self.t += round(s * 1e9)


def _schreiber(pfad: Path, uhr: Uhr, **kopf) -> mitschnitt.Schreiber:
    return mitschnitt.Schreiber(pfad, kopf or {"app": "test"}, uhr_ns=uhr, wanduhr_ns=lambda: 42)


def test_kopf_zuerst_dann_zeilen_und_uhr_alle_10_s(tmp_path) -> None:
    uhr = Uhr()
    s = _schreiber(tmp_path / "sensor_x_mitschnitt.jsonl", uhr, geraet={"name": "Gurt"})
    s.benachrichtigung("hr", b"\x00\x40", s=1, tm=5, tw=6)
    uhr.weiter(10.5)
    s.geschrieben("pmd_ctrl", pmd.ACC_START)
    s.gelesen("akku", b"\x5a")
    s.gelesen("info_modell", fehler="zeitüberschreitung")
    s.protokoll("Verbunden (MTU 232)", q="polar", zustand="verbunden")
    s.schliessen()
    s.protokoll("nach dem Schließen")  # passiert nichts
    zeilen = list(mitschnitt.lesen(s.pfad))
    assert [z["art"] for z in zeilen] == ["kopf", "n", "w", "uhr", "r", "r", "v"]
    kopf = zeilen[0]
    assert kopf["format"] == mitschnitt.FORMAT and kopf["wall_ns"] == 42
    assert kopf["geraet"] == {"name": "Gurt"} and kopf["start_utc"].endswith("Z")
    assert zeilen[1] == {
        "art": "n",
        "t": 1_000_000_000,
        "c": "hr",
        "x": "0040",
        "s": 1,
        "tm": 5,
        "tw": 6,
    }
    assert zeilen[2]["a"] is True and zeilen[2]["x"] == pmd.ACC_START.hex()
    assert zeilen[5] == {"art": "r", "t": uhr.t, "c": "info_modell", "fehler": "zeitüberschreitung"}
    assert s.zeilen == 7 and s.bytes == s.pfad.stat().st_size


def test_fsync_hoechstens_alle_5_s(tmp_path, monkeypatch) -> None:
    aufrufe: list[int] = []
    monkeypatch.setattr(mitschnitt.os, "fsync", lambda fd: aufrufe.append(fd))
    uhr = Uhr()
    s = _schreiber(tmp_path / "m_mitschnitt.jsonl", uhr)
    for _ in range(20):
        uhr.weiter(0.5)
        s.benachrichtigung("hr", b"\x00\x40")
    assert len(aufrufe) == 2  # nach 5 s und nach 10 s
    s.schliessen()
    assert len(aufrufe) == 3


def test_halbe_zeile_nach_absturz_und_marken_zaehlen_weiter(tmp_path) -> None:
    pfad = tmp_path / ".backup_1_mitschnitt.jsonl"
    uhr = Uhr()
    s = _schreiber(pfad, uhr)
    assert s.marke(mitschnitt.MARKE_WDH, nr=1)["id"] == 1
    s.marke(mitschnitt.MARKE_WDH, nr=2)
    s.schliessen()
    with open(pfad, "a", encoding="utf-8") as f:
        f.write('{"art":"marke","t":5,"id":3,"ty')  # Absturz mitten in der Zeile
    s2 = _schreiber(pfad, uhr)  # Neustart: kein zweiter Kopf, Uhrpaar sofort
    m = s2.marke(mitschnitt.MARKE_ATEM, quelle=mitschnitt.QUELLE_UHR, tm=99)
    s2.marke_weg(1)
    s2.schliessen()
    assert m["id"] == 3
    zeilen = list(mitschnitt.lesen(pfad))
    assert [z["art"] for z in zeilen] == ["kopf", "marke", "marke", "marke", "uhr", "marke_weg"]
    gelesen = mitschnitt.laden(pfad)
    assert [(z["id"], z["typ"]) for z in gelesen.marken()] == [(2, "wdh"), (3, "atem")]
    with pytest.raises(ValueError):
        s2.marke("unbekannt")


def test_umbenennen_schreibt_unter_dem_neuen_namen_weiter(tmp_path) -> None:
    uhr = Uhr()
    s = _schreiber(mitschnitt.journal_pfad(tmp_path / ".backup_2026-11-04_061500.json"), uhr)
    s.benachrichtigung("hr", b"\x00\x40")
    ziel = mitschnitt.mitschnitt_pfad(tmp_path / "sensor_2026-11-04_061500.json")
    assert (
        s.umbenennen(ziel) == ziel
        and not (tmp_path / ".backup_2026-11-04_061500_mitschnitt.jsonl").exists()
    )
    s.benachrichtigung("hr", b"\x00\x41")
    # Ein vorhandenes Ziel wird nie ersetzt — geschrieben wird weiter unter dem alten Namen
    belegt = tmp_path / "belegt_mitschnitt.jsonl"
    belegt.write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        s.umbenennen(belegt)
    s.benachrichtigung("hr", b"\x00\x42")
    s.schliessen()
    assert [z.get("x") for z in mitschnitt.lesen(ziel) if z["art"] == "n"] == [
        "0040",
        "0041",
        "0042",
    ]
    assert not ist_messdatei(ziel) and mitschnitt.ist_mitschnitt(ziel)


def test_schreibfehler_wird_gezaehlt_nicht_geworfen(tmp_path) -> None:
    s = _schreiber(tmp_path / "f_mitschnitt.jsonl", Uhr())

    class Kaputt:
        def write(self, _text: str) -> int:
            raise OSError("Speicher voll")

        def flush(self) -> None:  # pragma: no cover
            pass

        def close(self) -> None:
            pass

        def fileno(self) -> int:
            raise OSError("zu")

    s._datei = Kaputt()  # type: ignore[assignment]
    s.benachrichtigung("hr", b"\x00")
    assert s.fehler == 1 and "Speicher voll" in (s.letzter_fehler or "")
    s.schliessen()


def _ecg_zeilen(n_rahmen: int, *, luecke_nach: int | None = None) -> list[dict]:
    zeilen = []
    t_geraet = 10**12
    for k in range(n_rahmen):
        t_geraet += round(73 / 130 * 1e9)
        if luecke_nach is not None and k == luecke_nach + 1:
            t_geraet += 2 * 10**9
        x = pmd.rahmen_bauen(pmd.MEAS_ECG, t_geraet, pmd.ekg_kodieren(range(73)))
        zeilen.append(
            {"art": "n", "t": 5 * 10**9 + k * 10**8, "c": "pmd_data", "x": x.hex(), "s": k}
        )
    return zeilen


def test_stroeme_mit_luecke_komprimiertem_und_kopf_rate(tmp_path) -> None:
    zeilen = [{"art": "kopf", "t": 0, "stroeme": {"acc": {"rate_hz": 100}}}]
    zeilen += _ecg_zeilen(8, luecke_nach=3)
    for k in range(5):  # ACC 100 Hz, Rahmen zu 36 Proben
        x = pmd.rahmen_bauen(
            pmd.MEAS_ACC, 10**12 + (k + 1) * 360_000_000, pmd.acc_kodieren([(k, -k, 1000)] * 36), 1
        )
        zeilen.append({"art": "n", "t": 6 * 10**9 + k, "c": "pmd_data", "x": x.hex()})
    zeilen.append(
        {"art": "n", "t": 7, "c": "pmd_data", "x": pmd.rahmen_bauen(2, 0, bytes(12), 0x81).hex()}
    )
    zeilen.append({"art": "n", "t": 8, "c": "pmd_data", "x": "zz"})  # kein Hex: übergangen
    m = mitschnitt.Mitschnitt(kopf=zeilen[0], zeilen=zeilen)
    s = mitschnitt.stroeme(m)
    ecg, acc = s["ecg"], s["acc"]
    assert ecg.rahmen == 8 and ecg.n == 8 * 73 and ecg.rate_hz == pytest.approx(130, abs=0.01)
    assert len(ecg.luecken) == 1 and ecg.luecken[0]["nach_rahmen"] == 3
    assert ecg.luecken[0]["dauer_s"] == pytest.approx(2.0, abs=0.01)
    assert ecg.seq == list(range(8))
    # Probenzeiten: die letzte Probe jedes Rahmens liegt auf seiner Gerätezeit
    ende = np.cumsum(ecg.n_proben) - 1
    assert np.array_equal(ecg.proben_geraet_ns[ende], ecg.geraet_ns)
    assert acc.nennrate_hz == 100 and acc.rate_hz == pytest.approx(100.0)
    assert acc.werte.shape == (180, 3) and acc.ungelesen == 1 and acc.frame_typen == {1: 5, 0x81: 1}
    z = mitschnitt.zusammenfassen(m)
    assert z["stroeme"]["ecg"]["luecken"] == 1 and z["stroeme"]["acc"]["ungelesen"] == 1
    assert z["seq_luecken"] == 0 and z["pakete"] == {"pmd_data": 15}


def test_leser_geht_ueber_leere_und_kaputte_zeilen(tmp_path) -> None:
    pfad = tmp_path / "mitschnitt.jsonl"
    pfad.write_text('\n[1,2]\n{"t":1}\n{"art":"n","t":2,"c":"hr","x":"00"}\nkaputt\n', "utf-8")
    m = mitschnitt.laden(pfad)
    assert m.kopf == {} and [z["t"] for z in m.zeilen] == [2]
    assert m.benachrichtigungen("hr") == m.benachrichtigungen(mitschnitt.HR_MEASUREMENT_UUID)
    assert m.t0_ns == 2 and m.uhrpaare() == []


# -- deid -----------------------------------------------------------------------------------

NAME = "Polar H10 A1B2C3D4"
MAC = "E2:B4:CC:3F:08:44"


def _roher_mitschnitt(pfad: Path) -> Path:
    uhr = Uhr()
    s = mitschnitt.Schreiber(
        pfad,
        {"app": "trainingsapp", "geraet": {"name": NAME, "id": MAC, "profil": "polar_h10"}},
        uhr_ns=uhr,
        wanduhr_ns=lambda: 1,
    )
    s.protokoll(f"Verbinde mit {NAME} [{MAC}]", q="polar")
    s.protokoll("dienste 0000180d-0000-1000-8000-00805f9b34fb fb005c80-02e7-f387-1cad-8acd2d8df0c8")
    s.gelesen("00002a25-0000-1000-8000-00805f9b34fb", b"1234")  # darf nie vorkommen
    s.benachrichtigung("00002a00-0000-1000-8000-00805f9b34fb", NAME.encode())
    s.benachrichtigung("hr", b"\x00\x40")
    s.marke(mitschnitt.MARKE_WDH, nr=1, kontext={"uebung": "Kniebeuge", "satz": 2})
    s.kontext("satz", uebung="Kniebeuge", feld="reps", wert=12)
    s.zeile("gps", lat=52.1)
    s.zeile("probe", akku=80, unbekannt=1)
    s.schliessen()
    return pfad


def test_mitschnitt_deid_maskiert_kuerzt_und_entfernt(tmp_path) -> None:
    quelle = _roher_mitschnitt(tmp_path / "roh" / "sensor_2026-11-04_061500_mitschnitt.jsonl")
    ziel = tmp_path / "sauber_mitschnitt.jsonl"
    meldungen = deid.mitschnitt_deidentifizieren(quelle, ziel)
    text = ziel.read_text(encoding="utf-8")
    assert MAC not in text and "A1B2C3D4" not in text and "lat" not in text
    zeilen = [json.loads(z) for z in text.splitlines()]
    assert zeilen[0]["geraet"] == {
        "name": "Polar H10",
        "id": "E2:B4:CC:xx:xx:xx",
        "profil": "polar_h10",
    }
    assert zeilen[1]["text"] == "Verbinde mit Polar H10 [E2:B4:CC:xx:xx:xx]"
    assert "0000180d-0000-1000-8000-00805f9b34fb fb005c80" in zeilen[2]["text"]  # Dienste bleiben
    arten = [z["art"] for z in zeilen]
    assert arten == ["kopf", "v", "v", "n", "marke", "kontext", "probe"]
    assert zeilen[-1] == {"art": "probe", "t": zeilen[-1]["t"], "akku": 80}
    assert ("unbekannt", "gps") in meldungen and ("unbekannt", "probe.unbekannt") in meldungen
    assert ("entfernt", "r.c") in meldungen and ("entfernt", "n.c") in meldungen
    assert ("freitext", "marke.kontext.uebung") in meldungen
    # je Pfad nur einmal gemeldet
    assert len(meldungen) == len(set(meldungen))


def test_deid_nimmt_den_mitschnitt_als_beiwerk_mit_und_pruefen_urteilt(tmp_path) -> None:
    roh = tmp_path / "roh"
    roh.mkdir()
    messdatei = roh / "sensor_2026-11-04_061500.json"
    messdatei.write_text(
        json.dumps({"schema": "raw-v1", "geraet": NAME, "messungen": []}), encoding="utf-8"
    )
    _roher_mitschnitt(mitschnitt.mitschnitt_pfad(messdatei))
    assert deid.stamm(mitschnitt.mitschnitt_pfad(messdatei)) == "sensor_2026-11-04_061500"
    assert mitschnitt.mitschnitt_pfad(messdatei) in deid.beiwerk(messdatei)
    # Der rohe Mitschnitt fällt bei der Prüfung durch …
    bericht = deid.pruefen(roh, ordnerregel=False)
    gruende = [g for p, g in bericht.ablehnungen if p.name.endswith("_mitschnitt.jsonl")]
    assert any(g.startswith("Adresse unmaskiert") for g in gruende)
    assert any(g.startswith("Kennung des Geräts") for g in gruende)
    assert any(g.startswith("Seriennummer oder Adresse im Gerätenamen") for g in gruende)
    assert any(g.startswith("unbekanntes Feld") for g in gruende)
    # … die de-identifizierte Kopie besteht (Freitext nur als Hinweis)
    ziele = deid.deidentifizieren(messdatei, tmp_path / "selbst", mit_beiwerk=True)
    assert {z.name for z in ziele} == {messdatei.name, "sensor_2026-11-04_061500_mitschnitt.jsonl"}
    bericht = deid.pruefen(tmp_path / "selbst", ordnerregel=False)
    assert bericht.ok, bericht.ablehnungen
    assert bericht.geprueft == 2
    assert any("Freitext" in h for _, h in bericht.hinweise)


def test_adressen_im_text_aber_keine_uhrzeiten_und_dienste() -> None:
    assert deid.adressen_maskieren("08:15:00 · 2026-11-04 · 24-AC-AC-01-02-03") == (
        "08:15:00 · 2026-11-04 · 24-AC-AC-xx-xx-xx"
    )
    uuid = "fb005c81-02e7-f387-1cad-8acd2d8df0c8"
    assert deid.adressen_maskieren(uuid) == uuid
