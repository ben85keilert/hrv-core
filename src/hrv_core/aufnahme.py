"""Eine laufende Aufnahme: aus Einzelschlägen wird eine `raw-v1`-Datei.

Hier stehen die Schreibregeln, die praxis_gui beim Aufzeichnen anwendet
(`widget.py`, `_on_hr_received`) — als eigene Klasse, damit sie ohne Gerät und
ohne Oberfläche prüfbar sind. Vertrag: docs/kompatibilitaet.md, Abschnitt 3a/3b
und 6a.

Was die Klasse **nicht** tut: Bluetooth-Pakete zerlegen. Die Geräteschicht
liefert schon Einzelschläge mit Empfangszeit (``t_capture``) und Herkunft
(``tw_src``). Sie arbeitet nur mit Primitiven, damit `hrv_core` nichts aus
`devices` importieren muss.

Ablauf::

    aufnahme = Aufnahme(geraet="Polar H10 A1B2", geraet_profil="polar_h10",
                        intervall_quelle="ekg_rr", start_mono=time.monotonic(),
                        start_utc=datetime.now(UTC))
    aufnahme.schlag(rr_ms=812, hf_bpm=74, t_capture=..., tw_src="m")
    aufnahme.backup(ordner)          # alle 15 s
    aufnahme.speichern(ordner)       # beim Stopp — löscht das Backup

Bleibt ein Backup liegen (Akku leer, Absturz), findet `backups_finden` es beim
nächsten Start und `backup_lesen` macht daraus wieder ein `Recording` — die
Wiederherstellung selbst (Messdatei schreiben, Eintrag anlegen) macht
`devices.messlauf.backup_wiederherstellen`.

**Backup als Journal** (Ben, 28.10.2026, lange Aufnahmen): Das Backup besteht aus dem
**Kopf** ``.backup_<Start>.json`` (die Datei ohne ``messungen`` und ``ppi_pakete``, dazu
``_wiederherstellung`` und ``_journal``) und dem **Journal** ``.backup_<Start>.jsonl``, an
das jeder Aufruf nur die neuen Schläge und PPI-Pakete anhängt. Der Kopf wird nur neu
geschrieben, wenn sich darin etwas ändert (Titel, Notizen). So kostet ein Backup nach
36 Stunden dasselbe wie nach einer Minute — vorher wurde alle 15 s die ganze Datei
(11 MB bei 36 h) neu geschrieben. `backup_lesen` setzt beides zusammen und liest auch
ältere Backups, die die Schläge noch im Kopf tragen.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import AUFNAHME_RR_MAX_MS, AUFNAHME_RR_MIN_MS
from .recording import (
    Beat,
    FormatFehler,
    Recording,
    freier_pfad,
    json_atomar_schreiben,
    json_objekt_lesen,
    messdatei_name,
)

_TW_SRC = ("m", "r", "g")

#: Dateimuster des Crash-Backups (Vertrag, Abschnitt 6a)
BACKUP_MUSTER = ".backup_*.json"
#: Feld im Kopf: der Name des Journals neben ihm (nur im Backup, nie in der Messdatei)
JOURNAL = "_journal"
#: Block, den nur das Backup trägt — was die App zum Wiederherstellen braucht
#: (Profil, Abschnittsgrenzen des Timers) und was in keine Messdatei gehört.
WIEDERHERSTELLUNG = "_wiederherstellung"


class Aufnahme:
    """Sammelt die Schläge einer Aufnahme und schreibt sie als `raw-v1`.

    Args:
        geraet: Anzeigename, i. d. R. der BLE-Gerätename.
        geraet_profil: Profil-ID (``polar_h10``, ``verity_sense`` …).
        adresse: BLE-Adresse des Geräts, getrennt vom Namen (``deid`` leert sie).
        intervall_quelle: ``ekg_rr`` oder ``ppg_ppi``.
        start_mono: Nullpunkt der Wanduhr — derselbe Uhrtyp wie ``t_capture``
            (``time.monotonic()``), nie ``datetime.now()``.
        start_utc: Aufnahmestart als Datum/Uhrzeit (Kopf und Dateiname).
        ppi: Gerät liefert PPI-Pakete (Verity Sense) — dann trägt die Datei
            ``ppi_pakete``, auch wenn keines ankam.
        simulation: synthetische Daten. Die Datei bekommt ``simulation: true``;
            den Ordner ``Messungen/Generator`` wählt der Aufrufer
            (`recording.messordner`).

    Öffentliche Attribute, die der Aufrufer während der Aufnahme setzen darf:
    ``titel``, ``notiz``, ``batterie_prozent``, ``patient_id``,
    ``behandlung_id``.

    >>> from datetime import UTC, datetime
    >>> a = Aufnahme(geraet="H10", geraet_profil="polar_h10", intervall_quelle="ekg_rr",
    ...              start_mono=100.0, start_utc=datetime(2026, 10, 12, 8, 0, tzinfo=UTC))
    >>> a.schlag(800, 75, 100.8, "m").t_s
    0.8
    >>> a.schlag(0, 75, 101.8, "m").t_s          # Paket ohne RR: Herzuhr steht
    0.8
    >>> a.schlag(2400, 75, 104.2, "m").t_s       # implausibel: Zeile ja, Herzuhr nein
    0.8
    >>> [b.rr_ms for b in a.beats]
    [800, 0, 2400]
    """

    def __init__(
        self,
        *,
        geraet: str,
        geraet_profil: str,
        intervall_quelle: str,
        start_mono: float,
        start_utc: datetime,
        ppi: bool = False,
        simulation: bool = False,
        adresse: str | None = None,
    ) -> None:
        if start_utc.tzinfo is None:
            raise ValueError("start_utc braucht eine Zeitzone (UTC)")
        self.geraet = geraet
        self.geraet_profil = geraet_profil
        self.adresse = adresse
        self.intervall_quelle = intervall_quelle
        self.start_mono = float(start_mono)
        self.start_utc = start_utc.astimezone(UTC)
        self.simulation = bool(simulation)
        self.titel = ""
        self.notiz = ""
        self.batterie_prozent: int | None = None
        self.patient_id: int | None = None
        self.behandlung_id: int | None = None
        # Lokales Datum wie bei praxis_gui (`datetime.now()`), nicht das UTC-Datum.
        self.datum = self.start_utc.astimezone().strftime("%Y-%m-%d")

        #: Notizen während der Aufnahme (`hrv_core.ereignisse`), Anker auf `beats`
        self.ereignisse: list[dict[str, Any]] = []

        self._ppi = bool(ppi)
        self._beats: list[Beat] = []
        self._ppi_pakete: list[dict[str, Any]] = []
        self._herz_ms = 0  # ganze Millisekunden, wie praxis_gui
        self._backup_pfade: set[Path] = set()
        #: Was der Kopf des Backups zuletzt enthielt — neu geschrieben nur bei Änderung
        self._kopf_stand: str | None = None
        #: Bis wohin Schläge und PPI-Pakete im Journal stehen — und in welchem
        self._journal_beats = 0
        self._journal_ppi = 0
        self._journal_pfad: Path | None = None

    # -- Erfassen -----------------------------------------------------------

    def schlag(self, rr_ms: int, hf_bpm: int, t_capture: float, tw_src: str) -> Beat:
        """Hängt einen Schlag an und liefert die geschriebene Zeile.

        Die Zeile wird **immer** angehängt, mit dem Rohwert — auch ``rr_ms = 0``
        (Paket ohne RR) und implausible Werte. Die Herzuhr ``t_s`` wächst nur
        bei ``300 ≤ rr_ms ≤ 2000``; ``t_wall_s = round(t_capture − start_mono, 3)``.
        """
        if tw_src not in _TW_SRC:
            raise ValueError(f"tw_src muss eines von {_TW_SRC} sein, nicht {tw_src!r}")
        rr = int(rr_ms)
        if AUFNAHME_RR_MIN_MS <= rr <= AUFNAHME_RR_MAX_MS:
            self._herz_ms += rr
        beat = Beat(
            t_s=round(self._herz_ms / 1000.0, 3),
            rr_ms=rr,
            hf_bpm=int(hf_bpm),
            t_wall_s=round(float(t_capture) - self.start_mono, 3),
            tw_src=tw_src,
        )
        self._beats.append(beat)
        return beat

    def ppi_paket(
        self,
        t_capture: float,
        ppi_ms: Iterable[int],
        fehler_ms: Iterable[int],
        blocker: Iterable[int | bool],
        kontakt: Iterable[int | bool],
    ) -> None:
        """Ein PPI-Paket roh mitschreiben (Vertrag, Abschnitt 3b).

        Kommt ein Paket an, obwohl die Aufnahme ohne ``ppi=True`` angelegt
        wurde, schaltet sie auf PPI um — Rohdaten zu verwerfen wäre schlimmer
        als ein unerwarteter Schlüssel.
        """
        spalten = {
            "ppi_ms": [int(x) for x in ppi_ms],
            "fehler_ms": [int(x) for x in fehler_ms],
            "blocker": [1 if x else 0 for x in blocker],
            "kontakt": [1 if x else 0 for x in kontakt],
        }
        laengen = {len(v) for v in spalten.values()}
        if len(laengen) != 1:
            raise ValueError(f"PPI-Spalten unterschiedlich lang: {laengen}")
        self._ppi = True
        self._ppi_pakete.append(
            {"t_wall_s": round(float(t_capture) - self.start_mono, 3), **spalten}
        )

    # -- Abfragen -----------------------------------------------------------

    @property
    def beats(self) -> list[Beat]:
        """Die bisher geschriebenen Zeilen (Kopie)."""
        return list(self._beats)

    @property
    def ppi(self) -> bool:
        return self._ppi

    def dauer_s(self) -> float:
        """Wanduhrzeit vom Start bis zum letzten Schlag."""
        if not self._beats or self._beats[-1].t_wall_s is None:
            return 0.0
        return max(0.0, float(self._beats[-1].t_wall_s))

    def recording(self, *, titel: str = "", notiz: str = "") -> Recording:
        """Der aktuelle Stand als `Recording` (für Backup, Speichern, Anzeige).

        Ohne Argument gelten die Attribute ``titel``/``notiz``.
        """
        return Recording(
            beats=list(self._beats),
            geraet=self.geraet,
            geraet_profil=self.geraet_profil,
            adresse=self.adresse,
            intervall_quelle=self.intervall_quelle,
            start_utc=self.start_utc,
            patient_id=self.patient_id,
            behandlung_id=self.behandlung_id,
            batterie_prozent=self.batterie_prozent,
            simulation=self.simulation,
            titel=titel or self.titel,
            notiz=notiz or self.notiz,
            ereignisse=[dict(e) for e in self.ereignisse],
            datum=self.datum,
            ppg_aufzeichnung=False,
            ppi_pakete=[dict(p) for p in self._ppi_pakete] if self._ppi else None,
        )

    # -- Schreiben ----------------------------------------------------------

    def backup_name(self) -> str:
        """``.backup_<UTC-Start>.json`` — wie praxis_gui (`_start_backup`)."""
        return f".backup_{self.start_utc.strftime('%Y-%m-%d_%H%M%S')}.json"

    def journal_name(self) -> str:
        """``.backup_<UTC-Start>.jsonl`` — das Journal neben dem Kopf."""
        return self.backup_name() + "l"

    def dateiname(self) -> str:
        """Name der Messdatei, die `speichern` schreiben wird — schon während der Aufnahme
        (für Verweise, etwa eine Einheit der App, die über den Dateinamen verknüpft).

        Liegt beim Speichern schon eine Datei dieses Namens, bekommt die neue einen
        Zähler (``_1``, `recording.freier_pfad`) — maßgeblich ist der Pfad, den
        `speichern` zurückgibt.
        """
        return messdatei_name(self.start_utc)

    def backup(self, ordner: Path, *, zusatz: Mapping[str, Any] | None = None) -> Path:
        """Crash-Sicherung als Kopf und Journal (Vertrag, Abschnitt 6a; Modulkopf).

        Gedacht für einen 15-s-Takt. Der Punkt am Anfang hält die Dateien aus
        jeder Messungsliste heraus. ``zusatz`` steht im Kopf als Block
        ``_wiederherstellung`` — nur im Backup, nie in der Messdatei
        (`backup_lesen` nimmt ihn wieder heraus). Der Kopf wird atomar und nur
        bei Änderung geschrieben; ans Journal kommen die neuen Zeilen, jede für
        sich abgeschlossen. Gibt den Pfad des Kopfs zurück.
        """
        ordner = Path(ordner)
        ordner.mkdir(parents=True, exist_ok=True)
        doc = self.recording().to_dict()
        doc.pop("messungen", None)
        if self._ppi:
            doc["ppi_pakete"] = []  # der Schlüssel bleibt, die Pakete stehen im Journal
        if zusatz:
            doc[WIEDERHERSTELLUNG] = dict(zusatz)
        doc[JOURNAL] = self.journal_name()
        kopf_stand = json.dumps(doc, ensure_ascii=False, sort_keys=True, allow_nan=False)
        pfad = ordner / self.backup_name()
        if kopf_stand != self._kopf_stand or not pfad.exists():
            json_atomar_schreiben(pfad, doc, kompakt=True)
            self._kopf_stand = kopf_stand
        journal = ordner / self.journal_name()
        self._journal_anhaengen(journal)
        self._backup_pfade.update({pfad, journal})
        return pfad

    def _journal_anhaengen(self, pfad: Path) -> None:
        """Neue Schläge und PPI-Pakete ans Journal — eine Zeile je Eintrag, zuletzt fsync.

        Endet die Datei nicht mit einem Zeilenumbruch (ein Schreiben brach ab), beginnt
        der Anhang mit einem: Die halbe Zeile bleibt unlesbar und wird beim Lesen
        übersprungen, die Zähler rücken erst nach dem Schreiben vor.
        """
        if pfad != self._journal_pfad or not pfad.exists():
            # Ein anderer Ordner oder ein verschwundenes Journal: alles noch einmal
            self._journal_pfad = pfad
            self._journal_beats = self._journal_ppi = 0
        neue_beats = self._beats[self._journal_beats :]
        neue_ppi = self._ppi_pakete[self._journal_ppi :]
        if not neue_beats and not neue_ppi:
            return
        halb = False
        if pfad.exists() and pfad.stat().st_size:
            with open(pfad, "rb") as f:
                f.seek(-1, os.SEEK_END)
                halb = f.read(1) != b"\n"
        with open(pfad, "a", encoding="utf-8") as f:
            if halb:
                f.write("\n")
            for b in neue_beats:
                json.dump(
                    ["b", b.to_dict()],
                    f,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                f.write("\n")
            for p in neue_ppi:
                json.dump(["p", p], f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        self._journal_beats = len(self._beats)
        self._journal_ppi = len(self._ppi_pakete)

    def speichern(self, ordner: Path) -> Path:
        """Schreibt die Messdatei atomar und löscht danach das Backup.

        Eine vorhandene Datei gleichen Namens wird nie ersetzt — dann hängt ein
        Zähler an (`recording.freier_pfad`, wie praxis_gui); der Rückgabewert ist
        der tatsächliche Pfad.

        Raises:
            ValueError: Es wurde kein einziger Schlag aufgezeichnet — wie
                praxis_gui („Keine Daten zum Speichern") entsteht dann keine Datei.
        """
        if not self._beats:
            raise ValueError("Keine Daten zum Speichern")
        ordner = Path(ordner)
        ordner.mkdir(parents=True, exist_ok=True)
        rec = self.recording()
        pfad = json_atomar_schreiben(freier_pfad(ordner, rec.dateiname()), rec.to_dict())
        # Erst nach erfolgreichem Schreiben aufräumen — sonst ginge bei einem
        # Fehler die einzige Kopie verloren.
        for alt in {*self._backup_pfade, ordner / self.backup_name(), ordner / self.journal_name()}:
            alt.unlink(missing_ok=True)
        self._backup_pfade.clear()
        return pfad


# -- Liegengebliebene Backups ---------------------------------------------------


def backups_finden(messungen: Path | str) -> list[Path]:
    """Alle Crash-Backups unter ``Messungen/<Geräteordner>/`` — auch ``Generator``.

    Ein Backup, das nach dem Speichern noch da ist, gehört zu einer Aufnahme,
    die nicht ordentlich beendet wurde (Akku leer, Absturz). Fehlt das
    Verzeichnis, gibt es nichts.

    >>> import tempfile
    >>> ordner = tempfile.TemporaryDirectory()
    >>> backups_finden(Path(ordner.name) / "gibt_es_nicht")
    []
    >>> ordner.cleanup()
    """
    wurzel = Path(messungen)
    if not wurzel.is_dir():
        return []
    return sorted(p for p in wurzel.glob(f"*/{BACKUP_MUSTER}") if p.is_file())


def backup_lesen(pfad: Path | str) -> tuple[Recording, dict[str, Any]]:
    """Ein Backup als ``(Recording, Zusatz)``.

    Der Block ``_wiederherstellung`` wird **vor** `Recording.from_dict`
    herausgenommen — sonst landete er in ``extra`` und beim Speichern in der
    Messdatei. Backups von vor diesem Block liefern ``{}``.

    Raises:
        FormatFehler: kein JSON-Objekt (halb geschrieben, von Hand bearbeitet)
            oder ein unlesbarer Messwert — ein `ValueError`, wie bisher.
    """
    pfad = Path(pfad)
    try:
        doc = json_objekt_lesen(pfad)
    except FormatFehler as fehler:
        raise FormatFehler(f"Backup unlesbar: {fehler}") from fehler
    zusatz = doc.pop(WIEDERHERSTELLUNG, None)
    journal = doc.pop(JOURNAL, None)
    rec = Recording.from_dict(doc)
    journal_pfad = pfad.with_name(str(journal)) if journal else pfad.with_name(pfad.name + "l")
    if journal_pfad.is_file():
        _journal_lesen(journal_pfad, rec)
    return rec, dict(zusatz) if isinstance(zusatz, dict) else {}


def backup_entfernen(pfad: Path | str) -> None:
    """Kopf und Journal eines Backups löschen — nach der Wiederherstellung."""
    kopf = Path(pfad)
    kopf.unlink(missing_ok=True)
    kopf.with_name(kopf.name + "l").unlink(missing_ok=True)


def _journal_lesen(pfad: Path, rec: Recording) -> None:
    """Die Zeilen des Journals in die Messung — Unlesbares (eine halbe Zeile nach einem
    Abbruch) wird übersprungen, eine doppelte Zeile nach einem Abbruch ebenso."""
    letzte: dict[str, Any] | None = None
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if (
                not isinstance(eintrag, list)
                or len(eintrag) != 2
                or not isinstance(eintrag[1], dict)
            ):
                continue
            art, daten = eintrag
            if art == "b":
                if daten == letzte:
                    continue
                try:
                    rec.beats.append(Beat.from_dict(daten))
                except FormatFehler:
                    continue
                letzte = daten
            elif art == "p":
                if rec.ppi_pakete is None:
                    rec.ppi_pakete = []
                rec.ppi_pakete.append(daten)


__all__ = [
    "BACKUP_MUSTER",
    "JOURNAL",
    "WIEDERHERSTELLUNG",
    "Aufnahme",
    "backup_entfernen",
    "backup_lesen",
    "backups_finden",
]
