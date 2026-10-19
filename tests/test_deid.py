"""deid: Weißliste je Feld, Personenfelder leeren, Gerät kürzen; Prüfung des Datenordners."""

import json
from pathlib import Path

import pytest

from hrv_core import deid

# Erfundene Minimaldatei — kein echter Messwert.
ROH = {
    "behandlung_id": 42,
    "patient_id": 7,
    "datum": "1900-01-01",
    "geraet": "Testgerät",
    "schema": "raw-v1",
    "titel": "Testperson",
    "notiz": "",
    "ereignisse": [{"beat_index": 1, "dt_s": 0.1, "text": "Start"}],
    "messungen": [{"t_s": 0.8, "t_wall_s": 0.81, "tw_src": "m", "hf_bpm": 75, "rr_ms": 800}],
}


def _schreibe(pfad: Path, daten) -> None:
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")


def test_personenfelder_werden_null_und_rest_bleibt(tmp_path):
    quelle = tmp_path / "quelle" / "sensor_1900-01-01_000000.json"
    quelle.parent.mkdir()
    _schreibe(quelle, ROH)
    (ziel,) = deid.deidentifizieren(quelle, tmp_path / "p001")
    kopie = json.loads(ziel.read_text(encoding="utf-8"))
    assert kopie["patient_id"] is None and kopie["behandlung_id"] is None
    erwartet = dict(ROH, patient_id=None, behandlung_id=None)
    assert kopie == erwartet
    assert list(kopie) == list(ROH)  # Reihenfolge der Felder bleibt
    assert json.loads(quelle.read_text(encoding="utf-8")) == ROH  # Original unberührt


def test_beiwerk_kommt_mit_und_laeuft_durch_seine_weissliste(tmp_path):
    ordner = tmp_path / "quelle"
    ordner.mkdir()
    quelle = ordner / "sensor_1900-01-01_000000.json"
    _schreibe(quelle, ROH)
    sidecar = ordner / "sensor_1900-01-01_000000_analyzed.json"
    sidecar.write_bytes(b'{"schema": "analysis-v1",\n "corrections": []}')
    korrigiert = ordner / "sensor_1900-01-01_000000__c01.json"
    _schreibe(korrigiert, dict(ROH, schema="corrected-v1"))
    fremd = ordner / "sensor_1900-01-01_000001.json"
    _schreibe(fremd, ROH)

    ziele = deid.deidentifizieren(quelle, tmp_path / "p001", mit_beiwerk=True)
    namen = sorted(z.name for z in ziele)
    assert namen == sorted([quelle.name, sidecar.name, korrigiert.name])
    kopie_sidecar = json.loads((tmp_path / "p001" / sidecar.name).read_text(encoding="utf-8"))
    assert kopie_sidecar == {"schema": "analysis-v1", "corrections": []}  # analysis-v1-Weißliste
    kopie_c = json.loads((tmp_path / "p001" / korrigiert.name).read_text(encoding="utf-8"))
    assert kopie_c["patient_id"] is None


def test_vorhandenes_ziel_wird_nicht_ueberschrieben(tmp_path):
    quelle = tmp_path / "sensor_1900-01-01_000000.json"
    _schreibe(quelle, ROH)
    deid.deidentifizieren(quelle, tmp_path / "p001")
    with pytest.raises(FileExistsError):
        deid.deidentifizieren(quelle, tmp_path / "p001")
    deid.deidentifizieren(quelle, tmp_path / "p001", ueberschreiben=True)


def test_pruefen_lehnt_personenfelder_und_falsche_ordner_ab(tmp_path):
    (tmp_path / "p001").mkdir()
    (tmp_path / "Mueller").mkdir()
    _schreibe(tmp_path / "p001" / "sensor_a.json", dict(ROH, patient_id=None, behandlung_id=None))
    _schreibe(tmp_path / "p001" / "sensor_b.json", dict(ROH, behandlung_id=None))
    _schreibe(
        tmp_path / "Mueller" / "sensor_c.json",
        dict(ROH, patient_id=None, behandlung_id=None, titel="", ereignisse=[]),
    )
    (tmp_path / "p001" / "kaputt.json").write_text("{", encoding="utf-8")

    bericht = deid.pruefen(tmp_path)
    gruende = {p.name: g for p, g in bericht.ablehnungen}
    assert "Mueller" in gruende
    assert gruende["sensor_b.json"].endswith("patient_id")
    assert "kaputt.json" in gruende
    assert "sensor_a.json" not in gruende
    assert not bericht.ok
    hinweise = {p.name for p, _ in bericht.hinweise}
    assert hinweise == {"sensor_a.json", "sensor_b.json"}  # Freitext nur gemeldet
    assert bericht.geprueft == 4


def test_pruefen_ohne_ordnerregel_fuer_fixtures(tmp_path):
    (tmp_path / "praxis_gui").mkdir()
    _schreibe(
        tmp_path / "praxis_gui" / "sensor_a.json", dict(ROH, patient_id=None, behandlung_id=None)
    )
    assert not deid.pruefen(tmp_path).ok
    assert deid.pruefen(tmp_path, ordnerregel=False).ok


def test_versionierte_fixtures_tragen_keine_personenfelder():
    fixtures = Path(__file__).parent / "fixtures"
    bericht = deid.pruefen(fixtures, ordnerregel=False)
    assert bericht.ok, bericht.ablehnungen
    assert bericht.geprueft > 0


# ---------------------------------------------------------------------------
# Weißliste (Befund F12, 19.10.2026) — eine Datei mit allen genannten Feldern
# ---------------------------------------------------------------------------

#: Erfunden, kein echter Messwert. Trägt alles, was bis 19.10. unbemerkt durchging.
VOLL = {
    "behandlung_id": 42,
    "patient_id": 7,
    "datum": "1900-01-01",
    "geraet": "Polar H10 A1B2C3D4",
    "geraet_profil": "polar_h10",
    "intervall_quelle": "ekg_rr",
    "datenqualitaet": "rr_ekg",
    "simulation": False,
    "generator_config": None,
    "schema": "raw-v1",
    "analyzed": False,
    "start_utc": "1900-01-01T00:00:00Z",
    "batterie_prozent": 90,
    "ecg_aufzeichnung": False,
    "ppg_aufzeichnung": False,
    "titel": "Testperson",
    "notiz": "",
    "ereignisse": [
        {
            "beat_index": 1,
            "dt_s": 0.1,
            "t_wall_s": 0.9,
            "t_s": 0.9,
            "wall_time": "01:00:00",
            "text": "Start",
            "uebungen": ["2ATPZC"],
            "marke": {"quelle": "timer", "art": "start", "name": "Ruhe bei Frau X", "lat": 52.1},
        },
        {"t_s": 2.0, "text": "", "chart_x": 2.0},
    ],
    "messungen": [{"t_s": 0.8, "t_wall_s": 0.81, "tw_src": "m", "hf_bpm": 75, "rr_ms": 800}],
    "fremdes_feld": {"name": "X"},
    "_wiederherstellung": {"subject_id": "p-abc", "grenzen": [[{"t": 1.0}, "Ruhe", False]]},
}


def test_weissliste_entfernt_alles_was_sie_nicht_kennt(tmp_path):
    quelle = tmp_path / "quelle" / ".backup_1900-01-01_000000.json"
    quelle.parent.mkdir()
    _schreibe(quelle, VOLL)
    protokoll = []
    (ziel,) = deid.deidentifizieren(quelle, tmp_path / "p001", protokoll=protokoll)
    kopie = json.loads(ziel.read_text(encoding="utf-8"))

    assert kopie["patient_id"] is None and kopie["behandlung_id"] is None
    assert kopie["geraet"] == "Polar H10"  # Seriennummer weg
    assert "fremdes_feld" not in kopie and "_wiederherstellung" not in kopie
    assert kopie["ereignisse"][0]["marke"] == {
        "quelle": "timer",
        "art": "start",
        "name": "Ruhe bei Frau X",
    }
    assert kopie["ereignisse"][0]["uebungen"] == ["2ATPZC"]
    assert kopie["ereignisse"][1] == {"t_s": 2.0, "text": "", "chart_x": 2.0}
    assert (
        kopie["start_utc"] == VOLL["start_utc"] and kopie["datum"] == VOLL["datum"]
    )  # F13: bewusst
    assert kopie["messungen"] == VOLL["messungen"]
    gemeldet = {m for _, m in protokoll}
    assert gemeldet == {
        "geleert: behandlung_id",
        "geleert: patient_id",
        "gekuerzt: geraet",
        "freitext: titel",
        "freitext: ereignisse[0].text",
        "freitext: ereignisse[0].marke.name",
        "unbekannt: ereignisse[0].marke.lat",
        "unbekannt: fremdes_feld",
        "entfernt: _wiederherstellung",
    }
    assert deid.pruefen(tmp_path / "p001").ok


def test_pruefen_findet_verschachtelte_personenfelder_und_unbekanntes(tmp_path):
    (tmp_path / "p001").mkdir()
    _schreibe(tmp_path / "p001" / ".backup_a.json", VOLL)
    sitzung = {
        "schema": "sitzung-v1",
        "sitzung_id": "s1",
        "start_utc": "1900-01-01T00:00:00Z",
        "datum": "1900-01-01",
        "patient_id": None,
        "behandlung_id": None,
        "titel": "",
        "notiz": "",
        "teilnehmer": [
            {
                "geraet": "Polar Sense 1AB84530",
                "adresse": "AA:BB:CC:DD:EE:FF",
                "geraet_profil": "verity_sense",
                "intervall_quelle": "ppg_ppi",
                "ordner": "VeritySense",
                "datei": "sensor_a.json",
                "n_schlaege": 3,
            }
        ],
    }
    _schreibe(tmp_path / "p001" / "sitzung_1.json", sitzung)
    _schreibe(tmp_path / "p001" / "irgendwas.json", {"schema": "zukunft-v9", "x": 1})

    bericht = deid.pruefen(tmp_path)
    gruende = {}
    for pfad, grund in bericht.ablehnungen:
        gruende.setdefault(pfad.name, []).append(grund)
    assert gruende[".backup_a.json"] == [
        "Personenfeld gefüllt: behandlung_id, patient_id",
        "Seriennummer oder Adresse im Gerätenamen: geraet",
        "unbekannt" + "es Feld: ereignisse[0].marke.lat, fremdes_feld",
        "Personenfeld gefüllt: _wiederherstellung.subject_id",
    ]
    assert gruende["sitzung_1.json"] == [
        "Personenfeld gefüllt: teilnehmer[0].adresse",
        "Seriennummer im Gerätenamen: teilnehmer[0].geraet",
    ]
    assert gruende["irgendwas.json"] == ["unbekanntes Dateiformat"]
    hinweise = {p.name: h for p, h in bericht.hinweise}
    assert "marke.name" in hinweise[".backup_a.json"]

    # de-identifiziert ist die Sitzung sauber: Adresse null, Gerät gekürzt
    (ziel,) = deid.deidentifizieren(tmp_path / "p001" / "sitzung_1.json", tmp_path / "p002")
    kopie = json.loads(ziel.read_text(encoding="utf-8"))
    assert kopie["teilnehmer"][0]["adresse"] is None
    assert kopie["teilnehmer"][0]["geraet"] == "Polar Sense"
    assert deid.pruefen(tmp_path / "p002").ok


def test_unbekanntes_format_wird_nicht_geraten(tmp_path):
    quelle = tmp_path / "irgendwas.json"
    _schreibe(quelle, {"schema": "zukunft-v9", "x": 1})
    with pytest.raises(ValueError):
        deid.deidentifizieren(quelle, tmp_path / "p001")
    assert not (tmp_path / "p001" / "irgendwas.json").exists()


def test_adresse_wird_geleert_und_adresse_als_name_wird_unbekannt(tmp_path):
    """Gurt ohne Bluetooth-Namen: trainingsapp schrieb die MAC als `geraet` (19.10.2026).
    Seitdem steht die Adresse getrennt in `adresse`; beides darf die Kopie nicht tragen."""
    roh = dict(ROH, patient_id=None, behandlung_id=None, geraet="E2:B4:CC:3F:08:44")
    roh["adresse"] = "E2:B4:CC:3F:08:44"
    kopie, meldungen = deid.deidentifizieren_dict(roh, "sensor_1900-01-01_000000.json")
    assert kopie["geraet"] == "Unbekannt"
    assert kopie["adresse"] is None
    assert "gekuerzt: geraet" in meldungen and "geleert: adresse" in meldungen

    (tmp_path / "selbst").mkdir()
    _schreibe(tmp_path / "selbst" / "sensor_mac.json", dict(roh, adresse=None))
    _schreibe(tmp_path / "selbst" / "sensor_ok.json", dict(kopie))
    bericht = deid.pruefen(tmp_path)
    gruende = {p.name: g for p, g in bericht.ablehnungen}
    assert "Adresse im Gerätenamen: geraet" in gruende["sensor_mac.json"]
    assert "sensor_ok.json" not in gruende


def test_adresse_ueberlebt_den_round_trip_und_fehlt_ohne_wert():
    from hrv_core.recording import Recording

    rec = Recording.from_dict(dict(ROH, adresse="E2:B4:CC:3F:08:44"))
    assert rec.adresse == "E2:B4:CC:3F:08:44" and "adresse" not in rec.extra
    assert rec.to_dict()["adresse"] == "E2:B4:CC:3F:08:44"
    assert "adresse" not in Recording.from_dict(ROH).to_dict()
