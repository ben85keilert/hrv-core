"""Lesen und Schreiben des Austauschformats `raw-v1`.

Das ist der Kompatibilitätsvertrag mit `praxis_gui` in Code gegossen.
Die maßgebliche Beschreibung steht in `docs/kompatibilitaet.md` — bei
Abweichungen gilt das Dokument, und der Code ist zu korrigieren.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import (
    QUALITAET_BPM_ONLY,
    QUALITAET_PPI_OPTISCH,
    QUALITAET_RR_EKG,
    QUELLE_EKG_RR,
    QUELLE_PPG_PPI,
)

SCHEMA_RAW: str = "raw-v1"

_ZEITFORMAT_UTC = "%Y-%m-%dT%H:%M:%SZ"

# Endungen, die zwar mit `sensor_` beginnen, aber keine Messdateien sind.
_KEINE_MESSDATEI = ("_analyzed.json", "_ecg.json", "_ppg.json", "_truth.json")
_KORRIGIERT_MUSTER = re.compile(r"__c\d+$")

#: Unterordner unter ``Messungen/`` für synthetische Daten (Vertrag, Abschnitt 6).
GENERATOR_ORDNER: str = "Generator"


class FormatFehler(ValueError):
    """Die Datei ist kein lesbares `raw-v1` (oder Backup) — **ein** Fehlertyp für Aufrufer.

    Vorher warfen `laden`/`backup_lesen` je nach Stelle `KeyError`, `TypeError`,
    `ValueError` oder `AttributeError` (Befund F14); ein Backup mit einem kaputten
    Messwert brach so die Wiederherstellung ab. `ValueError` als Basis, damit
    bisherige ``except ValueError`` weiter greifen.
    """


@dataclass(slots=True)
class Beat:
    """Ein Herzschlag, wie ihn `raw-v1` in `messungen[]` ablegt.

    Zwei Zeitachsen, das ist kein Versehen:

    - ``t_s``      Herzuhr — kumulierte gültige RR-Intervalle. Kennt keine Lücken.
    - ``t_wall_s`` Wanduhr — reale Zeit seit Aufnahmestart. Kann negativ sein.

    Die Differenz beider zeigt Verbindungslücken. Ohne ``t_wall_s`` verschwindet
    eine Lücke spurlos und ihre Ränder werden stillschweigend überbrückt.

    ``tw_src`` sagt, woher der Wanduhrwert stammt: ``"m"`` = gemessene
    Paketankunft, ``"r"`` = rückwärts rekonstruiert. Eine BLE-Notification kann
    mehrere RR-Werte enthalten; nur der letzte hat eine echte Ankunftszeit.
    Rekonstruierte Stempel dürfen **nie** als Stützstellen der Spektralanalyse
    dienen.
    """

    t_s: float
    rr_ms: int
    hf_bpm: int = 0
    t_wall_s: float | None = None
    tw_src: str = "m"

    @property
    def hat_rr(self) -> bool:
        """``rr_ms == 0`` heißt: das Paket enthielt keine RR-Intervalle."""
        return self.rr_ms > 0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"t_s": round(self.t_s, 3)}
        if self.t_wall_s is not None:
            d["t_wall_s"] = round(self.t_wall_s, 3)
            d["tw_src"] = self.tw_src
        d["hf_bpm"] = int(self.hf_bpm)
        d["rr_ms"] = int(self.rr_ms)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Beat:
        """Eine Zeile aus ``messungen``; alles Unlesbare ist ein `FormatFehler`.

        >>> Beat.from_dict({"t_s": "x", "rr_ms": 800})
        Traceback (most recent call last):
        ...
        hrv_core.recording.FormatFehler: Messwert unlesbar: {'t_s': 'x', 'rr_ms': 800}
        """
        if not isinstance(d, dict):
            raise FormatFehler(f"Messwert ist kein Objekt: {d!r}")
        try:
            # `corrected-v1` enthält kein t_wall_s — dann bleibt es None statt zu raten.
            tw = d.get("t_wall_s")
            return cls(
                t_s=float(d["t_s"]),
                rr_ms=int(d.get("rr_ms") or 0),
                hf_bpm=int(d.get("hf_bpm") or 0),
                t_wall_s=None if tw is None else float(tw),
                tw_src=str(d.get("tw_src") or "m"),
            )
        except (KeyError, TypeError, ValueError, OverflowError) as fehler:
            raise FormatFehler(f"Messwert unlesbar: {d!r}") from fehler


@dataclass(slots=True, weakref_slot=True)
class Recording:
    """Eine Messung im Format `raw-v1`. ``weakref_slot``: `ppi._gemerkt` merkt sich
    abgeleitete Reihen je Messung, ohne sie am Leben zu halten."""

    beats: list[Beat] = field(default_factory=list)
    geraet: str = "Unbekannt"
    geraet_profil: str = "ble_generic"
    # BLE-Adresse des Geräts (MAC, auf macOS/iOS eine UUID) — getrennt vom Namen, weil
    # ein Gurt ohne Bluetooth-Namen sonst die Adresse als Namen trüge (Ben, 19.10.2026).
    # Pseudo-Identifikator des Geräts: `deid` leert das Feld. None = nicht bekannt.
    adresse: str | None = None
    intervall_quelle: str = QUELLE_EKG_RR
    # None heißt: aus Quelle und tatsächlichem Inhalt ableiten. Eine feste
    # Vorgabe wäre gefährlich — eine Uhr ohne RR-Intervalle würde sonst als
    # `rr_ekg` in die Datei geschrieben und die Messung als hochwertig gelten.
    datenqualitaet: str | None = None
    start_utc: datetime | None = None
    patient_id: int | None = None
    behandlung_id: int | None = None
    batterie_prozent: int | None = None
    ecg_aufzeichnung: bool = False
    simulation: bool = False
    generator_config: dict[str, Any] | None = None
    titel: str = ""
    notiz: str = ""
    ereignisse: list[dict[str, Any]] = field(default_factory=list)
    # Beim Lesen: alles, was wir nicht kennen. Bleibt beim Schreiben erhalten,
    # damit ein Round-Trip keine fremden Felder verliert.
    extra: dict[str, Any] = field(default_factory=dict)
    # Lokales Datum der Messung. None heißt: aus `start_utc` ableiten. Beim Lesen
    # wird es übernommen — kurz nach Mitternacht Ortszeit weicht es vom
    # UTC-Datum ab, und ein Round-Trip darf die Messung nicht umdatieren.
    datum: str | None = None
    ppg_aufzeichnung: bool = False
    # Rohe PPI-Pakete optischer Sensoren (Vertrag, Abschnitt 3b). None heißt:
    # Gerät ohne PPI — dann fehlt der Schlüssel in der Datei, wie bei praxis_gui.
    ppi_pakete: list[dict[str, Any]] | None = None
    # Kopf, wie gelesen (Befund F16): `schema` None heißt Altdatei ohne Schema —
    # ein Round-Trip behauptet dann kein `raw-v1`, das die Datei nie hatte (sie
    # trägt etwa noch den `hrv`-Block). `analyzed` setzt praxis_gui nach der
    # Nachberechnung; wir schreiben zurück, was wir gelesen haben.
    schema: str | None = SCHEMA_RAW
    analyzed: bool = False

    # -- abgeleitet ---------------------------------------------------------

    @property
    def rr_ms(self) -> list[int]:
        """Alle RR-Werte, auch implausible. Filtern macht `hrv_core.segments`."""
        return [b.rr_ms for b in self.beats]

    @property
    def dauer_s(self) -> float:
        return self.beats[-1].t_s if self.beats else 0.0

    @property
    def hat_rr(self) -> bool:
        """Ob überhaupt RR-Intervalle vorliegen — sonst ist keine HRV möglich."""
        return any(b.hat_rr for b in self.beats)

    def effektive_qualitaet(self) -> str:
        """Die Datenqualitätsstufe dieser Aufzeichnung.

        Wurde sie nicht ausdrücklich gesetzt, wird sie aus Intervallquelle und
        tatsächlichem Inhalt abgeleitet. Enthält die Messung keinen einzigen
        RR-Wert, ist sie ``bpm_only`` — unabhängig davon, was das Geräteprofil
        versprochen hat.
        """
        if self.datenqualitaet is not None:
            return self.datenqualitaet
        return _qualitaet_raten(self.intervall_quelle, self.beats)

    def dateiname(self) -> str:
        return messdatei_name(self.start_utc)

    # -- Serialisierung -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Erzeugt das `raw-v1`-Dokument.

        Feldreihenfolge wie im Schreiber von praxis_gui (`_save_recording`);
        unsere Erweiterung `datenqualitaet` steht hinter `intervall_quelle`,
        `ppi_pakete` nur bei Geräten mit PPI vor `titel`. Bewusst **ohne**
        `hrv`- und `quality`-Block: Rohdatei bleibt Rohdatei, die Nachberechnung
        setzt `analyzed` und legt das Sidecar an.

        >>> doc = Recording(geraet="Polar H10").to_dict()
        >>> list(doc)[4:7]
        ['geraet_profil', 'intervall_quelle', 'datenqualitaet']
        >>> list(doc)[-6:]
        ['ecg_aufzeichnung', 'ppg_aufzeichnung', 'titel', 'notiz', 'ereignisse', 'messungen']
        >>> "ppi_pakete" in doc, "adresse" in doc
        (False, False)
        >>> Recording(adresse="E2:B4:CC:3F:08:44").to_dict()["adresse"]
        'E2:B4:CC:3F:08:44'
        >>> "schema" in Recording(schema=None).to_dict()  # Altdatei ohne Schema bleibt ohne
        False
        """
        start = self.start_utc or datetime.now(UTC)
        doc: dict[str, Any] = {
            "behandlung_id": self.behandlung_id,
            "patient_id": self.patient_id,
            # Ortsdatum wie `Aufnahme` und praxis_gui (Vertrag §7), nicht das UTC-Datum
            "datum": self.datum or start.astimezone().strftime("%Y-%m-%d"),
            "geraet": self.geraet,
            "geraet_profil": self.geraet_profil,
            "intervall_quelle": self.intervall_quelle,
            "datenqualitaet": self.effektive_qualitaet(),
            "simulation": bool(self.simulation),
            "generator_config": self.generator_config,
            "schema": self.schema,
            "analyzed": bool(self.analyzed),
            "start_utc": start.strftime(_ZEITFORMAT_UTC),
            "batterie_prozent": self.batterie_prozent,
            "ecg_aufzeichnung": bool(self.ecg_aufzeichnung),
            "ppg_aufzeichnung": bool(self.ppg_aufzeichnung),
        }
        if self.schema is None:
            del doc["schema"]
        if self.ppi_pakete is not None:
            doc["ppi_pakete"] = self.ppi_pakete
        if self.adresse:  # nur wenn bekannt — Dateien ohne Adresse bleiben byteidentisch
            doc["adresse"] = self.adresse
        doc["titel"] = self.titel
        doc["notiz"] = self.notiz
        doc["ereignisse"] = self.ereignisse
        doc["messungen"] = [b.to_dict() for b in self.beats]
        # Unbekannte Felder aus einer gelesenen Datei erhalten, aber nie
        # bekannte überschreiben.
        for k, v in self.extra.items():
            doc.setdefault(k, v)
        return doc

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> Recording:
        """Liest `raw-v1` — und ältere Dateien, die vieles davon nicht haben.

        Defensiv, weil Altdateien weder `schema` noch `intervall_quelle` noch
        `geraet_profil` enthalten (siehe docs/kompatibilitaet.md, Abschnitt 7).

        Raises:
            FormatFehler: ``messungen`` oder ``ereignisse`` sind keine Liste, oder
                ein Messwert ist unlesbar. Eine Liste aus den Zeichen eines Strings
                (Befund F15) wäre Korruption beim nächsten Speichern, kein Lesen.
        """
        bekannt = {
            "behandlung_id",
            "patient_id",
            "datum",
            "geraet",
            "geraet_profil",
            "intervall_quelle",
            "datenqualitaet",
            "simulation",
            "generator_config",
            "schema",
            "analyzed",
            "start_utc",
            "batterie_prozent",
            "ecg_aufzeichnung",
            "ppg_aufzeichnung",
            "ppi_pakete",
            "adresse",
            "titel",
            "notiz",
            "ereignisse",
            "messungen",
        }
        quelle = str(doc.get("intervall_quelle") or QUELLE_EKG_RR)
        messungen = doc.get("messungen") or []
        ereignisse = doc.get("ereignisse") or []
        if not isinstance(messungen, list):
            raise FormatFehler("messungen ist keine Liste")
        if not isinstance(ereignisse, list):
            raise FormatFehler("ereignisse ist keine Liste")
        beats = [Beat.from_dict(m) for m in messungen]

        start_raw = doc.get("start_utc")
        start: datetime | None = None
        if start_raw:
            try:
                start = datetime.strptime(str(start_raw), _ZEITFORMAT_UTC).replace(tzinfo=UTC)
            except ValueError:
                start = None

        return cls(
            beats=beats,
            geraet=str(doc.get("geraet") or "Unbekannt"),
            geraet_profil=str(doc.get("geraet_profil") or "ble_generic"),
            adresse=(str(a) if (a := doc.get("adresse")) else None),
            intervall_quelle=quelle,
            datenqualitaet=(str(d) if (d := doc.get("datenqualitaet")) else None),
            start_utc=start,
            patient_id=doc.get("patient_id"),
            behandlung_id=doc.get("behandlung_id"),
            batterie_prozent=doc.get("batterie_prozent"),
            ecg_aufzeichnung=bool(doc.get("ecg_aufzeichnung")),
            simulation=bool(doc.get("simulation")),
            generator_config=doc.get("generator_config"),
            titel=str(doc.get("titel") or ""),
            notiz=str(doc.get("notiz") or ""),
            ereignisse=list(ereignisse),
            extra={k: v for k, v in doc.items() if k not in bekannt},
            datum=(str(d) if (d := doc.get("datum")) else None),
            ppg_aufzeichnung=bool(doc.get("ppg_aufzeichnung")),
            ppi_pakete=(list(pp) if isinstance(pp := doc.get("ppi_pakete"), list) else None),
            schema=(str(s) if (s := doc.get("schema")) else None),
            analyzed=bool(doc.get("analyzed")),
        )


def _qualitaet_raten(intervall_quelle: str, beats: list[Beat]) -> str:
    """Datenqualitätsstufe für Dateien, die das Feld nicht mitbringen."""
    if not any(b.hat_rr for b in beats):
        return QUALITAET_BPM_ONLY
    return QUALITAET_PPI_OPTISCH if intervall_quelle == QUELLE_PPG_PPI else QUALITAET_RR_EKG


# ---------------------------------------------------------------------------
# Dateizugriff
# ---------------------------------------------------------------------------


def ist_messdatei(pfad: Path | str) -> bool:
    """Ob diese Datei eine Rohmessung ist.

    Der Name entscheidet: `sensor_*.json`, aber keine Analyse-, EKG-, PPG-,
    Wahrheits- oder Korrekturdatei. Crash-Backups (`.backup_*`) und
    Zwischenstände (`*.tmp`) fallen schon durch Präfix bzw. Endung heraus.
    Vertrag: docs/kompatibilitaet.md, Abschnitt 2.

    >>> ist_messdatei("sensor_2026-05-23_125422.json")
    True
    >>> ist_messdatei("sensor_2026-05-23_125422_ppg.json")
    False
    >>> ist_messdatei(".backup_2026-05-23_125422.json")
    False
    """
    name = Path(pfad).name
    if not name.startswith("sensor_") or not name.endswith(".json"):
        return False
    if any(name.endswith(s) for s in _KEINE_MESSDATEI):
        return False
    return not _KORRIGIERT_MUSTER.search(Path(name).stem)


def laden(pfad: Path | str) -> Recording:
    """Liest eine Messdatei.

    Raises:
        FormatFehler: kein JSON, kein Objekt oder unlesbare Messwerte — ein
            Fehlertyp statt vier (Befund F14). ``OSError`` bleibt ``OSError``.
    """
    return Recording.from_dict(json_objekt_lesen(pfad))


def json_objekt_lesen(pfad: Path | str) -> dict[str, Any]:
    """Eine JSON-Datei als Objekt — sonst `FormatFehler`."""
    pfad = Path(pfad)
    with open(pfad, encoding="utf-8") as f:
        try:
            doc = json.load(f)
        except ValueError as fehler:  # JSONDecodeError, auch UnicodeDecodeError-Folgen
            raise FormatFehler(f"{pfad.name} ist kein JSON: {fehler}") from fehler
    if not isinstance(doc, dict):
        raise FormatFehler(f"{pfad.name} ist kein JSON-Objekt")
    return doc


def json_atomar_schreiben(pfad: Path | str, doc: Any, *, kompakt: bool = False) -> Path:
    """Schreibt JSON so, dass nie eine halbe Datei entsteht.

    Erst ``<pfad>.tmp`` vollständig schreiben und auf den Datenträger zwingen,
    dann mit `os.replace` an die Zielstelle tauschen — das ist auf allen
    Plattformen ein atomarer Schritt — und zuletzt den Ordner synchronisieren,
    damit der Rename bei Stromausfall nicht verloren geht (ext4 auf Android,
    Befund F19). Bricht das Schreiben ab, bleibt die alte Datei unverändert und
    der Zwischenstand wird entfernt.

    ``NaN``/``Infinity`` sind kein gültiges JSON (strikte Parser lehnen sie ab,
    Befund F18): ``allow_nan=False`` lässt das Schreiben dann mit ``ValueError``
    scheitern — die alte Datei bleibt.

    Args:
        kompakt: ohne Einrückung (für das 15-s-Backup, das bei langen Messungen
            sonst unnötig groß wird).
    """
    ziel = Path(pfad)
    tmp = ziel.with_name(ziel.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            if kompakt:
                json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            else:
                json.dump(doc, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ziel)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _ordner_fsync(ziel.parent)
    return ziel


def _ordner_fsync(ordner: Path) -> None:
    """Verzeichniseintrag auf den Datenträger zwingen — nur wo das Betriebssystem es kann."""
    if not hasattr(os, "O_DIRECTORY"):  # Windows
        return
    try:
        fd = os.open(ordner, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def messordner(basis: Path | str, geraeteordner: str, *, simulation: bool = False) -> Path:
    """Zielordner einer Messung: ``<basis>/Messungen/<Geräteordner>``.

    Simulationen landen zwingend unter ``Generator`` — sonst könnte Synthetik
    unbemerkt zwischen echten Messungen auftauchen.

    >>> messordner("/daten", "PolarH10").as_posix()
    '/daten/Messungen/PolarH10'
    >>> messordner("/daten", "PolarH10", simulation=True).as_posix()
    '/daten/Messungen/Generator'
    """
    return Path(basis) / "Messungen" / (GENERATOR_ORDNER if simulation else geraeteordner)


def messdatei_name(start_utc: datetime | None) -> str:
    """``sensor_<UTC-Start>.json`` — der Name einer Messdatei, schon während der Aufnahme.

    >>> messdatei_name(datetime(2026, 10, 17, 8, 5, 3, 250000, tzinfo=UTC))
    'sensor_2026-10-17_080503.json'
    """
    ts = (start_utc or datetime.now(UTC)).strftime("%Y-%m-%d_%H%M%S")
    return f"sensor_{ts}.json"


def freier_pfad(ordner: Path | str, dateiname: str) -> Path:
    """Ein Pfad, an dem noch keine Datei liegt: ``name.json``, ``name_1.json``, ``name_2.json`` …

    Wie praxis_gui (`_save_recording`): Zwei Aufnahmen mit derselben
    UTC-Startsekunde im selben Ordner (Simulator, zweiter Start nach einem
    Fehler) überschrieben sonst still die erste (Befund F10). `ist_messdatei`
    erkennt den Zählernamen.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     erster = freier_pfad(d, "sensor_2026-10-19_080000.json")
    ...     erster.write_text("{}")
    ...     freier_pfad(d, "sensor_2026-10-19_080000.json").name
    2
    'sensor_2026-10-19_080000_1.json'
    """
    ordner = Path(ordner)
    pfad = ordner / dateiname
    stamm, endung = os.path.splitext(dateiname)
    zaehler = 1
    while pfad.exists():
        pfad = ordner / f"{stamm}_{zaehler}{endung}"
        zaehler += 1
    return pfad


def speichern(rec: Recording, ordner: Path | str, dateiname: str | None = None) -> Path:
    """Schreibt eine Messung atomar als `raw-v1` und liefert den **tatsächlichen** Pfad.

    Den Ordner bestimmt der Aufrufer — für Simulationen `messordner(...,
    simulation=True)`, sonst könnte Synthetik in einer Patientenakte landen.
    Eine vorhandene Datei wird nie ersetzt: dann hängt ein Zähler an
    (`freier_pfad`), und der Rückgabewert weicht vom vorab bekannten Namen ab.
    Ohne ``start_utc`` wird die Startzeit einmal gezogen, damit Dateiname und
    Kopf dieselbe Sekunde tragen (Befund F17).
    """
    if rec.start_utc is None:
        rec = replace(rec, start_utc=datetime.now(UTC))
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    return json_atomar_schreiben(freier_pfad(ordner, dateiname or rec.dateiname()), rec.to_dict())


__all__ = [
    "GENERATOR_ORDNER",
    "SCHEMA_RAW",
    "Beat",
    "FormatFehler",
    "Recording",
    "freier_pfad",
    "ist_messdatei",
    "json_atomar_schreiben",
    "json_objekt_lesen",
    "laden",
    "messdatei_name",
    "messordner",
    "speichern",
]
