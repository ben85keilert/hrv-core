"""Polar Measurement Data (PMD) — Kommandos, Steuerantworten und Rahmen.

Byteweise wie ``praxis_gui/src/praxislab/sensors/devices/pmd.py``; bis 0.6.0 lag diese Fassung
in ``trainingsapp/devices/pmd.py`` (die App reicht sie seitdem nur durch), die Beschleunigung in
der Brustgurt-Diagnose von hrv-research. Reines Python — das Protokoll lässt sich ohne Gerät
prüfen; der Transport reicht nur rohe Bytes durch.

Stand der Verifikation: EKG (Typ 0) und Beschleunigung (Typ 2, 200 Hz, 16 bit, 8 g, Frame-Typ
``0x01``) am Polar H10 erprobt (praxis_gui; Brustgurt-Diagnose 3.11.2026), **PPI (Typ 3) am
Verity Sense geprüft** (19.09.2026). PPG kommt am Verity Sense delta-komprimiert; dafür gibt es
keinen Dekoder — solche Rahmen erkennt `ist_komprimiert`, `parse_pmd_rahmen` verwirft sie.

Rahmenaufbau (alle Typen)::

    Byte 0     Messtyp
    Byte 1–8   Zeitstempel, uint64 LE, Nanosekunden seit 2000-01-01 — Zeit der **letzten**
               Probe des Rahmens (bei PPI je nach Firmware 0)
    Byte 9     Frame-Typ (Bit 7 gesetzt = komprimiert)
    Byte 10+   Nutzdaten, je Messtyp und Frame-Typ verschieden

Steuerung: Kommando auf die Control-Characteristic schreiben (mit Antwort), die Antwort kommt
als Indication auf derselben Characteristic::

    [0xF0, Opcode, Messtyp, Fehler, mehr, Parameter …]

``mehr`` und die Parameter stehen nur in erfolgreichen Antworten. Die Parameter einer
Einstellungsabfrage (`OP_GET_SETTINGS`) sind Einträge ``<Kennung> <Anzahl> <Werte …>``
(`parse_einstellungen`) — dasselbe Muster wie die Einstellungen im Startkommando.
Bezeichnungen nach dem Polar BLE SDK (``PmdControlPointResponse``, ``PmdSetting``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Dienst und Characteristics
# ---------------------------------------------------------------------------
PMD_SERVICE_UUID = "fb005c80-02e7-f387-1cad-8acd2d8df0c8"
PMD_CONTROL_UUID = "fb005c81-02e7-f387-1cad-8acd2d8df0c8"
PMD_DATA_UUID = "fb005c82-02e7-f387-1cad-8acd2d8df0c8"

#: Länge des Rahmenkopfs (Messtyp, Zeitstempel, Frame-Typ)
HEADER_SIZE = 10

# Messtypen
MEAS_ECG = 0x00
MEAS_PPG = 0x01
MEAS_ACC = 0x02
MEAS_PPI = 0x03
MEAS_GYRO = 0x05
MEAS_MAG = 0x06

TYP_NAME: dict[int, str] = {
    MEAS_ECG: "ecg",
    MEAS_PPG: "ppg",
    MEAS_ACC: "acc",
    MEAS_PPI: "ppi",
    MEAS_GYRO: "gyro",
    MEAS_MAG: "mag",
}

# Steuerkommandos
OP_GET_SETTINGS = 0x01
OP_START = 0x02
OP_STOP = 0x03

#: Kennung einer Steuerantwort (Byte 0)
ANTWORT_KENNUNG = 0xF0
#: Kennung der Merkmalsliste (Byte 0 beim Lesen der Control-Characteristic)
MERKMAL_KENNUNG = 0x0F

# Einstellungskennungen — im Startkommando und in der Antwort auf `OP_GET_SETTINGS`
SET_SAMPLE_RATE = 0x00
SET_RESOLUTION = 0x01
SET_RANGE = 0x02
SET_RANGE_MILLIUNIT = 0x03
SET_CHANNELS = 0x04
SET_FACTOR = 0x05
SET_SECURITY = 0x06

#: Name und Breite (Byte je Wert) der Einstellungen — Breiten nach dem Polar BLE SDK
#: (``PmdSetting``); am H10 gesehen: Rate, Auflösung, Bereich (je 2 Byte)
EINSTELLUNG: dict[int, tuple[str, int]] = {
    SET_SAMPLE_RATE: ("rate_hz", 2),
    SET_RESOLUTION: ("aufloesung_bit", 2),
    SET_RANGE: ("bereich_g", 2),
    SET_RANGE_MILLIUNIT: ("bereich_milli", 8),
    SET_CHANNELS: ("kanaele", 1),
    SET_FACTOR: ("faktor", 4),
    SET_SECURITY: ("sicherheit", 16),
}

#: Fehlercodes der Steuerantwort — Bezeichnungen nach dem Polar BLE SDK
#: (``PmdControlPointResponseCode``), nur für die Anzeige.
FEHLER_TEXT: dict[int, str] = {
    0x00: "erfolgreich",
    0x01: "unbekannter Opcode",
    0x02: "unbekannter Messtyp",
    0x03: "nicht unterstützt",
    0x04: "falsche Länge",
    0x05: "ungültiger Parameter",
    0x06: "läuft bereits",
    0x07: "ungültige Auflösung",
    0x08: "ungültige Abtastrate",
    0x09: "ungültiger Bereich",
    0x0A: "ungültige MTU",
    0x0B: "ungültige Kanalzahl",
    0x0C: "ungültiger Zustand",
    0x0D: "Gerät lädt",
}

#: „läuft bereits“ — nach einem schnellen Reconnect harmlos.
FEHLER_LAEUFT_BEREITS = 0x06


# ---------------------------------------------------------------------------
# Kommandos
# ---------------------------------------------------------------------------


def einstellung(kennung: int, wert: int) -> bytes:
    """Eine Einstellung im Startkommando: ``<Kennung> <Anzahl=1> <Wert uint16 LE>``.

    >>> einstellung(SET_SAMPLE_RATE, 200).hex(" ")
    '00 01 c8 00'
    """
    return bytes([kennung, 0x01, wert & 0xFF, (wert >> 8) & 0xFF])


def start_kommando(typ: int, einstellungen: bytes = b"") -> bytes:
    """Startkommando für einen Messtyp.

    >>> start_kommando(MEAS_PPI).hex()
    '0203'
    """
    return bytes([OP_START, typ]) + einstellungen


def stop_kommando(typ: int) -> bytes:
    """Stoppkommando für einen Messtyp.

    >>> stop_kommando(MEAS_ECG).hex(), stop_kommando(MEAS_PPI).hex()
    ('0300', '0303')
    """
    return bytes([OP_STOP, typ])


def einstellungen_kommando(typ: int) -> bytes:
    """Fragt, welche Einstellungen ein Messtyp kennt (Antwort: `parse_einstellungen`).

    >>> einstellungen_kommando(MEAS_ACC).hex()
    '0102'
    """
    return bytes([OP_GET_SETTINGS, typ])


#: PPI kennt keine Einstellungen — der Algorithmus läuft im Gerät.
PPI_START = start_kommando(MEAS_PPI)
PPI_STOP = stop_kommando(MEAS_PPI)

#: Polar H10, EKG: 130 Hz, 14 bit — byteweise wie praxis_gui (dort am Gerät erprobt).
ECG_START = start_kommando(
    MEAS_ECG, einstellung(SET_SAMPLE_RATE, 130) + einstellung(SET_RESOLUTION, 14)
)
ECG_STOP = stop_kommando(MEAS_ECG)

#: Vorgaben der Beschleunigung: 200 Hz, damit auch Stöße und Klopfen sichtbar sind; 8 g, damit
#: Sprünge nicht abgeschnitten werden; 16 bit. Der H10 kennt 25, 50, 100, 200 Hz und 2, 4, 8 g.
ACC_RATE_HZ = 200
ACC_BEREICH_G = 8
ACC_AUFLOESUNG_BIT = 16


def acc_start(
    rate_hz: int = ACC_RATE_HZ,
    bereich_g: int = ACC_BEREICH_G,
    aufloesung_bit: int = ACC_AUFLOESUNG_BIT,
) -> bytes:
    """Startkommando für die Beschleunigung (am H10 erprobt).

    >>> acc_start().hex(" ")
    '02 02 00 01 c8 00 01 01 10 00 02 01 08 00'
    >>> acc_start(100).hex(" ")
    '02 02 00 01 64 00 01 01 10 00 02 01 08 00'
    """
    return start_kommando(
        MEAS_ACC,
        einstellung(SET_SAMPLE_RATE, rate_hz)
        + einstellung(SET_RESOLUTION, aufloesung_bit)
        + einstellung(SET_RANGE, bereich_g),
    )


ACC_START = acc_start()
ACC_STOP = stop_kommando(MEAS_ACC)
ACC_EINSTELLUNGEN = einstellungen_kommando(MEAS_ACC)
ECG_EINSTELLUNGEN = einstellungen_kommando(MEAS_ECG)


# ---------------------------------------------------------------------------
# Steuerantworten
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ControlAntwort:
    """Eine Steuerantwort; ``mehr`` und ``parameter`` nur bei Erfolg (sonst leer)."""

    opcode: int
    typ: int
    fehler: int
    mehr: bool = False
    parameter: bytes = b""

    @property
    def ok(self) -> bool:
        return self.fehler == 0x00

    @property
    def text(self) -> str:
        """Lesbare Beschreibung für Statusmeldungen."""
        strom = TYP_NAME.get(self.typ, f"typ {self.typ:#04x}")
        befehl = {OP_START: "Start", OP_STOP: "Stopp", OP_GET_SETTINGS: "Einstellungen"}.get(
            self.opcode, f"op {self.opcode:#04x}"
        )
        grund = FEHLER_TEXT.get(self.fehler, "unbekannter Fehler")
        return f"{befehl} {strom.upper()}: {grund} (Code {self.fehler})"

    def einstellungen(self) -> dict[str, list[int]]:
        """Die gemeldeten Einstellungen einer Antwort auf `OP_GET_SETTINGS` — sonst leer."""
        if self.opcode != OP_GET_SETTINGS or not self.ok:
            return {}
        return parse_einstellungen(self.parameter)


def parse_control_antwort(data: bytes | bytearray | None) -> ControlAntwort | None:
    """Antwort auf ein Steuerkommando: ``[0xF0, Opcode, Messtyp, Fehler, mehr, Parameter …]``.

    Achtung, alte Falle aus praxis_gui: Byte 2 ist der **Messtyp**, nicht der
    Fehler — beim EKG (Typ 0) fiel das nicht auf.

    >>> a = parse_control_antwort(bytes([0xF0, 0x02, 0x00, 0x00, 0x00]))
    >>> a.ok, a.opcode, a.typ
    (True, 2, 0)
    >>> f = parse_control_antwort(bytes([0xF0, 0x02, 0x03, 0x05, 0x00]))
    >>> f.ok, f.fehler, f.text, f.parameter
    (False, 5, 'Start PPI: ungültiger Parameter (Code 5)', b'')
    >>> parse_control_antwort(b"\\xF0") is None
    True
    >>> parse_control_antwort(bytes([0x0F, 0x02, 0x03, 0x00])) is None   # keine Antwort
    True
    """
    b = bytes(data or b"")
    if len(b) < 4 or b[0] != ANTWORT_KENNUNG:
        return None
    if b[3] != 0x00:
        return ControlAntwort(opcode=b[1], typ=b[2], fehler=b[3])
    return ControlAntwort(
        opcode=b[1],
        typ=b[2],
        fehler=0,
        mehr=len(b) > 4 and b[4] != 0,
        parameter=b[5:],
    )


def parse_einstellungen(parameter: bytes | bytearray) -> dict[str, list[int]]:
    """Einstellungen ``<Kennung> <Anzahl> <Werte …>`` → ``{Name: [Werte]}``.

    Werte sind vorzeichenlose Ganzzahlen (LE) in der Breite aus `EINSTELLUNG`. Eine unbekannte
    Kennung oder ein angebrochener Eintrag beendet das Lesen; was bis dahin gelesen war, gilt,
    der Rest steht als Bytes unter ``"rest"`` (nichts wird geraten).

    Synthetisch nach dem Format (Rate 25/50/100/200 Hz, 16 bit, 2/4/8 g)::

    >>> p = bytes.fromhex("0004 1900 3200 6400 c800 0101 1000 0203 0200 0400 0800")
    >>> parse_einstellungen(p)
    {'rate_hz': [25, 50, 100, 200], 'aufloesung_bit': [16], 'bereich_g': [2, 4, 8]}
    >>> parse_einstellungen(bytes.fromhex("0001 8200 09 01"))
    {'rate_hz': [130], 'rest': [9, 1]}
    >>> a = parse_control_antwort(bytes.fromhex("f0 01 00 00 00") + bytes.fromhex("0001 8200"))
    >>> a.einstellungen()
    {'rate_hz': [130]}
    """
    b = bytes(parameter)
    out: dict[str, list[int]] = {}
    off = 0
    while off < len(b):
        art = EINSTELLUNG.get(b[off])
        if art is None or off + 2 > len(b):
            break
        name, breite = art
        anzahl = b[off + 1]
        ende = off + 2 + anzahl * breite
        if ende > len(b):
            break
        out[name] = [
            int.from_bytes(b[off + 2 + i * breite : off + 2 + (i + 1) * breite], "little")
            for i in range(anzahl)
        ]
        off = ende
    if off < len(b):
        out["rest"] = list(b[off:])
    return out


def parse_feature_antwort(data: bytes | bytearray | None) -> frozenset[str]:
    """Welche Messtypen das Gerät anbietet (Lesen der Control-Characteristic).

    Bitmaske in Byte 1: Bit 0 EKG, Bit 1 PPG, Bit 2 ACC, Bit 3 PPI,
    Bit 5 Gyroskop, Bit 6 Magnetometer.

    >>> sorted(parse_feature_antwort(bytes([0x0F, 0b0000_0101])))   # Polar H10
    ['acc', 'ecg']
    >>> sorted(parse_feature_antwort(bytes([0x0F, 0b0000_1110])))   # Verity Sense
    ['acc', 'ppg', 'ppi']
    >>> parse_feature_antwort(bytes([0x01, 0xFF]))
    frozenset()
    """
    b = bytes(data or b"")
    if len(b) < 2 or b[0] != MERKMAL_KENNUNG:
        return frozenset()
    maske = b[1]
    return frozenset(
        name
        for bit, name in ((0, "ecg"), (1, "ppg"), (2, "acc"), (3, "ppi"), (5, "gyro"), (6, "mag"))
        if maske & (1 << bit)
    )


# ---------------------------------------------------------------------------
# Datenrahmen
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PmdRahmen:
    """Ein zerlegter Rahmenkopf samt unausgewerteter Nutzdaten."""

    typ: int
    zeitstempel_ns: int
    frame_typ: int
    nutzdaten: bytes

    @property
    def t_s(self) -> float:
        return self.zeitstempel_ns / 1e9

    @property
    def name(self) -> str:
        return TYP_NAME.get(self.typ, f"typ_{self.typ:#04x}")


def ist_komprimiert(daten: bytes | bytearray) -> bool:
    """Ob ein Rohrahmen komprimiert ist (Bit 7 im Frame-Typ).

    >>> ist_komprimiert(bytes([2]) + bytes(8) + bytes([0x81]))
    True
    >>> ist_komprimiert(bytes([2]) + bytes(8) + bytes([0x01]))
    False
    """
    return len(daten) >= HEADER_SIZE and bool(daten[9] & 0x80)


def parse_pmd_rahmen(data: bytes | bytearray | None) -> PmdRahmen | None:
    """Rahmenkopf zerlegen.

    ``None`` bei zu kurzem Rahmen und bei gesetztem Bit 7 im Frame-Typ
    (delta-komprimiert, z. B. PPG am Verity Sense): als Rohwerte gelesen ergäbe
    ein solcher Rahmen Zahlen, die wie Messwerte aussehen.

    >>> r = parse_pmd_rahmen(rahmen_bauen(MEAS_PPI, 2_000_000_000, b"\\x01\\x02"))
    >>> r.name, r.t_s, r.frame_typ, r.nutzdaten
    ('ppi', 2.0, 0, b'\\x01\\x02')
    >>> parse_pmd_rahmen(rahmen_bauen(MEAS_PPG, 0, b"\\x00" * 12, frame_typ=0x80)) is None
    True
    >>> parse_pmd_rahmen(b"\\x00\\x01\\x02") is None
    True
    """
    b = bytes(data or b"")
    if len(b) < HEADER_SIZE or ist_komprimiert(b):
        return None
    return PmdRahmen(
        typ=b[0],
        zeitstempel_ns=int.from_bytes(b[1:9], "little"),
        frame_typ=b[9],
        nutzdaten=b[HEADER_SIZE:],
    )


@dataclass(frozen=True, slots=True)
class PpiProbe:
    """Ein Puls-zu-Puls-Intervall samt Güte.

    ``fehler_ms`` ist die Schätzung des Geräts, wie sicher das Intervall ist —
    bei optischer Messung die wertvollste Angabe, weil sie Bewegungsartefakte
    kennzeichnet, bevor eine Ausreißerheuristik raten muss.
    """

    hf_bpm: int
    ppi_ms: int
    fehler_ms: int
    blocker: bool  # Intervall unbrauchbar (Bewegung, Aussetzer)
    hautkontakt: bool
    hautkontakt_unterstuetzt: bool

    @property
    def brauchbar(self) -> bool:
        return not self.blocker and self.ppi_ms > 0


def parse_ppi_proben(nutzdaten: bytes) -> list[PpiProbe]:
    """PPI-Nutzdaten: je Intervall 6 Byte.

    ::

        Byte 0     Herzfrequenz (bpm)
        Byte 1–2   Intervall, uint16 LE, ms
        Byte 3–4   Fehlerschätzung, uint16 LE, ms
        Byte 5     Flags — Bit 0 Blocker, Bit 1 Hautkontakt,
                   Bit 2 Hautkontakt-Erkennung unterstützt

    Ein angebrochener Rest (< 6 Byte) wird verworfen, nie aufgefüllt.

    >>> p = parse_ppi_proben(bytes([62, 0xC8, 0x03, 3, 0, 0b110, 61, 0xD9, 0x03, 120, 0, 0b111]))
    >>> [(x.ppi_ms, x.fehler_ms, x.blocker, x.brauchbar) for x in p]
    [(968, 3, False, True), (985, 120, True, False)]
    """
    proben: list[PpiProbe] = []
    off = 0
    while off + 6 <= len(nutzdaten):
        flags = nutzdaten[off + 5]
        proben.append(
            PpiProbe(
                hf_bpm=nutzdaten[off],
                ppi_ms=int.from_bytes(nutzdaten[off + 1 : off + 3], "little"),
                fehler_ms=int.from_bytes(nutzdaten[off + 3 : off + 5], "little"),
                blocker=bool(flags & 0x01),
                hautkontakt=bool(flags & 0x02),
                hautkontakt_unterstuetzt=bool(flags & 0x04),
            )
        )
        off += 6
    return proben


def parse_ekg_proben(nutzdaten: bytes) -> list[int]:
    """EKG-Nutzdaten (H10, Frame-Typ 0): fortlaufend 3 Byte, vorzeichenbehaftet, µV.

    >>> parse_ekg_proben(ekg_kodieren([0, 1, -1, 1000, -1000, 8388607, -8388608]))
    [0, 1, -1, 1000, -1000, 8388607, -8388608]
    """
    werte: list[int] = []
    off = 0
    while off + 3 <= len(nutzdaten):
        wert = int.from_bytes(nutzdaten[off : off + 3], "little")
        werte.append(wert - 0x1000000 if wert >= 0x800000 else wert)
        off += 3
    return werte


#: Bytes je Achse und Probe der Beschleunigung nach Frame-Typ (unkomprimiert)
ACC_BYTES_JE_ACHSE: dict[int, int] = {0x00: 1, 0x01: 2, 0x02: 3}


def parse_acc_proben(nutzdaten: bytes, frame_typ: int) -> list[tuple[int, int, int]] | None:
    """Nutzdaten eines ACC-Rahmens zu ``(x, y, z)`` in mG — ``None`` bei unbekanntem Frame-Typ.

    Laut Polar BLE SDK liefert der H10 drei Achsen in mG; erwartet wird der unkomprimierte
    Frame-Typ ``0x01`` (16 bit je Achse), ``0x00`` (8 bit) und ``0x02`` (24 bit) liest der
    Parser ebenso. Ein angebrochener Rest wird verworfen, nie aufgefüllt.

    >>> parse_acc_proben(acc_kodieren([(1, -2, 1000), (-1000, 0, 7)]), 0x01)
    [(1, -2, 1000), (-1000, 0, 7)]
    >>> parse_acc_proben(acc_kodieren([(5, -6, 7)], frame_typ=0x00), 0x00)
    [(5, -6, 7)]
    >>> parse_acc_proben(acc_kodieren([(70000, -70000, 1)], frame_typ=0x02), 0x02)
    [(70000, -70000, 1)]
    >>> parse_acc_proben(bytes(6), 0x05) is None
    True
    """
    breite = ACC_BYTES_JE_ACHSE.get(frame_typ)
    if breite is None:
        return None
    schritt = 3 * breite
    proben: list[tuple[int, int, int]] = []
    for off in range(0, len(nutzdaten) - schritt + 1, schritt):
        x, y, z = (
            int.from_bytes(
                nutzdaten[off + i * breite : off + (i + 1) * breite], "little", signed=True
            )
            for i in range(3)
        )
        proben.append((x, y, z))
    return proben


def acc_proben(rahmen: PmdRahmen) -> list[tuple[int, int, int]] | None:
    """Die Proben eines zerlegten ACC-Rahmens — ``None``, wenn es keiner ist.

    >>> r = parse_pmd_rahmen(rahmen_bauen(MEAS_ACC, 5, acc_kodieren([(1, 2, 3)]), frame_typ=1))
    >>> acc_proben(r), acc_proben(parse_pmd_rahmen(rahmen_bauen(MEAS_ECG, 5, b"")))
    ([(1, 2, 3)], None)
    """
    if rahmen.typ != MEAS_ACC:
        return None
    return parse_acc_proben(rahmen.nutzdaten, rahmen.frame_typ)


# ---------------------------------------------------------------------------
# Rahmen bauen — für Tests und Simulatoren
# ---------------------------------------------------------------------------


def rahmen_bauen(typ: int, t_ns: int, nutzdaten: bytes, frame_typ: int = 0) -> bytes:
    """Rahmen zusammensetzen (Gegenstück zu `parse_pmd_rahmen`)."""
    return bytes([typ]) + int(t_ns).to_bytes(8, "little") + bytes([frame_typ]) + nutzdaten


def ppi_kodieren(proben: Sequence[PpiProbe]) -> bytes:
    """PPI-Proben als Nutzdaten (Gegenstück zu `parse_ppi_proben`)."""
    out = bytearray()
    for p in proben:
        flags = (
            (1 if p.blocker else 0)
            | (2 if p.hautkontakt else 0)
            | (4 if p.hautkontakt_unterstuetzt else 0)
        )
        out += bytes([min(max(int(p.hf_bpm), 0), 255)])
        out += int(p.ppi_ms).to_bytes(2, "little")
        out += int(p.fehler_ms).to_bytes(2, "little")
        out += bytes([flags])
    return bytes(out)


def ekg_kodieren(werte: Sequence[int]) -> bytes:
    """EKG-Werte als Nutzdaten (Gegenstück zu `parse_ekg_proben`)."""
    out = bytearray()
    for v in werte:
        out += (int(v) & 0xFFFFFF).to_bytes(3, "little")
    return bytes(out)


def acc_kodieren(proben: Sequence[tuple[int, int, int]], frame_typ: int = 0x01) -> bytes:
    """Proben als Nutzdaten (Gegenstück zu `parse_acc_proben`), auf den Wertebereich begrenzt."""
    breite = ACC_BYTES_JE_ACHSE[frame_typ]
    grenze = 1 << (8 * breite - 1)
    out = bytearray()
    for probe in proben:
        for wert in probe:
            begrenzt = max(-grenze, min(grenze - 1, int(wert)))
            out += begrenzt.to_bytes(breite, "little", signed=True)
    return bytes(out)


def einstellungen_kodieren(einstellungen: dict[str, Sequence[int]]) -> bytes:
    """Einstellungen als Parameter (Gegenstück zu `parse_einstellungen`; für Simulatoren).

    >>> einstellungen_kodieren({"rate_hz": [130], "aufloesung_bit": [14]}).hex(" ")
    '00 01 82 00 01 01 0e 00'
    """
    nach_name = {name: (kennung, breite) for kennung, (name, breite) in EINSTELLUNG.items()}
    out = bytearray()
    for name, werte in einstellungen.items():
        kennung, breite = nach_name[name]
        out += bytes([kennung, len(werte)])
        for wert in werte:
            out += int(wert).to_bytes(breite, "little")
    return bytes(out)


__all__ = [
    "ACC_AUFLOESUNG_BIT",
    "ACC_BEREICH_G",
    "ACC_BYTES_JE_ACHSE",
    "ACC_EINSTELLUNGEN",
    "ACC_RATE_HZ",
    "ACC_START",
    "ACC_STOP",
    "ANTWORT_KENNUNG",
    "ECG_EINSTELLUNGEN",
    "ECG_START",
    "ECG_STOP",
    "EINSTELLUNG",
    "FEHLER_LAEUFT_BEREITS",
    "FEHLER_TEXT",
    "HEADER_SIZE",
    "MEAS_ACC",
    "MEAS_ECG",
    "MEAS_GYRO",
    "MEAS_MAG",
    "MEAS_PPG",
    "MEAS_PPI",
    "MERKMAL_KENNUNG",
    "OP_GET_SETTINGS",
    "OP_START",
    "OP_STOP",
    "PMD_CONTROL_UUID",
    "PMD_DATA_UUID",
    "PMD_SERVICE_UUID",
    "PPI_START",
    "PPI_STOP",
    "SET_CHANNELS",
    "SET_FACTOR",
    "SET_RANGE",
    "SET_RANGE_MILLIUNIT",
    "SET_RESOLUTION",
    "SET_SAMPLE_RATE",
    "SET_SECURITY",
    "TYP_NAME",
    "ControlAntwort",
    "PmdRahmen",
    "PpiProbe",
    "acc_kodieren",
    "acc_proben",
    "acc_start",
    "einstellung",
    "einstellungen_kodieren",
    "einstellungen_kommando",
    "ekg_kodieren",
    "ist_komprimiert",
    "parse_acc_proben",
    "parse_control_antwort",
    "parse_einstellungen",
    "parse_ekg_proben",
    "parse_feature_antwort",
    "parse_pmd_rahmen",
    "parse_ppi_proben",
    "ppi_kodieren",
    "rahmen_bauen",
    "start_kommando",
    "stop_kommando",
]
