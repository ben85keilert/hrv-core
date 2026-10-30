"""Herzfrequenz: Reihe, Ruhe- und Spitzenwerte, Bereiche, Erholung, Last — für beide Apps.

Die HRV-Kennzahlen rechnen auf der **Herzuhr** (Summe der RR-Intervalle). Die Herzfrequenz
rechnet auf der **Wanduhr** (``t_wall_s``): Ein reiner Pulsgeber (``bpm_only``) liefert keine
RR-Intervalle, seine Herzuhr bleibt bei 0 — auf ihr gäbe es weder Dauer noch Abschnitte
(hrv-research, Entscheidung 16). Grundlage aller Funktionen ist deshalb `HfReihe`: die
Herzfrequenz im **1-s-Raster** auf der Wanduhr, je Sekunde mit ihrer Quelle:

- ``QUELLE_RR``: ``60000 / RR`` der gültigen, nicht als Artefakt markierten Schläge der
  Sekunde (Mittel); Sekunden ohne Schlag werden bis `HF_LUECKE_S` linear gefüllt — bei
  40 bpm liegen 1,5 s zwischen zwei Schlägen, das ist keine Lücke.
- ``QUELLE_GERAET``: die vom Gerät gemeldete Herzfrequenz, wo RR fehlen (Paket ohne RR,
  Artefaktkette, reiner Pulsgeber). Der H10 glättet und hinkt 1–3 s nach; aus RR ist die
  bessere Live-Größe, deshalb hat RR Vorrang.
- ``QUELLE_KEINE``: nichts innerhalb von `HF_LUECKE_S` — NaN. Zählt in keinem Fenster,
  keinem Bereich, keiner Last.

Rechenvorschriften (INTERLIVE, `schumann2025interlive`; hrv-research `KONZEPT_HF_APP.md`,
Entscheidungen 11–16):

| Größe | Vorschrift |
|---|---|
| Ruhe-HF morgens | tiefstes 30-s-Rollmittel in ≥ 5 min liegend, Artefaktanteil < 5 % |
| Nacht-HF | tiefstes 2-h-Rollmittel in der bestätigten Schlafzeit (≥ 4 h) |
| Tagesminimum | tiefstes 10-min-Rollmittel eines Tages mit ≥ 10 h Daten |
| HFmax-Kandidat | höchstes 30-s-Rollmittel; Plateau (30 s davor ≥ 80 %), Artefakt < 5 % |
| %HRR | (HF − Ruhe) / (HFmax − Ruhe) · 100 |
| Schwellen | Milani-Gleichungen aus Ruhe- und Spitzen-HF (`milani2024equations`, ESC-Reha 2026) |
| Erholung | HF_ende = Mittel 5 s vor t0; HRR_t = HF_ende − Mittel 5 s um t0 + t (30, 60, 120) |
| TRIMP | Banister: Σ min · r · 0,64·e^(1,92 r), Frauen 0,86·e^(1,67 r), r = %HRR/100 |

Die Bibliothek **bewertet nicht**: keine Ampel, kein „zu hoch“, keine Normgrenze. Sie liefert
Zahlen mit Quelle und Unsicherheit; was daraus folgt, sagt die Person (trainingsapp solo)
oder das Fachpersonal (praxis_gui). Deshalb heißen Bereiche hier „Bereich 1…n“, und
Vorschlagswerte (Formel, Schätzung) tragen ihre Streuung mit.

Referenzfassung mit pandas-Rolling: hrv-research ``src/hrv_research/hf_referenz.py``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final

import numpy as np

from .constants import (
    HF_ARTEFAKT_MAX,
    HF_BOUT_ENDE_S,
    HF_BOUT_MIN_S,
    HF_BOUT_PROZENT,
    HF_ERHOLUNG_FENSTER_S,
    HF_ERHOLUNG_MITTEL_S,
    HF_FENSTER_ANTEIL,
    HF_GIPFEL_S,
    HF_LUECKE_S,
    HF_MAX_FENSTER_S,
    HF_MAX_PLATEAU,
    HF_MAX_SPRUNG,
    HF_NACHT_FENSTER_S,
    HF_NACHT_MIN_S,
    HF_RASTER_S,
    HF_RUHE_FENSTER_S,
    HF_RUHE_MIN_S,
    HF_RUHE_MIN_S_PHASE,
    HF_SCHLAF_MIN_S,
    HF_TAG_FENSTER_S,
    HF_TAG_GUELTIG_S,
    HF_TAG_MIN_S,
    RR_MAX_MS,
    RR_MIN_MS,
)
from .recording import Beat

# ---------------------------------------------------------------------------
# Quellen je Sekunde
# ---------------------------------------------------------------------------
QUELLE_KEINE: Final[int] = 0
QUELLE_RR: Final[int] = 1
QUELLE_GERAET: Final[int] = 2


@dataclass(slots=True)
class HfReihe:
    """Herzfrequenz im festen Raster auf der Wanduhr.

    ``t[k]`` ist der **Anfang** der k-ten Rasterzelle (Sekunden der Wanduhr); die Zelle
    deckt ``[t[k], t[k] + raster_s)``. ``hf`` ist NaN, wo nichts vorliegt; ``quelle``
    sagt je Zelle, woher der Wert stammt; ``n_rr``/``n_artefakt`` zählen die Schläge mit
    RR und davon die markierten — daraus entsteht der Artefaktanteil eines Fensters.
    """

    t: np.ndarray
    hf: np.ndarray
    quelle: np.ndarray
    n_rr: np.ndarray
    n_artefakt: np.ndarray
    raster_s: float = HF_RASTER_S

    @property
    def n(self) -> int:
        return int(self.t.size)

    @property
    def dauer_s(self) -> float:
        """Spanne der Reihe (erste bis hinter die letzte Zelle)."""
        return float(self.n * self.raster_s)

    def gueltig(self) -> np.ndarray:
        return ~np.isnan(self.hf)

    def abgedeckt_s(self, von: float | None = None, bis: float | None = None) -> float:
        """Sekunden mit Wert im Bereich ``[von, bis)``."""
        m = self.maske(von, bis) & self.gueltig()
        return float(m.sum() * self.raster_s)

    def maske(self, von: float | None = None, bis: float | None = None) -> np.ndarray:
        """Zellen, deren Anfang in ``[von, bis)`` liegt."""
        m = np.ones(self.n, dtype=bool)
        if von is not None:
            m &= self.t >= von
        if bis is not None:
            m &= self.t < bis
        return m

    def index(self, t: float) -> int:
        """Index der Zelle, die ``t`` enthält (auch außerhalb: geklemmt)."""
        if self.n == 0:
            return 0
        i = math.floor((t - float(self.t[0])) / self.raster_s)
        return min(max(i, 0), self.n - 1)

    def artefaktanteil(self, von: float | None = None, bis: float | None = None) -> float | None:
        """Markierte / alle Schläge mit RR im Bereich; None ohne RR-Schläge."""
        m = self.maske(von, bis)
        n = int(self.n_rr[m].sum())
        if n == 0:
            return None
        return float(self.n_artefakt[m].sum()) / n


def wanduhr(beats: Sequence[Beat]) -> np.ndarray:
    """Zeit je Schlag auf der Wanduhr; ohne Wanduhr (corrected-v1) die Herzuhr.

    >>> wanduhr([Beat(0.8, 800, 75, 1.0), Beat(1.6, 800, 75, 2.0)]).tolist()
    [1.0, 2.0]
    >>> wanduhr([Beat(0.8, 800), Beat(1.6, 800)]).tolist()
    [0.8, 1.6]
    """
    if beats and all(b.t_wall_s is not None for b in beats):
        return np.asarray([float(b.t_wall_s) for b in beats], dtype=float)  # type: ignore[arg-type]
    return np.asarray([float(b.t_s) for b in beats], dtype=float)


# ---------------------------------------------------------------------------
# Die Reihe
# ---------------------------------------------------------------------------


def _fuellen(werte: np.ndarray, max_zellen: int) -> np.ndarray:
    """Leere Zellen (NaN) linear füllen, wenn die Nachbarn höchstens ``max_zellen``
    Zellen auseinanderliegen; Ränder bleiben leer."""
    out = werte.copy()
    n = out.size
    if n == 0:
        return out
    voll = ~np.isnan(out)
    if voll.all() or not voll.any():
        return out
    idx = np.arange(n)
    # letzter gefüllter Index bis hier (einschließlich) …
    vor = np.where(voll, idx, -1)
    vor = np.maximum.accumulate(vor)
    # … und nächster gefüllter Index ab hier
    nach = np.where(voll, idx, n)
    nach = np.minimum.accumulate(nach[::-1])[::-1]
    leer = ~voll & (vor >= 0) & (nach < n) & ((nach - vor) <= max_zellen)
    if leer.any():
        a, b = vor[leer], nach[leer]
        w = (idx[leer] - a) / (b - a)
        out[leer] = out[a] * (1 - w) + out[b] * w
    return out


def _zellmittel(idx: np.ndarray, werte: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Mittel je Zelle und Anzahl je Zelle."""
    anzahl = np.bincount(idx, minlength=n).astype(float)
    summe = np.bincount(idx, weights=werte, minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        mittel = np.where(anzahl > 0, summe / anzahl, np.nan)
    return mittel, anzahl


def hf_reihe(
    t: Sequence[float] | np.ndarray,
    rr_ms: Sequence[float] | np.ndarray,
    hf_bpm: Sequence[float] | np.ndarray | None = None,
    *,
    artefakt: Sequence[bool] | np.ndarray | None = None,
    raster_s: float = HF_RASTER_S,
    luecke_s: float = HF_LUECKE_S,
    anfang: float | None = None,
    ende: float | None = None,
) -> HfReihe:
    """Herzfrequenz je Rasterzelle aus Schlagzeiten, RR und Geräte-HF (Modulkopf).

    Args:
        t: Zeit je Schlag (Wanduhr, s), aufsteigend.
        rr_ms: RR je Schlag; 0 = Paket ohne RR. Außerhalb 250–2000 ms zählt nicht.
        hf_bpm: vom Gerät gemeldete Herzfrequenz je Schlag; 0 = keine.
        artefakt: je Schlag ``True``, wenn markiert (dann zählt sein RR nicht).
        anfang, ende: Rasterbereich; Vorgabe: erste bis letzte Schlagzeit.

    >>> r = hf_reihe([0.5, 1.5, 2.5, 8.5], [1000, 1000, 1000, 1000], [60, 60, 60, 60])
    >>> r.t.tolist()
    [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    >>> r.hf.tolist()                    # 6 s ohne Schlag: Lücke (über HF_LUECKE_S)
    [60.0, 60.0, 60.0, nan, nan, nan, nan, nan, 60.0]
    >>> r.quelle.tolist()
    [1, 1, 1, 0, 0, 0, 0, 0, 1]
    >>> hf_reihe([0.5, 1.5], [0, 0], [72, 74]).hf.tolist()   # reiner Pulsgeber
    [72.0, 74.0]
    """
    ts = np.asarray(t, dtype=float)
    rr = np.asarray(rr_ms, dtype=float)
    if rr.shape != ts.shape:
        raise ValueError("t und rr_ms müssen gleich lang sein")
    hf = np.zeros_like(ts) if hf_bpm is None else np.asarray(hf_bpm, dtype=float).reshape(ts.shape)
    art = (
        np.zeros(ts.shape, dtype=bool)
        if artefakt is None
        else np.asarray(artefakt, dtype=bool).reshape(ts.shape)
    )
    if raster_s <= 0:
        raise ValueError("raster_s muss positiv sein")
    if ts.size == 0 and (anfang is None or ende is None):
        leer = np.zeros(0)
        return HfReihe(
            leer, leer, leer.astype(np.int8), leer.astype(int), leer.astype(int), raster_s
        )
    t0 = math.floor((float(ts.min()) if anfang is None else anfang) / raster_s) * raster_s
    t1 = float(ts.max()) if ende is None else ende
    n = max(1, math.floor((t1 - t0) / raster_s) + 1)
    achse = t0 + np.arange(n) * raster_s

    im = (ts >= t0) & (ts < t0 + n * raster_s)
    idx = np.floor((ts[im] - t0) / raster_s).astype(int)
    rr_i, hf_i, art_i = rr[im], hf[im], art[im]

    hat_rr = (rr_i >= RR_MIN_MS) & (rr_i <= RR_MAX_MS)
    gut = hat_rr & ~art_i
    aus_rr, _ = _zellmittel(idx[gut], 60000.0 / rr_i[gut], n)
    hat_geraet = hf_i > 0
    aus_geraet, _ = _zellmittel(idx[hat_geraet], hf_i[hat_geraet], n)
    n_rr = np.bincount(idx[hat_rr], minlength=n)
    n_art = np.bincount(idx[hat_rr & art_i], minlength=n)

    max_zellen = math.floor(luecke_s / raster_s)
    aus_rr = _fuellen(aus_rr, max_zellen)
    aus_geraet = _fuellen(aus_geraet, max_zellen)

    quelle = np.full(n, QUELLE_KEINE, dtype=np.int8)
    werte = np.full(n, np.nan)
    g = ~np.isnan(aus_geraet)
    werte[g] = aus_geraet[g]
    quelle[g] = QUELLE_GERAET
    r = ~np.isnan(aus_rr)
    werte[r] = aus_rr[r]
    quelle[r] = QUELLE_RR
    return HfReihe(achse, werte, quelle, n_rr.astype(int), n_art.astype(int), raster_s)


def reihe_aus_beats(
    beats: Sequence[Beat],
    *,
    artefakt: Sequence[bool] | np.ndarray | None = None,
    raster_s: float = HF_RASTER_S,
    luecke_s: float = HF_LUECKE_S,
) -> HfReihe:
    """`hf_reihe` direkt aus den Zeilen einer Messung (Wanduhr, RR, Geräte-HF)."""
    return hf_reihe(
        wanduhr(beats),
        [b.rr_ms for b in beats],
        [b.hf_bpm for b in beats],
        artefakt=artefakt,
        raster_s=raster_s,
        luecke_s=luecke_s,
    )


def auf_raster(
    t_quelle: Sequence[float] | np.ndarray,
    werte: Sequence[float] | np.ndarray,
    reihe: HfReihe,
    *,
    luecke_s: float = HF_LUECKE_S,
) -> np.ndarray:
    """Eine andere Größe (Tempo, Leistung) auf das Raster der Reihe bringen: Mittel je
    Zelle, Lücken bis ``luecke_s`` linear gefüllt, sonst NaN.

    >>> r = hf_reihe([0.5, 1.5, 2.5], [1000] * 3)
    >>> auf_raster([0.2, 2.2], [3.0, 5.0], r).tolist()
    [3.0, 4.0, 5.0]
    """
    tq = np.asarray(t_quelle, dtype=float)
    w = np.asarray(werte, dtype=float)
    n = reihe.n
    if n == 0:
        return np.zeros(0)
    im = (tq >= reihe.t[0]) & (tq < reihe.t[0] + n * reihe.raster_s) & ~np.isnan(w)
    idx = np.floor((tq[im] - reihe.t[0]) / reihe.raster_s).astype(int)
    mittel, _ = _zellmittel(idx, w[im], n)
    return _fuellen(mittel, math.floor(luecke_s / reihe.raster_s))


# ---------------------------------------------------------------------------
# Rollfenster
# ---------------------------------------------------------------------------


def rollmittel(
    hf: np.ndarray,
    fenster_s: float,
    *,
    raster_s: float = HF_RASTER_S,
    min_anteil: float = HF_FENSTER_ANTEIL,
) -> np.ndarray:
    """Nachlaufendes gleitendes Mittel über ``fenster_s``, NaN-tolerant.

    Wert an Stelle ``i`` = Mittel der gültigen Zellen ``i − n + 1 … i`` (``n`` Zellen je
    Fenster), wenn mindestens ``min_anteil · n`` davon gültig sind; sonst NaN. Die ersten
    ``n − 1`` Stellen sind NaN (kein volles Fenster).

    >>> rollmittel(np.array([60.0, 62.0, 64.0, np.nan, 66.0]), 2.0).tolist()
    [nan, 61.0, 63.0, nan, nan]
    >>> rollmittel(np.array([60.0, 62.0, 64.0, np.nan, 66.0]), 2.0, min_anteil=0.5).tolist()
    [nan, 61.0, 63.0, 64.0, 66.0]
    """
    x = np.asarray(hf, dtype=float)
    n = round(fenster_s / raster_s)
    if n < 1:
        raise ValueError("Fenster kürzer als eine Rasterzelle")
    out = np.full(x.size, np.nan)
    if x.size < n:
        return out
    gueltig = ~np.isnan(x)
    summe = np.concatenate(([0.0], np.cumsum(np.where(gueltig, x, 0.0))))
    anzahl = np.concatenate(([0], np.cumsum(gueltig.astype(int))))
    s = summe[n:] - summe[:-n]
    k = anzahl[n:] - anzahl[:-n]
    genug = k >= max(1, math.ceil(min_anteil * n - 1e-9))
    with np.errstate(invalid="ignore", divide="ignore"):
        werte = np.where(genug, s / np.where(k > 0, k, 1), np.nan)
    out[n - 1 :] = werte
    return out


def _rollsumme(x: np.ndarray, n: int) -> np.ndarray:
    """Nachlaufende Summe über ``n`` Zellen (erste ``n − 1`` Stellen NaN)."""
    out = np.full(x.size, np.nan)
    if x.size < n:
        return out
    c = np.concatenate(([0.0], np.cumsum(np.asarray(x, dtype=float))))
    out[n - 1 :] = c[n:] - c[:-n]
    return out


@dataclass(slots=True)
class Fensterwert:
    """Ergebnis einer Fenstersuche (Ruhe-HF, Nacht-HF, Tagesminimum, HFmax-Kandidat).

    ``wert`` ist das Fenstermittel in bpm, ``t_von``/``t_bis`` das Fenster auf der Wanduhr.
    ``gueltig`` sagt, ob die Vorschrift erfüllt ist; ``gruende`` nennt, was fehlt. Ein
    ungültiger Wert wird trotzdem geliefert (als Zahl mit Vorbehalt), nie erfunden.
    """

    wert: float | None
    t_von: float | None
    t_bis: float | None
    gueltig: bool
    gruende: list[str] = field(default_factory=list)
    abgedeckt_s: float = 0.0
    artefaktanteil: float | None = None
    quelle: int = QUELLE_KEINE

    def als_dict(self) -> dict[str, Any]:
        return {
            "wert": self.wert,
            "t_von": self.t_von,
            "t_bis": self.t_bis,
            "gueltig": self.gueltig,
            "gruende": list(self.gruende),
            "abgedeckt_s": self.abgedeckt_s,
            "artefaktanteil": self.artefaktanteil,
            "quelle": self.quelle,
        }


def _quelle_im_fenster(reihe: HfReihe, i0: int, i1: int) -> int:
    """Vorherrschende Quelle der Zellen ``i0 … i1`` (einschließlich)."""
    q = reihe.quelle[i0 : i1 + 1]
    n_rr = int((q == QUELLE_RR).sum())
    n_ger = int((q == QUELLE_GERAET).sum())
    if n_rr == 0 and n_ger == 0:
        return QUELLE_KEINE
    return QUELLE_RR if n_rr >= n_ger else QUELLE_GERAET


def _extrem(
    reihe: HfReihe,
    fenster_s: float,
    *,
    kleinstes: bool,
    von: float | None,
    bis: float | None,
    mindest_s: float,
    artefakt_max: float | None,
    min_anteil: float = HF_FENSTER_ANTEIL,
) -> Fensterwert:
    """Gemeinsamer Kern von Ruhe-HF, Nacht-HF und Tagesminimum."""
    gruende: list[str] = []
    m = reihe.maske(von, bis)
    abgedeckt = reihe.abgedeckt_s(von, bis)
    anteil = reihe.artefaktanteil(von, bis)
    if abgedeckt < mindest_s:
        gruende.append(f"zu wenig Daten ({abgedeckt:.0f} s, nötig {mindest_s:.0f} s)")
    if artefakt_max is not None and anteil is not None and anteil > artefakt_max:
        gruende.append(f"Artefaktanteil {100 * anteil:.1f} % über {100 * artefakt_max:.0f} %")
    hf = np.where(m, reihe.hf, np.nan)
    roll = rollmittel(hf, fenster_s, raster_s=reihe.raster_s, min_anteil=min_anteil)
    n = round(fenster_s / reihe.raster_s)
    if np.isnan(roll).all():
        gruende.append("kein volles Fenster")
        return Fensterwert(None, None, None, False, gruende, abgedeckt, anteil)
    i = int(np.nanargmin(roll) if kleinstes else np.nanargmax(roll))
    i0 = i - n + 1
    return Fensterwert(
        float(roll[i]),
        float(reihe.t[i0]),
        float(reihe.t[i] + reihe.raster_s),
        not gruende,
        gruende,
        abgedeckt,
        anteil,
        _quelle_im_fenster(reihe, i0, i),
    )


def ruhe_hf_morgen(
    reihe: HfReihe,
    von: float | None = None,
    bis: float | None = None,
    *,
    fenster_s: float = HF_RUHE_FENSTER_S,
    mindest_s: float = HF_RUHE_MIN_S,
    artefakt_max: float = HF_ARTEFAKT_MAX,
) -> Fensterwert:
    """Ruhe-HF einer Morgenmessung: tiefstes 30-s-Rollmittel in ``[von, bis)``.

    Gültig ab 5 min Daten (INTERLIVE empfiehlt 10 min liegend) und unter 5 % Artefakten.
    """
    return _extrem(
        reihe,
        fenster_s,
        kleinstes=True,
        von=von,
        bis=bis,
        mindest_s=mindest_s,
        artefakt_max=artefakt_max,
    )


def nacht_hf(
    reihe: HfReihe,
    schlaf_von: float,
    schlaf_bis: float,
    *,
    fenster_s: float = HF_NACHT_FENSTER_S,
    mindest_s: float = HF_NACHT_MIN_S,
) -> Fensterwert:
    """Nacht-HF: tiefstes 2-h-Rollmittel in der bestätigten Schlafzeit (≥ 4 h Daten).

    Die Schlafzeit gibt die Person an oder bestätigt sie (`schlaf_kandidat`); kein
    Hersteller-Schlaferkenner (INTERLIVE).
    """
    return _extrem(
        reihe,
        fenster_s,
        kleinstes=True,
        von=schlaf_von,
        bis=schlaf_bis,
        mindest_s=mindest_s,
        artefakt_max=None,
    )


def tagesminimum(
    reihe: HfReihe,
    von: float | None = None,
    bis: float | None = None,
    *,
    fenster_s: float = HF_TAG_FENSTER_S,
    mindest_s: float = HF_TAG_MIN_S,
) -> Fensterwert:
    """Tagesminimum: tiefstes 10-min-Rollmittel eines Tages mit ≥ 10 h Daten — Ersatz
    für die Ruhe-HF, wenn weder Morgen- noch Nachtmessung vorliegt."""
    return _extrem(
        reihe,
        fenster_s,
        kleinstes=True,
        von=von,
        bis=bis,
        mindest_s=mindest_s,
        artefakt_max=None,
    )


def hfmax_kandidat(
    reihe: HfReihe,
    von: float | None = None,
    bis: float | None = None,
    *,
    fenster_s: float = HF_MAX_FENSTER_S,
    plateau_anteil: float = HF_MAX_PLATEAU,
    artefakt_max: float = HF_ARTEFAKT_MAX,
    sprung_max: float = HF_MAX_SPRUNG,
) -> Fensterwert:
    """HFmax-Kandidat: das höchste 30-s-Rollmittel, das drei Prüfungen besteht.

    1. Artefaktanteil im Fenster < 5 % (bei Geräte-HF ohne RR entfällt die Prüfung,
       die Quelle steht im Ergebnis);
    2. kein Sprung > 30 % zwischen zwei Zellen im Fenster (Kontaktverlust, Doppelzählung);
    3. Plateau: das Mittel der 30 s davor erreicht ≥ 80 % des Kandidaten — eine
       Einzelspitze aus dem Stand ist kein Maximum.

    Besteht kein Fenster, kommt das höchste Fenster mit ``gueltig = False`` und den
    Gründen zurück. Die App **schlägt** den Kandidaten vor; gesetzt wird er nur durch
    die Person (Entscheidung 12).
    """
    m = reihe.maske(von, bis)
    hf = np.where(m, reihe.hf, np.nan)
    n = round(fenster_s / reihe.raster_s)
    roll = rollmittel(hf, fenster_s, raster_s=reihe.raster_s, min_anteil=1.0)
    if np.isnan(roll).all():
        return Fensterwert(
            None, None, None, False, ["kein volles Fenster"], reihe.abgedeckt_s(von, bis)
        )
    # Prüfgrößen je Fensterende
    n_rr = _rollsumme(reihe.n_rr.astype(float), n)
    n_art = _rollsumme(reihe.n_artefakt.astype(float), n)
    with np.errstate(invalid="ignore", divide="ignore"):
        anteil = np.where(n_rr > 0, n_art / n_rr, 0.0)
    rel = np.abs(np.diff(hf, prepend=np.nan)) / np.where(np.isnan(hf), np.nan, hf)
    rel = np.where(np.isnan(rel), 0.0, rel)
    fenster = np.lib.stride_tricks.sliding_window_view(rel, n)
    sprung = np.full(hf.size, 0.0)
    sprung[n - 1 :] = fenster.max(axis=1)
    davor = np.full(hf.size, np.nan)
    davor[n:] = roll[:-n]
    kandidaten = np.argsort(-np.where(np.isnan(roll), -np.inf, roll))
    bestes: Fensterwert | None = None
    for i in kandidaten:
        if np.isnan(roll[i]):
            break
        gruende: list[str] = []
        if anteil[i] > artefakt_max:
            gruende.append(f"Artefaktanteil {100 * anteil[i]:.1f} %")
        if sprung[i] > sprung_max:
            gruende.append(f"Sprung {100 * sprung[i]:.0f} % im Fenster")
        if np.isnan(davor[i]):
            gruende.append("kein Plateau prüfbar (Fenster davor fehlt)")
        elif davor[i] < plateau_anteil * roll[i]:
            gruende.append(f"kein Plateau ({davor[i]:.0f} bpm davor)")
        i0 = int(i) - n + 1
        fw = Fensterwert(
            float(roll[i]),
            float(reihe.t[i0]),
            float(reihe.t[i] + reihe.raster_s),
            not gruende,
            gruende,
            reihe.abgedeckt_s(von, bis),
            float(anteil[i]) if n_rr[i] > 0 else None,
            _quelle_im_fenster(reihe, i0, int(i)),
        )
        if fw.gueltig:
            return fw
        if bestes is None:
            bestes = fw
    assert bestes is not None
    return bestes


# ---------------------------------------------------------------------------
# Formeln, Reserve, Schwellen
# ---------------------------------------------------------------------------

#: HFmax-Formeln: (a, b, SEE, Name) für HFmax = a − b · Alter. 220 − Alter fehlt bewusst
#: (keine Datengrundlage, `robergs2002hrmax`). SEE: Nes 10,8 (publiziert); Tanaka ±10
#: (Streuung um die Regression, publiziert); Gulati ohne publizierten SEE — hier wie Nes
#: angesetzt, bis der Originalwert geprüft ist (hrv-research `literatur/heart-rate/`).
FORMELN: Final[dict[str, tuple[float, float, float, str]]] = {
    "nes": (211.0, 0.64, 10.8, "Nes 2013 (HUNT)"),
    "tanaka": (208.0, 0.7, 10.0, "Tanaka 2001"),
    "gulati": (206.0, 0.88, 10.8, "Gulati 2010 (Frauen)"),
}
FORMEL_MIN_ALTER: Final[int] = 18


@dataclass(frozen=True, slots=True)
class Formelwert:
    wert: float | None
    see: float
    formel: str
    name: str
    gueltig: bool
    grund: str = ""


def formel_hfmax(alter: float, formel: str = "nes") -> Formelwert:
    """HFmax aus dem Alter — ein **Startwert** mit Streuung, nie eine Messung.

    >>> f = formel_hfmax(40)
    >>> f.wert, f.see, f.gueltig
    (185.4, 10.8, True)
    >>> formel_hfmax(15).gueltig
    False
    """
    if formel not in FORMELN:
        raise ValueError(f"unbekannte Formel {formel!r}; bekannt: {sorted(FORMELN)}")
    a, b, see, name = FORMELN[formel]
    if alter < FORMEL_MIN_ALTER:
        return Formelwert(None, see, formel, name, False, f"Formel gilt ab {FORMEL_MIN_ALTER}")
    return Formelwert(round(a - b * float(alter), 1), see, formel, name, True)


def prozent_hrr(hf: float | np.ndarray, ruhe: float, hfmax: float) -> float | np.ndarray:
    """Prozent der Herzfrequenzreserve (Karvonen). Außerhalb 0–100 ist erlaubt (Rohwert).

    >>> prozent_hrr(120.0, 60.0, 180.0)
    50.0
    """
    if hfmax <= ruhe:
        raise ValueError("HFmax muss über der Ruhe-HF liegen")
    return (
        (np.asarray(hf, dtype=float) - ruhe) / (hfmax - ruhe) * 100.0
        if isinstance(hf, np.ndarray)
        else (float(hf) - ruhe) / (hfmax - ruhe) * 100.0
    )


def hf_aus_prozent(prozent: float, ruhe: float, hfmax: float) -> float:
    """Herzfrequenz zu einem Prozentsatz der Reserve.

    >>> hf_aus_prozent(50.0, 60.0, 180.0)
    120.0
    """
    if hfmax <= ruhe:
        raise ValueError("HFmax muss über der Ruhe-HF liegen")
    return ruhe + prozent / 100.0 * (hfmax - ruhe)


#: Milani et al. 2024 (`milani2024equations`), übernommen von der ESC-Reha-Leitlinie 2026:
#: HF an VT1/VT2 aus Spitzen- und Ruhe-HF; mittlerer absoluter Fehler 7,1 % bzw. 5,0 %.
MILANI_VT1: Final[tuple[float, float, float]] = (4.866, 0.405, 0.542)
MILANI_VT2: Final[tuple[float, float, float]] = (-2.606, 0.773, 0.254)
MILANI_MAE: Final[tuple[float, float]] = (0.071, 0.050)


@dataclass(frozen=True, slots=True)
class Schwellen:
    vt1: float
    vt2: float
    unsicherheit_vt1: float
    unsicherheit_vt2: float
    vt1_prozent: float
    vt2_prozent: float


def schwellen_milani(hf_peak: float, hf_ruhe: float) -> Schwellen:
    """HF an VT1 und VT2 aus **gemessener** Spitzen-HF und Ruhe-HF.

    Herkunft: Fahrradergometrie bei kardiometabolischen Patienten; für Gesunde eine
    Extrapolation, mit Formel-HFmax statt Peak erbt sie deren Fehler — beides sagt die
    App dazu.

    >>> s = schwellen_milani(185, 55)
    >>> round(s.vt1), round(s.vt2), round(s.vt1_prozent), round(s.vt2_prozent)
    (110, 154, 42, 76)
    """
    a1, b1, c1 = MILANI_VT1
    a2, b2, c2 = MILANI_VT2
    vt1 = a1 + b1 * hf_peak + c1 * hf_ruhe
    vt2 = a2 + b2 * hf_peak + c2 * hf_ruhe
    return Schwellen(
        vt1,
        vt2,
        MILANI_MAE[0] * vt1,
        MILANI_MAE[1] * vt2,
        float(prozent_hrr(vt1, hf_ruhe, hf_peak)),
        float(prozent_hrr(vt2, hf_ruhe, hf_peak)),
    )


# ---------------------------------------------------------------------------
# Bereiche
# ---------------------------------------------------------------------------

MODELL_DREI: Final[str] = "drei"
MODELL_ACSM: Final[str] = "acsm"
MODELL_CLUSTER: Final[str] = "cluster"
MODELL_EIGEN: Final[str] = "eigen"
#: Grenzen in % HRR je Modell (Eigen: von der Person)
MODELLE: Final[dict[str, tuple[float, ...]]] = {
    MODELL_DREI: (42.0, 77.0),
    MODELL_ACSM: (30.0, 40.0, 60.0, 90.0),
    MODELL_CLUSTER: tuple(float(x) for x in range(10, 100, 10)),
}
#: Beschriftung: ACSM nennt Intensitätsstufen (Leitlinienbegriffe, kein Urteil);
#: die anderen Modelle zählen durch (Stufe A: nie „Fettverbrennung“ oder „gesund“).
ACSM_NAMEN: Final[tuple[str, ...]] = (
    "sehr leicht",
    "leicht",
    "moderat",
    "anstrengend",
    "nahe maximal",
)
#: Unsicherheit einer Grenze in % HRR nach Herkunft (Entscheidung 13)
GRENZE_UNSICHERHEIT_PROZENT: Final[dict[str, float]] = {
    "labor": 2.5,
    "talk_test": 5.0,
    "milani": 6.0,
    "prozent_hrr": 6.0,
    "eigen": 0.0,
}


@dataclass(frozen=True, slots=True)
class Bereich:
    name: str
    von_bpm: float
    bis_bpm: float
    von_prozent: float
    bis_prozent: float
    #: Unsicherheit der **oberen** Grenze in bpm (0 beim offenen Ende)
    unsicherheit_bpm: float

    def enthaelt(self, hf: float) -> bool:
        return self.von_bpm <= hf < self.bis_bpm


def grenzen_prozent(modell: str, eigene: Sequence[float] | None = None) -> tuple[float, ...]:
    """Grenzen (% HRR) eines Modells; ``eigen`` nimmt die übergebenen, aufsteigend.

    >>> grenzen_prozent("drei"), grenzen_prozent("eigen", [50, 30])
    ((42.0, 77.0), (30.0, 50.0))
    """
    if modell == MODELL_EIGEN:
        return tuple(sorted(float(x) for x in (eigene or ())))
    if modell not in MODELLE:
        raise ValueError(f"unbekanntes Modell {modell!r}; bekannt: {sorted(MODELLE)}")
    return MODELLE[modell]


def grenz_unsicherheit_bpm(
    prozent: float, hrr_bpm: float, *, quelle_prozent: float, hfmax_bpm: float
) -> float:
    """Unsicherheit einer Grenze bei ``prozent`` % HRR in bpm:
    √((Quellfehler · HRR)² + (prozent · HFmax-Fehler)²) — der HFmax-Fehler geht anteilig
    ein, weil HF(x) = Ruhe + x · (HFmax − Ruhe).

    >>> round(grenz_unsicherheit_bpm(77, 130, quelle_prozent=6, hfmax_bpm=10.8), 1)
    11.4
    """
    return math.hypot(quelle_prozent / 100.0 * hrr_bpm, prozent / 100.0 * hfmax_bpm)


def bereiche(
    modell: str,
    ruhe: float,
    hfmax: float,
    *,
    eigene_prozent: Sequence[float] | None = None,
    eigene_bpm: Sequence[float] | None = None,
    namen: Sequence[str] | None = None,
    unsicherheit_hfmax_bpm: float = 0.0,
    unsicherheit_grenze_prozent: float | Sequence[float] = 0.0,
) -> list[Bereich]:
    """Bereiche eines Modells in bpm und % HRR, mit Unsicherheitsband je Grenze.

    ``eigene_bpm`` (Modell ``eigen``) setzt Grenzen direkt in bpm; sonst gelten
    Prozentgrenzen. Der erste Bereich beginnt bei der Ruhe-HF, der letzte endet bei HFmax
    (offen nach oben: ``bis_bpm`` = HFmax, die Zuordnung `bereich_index` klemmt).

    >>> b = bereiche("drei", 60, 180, unsicherheit_grenze_prozent=6)
    >>> [(x.name, round(x.von_bpm), round(x.bis_bpm)) for x in b]
    [('Bereich 1', 60, 110), ('Bereich 2', 110, 152), ('Bereich 3', 152, 180)]
    """
    if hfmax <= ruhe:
        raise ValueError("HFmax muss über der Ruhe-HF liegen")
    hrr = hfmax - ruhe
    if modell == MODELL_EIGEN and eigene_bpm is not None:
        bpm = tuple(sorted(float(x) for x in eigene_bpm))
        prozent = tuple(float(prozent_hrr(x, ruhe, hfmax)) for x in bpm)
    else:
        prozent = grenzen_prozent(modell, eigene_prozent)
        bpm = tuple(hf_aus_prozent(p, ruhe, hfmax) for p in prozent)
    k = len(prozent) + 1
    if isinstance(unsicherheit_grenze_prozent, (int, float)):
        quell = [float(unsicherheit_grenze_prozent)] * len(prozent)
    else:
        quell = [float(x) for x in unsicherheit_grenze_prozent]
        if len(quell) != len(prozent):
            raise ValueError("eine Unsicherheit je Grenze")
    if namen is None:
        namen = ACSM_NAMEN if modell == MODELL_ACSM else tuple(f"Bereich {i + 1}" for i in range(k))
    if len(namen) != k:
        raise ValueError(f"{k} Namen nötig, {len(namen)} gegeben")
    von_p = (0.0, *prozent)
    bis_p = (*prozent, 100.0)
    von_b = (ruhe, *bpm)
    bis_b = (*bpm, hfmax)
    out = []
    for i in range(k):
        u = (
            grenz_unsicherheit_bpm(
                bis_p[i], hrr, quelle_prozent=quell[i], hfmax_bpm=unsicherheit_hfmax_bpm
            )
            if i < k - 1
            else 0.0
        )
        out.append(Bereich(str(namen[i]), von_b[i], bis_b[i], von_p[i], bis_p[i], u))
    return out


def bereich_index(hf: float | np.ndarray, grenzen_bpm: Sequence[float]) -> np.ndarray:
    """Index des Bereichs je Wert: 0 unter der ersten Grenze … ``len(grenzen)`` darüber.

    >>> bereich_index(np.array([100.0, 110.0, 170.0, np.nan]), [110.0, 152.0]).tolist()
    [0, 1, 2, -1]
    """
    x = np.asarray(hf, dtype=float)
    idx = np.searchsorted(np.asarray(grenzen_bpm, dtype=float), x, side="right")
    return np.where(np.isnan(x), -1, idx).astype(int)


# ---------------------------------------------------------------------------
# Zusammenfassung eines Bezugs (Aufnahme, Abschnitt, Fenster)
# ---------------------------------------------------------------------------


def zeit_je_bereich(
    reihe: HfReihe,
    grenzen_bpm: Sequence[float],
    von: float | None = None,
    bis: float | None = None,
) -> list[float]:
    """Sekunden je Bereich in ``[von, bis)``; Lücken zählen nirgends.

    >>> r = hf_reihe([0.5, 1.5, 2.5, 3.5], [1000, 600, 500, 400])
    >>> zeit_je_bereich(r, [110.0, 130.0])
    [2.0, 1.0, 1.0]
    """
    m = reihe.maske(von, bis) & reihe.gueltig()
    idx = bereich_index(reihe.hf[m], grenzen_bpm)
    k = len(grenzen_bpm) + 1
    return [float(x) for x in np.bincount(idx, minlength=k)[:k] * reihe.raster_s]


def trimp_banister(
    reihe: HfReihe,
    ruhe: float,
    hfmax: float,
    *,
    geschlecht: str | None = None,
    von: float | None = None,
    bis: float | None = None,
) -> float | None:
    """TRIMP nach Banister: Σ Δt[min] · r · a · e^(b r), r = %HRR / 100 (geklemmt 0…1);
    Männer und ohne Angabe a = 0,64, b = 1,92; Frauen (``"w"``) 0,86 / 1,67.
    None ohne gültige Sekunde. Eine Konvention, so beschriftet — kein Normwert.

    >>> r = hf_reihe([0.5], [500], anfang=0, ende=3599)   # 60 min bei 120 bpm
    >>> round(trimp_banister(r, 60, 180), 1)
    0.0
    """
    m = reihe.maske(von, bis) & reihe.gueltig()
    if not m.any():
        return None
    a, b = (0.86, 1.67) if geschlecht == "w" else (0.64, 1.92)
    r = np.clip(np.asarray(prozent_hrr(reihe.hf[m], ruhe, hfmax)) / 100.0, 0.0, 1.0)
    return float(np.sum(reihe.raster_s / 60.0 * r * a * np.exp(b * r)))


def trimp_zonen(
    sekunden_je_bereich: Sequence[float], gewichte: Sequence[float] | None = None
) -> float:
    """Zonen-TRIMP: Minuten je Bereich mal Gewicht (Vorgabe 1, 2, 3, …).

    >>> trimp_zonen([600, 1200, 300])
    65.0
    """
    s = np.asarray(sekunden_je_bereich, dtype=float)
    g = (
        np.arange(1, s.size + 1, dtype=float)
        if gewichte is None
        else np.asarray(gewichte, dtype=float)
    )
    if g.size != s.size:
        raise ValueError("ein Gewicht je Bereich")
    return float(np.sum(s / 60.0 * g))


def zusammenfassung(
    reihe: HfReihe,
    von: float | None = None,
    bis: float | None = None,
    *,
    ruhe: float | None = None,
    hfmax: float | None = None,
    grenzen_bpm: Sequence[float] | None = None,
    geschlecht: str | None = None,
    gipfel_s: float = HF_GIPFEL_S,
) -> dict[str, Any]:
    """HF-Werte eines Bezugs: Dauer, gültige Sekunden, Ø, Gipfel (höchstes 5-s-Mittel),
    Minimum, Ø %HRR, Sekunden je Bereich, TRIMP — nur mit Profil, sonst None.

    Der Gipfel ist das höchste `gipfel_s`-Mittel, nicht die höchste Sekunde: Eine einzelne
    Sekunde ist bei RR-Rauschen und Geräte-Sprüngen kein Maximum.
    """
    m = reihe.maske(von, bis)
    g = m & reihe.gueltig()
    out: dict[str, Any] = {
        "dauer_s": float(m.sum() * reihe.raster_s),
        "gueltig_s": float(g.sum() * reihe.raster_s),
        "mittel_bpm": None,
        "gipfel_bpm": None,
        "minimum_bpm": None,
        "mittel_prozent": None,
        "sekunden_je_bereich": None,
        "trimp": None,
        "quelle_rr_anteil": None,
    }
    if not g.any():
        return out
    hf = reihe.hf[g]
    out["mittel_bpm"] = float(hf.mean())
    out["minimum_bpm"] = float(hf.min())
    roll = rollmittel(np.where(m, reihe.hf, np.nan), gipfel_s, raster_s=reihe.raster_s)
    out["gipfel_bpm"] = float(np.nanmax(roll)) if not np.isnan(roll).all() else float(hf.max())
    q = reihe.quelle[g]
    out["quelle_rr_anteil"] = float((q == QUELLE_RR).mean())
    if ruhe is not None and hfmax is not None and hfmax > ruhe:
        out["mittel_prozent"] = float(np.mean(prozent_hrr(hf, ruhe, hfmax)))
        out["trimp"] = trimp_banister(reihe, ruhe, hfmax, geschlecht=geschlecht, von=von, bis=bis)
    if grenzen_bpm is not None:
        out["sekunden_je_bereich"] = zeit_je_bereich(reihe, grenzen_bpm, von, bis)
    return out


# ---------------------------------------------------------------------------
# Erholung
# ---------------------------------------------------------------------------

KONTEXTE: Final[tuple[str, ...]] = (
    "dauer",
    "intervall",
    "sprint",
    "satz",
    "test_submaximal",
    "test_maximal",
)
HALTUNGEN: Final[tuple[str, ...]] = ("steht", "sitzt", "liegt", "geht")


@dataclass(slots=True)
class Erholung:
    """HF-Erholung nach einer Belastung, die bei ``t0`` endete.

    ``hf_nach[t]`` ist das 5-s-Mittel um ``t0 + t``; ``hrr[t] = hf_ende − hf_nach[t]``.
    Fehlt ein Wert (Lücke, Aufnahme zu kurz), steht None. ``kontext`` und ``haltung``
    setzt die App (Pflicht, Entscheidung 14); verglichen wird nur innerhalb gleicher Paare.
    """

    t0: float
    hf_ende: float | None
    hf_nach: dict[int, float | None]
    hrr: dict[int, float | None]
    kontext: str = ""
    haltung: str = ""

    def als_dict(self) -> dict[str, Any]:
        return {
            "t0": self.t0,
            "hf_ende": self.hf_ende,
            "hf_nach": {str(k): v for k, v in self.hf_nach.items()},
            "hrr": {str(k): v for k, v in self.hrr.items()},
            "kontext": self.kontext,
            "haltung": self.haltung,
        }


def _mittel_um(reihe: HfReihe, von: float, bis: float, min_anteil: float = 0.6) -> float | None:
    """Mittel der gültigen Zellen in ``[von, bis)``; None, wenn weniger als ``min_anteil``
    der **erwarteten** Zellen (auch außerhalb der Reihe) einen Wert haben."""
    m = reihe.maske(von, bis)
    erwartet = max(1, round((bis - von) / reihe.raster_s))
    w = reihe.hf[m]
    w = w[~np.isnan(w)]
    if w.size < max(1, math.ceil(min_anteil * erwartet - 1e-9)):
        return None
    return float(w.mean())


def hrr_erholung(
    reihe: HfReihe,
    t0: float,
    *,
    fenster: Sequence[int] = HF_ERHOLUNG_FENSTER_S,
    mittel_s: float = HF_ERHOLUNG_MITTEL_S,
    kontext: str = "",
    haltung: str = "",
) -> Erholung:
    """HRR30/60/120 nach Belastungsende ``t0`` (Modulkopf).

    >>> hf = [150.0] * 10 + [140.0 - i for i in range(130)]
    >>> r = hf_reihe(np.arange(140) + 0.5, [60000 / h for h in hf])
    >>> e = hrr_erholung(r, 10.0, fenster=(30, 60))
    >>> round(e.hf_ende), round(e.hrr[30]), round(e.hrr[60])
    (150, 40, 70)
    """
    halb = mittel_s / 2.0
    hf_ende = _mittel_um(reihe, t0 - mittel_s, t0)
    nach: dict[int, float | None] = {}
    hrr: dict[int, float | None] = {}
    for f in fenster:
        w = _mittel_um(reihe, t0 + f - halb, t0 + f + halb)
        nach[int(f)] = w
        hrr[int(f)] = None if (w is None or hf_ende is None) else hf_ende - w
    return Erholung(float(t0), hf_ende, nach, hrr, kontext, haltung)


# ---------------------------------------------------------------------------
# Drift, Entkopplung
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Drift:
    erste_haelfte: float | None
    zweite_haelfte: float | None
    differenz_bpm: float | None
    #: Entkopplung HF/Leistung in %: (HF/L zweite Hälfte) / (HF/L erste Hälfte) − 1;
    #: None ohne Leistungsreihe
    entkopplung_prozent: float | None


def drift(
    reihe: HfReihe,
    von: float,
    bis: float,
    *,
    leistung: np.ndarray | None = None,
) -> Drift:
    """HF der zweiten gegen die erste Hälfte eines gleichmäßigen Abschnitts; mit einer
    Leistungsreihe auf dem Raster (`auf_raster`: Tempo in m/s oder Watt) zusätzlich die
    Entkopplung in Prozent. Kein Grenzwert (die 5-%-Regel ist Trainerkonvention ohne
    Validierung) — nur die Zahl.

    >>> r = hf_reihe(np.arange(600) + 0.5, [60000 / (120 + i / 60) for i in range(600)])
    >>> d = drift(r, 0, 600)
    >>> round(d.differenz_bpm, 1)
    5.0
    """
    mitte = (von + bis) / 2.0
    a = _mittel_um(reihe, von, mitte, 0.5)
    b = _mittel_um(reihe, mitte, bis, 0.5)
    ent: float | None = None
    if leistung is not None and a is not None and b is not None:
        if leistung.shape != reihe.hf.shape:
            raise ValueError("leistung muss auf dem Raster der Reihe liegen")
        m1 = reihe.maske(von, mitte) & reihe.gueltig() & ~np.isnan(leistung) & (leistung > 0)
        m2 = reihe.maske(mitte, bis) & reihe.gueltig() & ~np.isnan(leistung) & (leistung > 0)
        if m1.any() and m2.any():
            q1 = float(reihe.hf[m1].mean() / leistung[m1].mean())
            q2 = float(reihe.hf[m2].mean() / leistung[m2].mean())
            ent = (q2 / q1 - 1.0) * 100.0
    return Drift(a, b, None if (a is None or b is None) else b - a, ent)


# ---------------------------------------------------------------------------
# Vorgeschlagene Abschnitte aus der Herzfrequenz
# ---------------------------------------------------------------------------

ART_BELASTUNG: Final[str] = "belastung"
ART_RUHE: Final[str] = "ruhe"
ART_SCHLAF: Final[str] = "schlaf"


@dataclass(frozen=True, slots=True)
class Phase:
    art: str
    von_s: float
    bis_s: float
    mittel_bpm: float

    @property
    def dauer_s(self) -> float:
        return self.bis_s - self.von_s


def _phasen(
    reihe: HfReihe,
    drin: np.ndarray,
    *,
    art: str,
    min_dauer_s: float,
    ende_s: float,
    min_anteil: float,
) -> list[Phase]:
    """Zusammenhängende Läufe von ``drin``; ein Lauf endet erst nach ``ende_s`` draußen."""
    out: list[Phase] = []
    n = reihe.n
    if n == 0:
        return out
    ende_zellen = round(ende_s / reihe.raster_s)
    start: int | None = None
    letzte_drin = -1
    for i in range(n + 1):
        d = bool(drin[i]) if i < n else False
        if d:
            if start is None:
                start = i
            letzte_drin = i
        elif start is not None and (i - letzte_drin > ende_zellen or i == n):
            dauer = (letzte_drin - start + 1) * reihe.raster_s
            teil = drin[start : letzte_drin + 1]
            if dauer >= min_dauer_s and teil.mean() >= min_anteil:
                hf = reihe.hf[start : letzte_drin + 1]
                out.append(
                    Phase(
                        art,
                        float(reihe.t[start]),
                        float(reihe.t[letzte_drin] + reihe.raster_s),
                        float(np.nanmean(hf)),
                    )
                )
            start = None
    return out


def bouts(
    reihe: HfReihe,
    schwelle_bpm: float,
    *,
    min_dauer_s: float = HF_BOUT_MIN_S,
    ende_s: float = HF_BOUT_ENDE_S,
    min_anteil: float = 0.7,
) -> list[Phase]:
    """Belastungsphasen: HF ≥ ``schwelle_bpm`` über ≥ 3 min; endet nach 2 min darunter.
    Mindestens 70 % der Zellen liegen über der Schwelle. Vorschläge — die Person bestätigt.

    Schwelle: `schwelle_belastung` (40 % HRR), ohne Profil Tagesminimum + 25 bpm.

    >>> hf = [70.0] * 100 + [140.0] * 300 + [70.0] * 200
    >>> r = hf_reihe(np.arange(600) + 0.5, [60000 / h for h in hf])
    >>> [(p.von_s, p.bis_s) for p in bouts(r, 110)]
    [(100.0, 400.0)]
    """
    drin = ~np.isnan(reihe.hf) & (reihe.hf >= schwelle_bpm)
    return _phasen(
        reihe,
        drin,
        art=ART_BELASTUNG,
        min_dauer_s=min_dauer_s,
        ende_s=ende_s,
        min_anteil=min_anteil,
    )


def ruhephasen(
    reihe: HfReihe,
    obergrenze_bpm: float,
    *,
    min_dauer_s: float = HF_RUHE_MIN_S_PHASE,
    ende_s: float = HF_BOUT_ENDE_S,
    min_anteil: float = 0.8,
) -> list[Phase]:
    """Ruhephasen: HF ≤ ``obergrenze_bpm`` (Tagesminimum + 10 bpm) über ≥ 10 min."""
    drin = ~np.isnan(reihe.hf) & (reihe.hf <= obergrenze_bpm)
    return _phasen(
        reihe, drin, art=ART_RUHE, min_dauer_s=min_dauer_s, ende_s=ende_s, min_anteil=min_anteil
    )


def schlaf_kandidat(
    phasen: Sequence[Phase],
    nacht_von_s: float,
    nacht_bis_s: float,
    *,
    mindest_s: float = HF_SCHLAF_MIN_S,
) -> Phase | None:
    """Die längste Ruhephase ≥ 4 h, die das Nachtfenster (``20–10 Uhr`` auf der Achse der
    Reihe, vom Aufrufer umgerechnet) überlappt — als **Vorschlag**; die Person bestätigt.

    >>> p = [Phase("ruhe", 0, 1000, 60), Phase("ruhe", 5000, 30000, 55)]
    >>> schlaf_kandidat(p, 3600, 40000).von_s
    5000
    """
    beste: Phase | None = None
    for p in phasen:
        if p.dauer_s < mindest_s or p.bis_s <= nacht_von_s or p.von_s >= nacht_bis_s:
            continue
        if beste is None or p.dauer_s > beste.dauer_s:
            beste = Phase(ART_SCHLAF, p.von_s, p.bis_s, p.mittel_bpm)
    return beste


def schwelle_belastung(
    ruhe: float | None, hfmax: float | None, tagesminimum_bpm: float | None = None
) -> float | None:
    """Schwelle für `bouts`: 40 % HRR mit Profil, sonst Tagesminimum + 25 bpm, sonst None.

    >>> schwelle_belastung(60, 180), schwelle_belastung(None, None, 58)
    (108.0, 83.0)
    """
    if ruhe is not None and hfmax is not None and hfmax > ruhe:
        return hf_aus_prozent(HF_BOUT_PROZENT, ruhe, hfmax)
    if tagesminimum_bpm is not None:
        return tagesminimum_bpm + 25.0
    return None


# ---------------------------------------------------------------------------
# Tagesprofil und Baseline
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Aktivitaetsprofil:
    sekunden_je_cluster: tuple[float, ...]
    gueltig_s: float
    gueltig: bool


def aktivitaetsprofil(
    reihe: HfReihe,
    ruhe: float,
    hfmax: float,
    von: float | None = None,
    bis: float | None = None,
    *,
    gueltig_ab_s: float = HF_TAG_GUELTIG_S,
) -> Aktivitaetsprofil:
    """Zeit je 10-%-HRR-Cluster eines Tages (INTERLIVE); gültig ab 16 h Daten. Unter 0 %
    zählt zum ersten, über 100 % zum letzten Cluster. Der INTERLIVE-Aktivitätsscore ist
    nicht umgesetzt (Gewichte dort nicht eindeutig entnommen — offen)."""
    grenzen = [hf_aus_prozent(p, ruhe, hfmax) for p in MODELLE[MODELL_CLUSTER]]
    s = zeit_je_bereich(reihe, grenzen, von, bis)
    g = reihe.abgedeckt_s(von, bis)
    return Aktivitaetsprofil(tuple(s), g, g >= gueltig_ab_s)


@dataclass(frozen=True, slots=True)
class Baseline:
    median: float | None
    unten: float | None
    oben: float | None
    n: int


def baseline(werte: Sequence[float | None], n: int = 7) -> Baseline:
    """Median der letzten ``n`` vorhandenen Werte mit Band ± 1 SD (Population); das Band
    erst ab drei Werten. Eine Linie mit Breite — kein Pfeil, kein Alarm.

    >>> baseline([50, None, 52, 54, 51, 53])
    Baseline(median=52.0, unten=50.585..., oben=53.414..., n=5)
    """
    w = np.asarray([float(x) for x in werte if x is not None][-n:], dtype=float)
    if w.size == 0:
        return Baseline(None, None, None, 0)
    med = float(np.median(w))
    if w.size < 3:
        return Baseline(med, None, None, int(w.size))
    sd = float(w.std(ddof=0))
    return Baseline(med, med - sd, med + sd, int(w.size))


# ---------------------------------------------------------------------------
# Wertehierarchie der Profilgrößen (Entscheidung 11)
# ---------------------------------------------------------------------------

GROESSE_RUHE: Final[str] = "ruhe_hf"
GROESSE_MAX: Final[str] = "hf_max"
GROESSE_VT1: Final[str] = "hf_vt1"
GROESSE_VT2: Final[str] = "hf_vt2"

#: Quellen je Größe, **genaueste zuerst**. Eine Messung schlägt jede Schätzung; eine
#: genauere Quelle schlägt eine ungenauere, solange sie im Gültigkeitsfenster liegt.
#: ``fest`` (Festsetzung durch die Person) steht außerhalb der Liste über allem.
RANGFOLGE: Final[dict[str, tuple[str, ...]]] = {
    GROESSE_RUHE: (
        "nacht",
        "messung_morgen_10",
        "messung_morgen_5",
        "eintrag",
        "tagesminimum",
        "tagesfeld",
    ),
    GROESSE_MAX: (
        "spiroergometrie",
        "ergometrie",
        "test_maximal",
        "feldmaximum",
        "eintrag",
        "formel_nes",
        "formel_tanaka",
        "formel_gulati",
    ),
    GROESSE_VT1: ("spiroergometrie", "laktat", "talk_test", "schaetzung_milani", "prozent_hrr"),
    GROESSE_VT2: ("spiroergometrie", "laktat", "schaetzung_milani", "prozent_hrr"),
}
#: Gültigkeit in Tagen je Quelle; None = unbegrenzt
GUELTIG_TAGE: Final[dict[str, int | None]] = {
    "nacht": 14,
    "messung_morgen_10": 14,
    "messung_morgen_5": 14,
    "eintrag": 90,
    "tagesminimum": 14,
    "tagesfeld": 14,
    "spiroergometrie": 365,
    "ergometrie": 365,
    "test_maximal": 365,
    "feldmaximum": 365,
    "formel_nes": None,
    "formel_tanaka": None,
    "formel_gulati": None,
    "laktat": 365,
    "talk_test": 90,
    "schaetzung_milani": None,
    "prozent_hrr": None,
}
#: Vorgabe-Unsicherheit in bpm je Quelle, wenn der Eintrag keine mitbringt
UNSICHERHEIT_BPM: Final[dict[str, float]] = {
    "nacht": 2.0,
    "messung_morgen_10": 3.0,
    "messung_morgen_5": 3.0,
    "eintrag": 5.0,
    "tagesminimum": 4.0,
    "tagesfeld": 5.0,
    "spiroergometrie": 2.0,
    "ergometrie": 3.0,
    "test_maximal": 3.0,
    "feldmaximum": 5.0,
    "formel_nes": FORMELN["nes"][2],
    "formel_tanaka": FORMELN["tanaka"][2],
    "formel_gulati": FORMELN["gulati"][2],
    "laktat": 3.0,
    "talk_test": 6.0,
    "schaetzung_milani": 8.0,
    "prozent_hrr": 8.0,
}
#: Quellen, die messen (gegen Schätzungen)
MESSENDE_QUELLEN: Final[frozenset[str]] = frozenset(
    {
        "nacht",
        "messung_morgen_10",
        "messung_morgen_5",
        "tagesminimum",
        "spiroergometrie",
        "ergometrie",
        "test_maximal",
        "feldmaximum",
        "laktat",
        "talk_test",
    }
)
#: Hysterese des Nenners: ein neuer Wert derselben Quelle ersetzt den alten erst ab 3 bpm
NENNER_HYSTERESE_BPM: Final[float] = 3.0


@dataclass(frozen=True, slots=True)
class ProfilEintrag:
    """Ein Wert einer Profilgröße mit Herkunft."""

    groesse: str
    wert: float
    quelle: str
    datum: date
    unsicherheit_bpm: float | None = None
    fest: bool = False
    geraet: str | None = None
    kennung: Any = None

    @property
    def unsicherheit(self) -> float:
        if self.unsicherheit_bpm is not None:
            return self.unsicherheit_bpm
        return UNSICHERHEIT_BPM.get(self.quelle, 5.0)

    @property
    def misst(self) -> bool:
        return self.quelle in MESSENDE_QUELLEN


def rang(groesse: str, quelle: str) -> int:
    """Rang einer Quelle für eine Größe (0 = genaueste); unbekannte Quellen zuletzt.

    >>> rang("ruhe_hf", "nacht"), rang("ruhe_hf", "tagesfeld"), rang("ruhe_hf", "x")
    (0, 5, 6)
    """
    folge = RANGFOLGE.get(groesse, ())
    return folge.index(quelle) if quelle in folge else len(folge)


def gueltig_am(e: ProfilEintrag, heute: date) -> bool:
    """Ob ein Eintrag am Stichtag noch im Gültigkeitsfenster seiner Quelle liegt."""
    if e.fest:
        return True
    tage = GUELTIG_TAGE.get(e.quelle)
    if tage is None:
        return True
    return 0 <= (heute - e.datum).days <= tage


def geltender_wert(
    eintraege: Sequence[ProfilEintrag], groesse: str, heute: date
) -> ProfilEintrag | None:
    """Der Eintrag, der für ``groesse`` am Stichtag gilt (Entscheidung 11):

    1. ein **festgesetzter** Eintrag (jüngster), sonst
    2. aus der genauesten Quelle, die einen gültigen Eintrag hat, der **jüngste**; sonst
    3. wenn kein Eintrag mehr gültig ist: der jüngste **bis zum Stichtag** (mit Vorbehalt des
       Alters — besser ein alter Messwert als keiner; die App zeigt das Datum); liegt keiner
       davor, der älteste danach (Entscheidung 19: eine Messung vor dem ersten Eintrag rechnet
       mit dem ersten Wert, nie mit einem späteren, wenn ein früherer da ist).

    >>> from datetime import date
    >>> e = [ProfilEintrag("ruhe_hf", 58, "eintrag", date(2026, 10, 1)),
    ...      ProfilEintrag("ruhe_hf", 52, "nacht", date(2026, 10, 20)),
    ...      ProfilEintrag("ruhe_hf", 54, "messung_morgen_5", date(2026, 10, 28))]
    >>> geltender_wert(e, "ruhe_hf", date(2026, 10, 29)).quelle
    'nacht'
    >>> geltender_wert(e, "ruhe_hf", date(2026, 11, 20)).quelle   # Nacht abgelaufen
    'eintrag'
    >>> geltender_wert(e[1:], "ruhe_hf", date(2026, 10, 5)).wert  # vor allen Einträgen
    52
    """
    passend = [e for e in eintraege if e.groesse == groesse]
    if not passend:
        return None
    feste = [e for e in passend if e.fest]
    if feste:
        return max(feste, key=lambda e: e.datum)
    gueltige = [e for e in passend if gueltig_am(e, heute)]
    if not gueltige:
        davor = [e for e in passend if e.datum <= heute]
        if davor:
            return max(davor, key=lambda e: e.datum)
        return min(passend, key=lambda e: e.datum)
    return min(gueltige, key=lambda e: (rang(groesse, e.quelle), -e.datum.toordinal()))


def nenner_fortschreiben(
    alt: float | None, neu: float, *, hysterese_bpm: float = NENNER_HYSTERESE_BPM
) -> float:
    """Der Nenner (Ruhe-HF der Bereiche) folgt einem neuen Wert derselben Quelle erst, wenn
    er um ≥ 3 bpm abweicht — damit Bereiche nicht täglich wandern. Ein Quellenwechsel
    geht nicht durch diese Funktion (er gilt sofort und wird angezeigt).

    >>> nenner_fortschreiben(55.0, 57.0), nenner_fortschreiben(55.0, 58.0)
    (55.0, 58.0)
    """
    if alt is None or abs(neu - alt) >= hysterese_bpm:
        return float(neu)
    return float(alt)


def median_letzter(werte: Sequence[float], n: int = 5) -> float | None:
    """Median der letzten ``n`` Werte (Fortschreibung je Quelle: Nacht, Morgen, Tag).

    >>> median_letzter([60, 58, 57, 59, 61, 56])
    58.0
    """
    w = [float(x) for x in werte][-n:]
    return float(np.median(w)) if w else None


__all__ = [
    "ACSM_NAMEN",
    "FORMELN",
    "GUELTIG_TAGE",
    "HALTUNGEN",
    "KONTEXTE",
    "MODELLE",
    "MODELL_ACSM",
    "MODELL_CLUSTER",
    "MODELL_DREI",
    "MODELL_EIGEN",
    "QUELLE_GERAET",
    "QUELLE_KEINE",
    "QUELLE_RR",
    "RANGFOLGE",
    "UNSICHERHEIT_BPM",
    "Aktivitaetsprofil",
    "Baseline",
    "Bereich",
    "Drift",
    "Erholung",
    "Fensterwert",
    "Formelwert",
    "HfReihe",
    "Phase",
    "ProfilEintrag",
    "Schwellen",
    "aktivitaetsprofil",
    "auf_raster",
    "baseline",
    "bereich_index",
    "bereiche",
    "bouts",
    "drift",
    "formel_hfmax",
    "geltender_wert",
    "grenz_unsicherheit_bpm",
    "grenzen_prozent",
    "gueltig_am",
    "hf_aus_prozent",
    "hf_reihe",
    "hfmax_kandidat",
    "hrr_erholung",
    "median_letzter",
    "nacht_hf",
    "nenner_fortschreiben",
    "prozent_hrr",
    "rang",
    "reihe_aus_beats",
    "rollmittel",
    "ruhe_hf_morgen",
    "ruhephasen",
    "schlaf_kandidat",
    "schwelle_belastung",
    "schwellen_milani",
    "tagesminimum",
    "trimp_banister",
    "trimp_zonen",
    "wanduhr",
    "zeit_je_bereich",
    "zusammenfassung",
]
