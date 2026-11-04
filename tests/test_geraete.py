"""Gerätewissen als Code: GATT-Namen, Dekoder 0x2A37, Treiber mit Reifegrad (0.7.0)."""

from __future__ import annotations

from hrv_core.geraete import gatt, pmd, treiber


def test_namen_und_herkunft() -> None:
    assert gatt.name(gatt.HR_SERVICE_UUID) == "Herzfrequenz"
    assert gatt.name(pmd.PMD_SERVICE_UUID) == "Polar Measurement Data (PMD)"
    assert gatt.ist_standard(gatt.uuid16(0x1818)) and not gatt.ist_standard(pmd.PMD_DATA_UUID)
    assert gatt.kurz_von(gatt.uuid16(0x2A63)) == 0x2A63
    assert gatt.beschreibung(gatt.uuid16(0x1234)) == "Standard 0x1234"
    assert gatt.SERIENNUMMER_UUID in gatt.NIE_LESEN and gatt.SYSTEMKENNUNG_UUID in gatt.NIE_LESEN


def test_dekoder_der_herzfrequenz() -> None:
    # 16-bit-HF, Energie, drei RR
    roh = bytes([0x19, 0x2C, 0x01, 0x10, 0x00, 0x00, 0x04, 0x00, 0x02, 0x00, 0x08])
    assert gatt.parse_hr_measurement(roh) == (300, [1000, 500, 2000])
    # halbes RR am Ende wird nicht gelesen
    assert gatt.parse_hr_measurement(bytes([0x10, 70, 0x00, 0x04, 0x01])) == (70, [1000])


def test_treiber_ids_reifegrade_und_erkennung() -> None:
    ids = [t.id for t in treiber.TREIBER]
    assert len(ids) == len(set(ids))
    assert all(t.reifegrad in treiber.REIFEGRADE for t in treiber.TREIBER)
    h10 = treiber.treiber("polar_h10")
    assert h10 is not None and h10.reifegrad == treiber.EMPFOHLEN
    assert h10.strom("acc") is not None and h10.strom("acc").raten_hz == (25, 50, 100, 200)
    assert treiber.erkennen("Polar Sense 1AB84530").id == "verity_sense"
    assert treiber.erkennen("Unbekannt", {pmd.PMD_SERVICE_UUID}) is None
    # Jeder Dekoder, den ein Strom nennt, gibt es wirklich
    for t in treiber.TREIBER:
        for s in t.stroeme:
            if s.dekoder:
                assert hasattr(gatt, s.dekoder) or hasattr(pmd, s.dekoder), (t.id, s.dekoder)
