"""De-Identifizierung von Messdateien und Prüfung des Testdatenordners.

Zwei Aufgaben, beide ohne Personenbezug im Code:

``deidentifizieren(quelle, zielordner)``
    kopiert eine Messdatei (``raw-v1`` oder jede andere JSON-Datei mit den
    Feldern), setzt ``patient_id`` und ``behandlung_id`` auf ``null`` und lässt
    **alles andere unverändert**: Datum, Uhrzeit, Gerät, Batteriestand, Titel,
    Notiz, Ereignisse, Messwerte. Welche Messungen zur selben Person gehören,
    sagt allein der Personenordner (Code wie ``p001``), nicht die Datei. Die
    Kopien gehören in das private Repo hrv-research (``$HRV_TESTDATA``), nie
    in dieses — hrv-core wird öffentlich.

``pruefen(wurzel)``
    läuft über den Testdatenordner und lehnt ab, was dort nicht hingehört:
    gefüllte Personenfelder und Ordnernamen, die nicht dem Code-Muster folgen.
    Freitextfelder (``titel``, ``notiz``, ``ereignisse[].text``) werden nur
    **gemeldet** — ob darin ein Name steht, sieht nur der Mensch.

Nie etwas aus dem Inhalt protokollieren; die Funktionen geben nur Pfade und
Feldnamen zurück.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

PERSONENFELDER = ("patient_id", "behandlung_id")
FREITEXTFELDER = ("titel", "notiz")
BEIWERK_SUFFIXE = ("_analyzed.json", "_ecg.json", "_ppg.json", "_truth.json")
ORDNER_MUSTER = re.compile(r"^(p\d{3}|selbst)$")
_KORRIGIERT = re.compile(r"__c\d+\.json$")


def stamm(pfad: Path) -> str:
    """Gemeinsamer Namensstamm einer Messdatei und ihres Beiwerks.

    >>> stamm(Path("sensor_2026-05-23_125422_analyzed.json"))
    'sensor_2026-05-23_125422'
    >>> stamm(Path("sensor_2026-05-23_125422__c01.json"))
    'sensor_2026-05-23_125422'
    """
    name = pfad.name
    for suffix in BEIWERK_SUFFIXE:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    treffer = _KORRIGIERT.search(name)
    if treffer:
        return name[: treffer.start()]
    if name.endswith(".json"):
        return name[:-5]
    raise ValueError(f"keine Messdatei: {name}")


def beiwerk(messdatei: Path) -> list[Path]:
    """Alle Dateien neben ``messdatei``, die an ihrem Stamm hängen (ohne sie selbst)."""
    messdatei = Path(messdatei)
    basis = stamm(messdatei)
    gefunden = []
    for kandidat in sorted(messdatei.parent.iterdir()):
        if kandidat == messdatei or not kandidat.is_file():
            continue
        if kandidat.name == f"{basis}.json":
            continue
        if kandidat.name.startswith(basis + "_") or kandidat.name.startswith(basis + "__c"):
            gefunden.append(kandidat)
    return gefunden


def _personenfelder_leeren(daten: dict) -> bool:
    """Setzt die Personenfelder auf None. True, wenn eines vorhanden war."""
    vorhanden = False
    for feld in PERSONENFELDER:
        if feld in daten:
            daten[feld] = None
            vorhanden = True
    return vorhanden


def _datei_deidentifizieren(quelle: Path, ziel: Path) -> None:
    """Eine Datei: JSON mit Personenfeldern wird neu geschrieben, alles andere byteweise kopiert."""
    if quelle.suffix.lower() == ".json":
        with open(quelle, encoding="utf-8") as fh:
            daten = json.load(fh)
        if isinstance(daten, dict) and _personenfelder_leeren(daten):
            with open(ziel, "w", encoding="utf-8") as fh:
                json.dump(daten, fh, ensure_ascii=False, indent=2)
            return
    shutil.copyfile(quelle, ziel)


def deidentifizieren(
    quelle: str | Path,
    zielordner: str | Path,
    *,
    mit_beiwerk: bool = False,
    ueberschreiben: bool = False,
) -> list[Path]:
    """Kopiert ``quelle`` de-identifiziert nach ``zielordner`` und gibt die Zielpfade zurück.

    Das Original bleibt unberührt. Mit ``mit_beiwerk`` kommen die Dateien am
    selben Stamm mit (``_analyzed``, ``_ecg``, ``_ppg``, ``_truth``, ``__cNN``);
    auch sie verlieren die Personenfelder, falls sie welche tragen. Ein
    vorhandenes Ziel wird ohne ``ueberschreiben`` nicht angefasst.
    """
    quelle = Path(quelle)
    zielordner = Path(zielordner)
    if not quelle.is_file():
        raise FileNotFoundError(quelle)
    zielordner.mkdir(parents=True, exist_ok=True)
    dateien = [quelle] + (beiwerk(quelle) if mit_beiwerk else [])
    ziele = []
    for datei in dateien:
        ziel = zielordner / datei.name
        if ziel.exists() and not ueberschreiben:
            raise FileExistsError(ziel)
        _datei_deidentifizieren(datei, ziel)
        ziele.append(ziel)
    return ziele


@dataclass
class Pruefbericht:
    """Ergebnis von ``pruefen``: Ablehnungen sind Fehler, Hinweise nur Lesestoff."""

    ablehnungen: list[tuple[Path, str]] = field(default_factory=list)
    hinweise: list[tuple[Path, str]] = field(default_factory=list)
    geprueft: int = 0

    @property
    def ok(self) -> bool:
        return not self.ablehnungen


def _freitext(daten: dict) -> list[str]:
    felder = [f for f in FREITEXTFELDER if daten.get(f)]
    ereignisse = daten.get("ereignisse") or []
    if any(isinstance(e, dict) and e.get("text") for e in ereignisse):
        felder.append("ereignisse[].text")
    return felder


def pruefen(wurzel: str | Path, *, ordnerregel: bool = True) -> Pruefbericht:
    """Prüft alle JSON-Dateien unter ``wurzel`` und die Namen der Personenordner."""
    wurzel = Path(wurzel)
    bericht = Pruefbericht()
    if not wurzel.is_dir():
        bericht.ablehnungen.append((wurzel, "Ordner fehlt"))
        return bericht
    if ordnerregel:
        for eintrag in sorted(wurzel.iterdir()):
            if eintrag.is_dir() and not ORDNER_MUSTER.match(eintrag.name):
                bericht.ablehnungen.append(
                    (eintrag, "Ordnername folgt nicht dem Muster p### oder selbst")
                )
    for datei in sorted(wurzel.rglob("*.json")):
        bericht.geprueft += 1
        try:
            with open(datei, encoding="utf-8") as fh:
                daten = json.load(fh)
        except (OSError, ValueError):
            bericht.ablehnungen.append((datei, "nicht als JSON lesbar"))
            continue
        if not isinstance(daten, dict):
            continue
        gefuellt = [f for f in PERSONENFELDER if daten.get(f) not in (None, "")]
        if gefuellt:
            bericht.ablehnungen.append((datei, "Personenfeld gefüllt: " + ", ".join(gefuellt)))
        freitext = _freitext(daten)
        if freitext:
            bericht.hinweise.append((datei, "Freitext vorhanden: " + ", ".join(freitext)))
    return bericht
