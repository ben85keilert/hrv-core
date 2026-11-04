"""PROTOTYP — Wiederholungen aus der Beschleunigung des Gurts zählen (nicht Grundlage
gespeicherter Kennzahlen, darf sich ohne ``ALGO_VERSION`` ändern; Regeln: `hrv_core.prototyp`).

Herkunft: hrv-research ``src/hrv_research/beschleunigung/wiederholungen.py`` (Entscheidung 22,
4.11.2026), Konzept B3 in einfachster Form. Ein Satz ist ein bekanntes Zeitfenster
(Satzgrenzen aus der App: Uhr der Übung, eingetragener Satz). Darin

1. Schwerkraft weg: je Achse ein gleitendes Mittel über `HOCHPASS_S` abziehen;
2. Hauptachse der Bewegung: erste Hauptkomponente der drei Achsen (Vorzeichen egal);
3. glätten: gleitendes Mittel über `GLAETTEN_S`;
4. Grundperiode aus der Autokorrelation zwischen `PERIODE_MIN_S` und `PERIODE_MAX_S`;
5. zu wenig Hub (`MIN_HUB_MG`): keine Wiederholung;
6. Gipfel zählen: lokale Maxima mit Mindestabstand ``ABSTAND_ANTEIL · Periode`` und
   Mindesthöhe ``HOEHE_ANTEIL · Streuung`` — für beide Vorzeichen; es gilt das Vorzeichen,
   dessen Abstände gleichmäßiger sind.

**Eingang mit Ausnahme** (Entscheidung 22 in hrv-research): geprüft an einer Sitzung (drei Sätze,
Parameter vorher festgelegt, alle exakt gegen Video), die zweite entsteht mit dem Diagnosemodus
der trainingsapp — dort wird der Zähler nur angezeigt, als Prototyp gekennzeichnet. Offen: welcher
Umkehrpunkt gezählt wird (oben oder unten). Nur numpy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import KENNZEICHEN

#: Schwerkraft weg: gleitendes Mittel über so viele Sekunden abziehen
HOCHPASS_S = 2.0
#: Glätten (s)
GLAETTEN_S = 0.25
#: Suchbereich der Grundperiode (s) — von schnellen Hampelmännern bis zu langsamen Kniebeugen
PERIODE_MIN_S = 0.8
PERIODE_MAX_S = 8.0
#: Gipfel: Mindestabstand als Anteil der Periode, Mindesthöhe als Anteil der Streuung
ABSTAND_ANTEIL = 0.6
HOEHE_ANTEIL = 0.4
#: Unter diesem Hub (mG, 10.–90. Perzentil der Hauptachse) ist es keine Bewegung, sondern
#: Rauschen, Atmung oder Herzschlag — dann zählt nichts
MIN_HUB_MG = 100.0


@dataclass(frozen=True, slots=True)
class Zaehlung:
    """Ergebnis eines Satzes — ``art`` ist immer `hrv_core.prototyp.KENNZEICHEN`."""

    anzahl: int
    #: Zeiten der gezählten Umkehrpunkte (s, auf der Zeitachse der Eingabe)
    zeiten_s: tuple[float, ...]
    #: Grundperiode (s), ``None``: keine erkennbar
    periode_s: float | None
    #: 0–1: wie gleichmäßig die Abstände sind (1 − Variationskoeffizient)
    gleichmaessigkeit: float
    art: str = KENNZEICHEN


def _gleitend(x: np.ndarray, n: int) -> np.ndarray:
    """Gleitendes Mittel (zentriert, Ränder mit kürzerem Fenster)."""
    n = max(1, int(n))
    if n == 1 or x.size == 0:
        return x.astype(np.float64)
    kern = np.ones(n) / n
    voll = np.convolve(x, kern, mode="same")
    gewicht = np.convolve(np.ones_like(x, dtype=np.float64), kern, mode="same")
    return voll / gewicht


def hauptachse(xyz: np.ndarray, rate_hz: float) -> np.ndarray:
    """Die Bewegung längs ihrer Hauptachse — ohne Schwerkraft, geglättet."""
    xyz = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
    hoch = xyz - np.column_stack(
        [_gleitend(xyz[:, k], round(HOCHPASS_S * rate_hz)) for k in range(3)]
    )
    if hoch.shape[0] < 3:
        return np.zeros(hoch.shape[0])
    _, _, vt = np.linalg.svd(hoch - hoch.mean(axis=0), full_matrices=False)
    achse = hoch @ vt[0]
    return _gleitend(achse, round(GLAETTEN_S * rate_hz))


def periode(signal: np.ndarray, rate_hz: float) -> float | None:
    """Grundperiode aus dem ersten deutlichen Gipfel der Autokorrelation (s).

    >>> t = np.arange(0, 30, 1 / 50)
    >>> round(periode(np.sin(2 * np.pi * t / 2.5), 50.0), 1)
    2.5
    """
    x = np.asarray(signal, dtype=np.float64)
    x = x - x.mean()
    if x.size < 4 or not np.any(x):
        return None
    n = x.size
    spektrum = np.fft.rfft(x, 2 * n)
    ak = np.fft.irfft(spektrum * np.conj(spektrum))[:n]
    ak = ak / ak[0]
    lo, hi = round(PERIODE_MIN_S * rate_hz), min(round(PERIODE_MAX_S * rate_hz), n - 2)
    if hi <= lo + 2:
        return None
    bereich = ak[lo:hi]
    # erster lokaler Gipfel über 0,2 — nicht das globale Maximum (Vielfache der Periode)
    for i in range(1, bereich.size - 1):
        if bereich[i] >= bereich[i - 1] and bereich[i] >= bereich[i + 1] and bereich[i] > 0.2:
            return (lo + i) / rate_hz
    return None


def _gipfel(x: np.ndarray, abstand: int, hoehe: float) -> np.ndarray:
    """Lokale Maxima über ``hoehe`` mit Mindestabstand — die höheren gewinnen."""
    if x.size < 3:
        return np.empty(0, dtype=np.int64)
    kandidaten = np.flatnonzero((x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:]) & (x[1:-1] > hoehe)) + 1
    gewaehlt: list[int] = []
    for i in kandidaten[np.argsort(-x[kandidaten])]:
        if all(abs(int(i) - j) >= abstand for j in gewaehlt):
            gewaehlt.append(int(i))
    return np.array(sorted(gewaehlt), dtype=np.int64)


def _gleichmaessigkeit(idx: np.ndarray) -> float:
    if idx.size < 3:
        return 0.0
    d = np.diff(idx).astype(np.float64)
    return float(max(0.0, 1.0 - d.std() / d.mean()))


def zaehlen(xyz: np.ndarray, rate_hz: float, t0_s: float = 0.0) -> Zaehlung:
    """Wiederholungen eines Satzes aus der Beschleunigung (Modultext).

    ``xyz``: Proben ``n × 3`` (mG) in gleichmäßigem Takt ``rate_hz``; ``t0_s``: Zeit der ersten
    Probe (für ``zeiten_s``).

    >>> rate = 100.0
    >>> t = np.arange(0, 24, 1 / rate)
    >>> bewegung = 300 * np.sin(2 * np.pi * t / 2.0)          # 12 Wiederholungen à 2 s
    >>> xyz = np.column_stack([0.2 * bewegung, -1000 + bewegung, 0.1 * bewegung])
    >>> z = zaehlen(xyz, rate)
    >>> z.anzahl, round(z.periode_s, 1), z.gleichmaessigkeit > 0.9
    (12, 2.0, True)
    >>> zaehlen(np.zeros((500, 3)), rate).anzahl
    0
    """
    achse = hauptachse(xyz, rate_hz)
    if achse.size < 3 or not np.any(achse):
        return Zaehlung(0, (), None, 0.0)
    hub = float(np.percentile(achse, 90) - np.percentile(achse, 10))
    if hub < MIN_HUB_MG:
        return Zaehlung(0, (), None, 0.0)
    t_per = periode(achse, rate_hz)
    if t_per is None:
        return Zaehlung(0, (), None, 0.0)
    abstand = max(1, round(ABSTAND_ANTEIL * t_per * rate_hz))
    streuung = float(achse.std())
    bestes: tuple[float, np.ndarray] | None = None
    for vorzeichen in (1.0, -1.0):
        x = vorzeichen * achse
        idx = _gipfel(x, abstand, HOEHE_ANTEIL * streuung)
        g = _gleichmaessigkeit(idx)
        if bestes is None or g > bestes[0]:
            bestes = (g, idx)
    assert bestes is not None
    g, idx = bestes
    return Zaehlung(
        int(idx.size), tuple(float(t0_s + i / rate_hz) for i in idx), float(t_per), round(g, 3)
    )


__all__ = [
    "ABSTAND_ANTEIL",
    "GLAETTEN_S",
    "HOCHPASS_S",
    "HOEHE_ANTEIL",
    "MIN_HUB_MG",
    "PERIODE_MAX_S",
    "PERIODE_MIN_S",
    "Zaehlung",
    "hauptachse",
    "periode",
    "zaehlen",
]
