"""Spektralprofil: Deskriptoren eines Frequenzspektrums — ohne Urteil.

Aus praxis_gui ``spektralprofil.py`` (Schritt 1 von
``docs/spektrum_bewertung_plan.md`` dort) übernommen. Ein Profil stellt zu
einem Fenster von RR-Intervallen die Größen nebeneinander, die man braucht,
um zwei Spektren zu vergleichen (Bereich A gegen B, Messung gegen Messung):
Leistung je Band, Verteilung, Form des dominanten Gipfels, Atmung und der
Kontext, ohne den keine Differenz lesbar ist. Was es bewusst **nicht**
liefert: eine zusammengerechnete „Gesundheitszahl".

Rechenweg: Bandwerte und Kurve aus **einer** Rechnung
(`frequency.frequenzbereich`, Bandpolitik, Nähte), die Form aus derselben
gemittelten Kurve, Atmung über `atmung.median` (Median der gültigen
Minutenfenster, dazu die Atemschwankung Spitze–Tal in ms). Nichtlineares
(DFA α1, SampEn) nur auf Anfrage — SampEn skaliert quadratisch und bleibt
gekappt.

Gegenüber praxis_gui entfällt der Kohärenzindex (Ben, 16.10.2026: keine
Bewertung mehr), die RSA kommt aus `atmung` statt aus Spline und Hilbert,
und das Spektrum liegt auf der Herzuhr je Teilstück statt auf der Wanduhr
(docs/VERGLEICH.md, R11).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from .atmung import RUHE
from .atmung import median as atmung_median
from .constants import MIN_BEATS_SEGMENT, SAMPEN_MAX_BEATS_LIVE
from .frequency import FREQ_BANDS, PSDMethode, frequenzbereich
from .nonlinear import compute_dfa_alpha1, compute_sampen
from .segments import filter_rr

#: Band, in dem Form und Entropie gerechnet werden: LF + HF. VLF braucht
#: 20 Minuten und würde kurze Fenster mit seinem Flankenanstieg dominieren.
FORMBAND: tuple[float, float] = (FREQ_BANDS["lf"][0], FREQ_BANDS["hf"][1])

#: Unter so vielen Schlägen gibt es gar kein Profil (wie ein Teilspektrum)
MIN_BEATS = MIN_BEATS_SEGMENT

#: 1 = praxis_gui (scipy-Lomb auf der Wanduhr, RSA Spline/Hilbert, Kohärenz);
#: 2 = hrv-core (numpy-Lomb auf der Herzuhr, RSA aus `atmung`, ohne Kohärenz)
PROFIL_VERSION = 2


def _zahl(x: Any) -> float | None:
    """NaN/Inf/None → None, sonst float (ungerundet)."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def peak_merkmale(
    freqs: Sequence[float] | np.ndarray,
    power: Sequence[float] | np.ndarray,
    band: tuple[float, float] = FORMBAND,
) -> dict[str, float | None] | None:
    """Dominanter Gipfel im Band: Lage, Höhe, Halbwertsbreite, Güte.

    Halbwertsbreite = zusammenhängender Bereich um das Maximum, in dem die
    Leistung mindestens die Hälfte des Maximums hat (mindestens ein Bin).
    ``peak_q`` = f0 / Breite — hoch heißt „ein Rhythmus dominiert", niedrig
    „breit verteilt". Beides kann gesund sein; die Zahl beschreibt die Form.

    >>> f = np.arange(0.01, 0.5, 0.01)
    >>> p = np.exp(-((f - 0.1) / 0.01) ** 2)
    >>> m = peak_merkmale(f, p)
    >>> round(m["peak_hz"], 2), round(m["peak_breite_hz"], 2), round(m["peak_anteil"], 2)
    (0.1, 0.01, 0.56)
    """
    f = np.asarray(freqs, dtype=float)
    p = np.asarray(power, dtype=float)
    if f.size == 0 or p.size != f.size:
        return None
    maske = (f >= band[0]) & (f <= band[1])
    if maske.sum() < 3:
        return None
    fb, pb = f[maske], p[maske]
    pk = int(np.argmax(pb))
    p0 = float(pb[pk])
    if not p0 > 0:
        return None
    halb = p0 / 2.0
    lo = pk
    while lo > 0 and pb[lo - 1] >= halb:
        lo -= 1
    hi = pk
    while hi < pb.size - 1 and pb[hi + 1] >= halb:
        hi += 1
    df = float(np.median(np.diff(fb))) if fb.size > 1 else 0.0
    breite = max(float(fb[hi] - fb[lo]), df if df > 0 else 1e-6)
    f0 = float(fb[pk])
    # Anteil der Bandleistung innerhalb der Halbwertsbreite — Form, nicht Wert.
    anteil = float(pb[lo : hi + 1].sum() / pb.sum()) if pb.sum() > 0 else None
    return {
        "peak_hz": f0,
        "peak_power": p0,
        "peak_breite_hz": breite,
        "peak_q": f0 / breite,
        "peak_anteil": _zahl(anteil),
    }


def spektrale_form(
    freqs: Sequence[float] | np.ndarray,
    power: Sequence[float] | np.ndarray,
    band: tuple[float, float] = FORMBAND,
) -> dict[str, Any] | None:
    """Normierte spektrale Entropie und Flatness im Band.

    Entropie: −Σ p ln p / ln n über die auf 1 normierte Leistung — 0 heißt
    eine einzige Linie, 1 heißt gleichverteilt. Flatness: geometrisches durch
    arithmetisches Mittel (0 … 1), robust gegen die Bin-Zahl.

    Beide hängen vom Frequenzraster ab (Fensterlänge, Methode): vergleichbar
    sind nur Profile mit derselben Rechenvorschrift — deshalb stehen Methode
    und Auflösung mit im Profil.

    >>> f = np.arange(0.05, 0.4, 0.01)
    >>> spektrale_form(f, np.ones_like(f))["spektral_entropie"]
    1.0
    """
    f = np.asarray(freqs, dtype=float)
    p = np.asarray(power, dtype=float)
    if f.size == 0 or p.size != f.size:
        return None
    pb = p[(f >= band[0]) & (f <= band[1])]
    pb = pb[np.isfinite(pb) & (pb > 0)]
    if pb.size < 3:
        return None
    q = pb / pb.sum()
    entropie = float(-(q * np.log(q)).sum() / math.log(q.size))
    flatness = float(math.exp(float(np.log(pb).mean())) / float(pb.mean()))
    return {
        "spektral_entropie": max(0.0, min(1.0, entropie)),
        "spektral_flatness": max(0.0, min(1.0, flatness)),
        "form_bins": int(pb.size),
    }


def _ln(x: Any) -> float | None:
    f = _zahl(x)
    return math.log(f) if f is not None and f > 0 else None


#: Welche Schlüssel aus `frequenzbereich` ins Profil übernommen werden
_FREQUENZ_FELDER = (
    "vlf",
    "lf",
    "hf",
    "total_power",
    "lf_hf",
    "lf_n",
    "hf_n",
    "gipfel_hz",
    "band_status",
    "band_reason",
    "band_reif",
    "dauer_s",
    "coverage_pct",
    "df_hz",
    "n_segments",
)


def spektralprofil(
    rr_ms: Sequence[float | None] | np.ndarray,
    t_s: Sequence[float] | np.ndarray | None = None,
    breaks: Sequence[int] | None = None,
    *,
    methode: PSDMethode = "lomb",
    mindestdauer: bool = True,
    atmung: bool = True,
    atem_modus: str = RUHE,
    nichtlinear: bool = False,
    sampen_max_beats: int = SAMPEN_MAX_BEATS_LIVE,
) -> dict[str, Any]:
    """Spektralprofil eines RR-Fensters.

    ``t_s``/``breaks`` wie bei `frequency.frequenzbereich` (Herzuhr je
    Schlag, Nähte). Liefert immer ein dict; ``status`` ist ``"ok"``,
    ``"zu_kurz"`` oder ``"kein_spektrum"``. Werte, die die Bandpolitik
    sperrt, sind ``None`` — ``band_status`` sagt warum.

    >>> t = np.cumsum(np.full(400, 800.0)) / 1000
    >>> rr = 800 + 30 * np.sin(2 * np.pi * 0.25 * t)
    >>> p = spektralprofil(rr, t, mindestdauer=False)
    >>> p["status"], round(p["peak_hz"], 2), p["resp_rate"] is not None
    ('ok', 0.25, True)
    """
    valide = filter_rr(rr_ms)
    n = int(valide.size)
    profil: dict[str, Any] = {
        "profil_version": PROFIL_VERSION,
        "n": n,
        "psd_method": methode,
        "status": "ok",
    }
    if n < MIN_BEATS:
        profil["status"] = "zu_kurz"
        return profil

    profil["mean_rr"] = float(valide.mean())
    profil["mean_bpm"] = 60000.0 / float(valide.mean())
    roh = [r for r in rr_ms if r is not None]
    profil["ektopie_anteil"] = 1.0 - n / max(1, len(roh))

    fd = frequenzbereich(rr_ms, t_s, breaks, methode, mindestdauer=mindestdauer) or {}
    for schl in _FREQUENZ_FELDER:
        profil[schl] = fd.get(schl)
    for schl in ("vlf", "lf", "hf", "total_power"):
        profil["ln_" + schl] = _ln(fd.get(schl))

    freqs, power = fd.get("freqs"), fd.get("psd")
    if freqs is None or power is None or np.asarray(freqs).size == 0:
        profil["status"] = "kein_spektrum"
        return profil
    profil.update(peak_merkmale(freqs, power) or {})
    profil.update(spektrale_form(freqs, power) or {})
    # Gipfellage je Band: wo der Atemrhythmus sitzt, entscheidet, ob HF oder LF
    # ihn trägt — ohne diese Zeile sind HF n.u. und LF/HF nicht lesbar.
    for name in ("lf", "hf"):
        pm = peak_merkmale(freqs, power, FREQ_BANDS[name])
        profil[f"peak_{name}_hz"] = pm["peak_hz"] if pm else None

    if atmung:
        zeit = np.asarray(t_s, dtype=float) if t_s is not None else np.cumsum(valide) / 1000.0
        rr_arr = np.asarray([np.nan if r is None else float(r) for r in rr_ms], dtype=float)
        if zeit.size != rr_arr.size:
            zeit, rr_arr = np.cumsum(valide) / 1000.0, valide
        m = atmung_median(zeit, rr_arr, modus=atem_modus)
        profil["resp_rate"] = m.rate_pro_min
        profil["resp_freq_hz"] = None if m.rate_pro_min is None else m.rate_pro_min / 60.0
        profil["resp_confidence"] = m.anteil
        profil["resp_gruende"] = list(m.gruende)
        profil["rsa_amp"] = m.rsa_ms

    if nichtlinear:
        dfa = compute_dfa_alpha1(valide)
        profil["dfa_alpha1"] = None if dfa is None else float(dfa["dfa_alpha1"])
        fenster = valide[-int(sampen_max_beats) :] if sampen_max_beats else valide
        profil["sampen"] = compute_sampen(fenster)
        profil["sampen_n"] = int(fenster.size)
    return profil


#: Reihenfolge und Beschriftung für Tabellen (A | B | Δ). Kontext zuerst — die
#: Atemfrequenz steht oben, weil sie die häufigste Erklärung einer Differenz ist.
PROFIL_ZEILEN: list[tuple[str, str, str]] = [
    # (Schlüssel, Beschriftung, Einheit)
    ("resp_rate", "Atemfrequenz", "/min"),
    ("mean_bpm", "Ø Herzfrequenz", "bpm"),
    ("dauer_s", "Fensterlänge", "s"),
    ("coverage_pct", "Abdeckung", "%"),
    ("ln_total_power", "ln Total Power", "ln ms²"),
    ("ln_hf", "ln HF", "ln ms²"),
    ("ln_lf", "ln LF", "ln ms²"),
    ("ln_vlf", "ln VLF", "ln ms²"),
    ("hf_n", "HF n.u.", ""),
    ("lf_hf", "LF/HF", ""),
    ("peak_hz", "Hauptgipfel", "Hz"),
    ("peak_breite_hz", "Halbwertsbreite", "Hz"),
    ("peak_q", "Gipfelgüte (f/Δf)", ""),
    ("peak_anteil", "Anteil im Gipfel", ""),
    ("spektral_entropie", "Spektrale Entropie", "0–1"),
    ("spektral_flatness", "Flatness", "0–1"),
    ("rsa_amp", "Atemschwankung (Spitze–Tal)", "ms"),
    ("dfa_alpha1", "DFA α1", ""),
    ("sampen", "Sample Entropy", ""),
]

__all__ = [
    "FORMBAND",
    "MIN_BEATS",
    "PROFIL_VERSION",
    "PROFIL_ZEILEN",
    "peak_merkmale",
    "spektrale_form",
    "spektralprofil",
]
