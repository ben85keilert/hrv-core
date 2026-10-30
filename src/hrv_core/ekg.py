"""EKG-Rohsignal als Beiwerk ``sensor_<ts>_ecg.json`` — sammeln, sichern, lesen.

Das Format stammt aus praxis_gui (Polar H10, PMD-Dienst, 130 Hz, µV je Probe):
``sample_rate_hz``, ``uv[]`` (alle Proben hintereinander), ``frame_offsets[]`` (Position
der ersten Probe jedes Rahmens in ``uv``, ein laufender Zähler), ``frame_sample_counts[]``,
``duration_s``, ``n_samples``, ``n_samples_expected``. Seit 30.10.2026 schreibt es auch die
trainingsapp (Ben: „die Werte werden mitgeschrieben, aber erstmal nicht gerechnet, man kann
sie extrahieren“) und ergänzt:

- ``frame_t_ns[]`` — der Gerätezeitstempel jedes Rahmens (Polar: Zeit der **letzten** Probe,
  ns seit 2000-01-01). Daraus ``gaps[]``: Rahmen, vor denen Zeit fehlt
  (``{"nach_probe", "dauer_s"}``), etwa wenn die Verbindung stockt oder der Gurt schwächelt.
- ``t_wall_start_s`` — Wanduhr der Messung (s seit Aufnahmestart) für Probe 0, aus der
  Ankunft des ersten Rahmens in der App; damit liegt das EKG neben den Schlägen der Messdatei.
- ``batterie[]`` — ``[t_wall_s, prozent]`` bei jeder Änderung des Akkustands (Ben will sehen,
  wie sich der Gurt verhält, wenn die Batterie zur Neige geht).

Die Proben bleiben rohe µV, so wie der Gurt sie sendet; gerechnet wird hier nichts (die
R-Zacken-Erkennung ist Entscheidung 1 in hrv-research, offen). `ist_messdatei` kennt die
Endung und übergeht die Datei; `deid` behält alle Felder.

Crash-Sicherheit: `EkgSammler.journal_anhaengen` hängt neue Rahmen als JSON-Zeilen an eine
``.jsonl`` neben dem Backup der Aufnahme; `EkgSammler.aus_journal` baut daraus den Sammler
wieder auf.
"""

from __future__ import annotations

import json
import os
from array import array
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

#: Abtastrate des Polar H10 (PMD-EKG)
EKG_RATE_HZ: int = 130
#: Endung des Beiwerks neben der Messdatei
EKG_ENDUNG: str = "_ecg.json"
#: Endung des Journals neben dem Crash-Backup
EKG_JOURNAL_ENDUNG: str = "_ecg.jsonl"
#: Eine Lücke zwischen zwei Rahmen zählt ab so vielen Proben Verzug
LUECKE_AB_PROBEN: float = 1.5


def ekg_pfad(messdatei: Path | str) -> Path:
    """Das EKG-Beiwerk zu einer Messdatei: ``sensor_<ts>.json`` → ``sensor_<ts>_ecg.json``.

    >>> ekg_pfad("Messungen/PolarH10/sensor_2026-10-30_061500.json").name
    'sensor_2026-10-30_061500_ecg.json'
    """
    p = Path(messdatei)
    return p.with_name(p.stem + EKG_ENDUNG)


def ekg_journal_pfad(backup: Path | str) -> Path:
    """Das EKG-Journal zu einem Crash-Backup ``.backup_<ts>.json``.

    >>> ekg_journal_pfad("Messungen/PolarH10/.backup_2026-10-30_061500.json").name
    '.backup_2026-10-30_061500_ecg.jsonl'
    """
    p = Path(backup)
    return p.with_name(p.stem + EKG_JOURNAL_ENDUNG)


class EkgSammler:
    """Rahmen eines EKG-Stroms sammeln und als Beiwerk schreiben.

    >>> s = EkgSammler(rate_hz=130)
    >>> s.rahmen(1_000_000_000, [1, 2, 3], t_wall_s=10.0)
    >>> s.rahmen(1_000_000_000 + round(3 / 130 * 1e9), [4, 5, 6], t_wall_s=10.02)
    >>> s.n, s.frame_offsets, s.luecken()
    (6, [0, 3], [])
    >>> s.rahmen(5_000_000_000, [7], t_wall_s=14.0)   # 4 s später: Lücke vor Probe 6
    >>> s.luecken()
    [{'nach_probe': 6, 'dauer_s': 3.969}]
    >>> round(s.t_wall_start_s, 4)
    9.9846
    """

    def __init__(self, rate_hz: int = EKG_RATE_HZ) -> None:
        self.rate_hz = int(rate_hz)
        self.uv: array[int] = array("i")
        self.frame_sample_counts: list[int] = []
        self.frame_t_ns: list[int] = []
        self.t_wall_start_s: float | None = None
        self.batterie: list[list[float]] = []
        self._journal_ab = 0  # so viele Rahmen stehen schon im Journal
        self._journal_batterie_ab = 0

    # -- Sammeln ---------------------------------------------------------------

    def rahmen(self, zeitstempel_ns: int, uv: Sequence[int], *, t_wall_s: float) -> None:
        """Ein PMD-Rahmen: Gerätezeit (letzte Probe), Proben in µV, Ankunft auf der Wanduhr."""
        werte = [int(v) for v in uv]
        if not werte:
            return
        if self.t_wall_start_s is None:
            # Ankunft des ersten Rahmens zurückgerechnet auf seine erste Probe
            self.t_wall_start_s = float(t_wall_s) - (len(werte) - 1) / self.rate_hz
        self.frame_sample_counts.append(len(werte))
        self.frame_t_ns.append(int(zeitstempel_ns))
        self.uv.extend(werte)

    def batterie_melden(self, t_wall_s: float, prozent: int | None) -> None:
        """Akkustand merken — nur, wenn er sich geändert hat."""
        if prozent is None:
            return
        if self.batterie and int(self.batterie[-1][1]) == int(prozent):
            return
        self.batterie.append([round(float(t_wall_s), 1), int(prozent)])

    # -- Ableitungen -----------------------------------------------------------

    @property
    def n(self) -> int:
        return len(self.uv)

    @property
    def n_rahmen(self) -> int:
        return len(self.frame_sample_counts)

    @property
    def dauer_s(self) -> float:
        return self.n / self.rate_hz

    @property
    def frame_offsets(self) -> list[int]:
        out: list[int] = []
        lauf = 0
        for n in self.frame_sample_counts:
            out.append(lauf)
            lauf += n
        return out

    def luecken(self) -> list[dict[str, Any]]:
        """Rahmen, vor denen laut Gerätezeit mehr Zeit verging, als ihre Proben füllen."""
        out: list[dict[str, Any]] = []
        offsets = self.frame_offsets
        for k in range(1, len(self.frame_t_ns)):
            vergangen = (self.frame_t_ns[k] - self.frame_t_ns[k - 1]) / 1e9
            erwartet = self.frame_sample_counts[k] / self.rate_hz
            if vergangen - erwartet > LUECKE_AB_PROBEN / self.rate_hz:
                out.append({"nach_probe": offsets[k], "dauer_s": round(vergangen - erwartet, 3)})
        return out

    def dokument(self) -> dict[str, Any]:
        """Das Beiwerk als Dict — Schlüssel wie praxis_gui plus die Erweiterungen oben."""
        luecken = self.luecken()
        verloren = sum(float(g["dauer_s"]) for g in luecken)
        return {
            "sample_rate_hz": self.rate_hz,
            "duration_s": round(self.dauer_s, 3),
            "n_samples_expected": self.n + round(verloren * self.rate_hz),
            "n_samples": self.n,
            "frame_offsets": self.frame_offsets,
            "frame_sample_counts": list(self.frame_sample_counts),
            "frame_t_ns": list(self.frame_t_ns),
            "gaps": luecken,
            "t_wall_start_s": None
            if self.t_wall_start_s is None
            else round(self.t_wall_start_s, 3),
            "batterie": [list(b) for b in self.batterie],
            "uv": self.uv.tolist(),
        }

    # -- Schreiben -------------------------------------------------------------

    def schreiben(self, messdatei: Path | str) -> Path:
        """Das Beiwerk neben die Messdatei schreiben (atomar); gibt den Pfad zurück."""
        ziel = ekg_pfad(messdatei)
        tmp = ziel.with_suffix(ziel.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.dokument(), f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, ziel)
        return ziel

    def journal_anhaengen(self, journal: Path | str) -> None:
        """Neue Rahmen (seit dem letzten Aufruf) an das Journal hängen.

        Zeilen: ``["r", t_ns, [uv…]]`` je Rahmen, ``["b", t_wall_s, prozent]`` je Akkostand;
        die erste Zeile ``["k", rate_hz, t_wall_start_s]`` ist der Kopf.
        """
        pfad = Path(journal)
        neu_rahmen = range(self._journal_ab, self.n_rahmen)
        neu_batterie = range(self._journal_batterie_ab, len(self.batterie))
        if not neu_rahmen and not neu_batterie and pfad.exists():
            return
        offsets = self.frame_offsets
        with open(pfad, "a", encoding="utf-8") as f:
            if self._journal_ab == 0 and self._journal_batterie_ab == 0:
                f.write(json.dumps(["k", self.rate_hz, self.t_wall_start_s]) + "\n")
            for k in neu_rahmen:
                lo = offsets[k]
                hi = lo + self.frame_sample_counts[k]
                f.write(json.dumps(["r", self.frame_t_ns[k], self.uv[lo:hi].tolist()]) + "\n")
            for k in neu_batterie:
                f.write(json.dumps(["b", *self.batterie[k]]) + "\n")
        self._journal_ab = self.n_rahmen
        self._journal_batterie_ab = len(self.batterie)

    @classmethod
    def aus_journal(cls, journal: Path | str) -> EkgSammler:
        """Den Sammler aus einem Journal wieder aufbauen (unlesbare Zeilen fallen weg)."""
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
                if art == "k" and len(eintrag) >= 3:
                    s.rate_hz = int(eintrag[1] or EKG_RATE_HZ)
                    s.t_wall_start_s = None if eintrag[2] is None else float(eintrag[2])
                elif art == "r" and len(eintrag) >= 3 and isinstance(eintrag[2], list):
                    werte = [int(v) for v in eintrag[2]]
                    if werte:
                        s.frame_sample_counts.append(len(werte))
                        s.frame_t_ns.append(int(eintrag[1]))
                        s.uv.extend(werte)
                elif art == "b" and len(eintrag) >= 3:
                    s.batterie.append([float(eintrag[1]), int(eintrag[2])])
        s._journal_ab = s.n_rahmen
        s._journal_batterie_ab = len(s.batterie)
        return s


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Ekg:
    """Ein gelesenes EKG-Beiwerk: Proben (µV) und ihre Zeit auf der Wanduhr der Messung."""

    rate_hz: int
    uv: np.ndarray
    frame_offsets: list[int]
    frame_sample_counts: list[int]
    frame_t_ns: list[int] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    t_wall_start_s: float = 0.0
    batterie: list[list[float]] = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(self.uv.size)

    @property
    def dauer_s(self) -> float:
        """Zeit von der ersten bis zur letzten Probe — mit Lücken, nach Gerätezeit."""
        t = self.zeit_s()
        return float(t[-1] - t[0]) if t.size else 0.0

    def zeit_s(self) -> np.ndarray:
        """Wanduhr (s seit Aufnahmestart) je Probe.

        Mit Gerätezeitstempeln liegt jeder Rahmen dort, wo das Gerät ihn gemessen hat (Lücken
        bleiben Lücken); ohne läuft die Zeit mit ``frame_offsets / rate`` einfach durch.
        """
        fs = float(self.rate_hz)
        if self.frame_t_ns and len(self.frame_t_ns) == len(self.frame_sample_counts):
            n0 = self.frame_sample_counts[0]
            # Ende des ersten Rahmens auf der Wanduhr
            ende0 = self.t_wall_start_s + (n0 - 1) / fs
            teile = []
            for _k, (t_ns, n) in enumerate(
                zip(self.frame_t_ns, self.frame_sample_counts, strict=True)
            ):
                ende = ende0 + (t_ns - self.frame_t_ns[0]) / 1e9
                teile.append(ende - np.arange(n - 1, -1, -1) / fs)
            return np.concatenate(teile) if teile else np.empty(0)
        return self.t_wall_start_s + np.arange(self.n) / fs

    def ausschnitt(self, von_s: float, bis_s: float) -> tuple[np.ndarray, np.ndarray]:
        """``(t, uv)`` der Proben mit ``von_s ≤ t < bis_s``."""
        t = self.zeit_s()
        m = (t >= von_s) & (t < bis_s)
        return t[m], self.uv[m]


def ekg_laden(pfad: Path | str) -> Ekg:
    """Ein EKG-Beiwerk lesen — das von praxis_gui wie das der trainingsapp.

    Raises:
        ValueError: kein EKG-Beiwerk (``uv`` fehlt).
    """
    with open(pfad, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict) or not isinstance(doc.get("uv"), list):
        raise ValueError(f"kein EKG-Beiwerk: {pfad}")
    uv = np.asarray(doc["uv"], dtype=np.int32)
    zaehl = [int(x) for x in doc.get("frame_sample_counts") or []]
    offsets = [int(x) for x in doc.get("frame_offsets") or []]
    if not zaehl or sum(zaehl) != uv.size:
        zaehl, offsets = [int(uv.size)], [0]
    t_ns = [int(x) for x in doc.get("frame_t_ns") or []]
    if len(t_ns) != len(zaehl):
        t_ns = []
    start = doc.get("t_wall_start_s")
    return Ekg(
        rate_hz=int(doc.get("sample_rate_hz") or EKG_RATE_HZ),
        uv=uv,
        frame_offsets=offsets,
        frame_sample_counts=zaehl,
        frame_t_ns=t_ns,
        gaps=[g for g in doc.get("gaps") or [] if isinstance(g, dict)],
        t_wall_start_s=float(start) if isinstance(start, int | float) else 0.0,
        batterie=[list(b) for b in doc.get("batterie") or [] if isinstance(b, list)],
    )


__all__ = [
    "EKG_ENDUNG",
    "EKG_JOURNAL_ENDUNG",
    "EKG_RATE_HZ",
    "Ekg",
    "EkgSammler",
    "ekg_journal_pfad",
    "ekg_laden",
    "ekg_pfad",
]
