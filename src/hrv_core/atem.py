"""Atemphasen als Beiwerk ``sensor_<ts>_atem.json`` (``atem-v1``) — sammeln, sichern, lesen.

Das Ergebnis der Atemerfassung aus dem Beschleunigungssensor (trainingsapp,
``docs/plan_beschleunigung.md`` §7.4 und §8: **Ergebnisse statt Rohdaten**, P123). Der
Inhalt stammt aus einem Prototyp (`hrv_core.prototyp`) und ist so gekennzeichnet
(``art``, ``prototyp``); das Dateiformat selbst ist stabil und wird hier gepflegt:

- ``erfasst[]`` — die Läufe von „Atmung erfassen“, ``[von_s, bis_s]`` je Lauf. Ohne einen
  solchen Eintrag ist eine Lücke „nicht gemessen“, nicht „kein Atemzug“.
- ``phasen[]`` — ``[t_s, "ein" | "aus"]``, Beginn von Ein- bzw. Ausatmen, zeitlich sortiert.
- ``fenster[]`` — ``[t_ende_s, rate_pro_min, gueltig, grund]`` je Prüffenster (alle 5 s,
  30 s lang, Ende des Fensters); ``rate_pro_min`` ist ``null`` und ``grund`` ein
  snake_case-Code aus dem Prototyp, wenn das Fenster nicht gültig ist — der **erste** Grund
  seiner Prüfreihenfolge (`hrv_core.prototyp.atemzuege`): ``bewegung``, ``amplitude_klein``,
  ``kein_gipfel`` / ``gipfel_undeutlich``, ``zu_wenig_zyklen``, ``ungleichmaessig`` /
  ``zyklen_passen_nicht``.
- Kopf: ``schema``, ``art`` (``prototyp``), ``prototyp`` (Modulname), ``hrv_core``
  (Version), ``quelle`` (``sensor`` — ``takt`` ist für den Taktgeber reserviert), ``geraet``
  (Profil-ID wie ``polar_h10``, nie Name, Adresse oder Seriennummer), ``rate_hz``.
- ``takt`` — **optional** (P141, 5.11.2026): die **Soll-Phasen des Taktgebers**, damit die
  Auswertung Soll gegen Ist (Sensor) legt und die Atem-HRV die Phasenlage gegen beides rechnet
  (trainingsapp ``docs/plan_taktgeber.md`` §3). Ein Objekt ``{"name", "rate_pro_min",
  "phasen", "laeufe"}``: ``phasen[]`` wie oben ``[t_s, "ein" | "aus"]``, zeitlich sortiert —
  **alle** Takt-Läufe der Messung in einer Liste; ``laeufe[]`` ``[von_s, bis_s, name,
  rate_pro_min]`` je Lauf (ohne Lauf ist eine Lücke „kein Takt“, wie ``erfasst``; so bleiben
  Name und Rate je Lauf erhalten, auch nach einer Tempoänderung); ``name`` und
  ``rate_pro_min`` oben sind die des **letzten** Laufs — der kurze Weg für Leser, die nur
  wissen wollen, welcher Takt lief. Das Feld steht nur in der Datei, wenn es Soll-Phasen gibt;
  ältere Leser übergehen es, alte Dateien ohne das Feld lesen sich unverändert
  (`Atem.takt` ``None``).

Alle Zeiten in Sekunden auf der **Wanduhr der Messung** (``t_wall_s`` wie die Schläge),
3 Nachkommastellen. Keine Rohproben, kein Ort, nichts vom Magnetometer, keine Korrekturen
(±1 steht in der Zeitleiste der Einheit). `recording.ist_messdatei` kennt die Endung und
übergeht die Datei; `deid` behält alle Felder.

Crash-Sicherheit wie beim EKG (`ekg`): `AtemSammler.journal_anhaengen` hängt nur Neues als
JSON-Zeilen an eine ``.jsonl`` neben dem Crash-Backup — ``["k", {kopf}]``, ``["e", von_s]``
(Lauf auf), ``["x", bis_s]`` (Lauf zu), ``["p", t_s, art]``, ``["f", t_ende_s, rate, gueltig,
grund]``, für den Taktgeber ``["t", t_s, name, rate]`` (Takt auf), ``["q", t_s, art]``
(Soll-Phase), ``["u", t_s]`` (Takt zu) —, jede Zeile für sich abgeschlossen, zuletzt ``fsync``;
endet die Datei mitten in einer Zeile, beginnt der Anhang mit einem Zeilenumbruch, und ein
anderes oder verschwundenes Journal bekommt alles noch einmal. `AtemSammler.aus_journal` baut
daraus den Sammler wieder auf und übergeht Unlesbares. Ein offener Lauf bleibt im Journal
offen; `dokument` und `schreiben` schließen ihn mit dem letzten bekannten Zeitpunkt (letzte
Phase oder letztes Fenster, sonst ``von_s``); ein offener Takt-Lauf ebenso mit seiner letzten
Soll-Phase.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__

#: Schema dieses Beiwerks
ATEM_SCHEMA: str = "atem-v1"
#: Endung des Beiwerks neben der Messdatei
ATEM_ENDUNG: str = "_atem.json"
#: Endung des Journals neben dem Crash-Backup
ATEM_JOURNAL_ENDUNG: str = "_atem.jsonl"
#: Kennzeichnung des Inhalts: er stammt aus einem Prototyp (`hrv_core.prototyp`)
ATEM_ART: str = "prototyp"
#: Die beiden Phasen eines Atemzugs
PHASEN: tuple[str, ...] = ("ein", "aus")
#: Quelle der Erfassung: Beschleunigungssensor; ``takt`` ist für den Taktgeber reserviert
QUELLE_SENSOR: str = "sensor"
QUELLE_TAKT: str = "takt"


def atem_pfad(messdatei: Path | str) -> Path:
    """Das Atem-Beiwerk zu einer Messdatei: ``sensor_<ts>.json`` → ``sensor_<ts>_atem.json``.

    >>> atem_pfad("Messungen/PolarH10/sensor_2026-11-05_061500.json").name
    'sensor_2026-11-05_061500_atem.json'
    """
    p = Path(messdatei)
    return p.with_name(p.stem + ATEM_ENDUNG)


def atem_journal_pfad(backup: Path | str) -> Path:
    """Das Atem-Journal zu einem Crash-Backup ``.backup_<ts>.json``.

    >>> atem_journal_pfad("Messungen/PolarH10/.backup_2026-11-05_061500.json").name
    '.backup_2026-11-05_061500_atem.jsonl'
    """
    p = Path(backup)
    return p.with_name(p.stem + ATEM_JOURNAL_ENDUNG)


def _zeit(t: Any) -> float:
    return round(float(t), 3)


def _rate(rate: Any) -> float | None:
    if rate is None:
        return None
    try:
        wert = float(rate)
    except (TypeError, ValueError):
        return None
    return None if wert != wert else round(wert, 2)  # NaN → None


def _laeufe_schliessen(laeufe: list[list[Any]], letzter: Any) -> list[list[Any]]:
    """Läufe ``[von, bis, …]`` kopieren; ``bis`` ``None`` (offen) wird ``letzter(von)``."""
    out: list[list[Any]] = []
    for lauf in laeufe:
        von, bis, *rest = lauf
        assert von is not None
        out.append([von, letzter(von) if bis is None else bis, *rest])
    return out


def _rate_hz(rate_hz: Any) -> float | None:
    if rate_hz is None:
        return None
    try:
        wert = float(rate_hz)
    except (TypeError, ValueError):
        return None
    return int(wert) if wert.is_integer() else wert


class AtemSammler:
    """Läufe, Phasen und Fenster der Atemerfassung sammeln und als Beiwerk schreiben.

    >>> s = AtemSammler("sensor", "polar_h10", 50, prototyp="hrv_core.prototyp.atemzuege")
    >>> s.leer
    True
    >>> s.lauf_beginn(10.0)
    >>> s.phase(12.345678, "ein")
    >>> s.phase(14.5, "aus")
    >>> s.fenster(40.0, 12.34, True)
    >>> s.fenster(45.0, None, False, "bewegung")
    >>> doc = s.dokument()           # offener Lauf: geschlossen mit dem letzten Fenster
    >>> doc["erfasst"], doc["phasen"]
    ([[10.0, 45.0]], [[12.346, 'ein'], [14.5, 'aus']])
    >>> doc["fenster"]
    [[40.0, 12.34, True, ''], [45.0, None, False, 'bewegung']]
    >>> s.lauf_ende(50.0)
    >>> s.dokument()["erfasst"]
    [[10.0, 50.0]]
    >>> "takt" in doc                   # ohne Soll-Phasen kein Feld
    False
    >>> s.takt_beginn(10.0, "Box 4-4", 7.5)
    >>> s.takt_phase(10.0, "ein")
    >>> s.takt_phase(14.0, "aus")
    >>> s.takt_ende(18.0)
    >>> t = s.dokument()["takt"]
    >>> t["name"], t["rate_pro_min"], t["phasen"]
    ('Box 4-4', 7.5, [[10.0, 'ein'], [14.0, 'aus']])
    >>> t["laeufe"]
    [[10.0, 18.0, 'Box 4-4', 7.5]]
    """

    def __init__(
        self,
        quelle: str = QUELLE_SENSOR,
        geraet: str = "",
        rate_hz: float | int | None = None,
        *,
        prototyp: str = "",
        hrv_core: str | None = None,
    ) -> None:
        self.quelle = str(quelle)
        self.geraet = str(geraet)
        self.rate_hz = _rate_hz(rate_hz)
        self.prototyp = str(prototyp)
        self.hrv_core = __version__ if hrv_core is None else str(hrv_core)
        #: ``[von_s, bis_s]`` je Lauf; ``bis_s`` ``None`` = noch offen (nur der letzte)
        self.laeufe: list[list[float | None]] = []
        self.phasen: list[tuple[float, str]] = []
        self.fenster_liste: list[tuple[float, float | None, bool, str]] = []
        #: Taktgeber: ``[von_s, bis_s, name, rate_pro_min]`` je Lauf; ``bis_s`` ``None`` = offen
        self.takt_laeufe: list[list[Any]] = []
        #: Soll-Phasen des Taktgebers ``(t_s, art)``, alle Läufe in einer Liste
        self.takt_phasen: list[tuple[float, str]] = []
        self._journal_kopf = False  # steht der Kopf („k“) schon im Journal?
        self._journal_laeufe_ab = 0  # so viele Läufe sind im Journal eröffnet („e“)
        self._journal_zu_ab = 0  # so viele Läufe sind im Journal geschlossen („x“)
        self._journal_phasen_ab = 0
        self._journal_fenster_ab = 0
        self._journal_takt_laeufe_ab = 0  # Takt-Läufe eröffnet („t“)
        self._journal_takt_zu_ab = 0  # Takt-Läufe geschlossen („u“)
        self._journal_takt_phasen_ab = 0  # Soll-Phasen („q“)
        self._journal_pfad: Path | None = None

    # -- Sammeln ---------------------------------------------------------------

    @property
    def offen(self) -> bool:
        """Ob gerade ein Lauf „Atmung erfassen“ läuft."""
        return bool(self.laeufe) and self.laeufe[-1][1] is None

    def lauf_beginn(self, t_s: float) -> None:
        """„Atmung erfassen“ beginnt. Ein noch offener Lauf endet hier (keine Lücke)."""
        t = _zeit(t_s)
        if self.offen:
            self.lauf_ende(t)
        self.laeufe.append([t, None])

    def lauf_ende(self, t_s: float) -> None:
        """„Atmung erfassen“ endet; ohne offenen Lauf passiert nichts."""
        if not self.offen:
            return
        von = self.laeufe[-1][0]
        assert von is not None
        self.laeufe[-1][1] = max(von, _zeit(t_s))

    def phase(self, t_s: float, art: str) -> None:
        """Beginn des Ein- (``"ein"``) oder Ausatmens (``"aus"``) auf der Wanduhr.

        Raises:
            ValueError: unbekannte Phase.
        """
        if art not in PHASEN:
            raise ValueError(f"unbekannte Atemphase: {art!r}")
        self.phasen.append((_zeit(t_s), art))

    def fenster(self, t_ende_s: float, rate: float | None, gueltig: bool, grund: str = "") -> None:
        """Ergebnis eines Prüffensters: Ende, Rate je Minute (``None`` = keine), gültig, Grund."""
        self.fenster_liste.append((_zeit(t_ende_s), _rate(rate), bool(gueltig), str(grund or "")))

    # -- Taktgeber (Soll-Phasen) ----------------------------------------------

    @property
    def takt_offen(self) -> bool:
        """Ob gerade ein Takt-Lauf offen ist."""
        return bool(self.takt_laeufe) and self.takt_laeufe[-1][1] is None

    def takt_beginn(self, t_s: float, name: str, rate_pro_min: float | None) -> None:
        """Der Taktgeber beginnt (auch nach einer Tempoänderung: neuer Lauf mit neuer Rate).
        Ein noch offener Takt-Lauf endet hier."""
        t = _zeit(t_s)
        if self.takt_offen:
            self.takt_ende(t)
        self.takt_laeufe.append([t, None, str(name or ""), _rate(rate_pro_min)])

    def takt_phase(self, t_s: float, art: str) -> None:
        """Soll-Beginn des Ein- (``"ein"``) oder Ausatmens (``"aus"``) laut Taktgeber.

        Raises:
            ValueError: unbekannte Phase.
        """
        if art not in PHASEN:
            raise ValueError(f"unbekannte Atemphase: {art!r}")
        self.takt_phasen.append((_zeit(t_s), art))

    def takt_ende(self, t_s: float) -> None:
        """Der Taktgeber endet; ohne offenen Takt-Lauf passiert nichts."""
        if not self.takt_offen:
            return
        von = self.takt_laeufe[-1][0]
        self.takt_laeufe[-1][1] = max(von, _zeit(t_s))

    # -- Ableitungen -----------------------------------------------------------

    @property
    def leer(self) -> bool:
        """Ob noch nichts gesammelt wurde — dann lohnt kein Beiwerk. Soll-Phasen des
        Taktgebers zählen mit: ein Takt ohne Sensor ergibt ein Beiwerk nur mit ``takt``."""
        return not (self.laeufe or self.phasen or self.fenster_liste or self.takt_phasen)

    def _letzter_zeitpunkt(self, ab: float) -> float:
        """Letzter bekannter Zeitpunkt: letzte Phase oder letztes Fenster, sonst ``ab``."""
        kandidaten = [ab]
        if self.phasen:
            kandidaten.append(max(t for t, _ in self.phasen))
        if self.fenster_liste:
            kandidaten.append(max(f[0] for f in self.fenster_liste))
        return max(kandidaten)

    def erfasst(self) -> list[list[float]]:
        """Die Läufe als ``[von_s, bis_s]``; ein offener Lauf wird mit dem letzten bekannten
        Zeitpunkt geschlossen (nur in der Ausgabe, der Sammler bleibt offen)."""
        return _laeufe_schliessen(self.laeufe, self._letzter_zeitpunkt)

    def _letzte_takt_phase(self, ab: float) -> float:
        """Letzte Soll-Phase, sonst ``ab``."""
        return max([ab, *(t for t, _ in self.takt_phasen)])

    def takt(self) -> dict[str, Any] | None:
        """Das Feld ``takt`` — ``None`` ohne Soll-Phasen. ``name`` und ``rate_pro_min`` sind
        die des letzten Laufs; ein offener Lauf endet (nur in der Ausgabe) mit seiner letzten
        Soll-Phase."""
        if not self.takt_phasen:
            return None
        laeufe = _laeufe_schliessen(self.takt_laeufe, self._letzte_takt_phase)
        name, rate = (laeufe[-1][2], laeufe[-1][3]) if laeufe else ("", None)
        return {
            "name": name,
            "rate_pro_min": rate,
            "phasen": [[t, art] for t, art in sorted(self.takt_phasen, key=lambda p: p[0])],
            "laeufe": laeufe,
        }

    def dokument(self) -> dict[str, Any]:
        """Das Beiwerk als Dict (``atem-v1``), Phasen zeitlich sortiert; ``takt`` nur,
        wenn es Soll-Phasen gibt."""
        takt = self.takt()
        return {
            "schema": ATEM_SCHEMA,
            "art": ATEM_ART,
            "prototyp": self.prototyp,
            "hrv_core": self.hrv_core,
            "quelle": self.quelle,
            "geraet": self.geraet,
            "rate_hz": self.rate_hz,
            "erfasst": self.erfasst(),
            "phasen": [[t, art] for t, art in sorted(self.phasen, key=lambda p: p[0])],
            "fenster": [list(f) for f in self.fenster_liste],
            **({"takt": takt} if takt is not None else {}),
        }

    # -- Schreiben -------------------------------------------------------------

    def schreiben(self, messdatei: Path | str) -> Path:
        """Das Beiwerk neben die Messdatei schreiben (atomar); gibt den Pfad zurück."""
        ziel = atem_pfad(messdatei)
        tmp = ziel.with_suffix(ziel.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.dokument(), f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, ziel)
        return ziel

    def _kopf(self) -> dict[str, Any]:
        return {
            "schema": ATEM_SCHEMA,
            "art": ATEM_ART,
            "prototyp": self.prototyp,
            "hrv_core": self.hrv_core,
            "quelle": self.quelle,
            "geraet": self.geraet,
            "rate_hz": self.rate_hz,
        }

    def journal_anhaengen(self, journal: Path | str) -> None:
        """Neues (seit dem letzten Aufruf) an das Journal hängen, zuletzt ``fsync``.

        Zeilen: ``["k", {kopf}]`` zuerst, dann ``["e", von_s]`` je eröffnetem Lauf,
        ``["x", bis_s]`` je geschlossenem, ``["p", t_s, art]`` je Phase, ``["f", t_ende_s,
        rate, gueltig, grund]`` je Fenster; Taktgeber: ``["t", t_s, name, rate]`` je
        begonnenem Takt-Lauf, ``["u", bis_s]`` je beendetem, ``["q", t_s, art]`` je
        Soll-Phase. Ein anderer Pfad als beim letzten Mal oder ein
        verschwundenes Journal: alles noch einmal, mit Kopf. Die Zähler rücken erst nach dem
        Schreiben vor — scheitert es, kommt beim nächsten Mal derselbe Stand.

        >>> import tempfile
        >>> ordner = Path(tempfile.mkdtemp())
        >>> s = AtemSammler("sensor", "polar_h10", 50)
        >>> s.lauf_beginn(1.0)
        >>> s.phase(2.0, "ein")
        >>> s.journal_anhaengen(ordner / "a.jsonl")
        >>> _ = (ordner / "a.jsonl").open("a").write('["p", 3.0, "au')   # halbe Zeile
        >>> s.phase(4.0, "aus")
        >>> s.lauf_ende(5.0)
        >>> s.journal_anhaengen(ordner / "a.jsonl")
        >>> w = AtemSammler.aus_journal(ordner / "a.jsonl")
        >>> w.phasen, w.laeufe, w.geraet
        ([(2.0, 'ein'), (4.0, 'aus')], [[1.0, 5.0]], 'polar_h10')
        """
        pfad = Path(journal)
        if pfad != self._journal_pfad or not pfad.exists():
            self._journal_pfad = pfad
            self._journal_kopf = False
            self._journal_laeufe_ab = self._journal_zu_ab = 0
            self._journal_phasen_ab = self._journal_fenster_ab = 0
            self._journal_takt_laeufe_ab = self._journal_takt_zu_ab = 0
            self._journal_takt_phasen_ab = 0
            pfad.unlink(missing_ok=True)  # ein fremder Rest bekäme sonst einen zweiten Kopf
        n_zu = sum(1 for _, bis in self.laeufe if bis is not None)
        n_takt_zu = sum(1 for lauf in self.takt_laeufe if lauf[1] is not None)
        neu_phasen = range(self._journal_phasen_ab, len(self.phasen))
        neu_fenster = range(self._journal_fenster_ab, len(self.fenster_liste))
        neu_takt_phasen = range(self._journal_takt_phasen_ab, len(self.takt_phasen))
        nichts_neu = (
            self._journal_laeufe_ab == len(self.laeufe)
            and self._journal_zu_ab == n_zu
            and not neu_phasen
            and not neu_fenster
            and self._journal_takt_laeufe_ab == len(self.takt_laeufe)
            and self._journal_takt_zu_ab == n_takt_zu
            and not neu_takt_phasen
        )
        if self._journal_kopf and nichts_neu:
            return
        halb = False
        if pfad.exists() and pfad.stat().st_size:
            with open(pfad, "rb") as f:
                f.seek(-1, os.SEEK_END)
                halb = f.read(1) != b"\n"
        with open(pfad, "a", encoding="utf-8") as f:
            if halb:
                f.write("\n")
            if not self._journal_kopf:
                f.write(json.dumps(["k", self._kopf()], ensure_ascii=False) + "\n")
            # Läufe in ihrer Reihenfolge: „e“ für jeden neuen, „x“ für jeden inzwischen
            # geschlossenen — nur der letzte Lauf kann offen sein, darum reicht ein Zähler
            # (geschlossen ≤ eröffnet).
            for k in range(self._journal_zu_ab, len(self.laeufe)):
                von, bis = self.laeufe[k]
                if k >= self._journal_laeufe_ab:
                    f.write(json.dumps(["e", von]) + "\n")
                if bis is not None and k >= self._journal_zu_ab:
                    f.write(json.dumps(["x", bis]) + "\n")
            for k in neu_phasen:
                f.write(json.dumps(["p", *self.phasen[k]], ensure_ascii=False) + "\n")
            for k in neu_fenster:
                f.write(json.dumps(["f", *self.fenster_liste[k]], ensure_ascii=False) + "\n")
            # Takt-Läufe genauso: „t“ je neuem (mit Name und Rate), „u“ je geschlossenem
            for k in range(self._journal_takt_zu_ab, len(self.takt_laeufe)):
                von, bis, name, rate = self.takt_laeufe[k]
                if k >= self._journal_takt_laeufe_ab:
                    f.write(json.dumps(["t", von, name, rate], ensure_ascii=False) + "\n")
                if bis is not None and k >= self._journal_takt_zu_ab:
                    f.write(json.dumps(["u", bis]) + "\n")
            for k in neu_takt_phasen:
                f.write(json.dumps(["q", *self.takt_phasen[k]], ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self._journal_kopf = True
        self._journal_laeufe_ab = len(self.laeufe)
        self._journal_zu_ab = n_zu
        self._journal_phasen_ab = len(self.phasen)
        self._journal_fenster_ab = len(self.fenster_liste)
        self._journal_takt_laeufe_ab = len(self.takt_laeufe)
        self._journal_takt_zu_ab = n_takt_zu
        self._journal_takt_phasen_ab = len(self.takt_phasen)

    @classmethod
    def aus_journal(cls, journal: Path | str) -> AtemSammler:
        """Den Sammler aus einem Journal wieder aufbauen (unlesbare Zeilen fallen weg).

        Ein Lauf, den das Journal nicht schließt, bleibt offen — `dokument` schließt ihn
        beim Schreiben mit dem letzten bekannten Zeitpunkt.
        """
        s = cls()
        with open(journal, encoding="utf-8") as f:
            for zeile in f:
                try:
                    eintrag = json.loads(zeile)
                except ValueError:
                    continue
                if not isinstance(eintrag, list) or not eintrag:
                    continue
                art = eintrag[0]
                try:
                    if art == "k" and len(eintrag) >= 2 and isinstance(eintrag[1], dict):
                        kopf = eintrag[1]
                        s.quelle = str(kopf.get("quelle") or QUELLE_SENSOR)
                        s.geraet = str(kopf.get("geraet") or "")
                        s.rate_hz = _rate_hz(kopf.get("rate_hz"))
                        s.prototyp = str(kopf.get("prototyp") or "")
                        s.hrv_core = str(kopf.get("hrv_core") or __version__)
                    elif art == "e" and len(eintrag) >= 2:
                        s.lauf_beginn(float(eintrag[1]))
                    elif art == "x" and len(eintrag) >= 2:
                        s.lauf_ende(float(eintrag[1]))
                    elif art == "p" and len(eintrag) >= 3 and eintrag[2] in PHASEN:
                        s.phase(float(eintrag[1]), str(eintrag[2]))
                    elif art == "f" and len(eintrag) >= 4:
                        grund = eintrag[4] if len(eintrag) >= 5 and eintrag[4] is not None else ""
                        s.fenster(float(eintrag[1]), eintrag[2], bool(eintrag[3]), str(grund))
                    elif art == "t" and len(eintrag) >= 2:
                        name = eintrag[2] if len(eintrag) >= 3 and eintrag[2] is not None else ""
                        rate = eintrag[3] if len(eintrag) >= 4 else None
                        s.takt_beginn(float(eintrag[1]), str(name), rate)
                    elif art == "u" and len(eintrag) >= 2:
                        s.takt_ende(float(eintrag[1]))
                    elif art == "q" and len(eintrag) >= 3 and eintrag[2] in PHASEN:
                        s.takt_phase(float(eintrag[1]), str(eintrag[2]))
                except (TypeError, ValueError):
                    continue
        s._journal_kopf = True
        s._journal_laeufe_ab = len(s.laeufe)
        s._journal_zu_ab = sum(1 for _, bis in s.laeufe if bis is not None)
        s._journal_phasen_ab = len(s.phasen)
        s._journal_fenster_ab = len(s.fenster_liste)
        s._journal_takt_laeufe_ab = len(s.takt_laeufe)
        s._journal_takt_zu_ab = sum(1 for lauf in s.takt_laeufe if lauf[1] is not None)
        s._journal_takt_phasen_ab = len(s.takt_phasen)
        s._journal_pfad = Path(journal)
        return s


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Takt:
    """Die Soll-Phasen des Taktgebers aus dem Feld ``takt`` (P141)."""

    #: Name und Rate des letzten Takt-Laufs
    name: str = ""
    rate_pro_min: float | None = None
    #: ``(t_s, "ein" | "aus")`` — Soll-Beginn der Phasen, alle Läufe, zeitlich sortiert
    phasen: list[tuple[float, str]] = field(default_factory=list)
    #: ``(von_s, bis_s, name, rate_pro_min)`` je Takt-Lauf
    laeufe: list[tuple[float, float, str, float | None]] = field(default_factory=list)

    def ist_getaktet(self, t_s: float) -> bool:
        """Ob zur Zeit ``t_s`` ein Takt-Lauf lief."""
        return any(von <= t_s <= bis for von, bis, _, _ in self.laeufe)

    def phasen_zwischen(self, von_s: float, bis_s: float) -> list[tuple[float, str]]:
        """Die Soll-Phasen mit ``von_s ≤ t < bis_s``."""
        return [(t, art) for t, art in self.phasen if von_s <= t < bis_s]


@dataclass(slots=True)
class Atem:
    """Ein gelesenes Atem-Beiwerk: Läufe, Phasen und Fenster auf der Wanduhr der Messung;
    dazu ``takt`` (Soll-Phasen des Taktgebers), ``None`` ohne das Feld."""

    quelle: str = QUELLE_SENSOR
    geraet: str = ""
    rate_hz: float | None = None
    art: str = ATEM_ART
    prototyp: str = ""
    hrv_core: str = ""
    #: ``(von_s, bis_s)`` je Lauf „Atmung erfassen“
    erfasst: list[tuple[float, float]] = field(default_factory=list)
    #: ``(t_s, "ein" | "aus")``, zeitlich sortiert
    phasen: list[tuple[float, str]] = field(default_factory=list)
    #: ``(t_ende_s, rate_pro_min | None, gueltig, grund)`` je Prüffenster
    fenster: list[tuple[float, float | None, bool, str]] = field(default_factory=list)
    #: Soll-Phasen des Taktgebers — ``None``, wenn die Datei das Feld nicht hat
    takt: Takt | None = None

    @property
    def dauer_erfasst_s(self) -> float:
        """Summe aller Läufe in Sekunden."""
        return float(sum(max(0.0, bis - von) for von, bis in self.erfasst))

    def ist_erfasst(self, t_s: float) -> bool:
        """Ob zur Zeit ``t_s`` die Atmung erfasst wurde (sonst: nicht gemessen)."""
        return any(von <= t_s <= bis for von, bis in self.erfasst)

    def phasen_zwischen(self, von_s: float, bis_s: float) -> list[tuple[float, str]]:
        """Die Phasen mit ``von_s ≤ t < bis_s``."""
        return [(t, art) for t, art in self.phasen if von_s <= t < bis_s]

    def takt_phasen_zwischen(self, von_s: float, bis_s: float) -> list[tuple[float, str]]:
        """Die Soll-Phasen des Taktgebers mit ``von_s ≤ t < bis_s``; leer ohne ``takt``."""
        return [] if self.takt is None else self.takt.phasen_zwischen(von_s, bis_s)

    def raten(self, *, nur_gueltig: bool = True) -> list[tuple[float, float]]:
        """``(t_ende_s, rate_pro_min)`` der Fenster — ohne ``nur_gueltig`` auch ungültige
        Fenster, sofern sie eine Rate tragen."""
        return [
            (t, rate)
            for t, rate, gueltig, _ in self.fenster
            if rate is not None and (gueltig or not nur_gueltig)
        ]


def _laeufe_lesen(roh: Any) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for lauf in roh if isinstance(roh, list) else []:
        if not isinstance(lauf, list | tuple) or len(lauf) < 2 or lauf[0] is None:
            continue
        try:
            von = float(lauf[0])
            bis = von if lauf[1] is None else float(lauf[1])
        except (TypeError, ValueError):
            continue
        out.append((von, max(von, bis)))
    return out


def _phasen_lesen(roh: Any) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for p in roh if isinstance(roh, list) else []:
        if not isinstance(p, list | tuple) or len(p) < 2 or p[1] not in PHASEN:
            continue
        try:
            out.append((float(p[0]), str(p[1])))
        except (TypeError, ValueError):
            continue
    return sorted(out, key=lambda p: p[0])


def _fenster_lesen(roh: Any) -> list[tuple[float, float | None, bool, str]]:
    out: list[tuple[float, float | None, bool, str]] = []
    for f in roh if isinstance(roh, list) else []:
        if not isinstance(f, list | tuple) or len(f) < 3:
            continue
        try:
            t = float(f[0])
        except (TypeError, ValueError):
            continue
        grund = f[3] if len(f) >= 4 and f[3] is not None else ""
        out.append((t, _rate(f[1]), bool(f[2]), str(grund)))
    return out


def _takt_laeufe_lesen(roh: Any) -> list[tuple[float, float, str, float | None]]:
    out: list[tuple[float, float, str, float | None]] = []
    for lauf in roh if isinstance(roh, list) else []:
        if not isinstance(lauf, list | tuple) or len(lauf) < 2 or lauf[0] is None:
            continue
        try:
            von = float(lauf[0])
            bis = von if lauf[1] is None else float(lauf[1])
        except (TypeError, ValueError):
            continue
        name = lauf[2] if len(lauf) >= 3 and lauf[2] is not None else ""
        rate = _rate(lauf[3]) if len(lauf) >= 4 else None
        out.append((von, max(von, bis), str(name), rate))
    return out


def _takt_lesen(roh: Any) -> Takt | None:
    """Das Feld ``takt`` — ``None``, wenn es fehlt oder kein Objekt ist."""
    if not isinstance(roh, dict):
        return None
    return Takt(
        name=str(roh.get("name") or ""),
        rate_pro_min=_rate(roh.get("rate_pro_min")),
        phasen=_phasen_lesen(roh.get("phasen")),
        laeufe=_takt_laeufe_lesen(roh.get("laeufe")),
    )


def atem_laden(pfad: Path | str) -> Atem:
    """Ein Atem-Beiwerk lesen — tolerant: fehlende oder kaputte Listen sind leer, ohne
    ``takt`` ist `Atem.takt` ``None``.

    Raises:
        ValueError: kein Atem-Beiwerk (kein JSON-Objekt oder ``schema`` nicht ``atem-v1``).
    """
    with open(pfad, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict) or doc.get("schema") != ATEM_SCHEMA:
        raise ValueError(f"kein Atem-Beiwerk: {pfad}")
    return Atem(
        quelle=str(doc.get("quelle") or QUELLE_SENSOR),
        geraet=str(doc.get("geraet") or ""),
        rate_hz=_rate_hz(doc.get("rate_hz")),
        art=str(doc.get("art") or ATEM_ART),
        prototyp=str(doc.get("prototyp") or ""),
        hrv_core=str(doc.get("hrv_core") or ""),
        erfasst=_laeufe_lesen(doc.get("erfasst")),
        phasen=_phasen_lesen(doc.get("phasen")),
        fenster=_fenster_lesen(doc.get("fenster")),
        takt=_takt_lesen(doc.get("takt")),
    )


__all__ = [
    "ATEM_ART",
    "ATEM_ENDUNG",
    "ATEM_JOURNAL_ENDUNG",
    "ATEM_SCHEMA",
    "PHASEN",
    "QUELLE_SENSOR",
    "QUELLE_TAKT",
    "Atem",
    "AtemSammler",
    "Takt",
    "atem_journal_pfad",
    "atem_laden",
    "atem_pfad",
]
