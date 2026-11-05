"""De-Identifizierung von Messdateien und Prüfung des Testdatenordners.

Zwei Aufgaben, beide ohne Personenbezug im Code:

``deidentifizieren(quelle, zielordner)``
    kopiert eine Messdatei (``raw-v1``, Backup, ``corrected-v1``, Sidecar
    ``analysis-v1``, ``truth-v1``, ``sitzung-v1``, ``atem-v1``, EKG/PPG-Rohdaten) über eine
    **Weißliste je Feld** (`REGELN`): Personenfelder werden ``null``
    (``patient_id``, ``behandlung_id``, ``subject_id``, BLE-``adresse``), der
    Gerätename auf das Modell gekürzt (``"Polar H10 ABC123"`` → ``"Polar H10"``,
    die Seriennummer wäre ein Pseudo-Identifikator über Dateien hinweg), Freitext
    bleibt und wird gemeldet, die Backup-Felder ``_wiederherstellung`` und ``_journal``
    (nur in ``.backup_*``-Köpfen, `aufnahme`) fallen weg —
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

``mitschnitt_deidentifizieren(quelle, ziel)``
    dasselbe Zeile für Zeile für den Rohmitschnitt ``mitschnitt-v1``
    (`MITSCHNITT_REGELN`, `hrv_core.mitschnitt`): Adressen maskiert
    (`adressen_maskieren`, der Herstellerteil bleibt), der Gerätename auf das Modell
    gekürzt — auch in den Protokollzeilen —, Zeilen der Merkmale mit einer Kennung des
    Geräts (Gerätename, Systemkennung, Seriennummer) fallen weg, unbekannte Arten und
    Felder ebenso.

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

from . import mitschnitt
from .ereignisse import ANKER_FELDER, MARKE_FELDER

PERSONENFELDER = ("patient_id", "behandlung_id", "subject_id", "adresse")
FREITEXTFELDER = ("titel", "notiz")
BEIWERK_SUFFIXE = (
    "_analyzed.json",
    "_ecg.json",
    "_ppg.json",
    "_truth.json",
    "_atem.json",  # `hrv_core.atem` (`atem-v1`)
    mitschnitt.ENDUNG,
)
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
#: Dieselben Formen irgendwo im Text (wie ``trainingsapp.core.hrv_export.ADRESSE_MUSTER``):
#: die Ränder verlangen ein Nicht-Hex-Zeichen, damit Uhrzeiten (``08:15:00``) und Datumsangaben
#: nie anschlagen. Die Merkmals-UUIDs von Bluetooth (``0000180d-0000-1000-8000-00805f9b34fb``)
#: haben dieselbe Form — sie bleiben (`_BT_BASIS`).
ADRESSE_IM_TEXT = re.compile(
    r"(?<![0-9A-Fa-f:-])(?:"
    r"(?P<mac>(?:[0-9A-Fa-f]{2}[:-]){3})(?:[0-9A-Fa-f]{2}[:-]){2}[0-9A-Fa-f]{2}"
    r"|(?P<uuid>[0-9A-Fa-f]{8})-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
    r")(?![0-9A-Fa-f:-])"
)
#: Endung der Bluetooth-Basis-UUID: ``0000xxxx-0000-1000-8000-00805f9b34fb`` ist ein Dienst
#: oder Merkmal, keine Geräteadresse; herstellereigene Dienste (Polar PMD ``fb005c80-…``)
#: stehen in `_DIENSTE`.
_BT_BASIS = "-0000-1000-8000-00805f9b34fb"
_DIENSTE = frozenset(
    u.lower()
    for u in (
        "fb005c80-02e7-f387-1cad-8acd2d8df0c8",
        "fb005c81-02e7-f387-1cad-8acd2d8df0c8",
        "fb005c82-02e7-f387-1cad-8acd2d8df0c8",
    )
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
ADRESSE = "adresse"  # Adressen im Wert maskiert, der Herstellerteil bleibt
PROTOKOLL = "protokoll"  # Protokolltext der App: Adressen maskiert, nicht gemeldet

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
    # Protokollfeld „Atmung“ der trainingsapp (P125): `art` (spontan/getaktet/uebung),
    # `takt_pro_min`, `uebung` (Kurzcode) — als Ganzes, nichts davon ist personenbezogen
    "atmung": KEEP,
    "titel": FREITEXT,
    "notiz": FREITEXT,
    "ereignisse": [EREIGNIS_REGELN],
    "messungen": KEEP,
    "hrv": KEEP,
    "quality": KEEP,
    "_wiederherstellung": ENTFERNEN,  # Backup: Profil-ID und Timer-Grenzen der App
    "_journal": ENTFERNEN,  # Backup: Name des Journals (`aufnahme.JOURNAL`), seit 0.9.2
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
#: atem-v1 (`hrv_core.atem`): Ergebnis der Atemerfassung — Läufe, Phasen, Fenster auf der
#: Wanduhr; `geraet` ist die Profil-ID (``polar_h10``), nie Name oder Adresse. Alles bleibt.
ATEM_REGELN: dict[str, Any] = {
    f: KEEP
    for f in (
        "schema",
        "art",
        "prototyp",
        "hrv_core",
        "quelle",
        "geraet",
        "rate_hz",
        "erfasst",
        "phasen",
        "fenster",
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
    "atem-v1": ATEM_REGELN,
}


#: ``mitschnitt-v1`` (`hrv_core.mitschnitt`) — eine Weißliste je Art der Zeile. Zeilen einer
#: unbekannten Art fallen ganz weg; ``c`` aus `mitschnitt.KENNUNGS_MERKMALE` ebenso.
_ZEIT = {"art": KEEP, "t": KEEP}
MITSCHNITT_REGELN: dict[str, dict[str, Any]] = {
    mitschnitt.KOPF: {
        **_ZEIT,
        "format": KEEP,
        "app": KEEP,
        "version": KEEP,
        "plattform": KEEP,
        "start_utc": KEEP,
        "wall_ns": KEEP,
        "messdatei": KEEP,
        # Nullpunkt der Aufnahme auf der Uhr der Zeilen: t_wall_s = (t − start_mono_ns) / 1e9
        "aufnahme": {"start_mono_ns": KEEP, "start_utc": KEEP},
        "geraet": {
            "name": GERAET,
            "id": ADRESSE,
            "profil": KEEP,
            "art": KEEP,
            "info": KEEP,  # Hersteller, Modell, Firmware … — nie die Seriennummer
        },
        "stroeme": KEEP,
        "dienste": KEEP,
        "marken": KEEP,
    },
    mitschnitt.N: {**_ZEIT, "c": KEEP, "x": KEEP, "s": KEEP, "tm": KEEP, "tw": KEEP},
    mitschnitt.W: {**_ZEIT, "c": KEEP, "x": KEEP, "a": KEEP},
    mitschnitt.R: {**_ZEIT, "c": KEEP, "x": KEEP, "fehler": PROTOKOLL},
    mitschnitt.V: {
        **_ZEIT,
        "text": PROTOKOLL,
        "q": KEEP,
        "zustand": KEEP,
        "grund": PROTOKOLL,
        "code": KEEP,
    },
    mitschnitt.UHR: {**_ZEIT, "utc": KEEP, "wall_ns": KEEP},
    mitschnitt.PROBE: {
        **_ZEIT,
        "akku": KEEP,
        "akku_handy": KEEP,
        "laedt": KEEP,
        "bildschirm": KEEP,
        "verzug_ms": KEEP,
        "verzug_spitze_ms": KEEP,
        "pakete": KEEP,
        "mb": KEEP,
    },
    mitschnitt.MARKE: {
        **_ZEIT,
        "id": KEEP,
        "typ": KEEP,
        "quelle": KEEP,
        "nr": KEEP,
        "tm": KEEP,
        "kontext": {
            "uebung": FREITEXT,
            "uebung_id": KEEP,
            "satz": KEEP,
            "phase": KEEP,
            "feld": KEEP,
        },
    },
    mitschnitt.MARKE_WEG: {**_ZEIT, "id": KEEP, "quelle": KEEP},
    mitschnitt.KONTEXT: {
        **_ZEIT,
        "was": KEEP,
        "uebung": FREITEXT,
        "uebung_id": KEEP,
        "satz": KEEP,
        "feld": KEEP,
        "wert": KEEP,
        "abschnitt": FREITEXT,
        "dauer_s": KEEP,
        "phase": KEEP,
        "art_marke": KEEP,
        # wie die Marke im Ereignis der Messdatei (Vertrag §4): Plan, Runde, Timer-Profil
        "plan": FREITEXT,
        "runde": KEEP,
        "von": KEEP,
        "profil": KEEP,
        "soll_s": KEEP,
    },
}


def adressen_maskieren(text: str) -> str:
    """Alle BLE-Adressen im Text unkenntlich machen — wie die trainingsapp beim Teilen.

    Von einer MAC bleiben die ersten drei Oktette (der Herstellerteil), von einer UUID die
    ersten acht Zeichen. Dienst- und Merkmals-UUIDs von Bluetooth bleiben stehen.

    >>> adressen_maskieren("Polar H10 [E2:B4:CC:3F:08:44] um 08:15:00")
    'Polar H10 [E2:B4:CC:xx:xx:xx] um 08:15:00'
    >>> adressen_maskieren("0F1E2D3C-4B5A-6978-8796-A5B4C3D2E1F0 und "
    ...                    "0000180d-0000-1000-8000-00805f9b34fb")
    '0F1E2D3C-xxxx-xxxx-xxxx-xxxxxxxxxxxx und 0000180d-0000-1000-8000-00805f9b34fb'
    """

    def ersetzen(treffer: re.Match[str]) -> str:
        mac = treffer.group("mac")
        if mac:
            trenner = mac[2]
            return mac + trenner.join(("xx", "xx", "xx"))
        ganz = treffer.group(0).lower()
        if ganz.endswith(_BT_BASIS) or ganz in _DIENSTE:
            return treffer.group(0)
        return treffer.group("uuid") + "-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

    return ADRESSE_IM_TEXT.sub(ersetzen, text)


def stamm(pfad: Path) -> str:
    """Gemeinsamer Namensstamm einer Messdatei und ihres Beiwerks.

    >>> stamm(Path("sensor_2026-05-23_125422_analyzed.json"))
    'sensor_2026-05-23_125422'
    >>> stamm(Path("sensor_2026-05-23_125422__c01.json"))
    'sensor_2026-05-23_125422'
    >>> stamm(Path("sensor_2026-05-23_125422_mitschnitt.jsonl"))
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
    >>> format_erkennen({"schema": "atem-v1"}, "x.json"), format_erkennen({}, "sensor_1_atem.json")
    ('atem-v1', 'atem-v1')
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
    if dateiname.endswith("_atem.json"):
        return "atem-v1"
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
    if regel in (ADRESSE, PROTOKOLL):
        if not isinstance(wert, str):
            return wert
        neu = adressen_maskieren(wert)
        if neu != wert:
            meldungen.append(("maskiert", pfad))
        return neu
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
    """Eine Datei: JSON über die Weißliste neu schreiben, den Mitschnitt Zeile für Zeile,
    alles andere byteweise kopieren."""
    if mitschnitt.ist_mitschnitt(quelle):
        return mitschnitt_deidentifizieren(quelle, ziel)
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


def _merkmal(c: Any) -> str:
    return mitschnitt.uuid_von(str(c)) if isinstance(c, str) else ""


def mitschnitt_zeilen(zeilen: Any, meldungen: list[tuple[str, str]] | None = None) -> Any:
    """Zeilen eines Mitschnitts über die Weißliste — ein Generator, Zeile für Zeile.

    ``meldungen`` nimmt ``(art, pfad)`` auf, je Pfad (``n.c``, ``v.text`` …) einmal. Der volle
    Gerätename aus dem Kopf wird überall durch das Modell ersetzt; der Kopf muss dafür vorn
    stehen (wie ihn `mitschnitt.Schreiber` schreibt).

    >>> m = []
    >>> list(mitschnitt_zeilen([
    ...     {"art": "kopf", "t": 0,
    ...      "geraet": {"name": "Polar H10 A1B2C3D4", "id": "E2:B4:CC:3F:08:44"}},
    ...     {"art": "v", "t": 1, "text": "Verbinde mit Polar H10 A1B2C3D4 [E2:B4:CC:3F:08:44]"},
    ...     {"art": "r", "t": 2, "c": "00002a25-0000-1000-8000-00805f9b34fb", "x": "41"},
    ...     {"art": "gps", "t": 3, "lat": 52.1}], m))  # doctest: +NORMALIZE_WHITESPACE
    [{'art': 'kopf', 't': 0, 'geraet': {'name': 'Polar H10', 'id': 'E2:B4:CC:xx:xx:xx'}},
     {'art': 'v', 't': 1, 'text': 'Verbinde mit Polar H10 [E2:B4:CC:xx:xx:xx]'}]
    >>> sorted({a for a, _ in m})
    ['entfernt', 'gekuerzt', 'maskiert', 'unbekannt']
    """
    gesehen: set[tuple[str, str]] = set()
    sammel: list[tuple[str, str]] = []
    name_voll: str | None = None
    name_kurz: str | None = None
    for zeile in zeilen:
        sammel.clear()
        art = zeile.get("art") if isinstance(zeile, dict) else None
        regel = MITSCHNITT_REGELN.get(art) if isinstance(art, str) else None
        if regel is None:
            sammel.append(("unbekannt", str(art)))
            neu: Any = _WEG
        elif art in (mitschnitt.N, mitschnitt.R, mitschnitt.W) and (
            _merkmal(zeile.get("c")) in mitschnitt.KENNUNGS_MERKMALE
        ):
            sammel.append(("entfernt", f"{art}.c"))
            neu = _WEG
        else:
            if art == mitschnitt.KOPF:
                geraet = zeile.get("geraet")
                name = geraet.get("name") if isinstance(geraet, dict) else None
                if isinstance(name, str):
                    kurz = geraet_modell(name)
                    if kurz != name:
                        name_voll, name_kurz = name, str(kurz)
            neu = _anwenden(zeile, regel, str(art), sammel)
            if name_voll and name_kurz and isinstance(neu, dict):
                for feld in ("text", "grund", "fehler"):
                    wert = neu.get(feld)
                    if isinstance(wert, str) and name_voll in wert:
                        neu[feld] = wert.replace(name_voll, name_kurz)
                        sammel.append(("gekuerzt", f"{art}.{feld}"))
        if meldungen is not None:
            for eintrag in sammel:
                if eintrag not in gesehen:
                    gesehen.add(eintrag)
                    meldungen.append(eintrag)
        if neu is not _WEG:
            yield neu


def mitschnitt_deidentifizieren(quelle: Path | str, ziel: Path | str) -> list[tuple[str, str]]:
    """Einen Mitschnitt de-identifiziert nach ``ziel`` schreiben — die Meldungen zurück."""
    meldungen: list[tuple[str, str]] = []
    with open(ziel, "w", encoding="utf-8") as fh:
        for zeile in mitschnitt_zeilen(mitschnitt.lesen(quelle), meldungen):
            fh.write(json.dumps(zeile, ensure_ascii=False, separators=(",", ":")) + "\n")
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
    _urteilen(meldungen, daten, datei, bericht)


def _mitschnitt_pruefen(datei: Path, bericht: Pruefbericht) -> None:
    """Ein Mitschnitt über `mitschnitt_zeilen`, nur urteilend: maskierte Adressen,
    gekürzte Namen und entfernte Zeilen hießen, dass die Datei nicht bereinigt ist."""
    meldungen: list[tuple[str, str]] = []
    try:
        for _ in mitschnitt_zeilen(mitschnitt.lesen(datei), meldungen):
            pass
    except OSError:
        bericht.ablehnungen.append((datei, "nicht lesbar"))
        return
    nach_art: dict[str, list[str]] = {}
    for was, pfad in meldungen:
        nach_art.setdefault(was, []).append(pfad)
    if "maskiert" in nach_art:
        bericht.ablehnungen.append(
            (datei, "Adresse unmaskiert: " + ", ".join(nach_art["maskiert"]))
        )
    if "entfernt" in nach_art:
        bericht.ablehnungen.append(
            (
                datei,
                "Kennung des Geräts (Name, Systemkennung, Seriennummer): "
                + ", ".join(nach_art["entfernt"]),
            )
        )
    _urteilen([m for m in meldungen if m[0] not in ("maskiert", "entfernt")], {}, datei, bericht)


def _urteilen(
    meldungen: list[tuple[str, str]], daten: dict, datei: Path, bericht: Pruefbericht
) -> None:
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
    if "entfernt" in nach_art:  # Backup-Felder: nur mit Personenbezug ein Fehler
        block = daten.get("_wiederherstellung")
        if isinstance(block, dict) and block.get("subject_id") not in (None, ""):
            bericht.ablehnungen.append(
                (datei, "Personenfeld gefüllt: _wiederherstellung.subject_id")
            )
        else:
            bericht.hinweise.append(
                (datei, "Backup-Felder vorhanden: " + ", ".join(nach_art["entfernt"]))
            )
    if "freitext" in nach_art:
        bericht.hinweise.append((datei, "Freitext vorhanden: " + ", ".join(nach_art["freitext"])))


def pruefen(wurzel: str | Path, *, ordnerregel: bool = True) -> Pruefbericht:
    """Prüft alle JSON-Dateien unter ``wurzel`` (auch ``.backup_*``), die Mitschnitte
    (``*_mitschnitt.jsonl``, ``mitschnitt.jsonl``) und die Personenordner."""
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
    for datei in sorted(wurzel.rglob("*.jsonl")):
        if mitschnitt.ist_mitschnitt(datei):
            bericht.geprueft += 1
            _mitschnitt_pruefen(datei, bericht)
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
    "ADRESSE_IM_TEXT",
    "BEIWERK_SUFFIXE",
    "FREITEXTFELDER",
    "MITSCHNITT_REGELN",
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
