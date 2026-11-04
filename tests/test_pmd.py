"""PMD-Dekoder `geraete/pmd.py`: Kommandos, Steuerantworten, Einstellungen, Rahmen.

Synthetische Bytes nach dem Format des Polar BLE SDK — keine Aufnahme eines Geräts.
"""

from __future__ import annotations

import pytest

from hrv_core.geraete import pmd


def test_kommandos_sind_byteweise_wie_am_geraet_erprobt() -> None:
    assert pmd.ECG_START.hex(" ") == "02 00 00 01 82 00 01 01 0e 00"
    assert pmd.ACC_START.hex(" ") == "02 02 00 01 c8 00 01 01 10 00 02 01 08 00"
    assert pmd.ACC_STOP.hex() == "0302" and pmd.ECG_STOP.hex() == "0300"
    assert pmd.ACC_EINSTELLUNGEN.hex() == "0102" and pmd.ECG_EINSTELLUNGEN.hex() == "0100"
    assert pmd.PPI_START.hex() == "0203" and pmd.PPI_STOP.hex() == "0303"
    assert pmd.acc_start(25, 2).hex(" ") == "02 02 00 01 19 00 01 01 10 00 02 01 02 00"


def test_steuerantwort_mit_parametern_und_fehler() -> None:
    gut = pmd.parse_control_antwort(bytes.fromhex("f0 02 02 00 00 01"))
    assert gut is not None and gut.ok and gut.typ == pmd.MEAS_ACC and not gut.mehr
    assert gut.parameter == b"\x01" and gut.einstellungen() == {}
    mehr = pmd.parse_control_antwort(bytes.fromhex("f0 01 02 00 01 00 01 c8 00"))
    assert mehr is not None and mehr.mehr and mehr.einstellungen() == {"rate_hz": [200]}
    schlecht = pmd.parse_control_antwort(bytes.fromhex("f0 02 02 06 00 01"))
    assert schlecht is not None and schlecht.fehler == pmd.FEHLER_LAEUFT_BEREITS
    assert schlecht.parameter == b"" and not schlecht.mehr
    assert schlecht.text == "Start ACC: läuft bereits (Code 6)"
    # eine kurze Antwort (nur vier Byte) wie vor 0.6.0
    kurz = pmd.parse_control_antwort(bytes.fromhex("f0 03 00 00"))
    assert kurz is not None and kurz.ok and kurz.parameter == b""


def test_einstellungen_hin_und_zurueck_und_unbekanntes_bleibt_roh() -> None:
    soll = {"rate_hz": [25, 50, 100, 200], "aufloesung_bit": [16], "bereich_g": [2, 4, 8]}
    assert pmd.parse_einstellungen(pmd.einstellungen_kodieren(soll)) == soll
    mit_kanaelen = {"rate_hz": [52], "kanaele": [3], "faktor": [1065353216]}
    assert pmd.parse_einstellungen(pmd.einstellungen_kodieren(mit_kanaelen)) == mit_kanaelen
    # Kennung 0x09 kennt das SDK nicht: Lesen endet, der Rest bleibt als Bytes
    roh = pmd.einstellungen_kodieren({"rate_hz": [130]}) + bytes([0x09, 0x01, 0xAA])
    assert pmd.parse_einstellungen(roh) == {"rate_hz": [130], "rest": [9, 1, 0xAA]}
    # ein angebrochener Eintrag ebenso
    assert pmd.parse_einstellungen(bytes.fromhex("00 02 c8 00 64")) == {
        "rest": [0, 2, 0xC8, 0, 0x64]
    }
    assert pmd.parse_einstellungen(b"") == {}


def test_merkmalsliste() -> None:
    assert pmd.parse_feature_antwort(bytes([0x0F, 0b0110_0111])) == frozenset(
        {"ecg", "ppg", "acc", "gyro", "mag"}
    )
    assert pmd.parse_feature_antwort(None) == frozenset()


@pytest.mark.parametrize("frame_typ", [0x00, 0x01, 0x02])
def test_beschleunigung_je_frame_typ(frame_typ: int) -> None:
    grenze = 1 << (8 * pmd.ACC_BYTES_JE_ACHSE[frame_typ] - 1)
    proben = [(grenze - 1, -grenze, 0), (1, -1, 7)]
    nutz = pmd.acc_kodieren(proben, frame_typ)
    r = pmd.parse_pmd_rahmen(pmd.rahmen_bauen(pmd.MEAS_ACC, 123, nutz + b"\x01", frame_typ))
    assert r is not None and r.zeitstempel_ns == 123 and r.name == "acc"
    assert pmd.acc_proben(r) == proben  # der angebrochene Rest fällt weg


def test_beschleunigung_wird_begrenzt_und_komprimiertes_nie_gelesen() -> None:
    nutz = pmd.acc_kodieren([(10**6, -(10**6), 0)])
    assert pmd.parse_acc_proben(nutz, 0x01) == [(32767, -32768, 0)]
    roh = pmd.rahmen_bauen(pmd.MEAS_ACC, 1, nutz, frame_typ=0x81)
    assert pmd.ist_komprimiert(roh) and pmd.parse_pmd_rahmen(roh) is None
    assert pmd.parse_acc_proben(nutz, 0x81) is None


def test_ekg_und_ppi_wie_bisher() -> None:
    werte = [0, 1, -1, 2**23 - 1, -(2**23)]
    r = pmd.parse_pmd_rahmen(pmd.rahmen_bauen(pmd.MEAS_ECG, 5, pmd.ekg_kodieren(werte)))
    assert r is not None and pmd.parse_ekg_proben(r.nutzdaten) == werte
    assert pmd.acc_proben(r) is None
    p = [pmd.PpiProbe(60, 1000, 5, False, True, True)]
    assert pmd.parse_ppi_proben(pmd.ppi_kodieren(p)) == p
