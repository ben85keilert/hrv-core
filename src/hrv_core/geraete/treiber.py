"""Treiber je Gerät mit Reifegrad — was hrv-core über ein Gerät weiß, ohne Bluetooth.

Plan Diagnosemodus der trainingsapp §8.3 (Stufe 7). Ein Treiber sagt, woran man ein Gerät
erkennt, welche Ströme es hat, wie man sie einschaltet, wie man sie entschlüsselt und wie
weit das geprüft ist. Die Apps behalten den Transport und ihre Quelle (trainingsapp
``devices/polar.py``, praxis_gui); sie lesen hier den **Reifegrad**, um ihn anzuzeigen, und
die Ströme, um sie im Sensorblatt anzubieten. Die IDs sind die Profil-IDs der Apps
(``geraet_profil`` in den Messdateien) — „ein Eintrag, kein Umbau“.

**Reifegrade** (sichtbar in der App):

- *erkannt* — Dienste bekannt, nur Standardströme; das Gerät wurde nicht eigens geprüft;
- *Prototyp* — der Dekoder ist an einer Geräteprobe getestet (Rohmitschnitt, ``mitschnitt-v1``);
- *geprüft* — an zwei Geräten oder zwei Personen gegen den H10 geprüft
  (``docs/geraete/ble_uebertragung_pruefen.md``);
- *empfohlen* — geprüft und als Referenz oder für HRV ausdrücklich geeignet.

**Weg einer Geräteprobe zum Treiber** (``docs/geraete/README.md``): Rohmitschnitt ohne Messung
in der App (Diagnosemodus) → Probe bei Ben (fremde Proben bleiben lokal und kommen nie in ein
Repo, P115) → Befund unter ``docs/geraete/<gerät>/`` → Treiber hier als *Prototyp* mit Test auf
einem synthetischen Nachbau → Reifegrad hebt sich mit der Prüfung.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from . import gatt, pmd

ERKANNT = "erkannt"
PROTOTYP = "prototyp"
GEPRUEFT = "geprueft"
EMPFOHLEN = "empfohlen"
REIFEGRADE: tuple[str, ...] = (ERKANNT, PROTOTYP, GEPRUEFT, EMPFOHLEN)
REIFEGRAD_TEXT: dict[str, str] = {
    ERKANNT: "erkannt",
    PROTOTYP: "Prototyp",
    GEPRUEFT: "geprüft",
    EMPFOHLEN: "empfohlen",
}


@dataclass(frozen=True, slots=True)
class Strom:
    """Ein Datenstrom des Geräts."""

    name: str  # hr, ecg, acc, ppi, ppg, gyro, mag
    merkmal: str  # UUID der Characteristic
    #: Dekoder (Funktionsname in `gatt` oder `pmd`), leer: nur roh
    dekoder: str = ""
    #: einschalten: ``""`` (abonnieren genügt) oder ``"pmd"`` (Startkommando)
    start: str = ""
    raten_hz: tuple[int, ...] = ()
    #: im Diagnosemodus der trainingsapp am Gerät erprobt
    erprobt: bool = False


@dataclass(frozen=True, slots=True)
class Treiber:
    """Was über ein Gerät bekannt ist (Modultext)."""

    id: str
    name: str
    reifegrad: str
    muster: tuple[str, ...] = ()
    dienste: tuple[str, ...] = ()
    stroeme: tuple[Strom, ...] = ()
    #: Befund in Worten (Pfad unter ``docs/geraete/``)
    befund: str = ""
    hinweise: tuple[str, ...] = field(default_factory=tuple)

    @property
    def reifegrad_text(self) -> str:
        return REIFEGRAD_TEXT.get(self.reifegrad, self.reifegrad)

    def strom(self, name: str) -> Strom | None:
        return next((s for s in self.stroeme if s.name == name), None)


_HR = Strom("hr", gatt.HR_MEASUREMENT_UUID, "parse_hr_measurement", erprobt=True)

TREIBER: tuple[Treiber, ...] = (
    Treiber(
        "polar_h10",
        "Polar H10",
        EMPFOHLEN,
        muster=("polar h10", "h10"),
        dienste=(gatt.HR_SERVICE_UUID, pmd.PMD_SERVICE_UUID),
        stroeme=(
            _HR,
            Strom("ecg", pmd.PMD_DATA_UUID, "parse_ekg_proben", "pmd", (130,), erprobt=True),
            Strom("acc", pmd.PMD_DATA_UUID, "parse_acc_proben", "pmd", (25, 50, 100, 200), True),
        ),
        befund="geraete.md",
        hinweise=("Referenz und Goldstandard: RR aus dem EKG, 1/1024 s.",),
    ),
    Treiber(
        "polar_h9",
        "Polar H9",
        ERKANNT,
        muster=("polar h9", "h9"),
        dienste=(gatt.HR_SERVICE_UUID,),
        stroeme=(_HR,),
        befund="geraete.md",
        hinweise=("Nach Profil, ungetestet; kein PMD-Dienst.",),
    ),
    Treiber(
        "verity_sense",
        "Polar Verity Sense",
        GEPRUEFT,
        muster=("verity", "polar sense"),
        dienste=(gatt.HR_SERVICE_UUID, pmd.PMD_SERVICE_UUID),
        stroeme=(
            _HR,
            Strom("ppi", pmd.PMD_DATA_UUID, "parse_ppi_proben", "pmd", erprobt=True),
            Strom("acc", pmd.PMD_DATA_UUID, "parse_acc_proben", "pmd", (52,)),
            Strom("ppg", pmd.PMD_DATA_UUID, "", "pmd", (55,)),
        ),
        befund="verity_sense/README.md",
        hinweise=(
            "Intervalle gegen den H10 geprüft; die Zeitachse der Pakete ist schwach.",
            "PPG kommt komprimiert — ohne Dekoder nur roh.",
        ),
    ),
    Treiber(
        "polar_watch",
        "Polar-Uhr (PMD)",
        ERKANNT,
        muster=("polar ignite", "polar pacer", "polar vantage", "polar grit"),
        dienste=(gatt.HR_SERVICE_UUID, pmd.PMD_SERVICE_UUID),
        stroeme=(_HR, Strom("ppi", pmd.PMD_DATA_UUID, "parse_ppi_proben", "pmd")),
    ),
    Treiber(
        "ble_optisch",
        "Optischer Sensor (Armband)",
        ERKANNT,
        dienste=(gatt.HR_SERVICE_UUID,),
        stroeme=(_HR,),
    ),
    Treiber(
        "watch_broadcast",
        "Uhr (Herzfrequenz-Übertragung)",
        ERKANNT,
        dienste=(gatt.HR_SERVICE_UUID,),
        stroeme=(_HR,),
        hinweise=("Meist nur die Herzfrequenz, keine Intervalle.",),
    ),
    Treiber(
        "ble_generic",
        "Herzfrequenz-Sensor (Standardprofil)",
        ERKANNT,
        dienste=(gatt.HR_SERVICE_UUID,),
        stroeme=(_HR,),
        befund="ble_uebertragung_pruefen.md",
        hinweise=("Ob RR stimmen, sagt erst die Prüfung gegen den H10.",),
    ),
)

_NACH_ID: dict[str, Treiber] = {t.id: t for t in TREIBER}


def treiber(profil_id: str) -> Treiber | None:
    """Der Treiber zu einer Profil-ID — ``None``, wenn es keinen gibt.

    >>> treiber("polar_h10").reifegrad_text, treiber("unbekannt") is None
    ('empfohlen', True)
    """
    return _NACH_ID.get(profil_id)


def reifegrad(profil_id: str) -> str | None:
    """Der Reifegrad zu einer Profil-ID (``None``: unbekanntes Gerät).

    >>> reifegrad("verity_sense"), reifegrad("polar_h9"), reifegrad("")
    ('geprueft', 'erkannt', None)
    """
    t = treiber(profil_id)
    return t.reifegrad if t is not None else None


def erkennen(name: str, dienste: Iterable[str] = ()) -> Treiber | None:
    """Ein Treiber nach Name, sonst nach Diensten (Herzfrequenz → Standardprofil).

    >>> erkennen("Polar H10 A1B2C3D4").id, erkennen("Fernseher") is None
    ('polar_h10', True)
    >>> erkennen("Gurt", {gatt.HR_SERVICE_UUID}).id
    'ble_generic'
    """
    klein = (name or "").lower()
    for t in TREIBER:
        if any(m in klein for m in t.muster):
            return t
    gemeldet = {d.lower() for d in dienste}
    if gatt.HR_SERVICE_UUID in gemeldet:
        return _NACH_ID["ble_generic"]
    return None


__all__ = [
    "EMPFOHLEN",
    "ERKANNT",
    "GEPRUEFT",
    "PROTOTYP",
    "REIFEGRADE",
    "REIFEGRAD_TEXT",
    "TREIBER",
    "Strom",
    "Treiber",
    "erkennen",
    "reifegrad",
    "treiber",
]
