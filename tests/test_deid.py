"""deid: Personenfelder leeren, alles andere unverändert; Prüfung des Datenordners."""

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


def test_beiwerk_kommt_mit_und_wird_byteweise_kopiert(tmp_path):
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
    assert (tmp_path / "p001" / sidecar.name).read_bytes() == sidecar.read_bytes()
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
    _schreibe(tmp_path / "Mueller" / "sensor_c.json", dict(ROH, patient_id=None, behandlung_id=None, titel="", ereignisse=[]))
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
    _schreibe(tmp_path / "praxis_gui" / "sensor_a.json", dict(ROH, patient_id=None, behandlung_id=None))
    assert not deid.pruefen(tmp_path).ok
    assert deid.pruefen(tmp_path, ordnerregel=False).ok


def test_versionierte_fixtures_tragen_keine_personenfelder():
    fixtures = Path(__file__).parent / "fixtures"
    bericht = deid.pruefen(fixtures, ordnerregel=False)
    assert bericht.ok, bericht.ablehnungen
    assert bericht.geprueft > 0
