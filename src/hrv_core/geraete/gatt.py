"""Bluetooth-Standardwissen: Namen der Dienste und Merkmale, Dekoder der Herzfrequenz-Messung.

Was ein unbekanntes Gerät beim Verbinden meldet, soll lesbar sein (Rohmitschnitt ohne Messung,
Plan Diagnosemodus der trainingsapp §2.8): „Herzfrequenz“, „Akku“, „Laufsensor“ statt
``0000180d-…``. Herstellereigene Dienste (alles außerhalb der Bluetooth-Basis-UUID) sind als
solche erkennbar (`ist_standard`). Die Namen folgen den *Assigned Numbers* der Bluetooth SIG,
deutsch und kurz; nur, was für Sport- und Gesundheitssensoren vorkommt.

Dazu der Dekoder des Standardstroms 0x2A37 — bis 0.7.0 in ``trainingsapp/devices/base.py``
(dort weiter durchgereicht), gleiche Bytes, gleiche Werte wie praxis_gui.
"""

from __future__ import annotations

from .pmd import PMD_CONTROL_UUID, PMD_DATA_UUID, PMD_SERVICE_UUID

#: Endung der Bluetooth-Basis-UUID — ``0000xxxx-0000-1000-8000-00805f9b34fb``
BASIS = "-0000-1000-8000-00805f9b34fb"


def uuid16(kurz: int) -> str:
    """Die volle UUID einer 16-bit-Kennung.

    >>> uuid16(0x180D)
    '0000180d-0000-1000-8000-00805f9b34fb'
    """
    return f"0000{kurz:04x}{BASIS}"


def kurz_von(uuid: str) -> int | None:
    """Die 16-bit-Kennung einer Standard-UUID — ``None`` für herstellereigene.

    >>> kurz_von("0000180D-0000-1000-8000-00805F9B34FB"), kurz_von(PMD_SERVICE_UUID)
    (6157, None)
    """
    u = uuid.lower()
    if not ist_standard(u) or not u.startswith("0000"):
        return None
    return int(u[4:8], 16)


def ist_standard(uuid: str) -> bool:
    """Liegt die UUID in der Bluetooth-Basis (Standard der SIG)? Sonst herstellereigen.

    >>> ist_standard(uuid16(0x2A37)), ist_standard(PMD_DATA_UUID)
    (True, False)
    """
    return uuid.lower().endswith(BASIS)


HR_SERVICE_UUID = uuid16(0x180D)
HR_MEASUREMENT_UUID = uuid16(0x2A37)
BATTERY_SERVICE_UUID = uuid16(0x180F)
BATTERY_LEVEL_UUID = uuid16(0x2A19)
DEVICE_INFO_SERVICE_UUID = uuid16(0x180A)

#: Merkmale mit einer Kennung des einzelnen Geräts — die Apps lesen sie nie (Gerätename steht
#: ohnehin im Scan; Systemkennung ist oft aus der Adresse abgeleitet)
SERIENNUMMER_UUID = uuid16(0x2A25)
SYSTEMKENNUNG_UUID = uuid16(0x2A23)
NIE_LESEN: frozenset[str] = frozenset({SERIENNUMMER_UUID, SYSTEMKENNUNG_UUID})

DIENSTE: dict[str, str] = {
    uuid16(0x1800): "Allgemeiner Zugang (GAP)",
    uuid16(0x1801): "Allgemeine Attribute (GATT)",
    uuid16(0x180A): "Geräteinformation",
    uuid16(0x180D): "Herzfrequenz",
    uuid16(0x180F): "Akku",
    uuid16(0x1805): "Uhrzeit",
    uuid16(0x1809): "Thermometer",
    uuid16(0x1808): "Glukose",
    uuid16(0x1810): "Blutdruck",
    uuid16(0x1814): "Laufsensor (RSC)",
    uuid16(0x1816): "Rad: Geschwindigkeit und Trittfrequenz (CSC)",
    uuid16(0x1818): "Radleistung",
    uuid16(0x1819): "Ort und Navigation",
    uuid16(0x181C): "Benutzerdaten",
    uuid16(0x181D): "Körpergewicht",
    uuid16(0x1822): "Pulsoximeter",
    uuid16(0x1826): "Fitnessgerät (FTMS)",
    PMD_SERVICE_UUID: "Polar Measurement Data (PMD)",
}

MERKMALE: dict[str, str] = {
    uuid16(0x2A00): "Gerätename",
    uuid16(0x2A01): "Erscheinungsbild",
    uuid16(0x2A04): "Verbindungsparameter",
    uuid16(0x2A05): "Dienste geändert",
    uuid16(0x2A19): "Akkustand",
    uuid16(0x2A23): "Systemkennung",
    uuid16(0x2A24): "Modellnummer",
    uuid16(0x2A25): "Seriennummer",
    uuid16(0x2A26): "Firmware",
    uuid16(0x2A27): "Hardware",
    uuid16(0x2A28): "Software",
    uuid16(0x2A29): "Hersteller",
    uuid16(0x2A2A): "Zulassungsdaten",
    uuid16(0x2A50): "PnP-Kennung",
    uuid16(0x2A37): "Herzfrequenz-Messung",
    uuid16(0x2A38): "Sensorlage",
    uuid16(0x2A39): "Herzfrequenz-Steuerpunkt",
    uuid16(0x2A53): "Lauf-Messung (RSC)",
    uuid16(0x2A54): "Lauf-Merkmale",
    uuid16(0x2A5B): "Rad-Messung (CSC)",
    uuid16(0x2A5C): "Rad-Merkmale",
    uuid16(0x2A5D): "Sensorlage (Rad)",
    uuid16(0x2A63): "Radleistung-Messung",
    uuid16(0x2A65): "Radleistung-Merkmale",
    uuid16(0x2A5E): "SpO2-Einzelmessung",
    uuid16(0x2A5F): "SpO2 fortlaufend",
    uuid16(0x2A60): "Pulsoximeter-Merkmale",
    uuid16(0x2A35): "Blutdruck-Messung",
    uuid16(0x2A1C): "Temperatur-Messung",
    uuid16(0x2ACD): "Laufband-Daten (FTMS)",
    uuid16(0x2AD2): "Indoor-Rad-Daten (FTMS)",
    PMD_CONTROL_UUID: "PMD-Steuerung",
    PMD_DATA_UUID: "PMD-Daten",
}


def name(uuid: str) -> str | None:
    """Der Name eines Dienstes oder Merkmals — ``None``, wenn unbekannt.

    >>> name("0000180D-0000-1000-8000-00805F9B34FB"), name(PMD_DATA_UUID), name("1234")
    ('Herzfrequenz', 'PMD-Daten', None)
    """
    u = uuid.lower()
    return DIENSTE.get(u) or MERKMALE.get(u)


def beschreibung(uuid: str) -> str:
    """Name samt Herkunft — für Listen.

    >>> beschreibung(uuid16(0x2A19)), beschreibung("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
    ('Akkustand (0x2A19)', 'herstellereigen (6e400001…)')
    """
    u = uuid.lower()
    bekannt = name(u)
    kurz = kurz_von(u)
    if bekannt and kurz is not None:
        return f"{bekannt} (0x{kurz:04X})"
    if bekannt:
        return bekannt
    if kurz is not None:
        return f"Standard 0x{kurz:04X}"
    return f"herstellereigen ({u[:8]}…)"


# ---------------------------------------------------------------------------
# Dekoder 0x2A37 — Herzfrequenz-Messung
# ---------------------------------------------------------------------------


def parse_hr_measurement(data: bytes | bytearray) -> tuple[int, list[int]]:
    """Zerlegt eine Notification der Characteristic 0x2A37.

    Aufbau: Flags-Byte, dann Herzfrequenz (8 oder 16 Bit), optional „energy expended“
    (2 Byte), dann **beliebig viele** RR-Intervalle zu je 2 Byte in Einheiten von 1/1024 s.

    Achtung: Ein Gerät sendet bei Pulsen über 60 bpm regelmäßig **zwei** RR-Werte pro
    Notification. Wer nur den ersten liest, verliert rund die Hälfte aller Intervalle (in
    praxis_gui einst 84 s Drift in 28 min). Deshalb die Schleife bis zum Paketende.

    Returns:
        ``(bpm, rr_ms_liste)`` — die Liste ist leer, wenn Bit 4 der Flags nicht gesetzt ist.

    >>> parse_hr_measurement(bytes([0x10, 60, 0x00, 0x04]))   # Flags: RR vorhanden
    (60, [1000])
    >>> parse_hr_measurement(bytes([0x10, 60, 0x00, 0x04, 0x48, 0x03]))  # zwei RR
    (60, [1000, 820])
    >>> parse_hr_measurement(bytes([0x00, 72])), parse_hr_measurement(b"")
    ((72, []), (0, []))
    >>> parse_hr_measurement(bytes([0x19, 0x2C, 0x01, 0x10, 0x00, 0x00, 0x04]))  # 16 bit, Energie
    (300, [1000])
    """
    if not data:
        return 0, []
    flags = data[0]
    hf_16bit = bool(flags & 0x01)
    energie_vorhanden = bool((flags >> 3) & 0x01)
    rr_vorhanden = bool((flags >> 4) & 0x01)
    idx = 1
    if hf_16bit:
        bpm = int.from_bytes(data[idx : idx + 2], "little")
        idx += 2
    else:
        bpm = data[idx] if idx < len(data) else 0
        idx += 1
    if energie_vorhanden:
        idx += 2
    rr_ms: list[int] = []
    if rr_vorhanden:
        while idx + 1 < len(data):
            roh = int.from_bytes(data[idx : idx + 2], "little")
            rr_ms.append(round(roh * 1000 / 1024))
            idx += 2
    return bpm, rr_ms


def hautkontakt_aus_flags(data: bytes | bytearray) -> bool | None:
    """Hautkontakt aus dem Flags-Byte einer 0x2A37-Notification.

    Bit 2 sagt, ob das Gerät Kontakt überhaupt erkennt; nur dann bedeutet Bit 1 „Kontakt
    da“. Ohne Bit 2 ist die Antwort ``None`` (unbekannt), nicht ``False``.

    >>> hautkontakt_aus_flags(bytes([0x16, 60])), hautkontakt_aus_flags(bytes([0x14, 60]))
    (True, False)
    >>> hautkontakt_aus_flags(bytes([0x12, 60])) is None, hautkontakt_aus_flags(b"") is None
    (True, True)
    """
    if not data:
        return None
    flags = data[0]
    if not flags & 0x04:
        return None
    return bool(flags & 0x02)


def parse_akkustand(data: bytes | bytearray) -> int | None:
    """Akkustand 0x2A19: ein Byte, Prozent — ``None`` bei leerem oder unsinnigem Wert.

    >>> parse_akkustand(bytes([87])), parse_akkustand(b""), parse_akkustand(bytes([250]))
    (87, None, None)
    """
    if not data or data[0] > 100:
        return None
    return int(data[0])


__all__ = [
    "BASIS",
    "BATTERY_LEVEL_UUID",
    "BATTERY_SERVICE_UUID",
    "DEVICE_INFO_SERVICE_UUID",
    "DIENSTE",
    "HR_MEASUREMENT_UUID",
    "HR_SERVICE_UUID",
    "MERKMALE",
    "NIE_LESEN",
    "SERIENNUMMER_UUID",
    "SYSTEMKENNUNG_UUID",
    "beschreibung",
    "hautkontakt_aus_flags",
    "ist_standard",
    "kurz_von",
    "name",
    "parse_akkustand",
    "parse_hr_measurement",
    "uuid16",
]
