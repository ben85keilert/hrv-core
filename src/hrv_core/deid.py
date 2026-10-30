"""De-Identifizierung von Messdateien und Prüfung des Testdatenordners.

Zwei Aufgaben, beide ohne Personenbezug im Code:

``deidentifizieren(quelle, zielordner)``
    kopiert eine Messdatei (``raw-v1``, Backup, ``corrected-v1``, Sidecar
    ``analysis-v1``, ``truth-v1``, ``sitzung-v1``, EKG/PPG-Rohdaten) über eine
    **Weißliste je Feld** (`REGELN`): Personenfelder werden ``null``
    (``patient_id``, ``behandlung_id``, ``subject_id``, BLE-``adresse``), der
    Gerätename auf das Modell gekürzt (``"Polar H10 ABC123"`` → ``"Polar H10"``,
    die Seriennummer wäre ein Pseudo-Identifikator über Dateien hinweg), Freitext
    bleibt und wird gemeldet, der Backup-Block ``_wiederherstellung`` fällt weg —
    und **jedes Feld, das die Weißliste nicht kennt, fällt weg** (rekursiv, auch
    in ``ereignisse[]``, ``marke``, ``segments[]``, ``teilnehmer[]``). Bis
    19.10.2026 leerte eine Schwarzliste nur zwei Top-Level-Felder (Befund F12).

    **Bewusst erhalten** (Ben, 19.10.2026, Befund F13): ``start_utc``, ``datum``,
    ``wall_time`` und der Dateiname mit der UTC-Startsekunde. Tagesdatum und
    Tageszeit sind für HRV-Aussagen wichtig (Tagesrhythmus, Abstand zu Mahlzeit
    und Training); zusammen mit dem Praxiskalender wären sie re-identifizierend —
    darum liegen die Kopien nur im privaten Repo hrv-research (``$HRV_TESTDATA``),
    und die Zuordnung Code ↔ Person steht außerhalb jedes Repos. Welche Messungen
    zur selben Person gehören, sagt allein der Personenordner (``p001``).

``pruefen(wurzel)``
    läuft über den Testdatenordner und lehnt ab, was dort nicht hingehört:
    gefüllte Personenfelder, Seriennummern im Gerätenamen, unbekannte Felder,
    unbekannte Dateiformate und Ordnernamen, die nicht dem Code-Muster folgen.
    Freitextfelder (``titel``, ``notiz``, ``ereignisse[].text``, ``marke.name``,
    ``segments[].name``) werden nur **gemeldet** — ob darin ein Name steht, sieht
    nur der Mensch.

Nie etwas aus dem Inhalt protokollieren; die Funktionen geben nur Pfade und
Feldnamen zurück. Welche Felder hrv-core schreibt: ``docs/formate.md``.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ereignisse import ANKER_FELDER, MARKE_FELDER

PERSONENFELDER = ("patient_id", "behandlung_id", "subject_id", "adresse")
FREITEXTFELDER = ("titel", "notiz")
BEIWERK_SUFFIXE = ("_analyzed.json", "_ecg.json", "_ppg.json", "_truth.json")
ORDNER_MUSTER = re.compile(r"^(p\d{3}|selbst)$")
_KORRIGIERT = re.compile(r"__c\d+\.json$")
#: Seriennummer am Ende eines BLE-Gerätenamens: Polar hängt 8 Zeichen [0-9A-F] an
#: („Polar H10 A1B2C3D4“, „Polar Sense 1AB84530“). Mindestens 6 Zeichen, nur
#: Großbuchstaben/Ziffern, mindestens eine Ziffer — „H10“, „nsr001“, „SYNTH“ nicht.
_SERIENNUMMER = re.compile(r"^(?=.*\d)[0-9A-Z]{6,}$")
#: BLE-Adresse (MAC `E2:B4:CC:3F:08:44`) oder Geräte-UUID (macOS/iOS) — landet im
#: Gerätenamen, wenn ein Gurt keinen Bluetooth-Namen meldet (trainingsapp bis 19.10.2026).
_ADRESSE = re.compile(
    r"^(?:(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}"
    r"|[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})$"
)

# -- Weißliste ------------------------------------------------------------------
#: Regeln je Feld: KEEP (bleibt), NULL (wird None), FREITEXT (bleibt, gemeldet),
#: GERAET (auf Modell gekürzt), ENTFERNEN (fällt weg); ein dict ist eine
#: verschachtelte Weißliste, eine Liste ``[dict]`` eine Liste solcher Objekte.
KEEP = "keep"
NULL = "null"
FREITEXT = "freitext"
GERAET = "geraet"
ENTFERNEN = "entfernen"

MARKE_REGELN: dict[str, Any] = {f: KEEP for f in MARKE_FELDER} | {"name": FREITEXT}
EREIGNIS_REGELN: dict[str, Any] = {
    **{f: KEEP for f in ANKER_FELDER},
    "wall_time": KEEP,
    "chart_x": KEEP,  # praxis_gui bis 2026-05
    "text": FREITEXT,
    "uebungen": KEEP,  # Kurzcodes der Übungen
    "marke": MARKE_REGELN,
}
#: raw-v1, corrected-v1 und das Crash-Backup (`recording.Recording.to_dict`,
#: `aufnahme.Aufnahme.backup`); `hrv`/`quality` sind Kennzahlenblöcke alter praxis_gui-Dateien.
RAW_REGELN: dict[str, Any] = {
    "behandlung_id": NULL,
    "patient_id": NULL,
    "datum": KEEP,
    "geraet": GERAET,
    "geraet_profil": KEEP,
    "adresse": NULL,  # BLE-MAC: Pseudo-Identifikator des Geräts
    "intervall_quelle": KEEP,
    "datenqualitaet": KEEP,
    "simulation": KEEP,
    "generator_config": KEEP,
    "schema": KEEP,
    "analyzed": KEEP,
    "start_utc": KEEP,
    "batterie_prozent": KEEP,
    "ecg_aufzeichnung": KEEP,
    "ppg_aufzeichnung": KEEP,
    "ppi_pakete": KEEP,
    "titel": FREITEXT,
    "notiz": FREITEXT,
    "ereignisse": [EREIGNIS_REGELN],
    "messungen": KEEP,
    "hrv": KEEP,
    "quality": KEEP,
    "_wiederherstellung": ENTFERNEN,  # Backup: Profil-ID und Timer-Grenzen der App
}
SEGMENT_REGELN: dict[str, Any] = {
    "id": KEEP,
    "name": FREITEXT,
    "t_start_s": KEEP,
    "t_end_s": KEEP,
    "color": KEEP,
    "metrics": KEEP,
    "computed_utc": KEEP,
    "active": KEEP,
    "visible": KEEP,
}
#: analysis-v1 — was hrv-core schreibt (`korrektur.analyse_speichern`,
#: `ausschnitte.zusatz_speichern`) und die Kennzahlenblöcke, die praxis_gui daneben
#: ablegt (Stand der Fixtures vom 15.10.2026).
ANALYSE_REGELN: dict[str, Any] = {
    "schema": KEEP,
    "source_file": KEEP,
    "source_file_sha1": KEEP,
    "updated_utc": KEEP,
    "corrections": KEEP,
    "corrections_meta": KEEP,
    "corrections_ppi": KEEP,
    "rr_corrected": KEEP,
    "active_crop": KEEP,
    "segments": [SEGMENT_REGELN],
    "metric_selection": KEEP,
    "rolling_rmssd": KEEP,
    "rolling_metrics": KEEP,
    "rolling_window_s": KEEP,
    "rolling_dfa_alpha1": KEEP,
    "frequency_summary": KEEP,
    "nonlinear_summary": KEEP,
    "neurokit2_hrv_rr": KEEP,
    "neurokit2_hrv_ecg": KEEP,
    "ecg_qualitaet": KEEP,
    "ecg_morphologie": KEEP,
}
TRUTH_REGELN: dict[str, Any] = {
    f: KEEP
    for f in (
        "schema",
        "generator_version",
        "scenario",
        "label",
        "seed",
        "duration_s",
        "n_beats_sinus",
        "n_beats_kardial",
        "n_records",
        "sinus",
        "kardial",
        "respiration",
        "events",
        "ecg",
        "battery",
        "index_maps",
    )
}
ECG_REGELN: dict[str, Any] = {
    f: KEEP
    for f in (
        "sample_rate_hz",
        "duration_s",
        "n_samples_expected",
        "n_samples",
        "gaps",
        "uv",
        "frame_offsets",
        "frame_sample_counts",
        # Erweiterungen der trainingsapp (`ekg.py`): Gerätezeit je Rahmen, Wanduhr der
        # ersten Probe, Akkustand im Verlauf — nichts davon ist personenbezogen
        "frame_t_ns",
        "t_wall_start_s",
        "batterie",
    )
}
PPG_REGELN: dict[str, Any] = {
    f: KEEP
    for f in (
        "sample_rate_hz",
        "kanaele",
        "kanal_namen",
        "werte",
        "frame_offsets",
        "frame_sample_counts",
    )
}
TEILNEHMER_REGELN: dict[str, Any] = {
    "geraet": GERAET,
    "adresse": NULL,  # BLE-MAC: Pseudo-Identifikator des Geräts
    "geraet_profil": KEEP,
    "intervall_quelle": KEEP,
    "ordner": KEEP,
    "datei": KEEP,
    "n_schlaege": KEEP,
}
#: sitzung-v1 (praxis_gui Mehrgerätebetrieb, trainingsapp liest nur)
SITZUNG_REGELN: dict[str, Any] = {
    "schema": KEEP,
    "sitzung_id": KEEP,
    "start_utc": KEEP,
    "datum": KEEP,
    "patient_id": NULL,
    "behandlung_id": NULL,
    "titel": FREITEXT,
    "notiz": FREITEXT,
    "teilnehmer": [TEILNEHMER_REGELN],
}
REGELN: dict[str, dict[str, Any]] = {
    "raw-v1": RAW_REGELN,
    "corrected-v1": RAW_REGELN,
    "analysis-v1": ANALYSE_REGELN,
    "truth-v1": TRUTH_REGELN,
    "sitzung-v1": SITZUNG_REGELN,
    "ecg": ECG_REGELN,
    "ppg": PPG_REGELN,
}


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


def geraet_modell(name: Any) -> Any:
    """Gerätename ohne Seriennummer oder BLE-Adresse am Ende.

    Besteht der Name nur aus der Adresse (Gurt ohne Bluetooth-Namen), bleibt
    ``Unbekannt`` — der Gerätetyp ist dann wirklich nicht bekannt.

    >>> geraet_modell("Polar H10 A1B2C3D4"), geraet_modell("Polar Sense 1AB84530")
    ('Polar H10', 'Polar Sense')
    >>> geraet_modell("Polar H10"), geraet_modell("PhysioNet nsr001"), geraet_modell(None)
    ('Polar H10', 'PhysioNet nsr001', None)
    >>> geraet_modell("E2:B4:CC:3F:08:44"), geraet_modell("TICKR E2-B4-CC-3F-08-44")
    ('Unbekannt', 'TICKR')
    >>> geraet_modell("Gurt 12345678-1234-1234-1234-123456789abc")
    'Gurt'
    """
    if not isinstance(name, str):
        return name
    teile = name.split()
    if teile and _ADRESSE.match(teile[-1]):
        teile = teile[:-1]
        return " ".join(teile) or "Unbekannt"
    if len(teile) >= 2 and _SERIENNUMMER.match(teile[-1]):
        return " ".join(teile[:-1])
    return name


def format_erkennen(daten: dict, dateiname: str) -> str | None:
    """Schlüssel in `REGELN` für diese Datei — ``None``, wenn unbekannt.

    >>> format_erkennen({"messungen": []}, "sensor_2026-05-23_125422.json")
    'raw-v1'
    >>> format_erkennen({}, "sensor_2026-05-23_125422_ecg.json")
    'ecg'
    >>> format_erkennen({"schema": "sitzung-v1"}, "sitzung_1.json")
    'sitzung-v1'
    """
    schema = daten.get("schema")
    if isinstance(schema, str) and schema in REGELN:
        return schema
    if dateiname.endswith("_analyzed.json"):
        return "analysis-v1"
    if dateiname.endswith("_truth.json"):
        return "truth-v1"
    if dateiname.endswith("_ecg.json"):
        return "ecg"
    if dateiname.endswith("_ppg.json"):
        return "ppg"
    if "messungen" in daten or dateiname.startswith(("sensor_", ".backup_")):
        return "raw-v1"
    return None


_WEG = object()


def _anwenden(wert: Any, regel: Any, pfad: str, meldungen: list[tuple[str, str]]) -> Any:
    """Weißliste rekursiv anwenden; liefert den bereinigten Wert oder ``_WEG``.

    ``meldungen``: ``(art, pfad)`` mit ``art`` aus ``geleert``, ``gekuerzt``,
    ``freitext``, ``entfernt``, ``unbekannt``, ``falscher_typ``.
    """
    if regel == KEEP:
        return wert
    if regel == NULL:
        if wert not in (None, ""):
            meldungen.append(("geleert", pfad))
        return None
    if regel == FREITEXT:
        if wert:
            meldungen.append(("freitext", pfad))
        return wert
    if regel == GERAET:
        modell = geraet_modell(wert)
        if modell != wert:
            meldungen.append(("gekuerzt", pfad))
        return modell
    if regel == ENTFERNEN:
        meldungen.append(("entfernt", pfad))
        return _WEG
    if wert is None:
        return None
    if isinstance(regel, list):
        if not isinstance(wert, list):
            meldungen.append(("falscher_typ", pfad))
            return _WEG
        out = []
        for i, element in enumerate(wert):
            neu = _anwenden(element, regel[0], f"{pfad}[{i}]", meldungen)
            if neu is not _WEG:
                out.append(neu)
        return out
    if isinstance(regel, dict):
        if not isinstance(wert, dict):
            meldungen.append(("falscher_typ", pfad))
            return _WEG
        out = {}
        for k, v in wert.items():
            unter = f"{pfad}.{k}" if pfad else k
            if k not in regel:
                meldungen.append(("unbekannt", unter))
                continue
            neu = _anwenden(v, regel[k], unter, meldungen)
            if neu is not _WEG:
                out[k] = neu
        return out
    raise ValueError(f"unbekannte Regel {regel!r} für {pfad}")  # pragma: no cover


def deidentifizieren_dict(
    daten: dict, dateiname: str = "sensor_.json"
) -> tuple[dict, list[tuple[str, str]]]:
    """Ein geladenes JSON-Objekt über die Weißliste — ``(bereinigt, meldungen)``.

    >>> neu, m = deidentifizieren_dict({"patient_id": 7, "geraet": "Polar H10 A1B2C3D4",
    ...     "titel": "x", "fremd": 1, "ereignisse": [{"text": "Start", "lat": 52.1}]})
    >>> neu
    {'patient_id': None, 'geraet': 'Polar H10', 'titel': 'x', 'ereignisse': [{'text': 'Start'}]}
    >>> [f"{a}: {p}" for a, p in m]  # doctest: +NORMALIZE_WHITESPACE
    ['geleert: patient_id', 'gekuerzt: geraet', 'freitext: titel', 'unbekannt: fremd',
     'freitext: ereignisse[0].text', 'unbekannt: ereignisse[0].lat']

    Raises:
        ValueError: Format nicht erkannt — nichts wird geraten.
    """
    art = format_erkennen(daten, dateiname)
    if art is None:
        raise ValueError(f"unbekanntes Dateiformat: {dateiname}")
    meldungen: list[tuple[str, str]] = []
    neu = _anwenden(daten, REGELN[art], "", meldungen)
    return neu, meldungen


def _datei_deidentifizieren(quelle: Path, ziel: Path) -> list[tuple[str, str]]:
    """Eine Datei: JSON über die Weißliste neu schreiben, alles andere byteweise kopieren."""
    if quelle.suffix.lower() != ".json":
        shutil.copyfile(quelle, ziel)
        return []
    with open(quelle, encoding="utf-8") as fh:
        daten = json.load(fh)
    if not isinstance(daten, dict):
        raise ValueError(f"kein JSON-Objekt: {quelle.name}")
    neu, meldungen = deidentifizieren_dict(daten, quelle.name)
    with open(ziel, "w", encoding="utf-8") as fh:
        json.dump(neu, fh, ensure_ascii=False, indent=2)
    return meldungen


def deidentifizieren(
    quelle: str | Path,
    zielordner: str | Path,
    *,
    mit_beiwerk: bool = False,
    ueberschreiben: bool = False,
    protokoll: list[tuple[Path, str]] | None = None,
) -> list[Path]:
    """Kopiert ``quelle`` de-identifiziert nach ``zielordner`` und gibt die Zielpfade zurück.

    Das Original bleibt unberührt. Mit ``mit_beiwerk`` kommen die Dateien am
    selben Stamm mit (``_analyzed``, ``_ecg``, ``_ppg``, ``_truth``, ``__cNN``) —
    jede über ihre eigene Weißliste. Ein vorhandenes Ziel wird ohne
    ``ueberschreiben`` nicht angefasst. ``protokoll`` (eine Liste) nimmt je Datei
    auf, was geleert, gekürzt, entfernt oder als Freitext gemeldet wurde — nur
    Feldpfade, nie Inhalte.
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
        meldungen = _datei_deidentifizieren(datei, ziel)
        if protokoll is not None:
            protokoll.extend((ziel, f"{art}: {pfad}") for art, pfad in meldungen)
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


def _datei_pruefen(daten: dict, datei: Path, bericht: Pruefbericht) -> None:
    """Dieselbe Weißliste wie `deidentifizieren_dict`, nur urteilend statt schreibend."""
    art = format_erkennen(daten, datei.name)
    if art is None:
        bericht.ablehnungen.append((datei, "unbekanntes Dateiformat"))
        return
    meldungen: list[tuple[str, str]] = []
    _anwenden(daten, REGELN[art], "", meldungen)
    nach_art: dict[str, list[str]] = {}
    for was, pfad in meldungen:
        nach_art.setdefault(was, []).append(pfad)
    if "geleert" in nach_art:
        bericht.ablehnungen.append(
            (datei, "Personenfeld gefüllt: " + ", ".join(nach_art["geleert"]))
        )
    if "gekuerzt" in nach_art:
        bericht.ablehnungen.append(
            (datei, "Seriennummer oder Adresse im Gerätenamen: " + ", ".join(nach_art["gekuerzt"]))
        )
    if "unbekannt" in nach_art or "falscher_typ" in nach_art:
        felder = nach_art.get("unbekannt", []) + nach_art.get("falscher_typ", [])
        bericht.ablehnungen.append((datei, "unbekanntes Feld: " + ", ".join(felder)))
    if "entfernt" in nach_art:  # Backup-Block: nur mit Personenbezug ein Fehler
        block = daten.get("_wiederherstellung")
        if isinstance(block, dict) and block.get("subject_id") not in (None, ""):
            bericht.ablehnungen.append(
                (datei, "Personenfeld gefüllt: _wiederherstellung.subject_id")
            )
        else:
            bericht.hinweise.append((datei, "Backup-Block vorhanden: _wiederherstellung"))
    if "freitext" in nach_art:
        bericht.hinweise.append((datei, "Freitext vorhanden: " + ", ".join(nach_art["freitext"])))


def pruefen(wurzel: str | Path, *, ordnerregel: bool = True) -> Pruefbericht:
    """Prüft alle JSON-Dateien unter ``wurzel`` (auch ``.backup_*``) und die Personenordner."""
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
            bericht.ablehnungen.append((datei, "kein JSON-Objekt"))
            continue
        _datei_pruefen(daten, datei, bericht)
    return bericht


__all__ = [
    "BEIWERK_SUFFIXE",
    "FREITEXTFELDER",
    "ORDNER_MUSTER",
    "PERSONENFELDER",
    "REGELN",
    "Pruefbericht",
    "beiwerk",
    "deidentifizieren",
    "deidentifizieren_dict",
    "format_erkennen",
    "geraet_modell",
    "pruefen",
    "stamm",
]
