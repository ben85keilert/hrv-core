"""PROTOTYP — Atemzüge und Atemphasen live aus der Beschleunigung des Gurts (nicht Grundlage
gespeicherter Kennzahlen, darf sich ohne ``ALGO_VERSION`` ändern; Regeln: `hrv_core.prototyp`).

Herkunft: hrv-research ``src/hrv_research/beschleunigung/atem_live.py`` (Entscheidung 24,
5.11.2026; Forschungspakete F3 und F4). Kausale Fassung des Offline-Verfahrens K3 mit der
Prüfung aus K2: rahmenweise Eingabe, keine Zukunft, kein nullphasiger Filter, kein Blick über
ein ganzes Fenster — nur Ringpuffer und gleitende Größen mit bekannter Verzögerung. Je Probe
auf ~25 Hz:

1. **Herunterbrechen:** Blockmittel der Rohproben auf ``rate_hz / k`` mit
   ``k = round(rate_hz / FS_ZIEL)`` (50 → 25 Hz, 52 → 26 Hz, 200 → 25 Hz); Zeit = Mitte des Blocks.
2. **Bewegung** (nachlaufend): Unruhe = RMS über `UNRUHE_S` der Abweichung des Vektors von
   seinem nachlaufenden `UNRUHE_S`-Mittel; Sprung = Abstand des nachlaufenden `SPRUNG_S`-Mittels
   zu dem von vor `SPRUNG_S`. Über `UNRUHE_AB_MG` oder `SPRUNG_AB_MG` ist die Probe bewegt, ebenso
   bei einer Lücke in der Zeitachse über `MAX_LUECKE_S`; `BEWEGUNG_RAND_S` davor und danach gilt
   ebenfalls als bewegt — nach vorn durch Warten, nach hinten durch Zurücknehmen noch nicht
   bestätigter Ereignisse. Ein ruhiges **Stück** beginnt nach jeder Bewegung neu; Abstände
   zählen nur innerhalb eines Stücks.
3. **Atemwelle:** Projektion auf die feste Richtung `RICHTUNG` (x − z, siehe unten), Hochpass =
   nachlaufendes Mittel über `HOCHPASS_S` abziehen (ab Stückbeginn wachsend), Tiefpass =
   nachlaufendes Mittel über `TIEFPASS_S` (Zeit auf die Fenstermitte, Verzögerung
   ``TIEFPASS_S / 2``).
4. **Wendepunkte mit Hysterese:** Hülle = nachlaufender RMS über `HUELLE_S` mal √2, nie unter
   `HUELLE_MIN_MG`; ``h = HYSTERESE · Hülle``. Ein Tal ist erkannt, wenn das Signal seit dem Tal
   um ``h`` gestiegen ist; ein Gipfel, wenn es um ``h`` gefallen ist. Zeit des Wendepunkts ist
   der **Ansatz** (letzter Punkt höchstens ``ANSATZ_ANTEIL · h`` vom Extremum: Ende der Sohle
   bzw. des Plateaus). **Tal = Beginn „ein“, Gipfel = Beginn „aus“** (F4). Der erste Wendepunkt
   eines Stücks setzt nur die Richtung.
5. **Gespaltene Atemzüge:** ein Tal näher als ``max(MIN_ATEMZUG_S, KURZ_ANTEIL · typisch)`` am
   vorigen ist kein neuer Atemzug (typisch = Median der letzten `TYPISCH_ANZAHL` Abstände) — es
   sei denn, der Schwung vom Gipfel davor ins Tal ist mindestens ``MIN_SCHWUNG · Hülle``.
   Kausale Entsprechung der Regel „zusammenlegen“ aus K3: dort fiel von zwei zu nahen Atemzügen
   der weg, dessen Wegfall den Abstand näher ans Typische brachte — das braucht den nächsten
   Abstand, also Zukunft. Hier bleibt der **erste**; ein „aus“ gibt es je Atemzug nur einmal
   (der erste Gipfel nach dem Tal).
6. **Bestätigen:** Ein Wendepunkt wird erst `BEWEGUNG_RAND_S` nach seiner Zeit gemeldet — kommt
   bis dahin eine Bewegung, war er keiner. Verzögerung je Ereignis: ``TIEFPASS_S / 2`` plus die
   Zeit, bis das Signal um ``h`` weiter ist (etwa ein Achtel Zyklus), plus `BEWEGUNG_RAND_S`.
7. **Gültigkeit** alle `SCHRITT_S` über die letzten `FENSTER_S` (Prüfung wie K2): Ruheanteil
   ≥ `MIN_RUHE_ANTEIL`, Amplitude ≥ `MIN_AMPLITUDE_MG`, genug Abstände
   (`noetige_abstaende`), Variationskoeffizient ≤ `MAX_CV`, Lomb-Scargle über die ruhigen
   Proben: Gipfel in `SUCH_HZ` mit Anteil ≥ `MIN_ANTEIL`, Zyklenrate (60 / Median der
   Abstände) höchstens ``max(MAX_ABWEICHUNG_PRO_MIN, MAX_ABWEICHUNG_REL · Gipfel)`` daneben.
   Rate = 60 / Median der Abstände, sonst ``None`` mit Gründen als kurze Codes (snake_case):
   ``bewegung``, ``amplitude_klein``, ``kein_gipfel``, ``gipfel_undeutlich``,
   ``zu_wenig_zyklen``, ``ungleichmaessig``, ``zyklen_passen_nicht``; vor dem ersten Fenster
   ``zu_kurz``.

**Vorzeichen (F4, aus den Daten der Brustgurt-Diagnose):** Keine einzelne Achse des H10 steigt
in allen Haltungen beim Einatmen — sitzend liegt die Welle auf z (fällt beim Einatmen), liegend
auf x (steigt), bei geneigtem Gurt auf beiden. Die **feste Richtung ``(x − z) / √2`` steigt in
allen untersuchten Haltungen beim Einatmen**; darum eine feste Richtung ohne Takt und ohne RSA
(Takt und RSA bleiben als zweite Stufe für Haltungen, die noch nicht vorkamen).

**Bekannte Grenzen:** ein Mensch, ein Tag, ein Gurt (H10 am unteren Brustbein). Langsames
**und** flaches Atmen zeigt Doppeltäler in der langen Ausatmung — die Zahl stimmt dort nicht,
die Fensterprüfung verwirft die Fenster (keine Rate). Der erste Atemzug je ruhigem Stück fehlt
oder verschiebt sich (Anlauf des Hochpasses). Live bleibt hinter dem Offline-Verfahren zurück
(kein Blick nach vorn beim Zusammenlegen, kein Bandpass über das ganze Stück). Verity Sense am
Arm: keine Daten, die feste Richtung gilt nur für die Brust; Seiten- und Bauchlage nicht
untersucht. Es gibt keine Bewertung: Zahlen, Phasen, Gültigkeit mit Gründen — kein Rat.

**Eingang mit Ausnahme** (Entscheidung 24 in hrv-research): eingestellt nur an drei Schritten
einer Sitzung, geprüft an allen übrigen Schritten zweier Sitzungen eines Menschen. Nur numpy
(``hrv_core.frequency.lomb_psd``).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from ..frequency import lomb_psd
from . import KENNZEICHEN

#: Zielrate der Verarbeitung (Hz); gerechnet wird mit ``rate_hz / round(rate_hz / FS_ZIEL)``
FS_ZIEL = 25.0
#: Feste Richtung der Atemwelle: ``(x − z) / √2`` steigt beim Einatmen (Modultext)
RICHTUNG = (1.0 / math.sqrt(2.0), 0.0, -1.0 / math.sqrt(2.0))
#: Hochpass: nachlaufendes Mittel über so viele Sekunden abziehen (Perioden über 20 s weg,
#: Gewinn 1 ± 0,2 und Phase unter 12° zwischen 0,1 und 0,35 Hz)
HOCHPASS_S = 10.0
#: Tiefpass: nachlaufendes Mittel (Null bei 1 Hz: der Herzschlag, 60–90/min, fällt auf unter ein
#: Viertel; 20 Atemzüge/min bleiben zu 83 %), Verzögerung die Hälfte
TIEFPASS_S = 1.0

#: Bewegung (Schwellen aus `brustgurt_atem`, dort aus P und B): Unruhe = RMS über `UNRUHE_S`
#: der Abweichung vom gleitenden `UNRUHE_S`-Mittel; Sprung = Änderung des `SPRUNG_S`-Mittels
UNRUHE_S = 0.5
SPRUNG_S = 1.0
UNRUHE_AB_MG = 25.0
SPRUNG_AB_MG = 80.0
#: So weit (s) vor und nach jeder Bewegung gilt das Signal ebenfalls als gestört
BEWEGUNG_RAND_S = 1.0
#: Eine Lücke in der Zeitachse ab so vielen Sekunden gilt als Bewegung (Strom abgerissen)
MAX_LUECKE_S = 1.0

#: Hysterese als Anteil der laufenden Hülle; Hülle = nachlaufender RMS über `HUELLE_S` · √2,
#: nie unter `HUELLE_MIN_MG` (darunter ist es Rauschen, keine Atmung)
HYSTERESE = 0.4
HUELLE_S = 10.0
HUELLE_MIN_MG = 2.0
#: Kürzester Atemzug (s). Ein Tal näher als `KURZ_ANTEIL` × typisch am vorigen (typisch =
#: Median der letzten `TYPISCH_ANZAHL` Abstände) ist ein gespaltener Atemzug — aber nur, wenn
#: auch der Schwung vom Gipfel davor ins Tal kleiner ist als `MIN_SCHWUNG` × Hülle: Ein voller
#: Schwung ist ein Atemzug, auch wenn das Tempo gerade gewechselt hat (sonst rastet die Regel
#: nach einem Wechsel von langsam zu schnell auf jedem zweiten Atemzug ein)
MIN_ATEMZUG_S = 1.4
KURZ_ANTEIL = 0.55
TYPISCH_ANZAHL = 8
MIN_SCHWUNG = 1.0
#: Beginn einer Phase ist nicht das Extremum, sondern der letzte Punkt davor, an dem das Signal
#: noch höchstens `ANSATZ_ANTEIL` × h vom Extremum entfernt war — das Ende der Sohle bzw. des
#: Plateaus (bei 4 s ein / 6 s aus liegt das Tal irgendwo auf einer flachen Sohle)
ANSATZ_ANTEIL = 0.5

#: Gültigkeit: Fenster (s), Abstand der Fenster (s)
FENSTER_S = 30.0
SCHRITT_S = 5.0
#: Band des Spektrums und Suchbereich des Gipfels (Hz) — wie `brustgurt_atem`
BAND_HZ = (0.05, 0.70)
SUCH_HZ = (0.08, 0.70)
DF_HZ = 0.002
MIN_RUHE_ANTEIL = 0.6
#: Kleinste Amplitude (Standardabweichung der Welle, mG): K2 verlangte 1,5 mG auf der
#: Hauptachse; die feste Richtung trägt von einer Welle auf einer Achse nur 1/√2, darum 1,5/√2
MIN_AMPLITUDE_MG = 1.5 / math.sqrt(2.0)
MIN_ANTEIL = 0.35
ANTEIL_BREITE_HZ = 0.03
MIN_ZYKLEN = 3
#: Zyklenrate gegen Spektralgipfel: der Gipfel über 30 s hinkt einer Tempoänderung nach,
#: darum weiter als in K2 (dort 1,5/min bzw. 15 %); „Gurt locker“ (doppelt gezählt) bleibt draußen
MAX_ABWEICHUNG_PRO_MIN = 2.0
MAX_ABWEICHUNG_REL = 0.25
#: Variationskoeffizient der Abstände im Fenster, darüber „ungleichmaessig“
MAX_CV = 0.5

#: Ereignisarten
EIN = "ein"
AUS = "aus"


@dataclass(frozen=True, slots=True)
class Phase:
    """Beginn einer Atemphase: ``art`` `EIN` (Tal) oder `AUS` (Gipfel), ``nr`` der Atemzug."""

    t_s: float
    art: str
    nr: int


@dataclass(frozen=True, slots=True)
class Fenster:
    """Gültigkeit der letzten `FENSTER_S` Sekunden, alle `SCHRITT_S`.

    ``rate_pro_min`` nur, wenn ``gueltig``; ``rate_roh`` immer, wenn mindestens zwei Abstände da
    sind (zur Diagnose, nie zur Anzeige).
    """

    von_s: float
    bis_s: float
    rate_pro_min: float | None
    gueltig: bool
    gruende: tuple[str, ...]
    zyklen: int
    ruhe: float
    amplitude_mg: float
    cv: float | None
    gipfel_pro_min: float | None
    rate_roh: float | None


@dataclass(frozen=True, slots=True)
class Stand:
    """Was die Anzeige jetzt zeigt: Zahl der Atemzüge, vorläufige Phase (steigt das Signal
    seit dem letzten Tal: „ein“; fällt es: „aus“; bewegt oder unbekannt: ``None``), letzte Rate."""

    t_s: float
    atemzuege: int
    phase: str | None
    rate_pro_min: float | None
    gueltig: bool
    gruende: tuple[str, ...]
    art: str = KENNZEICHEN


@dataclass(frozen=True, slots=True)
class Atemzuege:
    """Ergebnis der Offline-Hülle `atemzuege` — ``art`` ist immer `KENNZEICHEN`."""

    ein_s: tuple[float, ...]
    aus_s: tuple[float, ...]
    #: Median der gültigen Fensterraten, ``None`` ohne gültiges Fenster
    rate_pro_min: float | None
    #: 0–1: 1 − Variationskoeffizient aller Abstände innerhalb ruhiger Stücke
    gleichmaessigkeit: float
    gueltig: bool
    gruende: tuple[str, ...]
    fenster: tuple[Fenster, ...]
    art: str = KENNZEICHEN


def noetige_abstaende(rate_pro_min: float, dauer_s: float) -> int:
    """Wie viele Abstände ein Fenster mindestens braucht: `MIN_ZYKLEN`, bei langsamem Atmen so
    viele, wie hineinpassen, nie unter zwei.

    >>> noetige_abstaende(12.0, 30.0), noetige_abstaende(6.0, 30.0), noetige_abstaende(4.0, 30.0)
    (3, 2, 2)
    """
    passen = math.floor(rate_pro_min / 60.0 * dauer_s + 1e-9) - 1
    return max(2, min(MIN_ZYKLEN, passen))


def gipfel(f: np.ndarray, p: np.ndarray, lo: float, hi: float) -> float | None:
    """Lage des höchsten lokalen Maximums im Inneren von ``lo``–``hi``, parabolisch verfeinert.

    >>> f = np.linspace(0, 1, 101)
    >>> gipfel(f, np.exp(-((f - 0.253) ** 2) / 0.002), 0.08, 0.7)
    0.253
    """
    idx = np.flatnonzero((f >= lo) & (f <= hi))
    if idx.size < 3:
        return None
    innen = idx[1:-1]
    lokal = innen[(p[innen] >= p[innen - 1]) & (p[innen] > p[innen + 1])]
    if lokal.size == 0:
        return None
    i = int(lokal[np.argmax(p[lokal])])
    a, b, c = (math.log(float(p[j]) + 1e-12) for j in (i - 1, i, i + 1))
    nenner = a - 2 * b + c
    versatz = 0.5 * (a - c) / nenner if nenner != 0 else 0.0
    return round(float(f[i] + np.clip(versatz, -0.5, 0.5) * (f[1] - f[0])), 4)


def anteil(f: np.ndarray, p: np.ndarray, f0: float) -> float:
    """Leistung um ``f0`` (± `ANTEIL_BREITE_HZ`) im Verhältnis zur Leistung im Suchbereich."""
    band = (f >= SUCH_HZ[0]) & (f <= SUCH_HZ[1])
    um = band & (np.abs(f - f0) <= ANTEIL_BREITE_HZ)
    gesamt = float(p[band].sum())
    return float(p[um].sum()) / gesamt if gesamt > 0 else 0.0


class _Summe:
    """Nachlaufende Summe über höchstens ``n`` Werte — am Anfang (und nach `leeren`) über so
    viele, wie da sind."""

    __slots__ = ("n", "summe", "werte")

    def __init__(self, n: int) -> None:
        self.n = max(1, int(n))
        self.werte: deque[float] = deque()
        self.summe = 0.0

    def leeren(self) -> None:
        self.werte.clear()
        self.summe = 0.0

    def schieben(self, x: float) -> float:
        """Neuen Wert aufnehmen, Mittel zurückgeben."""
        self.werte.append(x)
        self.summe += x
        if len(self.werte) > self.n:
            self.summe -= self.werte.popleft()
        return self.summe / len(self.werte)


class AtemLive:
    """Atemzüge und Phasen rahmenweise (Modultext). Zeiten auf der Achse der Eingabe.

    >>> rate = 50.0
    >>> live = AtemLive(rate)
    >>> t = np.arange(0, 60, 1 / rate)
    >>> welle = -15 * np.cos(2 * np.pi * t / 5.0)                 # 12/min: Tal bei 0, 5, 10 …
    >>> xyz = np.column_stack([0 * t, -1000 + 0 * t, 20 - welle])  # sitzend: z fällt beim Einatmen
    >>> ereignisse = []
    >>> for i in range(0, t.size, 50):
    ...     ereignisse += live.rahmen(xyz[i : i + 50], float(t[i]))
    >>> ein = [round(e.t_s) for e in ereignisse if isinstance(e, Phase) and e.art == "ein"]
    >>> ein[:4], live.stand().atemzuege >= 10    # das erste Tal (0 s) hat keinen Gipfel davor
    ([5, 10, 15, 20], True)
    >>> f = [e for e in ereignisse if isinstance(e, Fenster)][-1]
    >>> f.gueltig, round(f.rate_pro_min or 0)
    (True, 12)
    """

    def __init__(self, rate_hz: float) -> None:
        if rate_hz <= 0:
            raise ValueError("rate_hz muss positiv sein")
        self.rate_hz = float(rate_hz)
        self.k = max(1, round(self.rate_hz / FS_ZIEL))
        self.fs = self.rate_hz / self.k
        fs = self.fs
        self.dt = 1.0 / fs
        # Rest eines Blocks zwischen zwei Rahmen (Rohproben und ihre Zeiten)
        self._rest: list[tuple[float, float, float, float]] = []
        # Bewegung
        n_u = max(1, round(UNRUHE_S * fs))
        self._m05 = [_Summe(n_u) for _ in range(3)]
        self._dev2 = _Summe(n_u)
        n_s = max(1, round(SPRUNG_S * fs))
        self._m1 = [_Summe(n_s) for _ in range(3)]
        self._m1_alt: deque[tuple[float, float, float]] = deque(maxlen=n_s)
        self._rand = max(1, round(BEWEGUNG_RAND_S * fs))
        self._seit_bewegung = 10**9  # Proben seit der letzten bewegten
        self._stueck = 0
        self._stueck_alter = 0  # ruhige Proben im laufenden Stück
        # Atemwelle
        self._hp = _Summe(round(HOCHPASS_S * fs))
        self._lp = _Summe(max(1, round(TIEFPASS_S * fs)))
        self._lp_versatz = (self._lp.n - 1) / 2.0 * self.dt
        self._huelle = _Summe(round(HUELLE_S * fs))
        # Wendepunkte
        self._richtung = 0  # +1 steigt (nach einem Tal), −1 fällt, 0 unbekannt
        self._min: tuple[float, float] | None = None  # (Wert, Zeit)
        self._max: tuple[float, float] | None = None
        self._min_ansatz = 0.0  # letzte Zeit nahe am Minimum (Ende der Sohle)
        self._max_ansatz = 0.0
        self._gipfel_wert: float | None = None  # Wert des letzten Gipfels (für den Schwung)
        self._huelle_jetzt = HUELLE_MIN_MG
        self._erster = True  # erster Wendepunkt des Stücks setzt nur die Richtung
        self._nr = 0
        self._letztes_ein: tuple[float, int] | None = None  # (Zeit, Stück)
        self._aus_offen = False  # das laufende Ein hat noch keinen Gipfel
        self._pending: list[Phase] = []  # noch nicht bestätigt (Zeit + Rand)
        self._bestaetigt_ein: deque[tuple[float, int]] = deque()  # (Zeit, Stück), ≤ Fenster
        self._abstaende: deque[float] = deque(maxlen=TYPISCH_ANZAHL)
        # Fenster
        n_f = round(FENSTER_S * fs)
        self._t_ring: deque[float] = deque(maxlen=n_f)
        self._y_ring: deque[float] = deque(maxlen=n_f)
        self._ruhig_ring: deque[bool] = deque(maxlen=n_f)
        self._freqs = np.arange(BAND_HZ[0], BAND_HZ[1] + DF_HZ / 2, DF_HZ)
        self._t_start: float | None = None
        self._naechstes_fenster = FENSTER_S
        self._t_letzte: float | None = None
        self._n_proben = 0
        self._letztes_fenster: Fenster | None = None

    # -- Eingabe --------------------------------------------------------------------------------

    def rahmen(self, xyz: np.ndarray, t0_s: float) -> list[Phase | Fenster]:
        """Einen Rahmen Rohproben ``n × 3`` (mG) ab ``t0_s`` verarbeiten; liefert die neu
        bestätigten Phasen und fertigen Fenster, nach Zeit geordnet."""
        v = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
        if v.shape[0] == 0:
            return []
        t = t0_s + np.arange(v.shape[0]) / self.rate_hz
        # Blockmittel mit dem Rest des vorigen Rahmens
        if self._rest:
            rest = np.array(self._rest)
            t = np.concatenate([rest[:, 0], t])
            v = np.vstack([rest[:, 1:], v])
            self._rest = []
        n = (t.shape[0] // self.k) * self.k
        if n < t.shape[0]:
            self._rest = [(float(t[i]), *map(float, v[i])) for i in range(n, t.shape[0])]
        if n == 0:
            return []
        tb = t[:n].reshape(-1, self.k).mean(axis=1)
        vb = v[:n].reshape(-1, self.k, 3).mean(axis=1)
        heraus: list[Phase | Fenster] = []
        for i in range(tb.shape[0]):
            heraus += self._probe(float(tb[i]), float(vb[i, 0]), float(vb[i, 1]), float(vb[i, 2]))
        heraus.sort(key=lambda e: e.t_s if isinstance(e, Phase) else e.bis_s)
        return heraus

    def abschluss(self) -> list[Phase | Fenster]:
        """Am Ende des Stroms: noch offene Wendepunkte bestätigen (es kommt keine Bewegung mehr)."""
        heraus: list[Phase | Fenster] = list(self._pending)
        for e in self._pending:
            if e.art == EIN:
                self._ein_bestaetigt(e.t_s)
        self._pending = []
        return heraus

    def stand(self) -> Stand:
        """Momentaufnahme für die Anzeige."""
        f = self._letztes_fenster
        ruhig = self._seit_bewegung >= self._rand
        phase = None
        if ruhig and not self._erster:
            phase = EIN if self._richtung > 0 else (AUS if self._richtung < 0 else None)
        return Stand(
            t_s=self._t_letzte if self._t_letzte is not None else 0.0,
            atemzuege=self._nr,
            phase=phase,
            rate_pro_min=f.rate_pro_min if f else None,
            gueltig=bool(f.gueltig) if f else False,
            gruende=f.gruende if f else ("zu_kurz",),
        )

    # -- je Probe ---------------------------------------------------------------------------------

    def _probe(self, t: float, x: float, y: float, z: float) -> list[Phase | Fenster]:
        heraus: list[Phase | Fenster] = []
        if self._t_start is None:
            self._t_start = t
        luecke = self._t_letzte is not None and t - self._t_letzte > MAX_LUECKE_S
        self._t_letzte = t
        self._n_proben += 1
        # Bewegung
        mx, my, mz = self._m05[0].schieben(x), self._m05[1].schieben(y), self._m05[2].schieben(z)
        dev2 = (x - mx) ** 2 + (y - my) ** 2 + (z - mz) ** 2
        unruhe = math.sqrt(self._dev2.schieben(dev2))
        s = (self._m1[0].schieben(x), self._m1[1].schieben(y), self._m1[2].schieben(z))
        sprung = 0.0
        if len(self._m1_alt) == self._m1_alt.maxlen:
            a = self._m1_alt[0]
            sprung = math.sqrt((s[0] - a[0]) ** 2 + (s[1] - a[1]) ** 2 + (s[2] - a[2]) ** 2)
        self._m1_alt.append(s)
        bewegt = luecke or unruhe > UNRUHE_AB_MG or sprung > SPRUNG_AB_MG
        if bewegt:
            heraus += self._bewegung(t)
            self._seit_bewegung = 0
        else:
            self._seit_bewegung += 1
        ruhig = self._seit_bewegung >= self._rand
        if ruhig and self._stueck_alter == 0:
            self._stueck += 1
            self._hp.leeren()
            self._lp.leeren()
            self._huelle.leeren()
            self._richtung = 0
            self._min = self._max = None
            self._gipfel_wert = None
            self._erster = True
        if ruhig:
            self._stueck_alter += 1
        else:
            self._stueck_alter = 0
        # Atemwelle (nur im ruhigen Stück gerechnet)
        yw = 0.0
        if ruhig:
            p = x * RICHTUNG[0] + y * RICHTUNG[1] + z * RICHTUNG[2]
            yh = p - self._hp.schieben(p)
            yw = self._lp.schieben(yh)
            tw = t - self._lp_versatz
            huelle = math.sqrt(self._huelle.schieben(yw * yw)) * math.sqrt(2.0)
            self._huelle_jetzt = max(huelle, HUELLE_MIN_MG)
            heraus += self._wendepunkte(tw, yw, HYSTERESE * self._huelle_jetzt)
        self._t_ring.append(t)
        self._y_ring.append(yw)
        self._ruhig_ring.append(ruhig)
        # Bestätigen, was den Rand überstanden hat
        if self._pending:
            grenze = t - BEWEGUNG_RAND_S
            fertig = [e for e in self._pending if e.t_s <= grenze]
            if fertig:
                self._pending = [e for e in self._pending if e.t_s > grenze]
                for e in fertig:
                    if e.art == EIN:
                        self._ein_bestaetigt(e.t_s)
                heraus += fertig
        # Fenster
        if t - self._t_start >= self._naechstes_fenster - 1e-9:
            self._naechstes_fenster += SCHRITT_S
            f = self._fenster(t)
            self._letztes_fenster = f
            heraus.append(f)
        return heraus

    def _bewegung(self, t: float) -> list[Phase | Fenster]:
        """Eine bewegte Probe: `BEWEGUNG_RAND_S` zurück gilt als bewegt, offene Wendepunkte in
        dieser Spanne fallen weg."""
        grenze = t - BEWEGUNG_RAND_S
        weg = [e for e in self._pending if e.t_s > grenze]
        if weg:
            self._pending = [e for e in self._pending if e.t_s <= grenze]
            for e in weg:
                if e.art == EIN:
                    self._nr -= 1
                    self._letztes_ein = None
                    self._aus_offen = False
        n = min(self._rand, len(self._ruhig_ring))
        for i in range(1, n + 1):
            self._ruhig_ring[-i] = False
        self._stueck_alter = 0
        return []

    def _wendepunkte(self, t: float, y: float, h: float) -> list[Phase | Fenster]:
        heraus: list[Phase | Fenster] = []
        nah = ANSATZ_ANTEIL * h
        if self._min is None or y < self._min[0]:
            self._min = (y, t)
        if self._min is not None and y <= self._min[0] + nah:
            self._min_ansatz = t
        if self._max is None or y > self._max[0]:
            self._max = (y, t)
        if self._max is not None and y >= self._max[0] - nah:
            self._max_ansatz = t
        if self._richtung <= 0 and self._min is not None and y >= self._min[0] + h:
            tal_wert = self._min[0]
            self._richtung = 1
            self._max = (y, t)
            self._max_ansatz = t
            if self._erster:
                self._erster = False
            else:
                heraus += self._tal(self._min_ansatz, tal_wert)
        elif self._richtung >= 0 and self._max is not None and y <= self._max[0] - h:
            self._gipfel_wert = self._max[0]
            gipfel_t = self._max_ansatz
            self._richtung = -1
            self._min = (y, t)
            self._min_ansatz = t
            if self._erster:
                self._erster = False
            elif self._aus_offen:
                self._aus_offen = False
                self._pending.append(Phase(gipfel_t, AUS, self._nr))
        return heraus

    def _tal(self, t: float, wert: float) -> list[Phase | Fenster]:
        """Ein Tal im laufenden Stück: neuer Atemzug, wenn es nicht zu nah am vorigen liegt
        oder der Schwung hinein voll ist (Modultext, Punkt 5)."""
        if self._letztes_ein is not None and self._letztes_ein[1] == self._stueck:
            abstand = t - self._letztes_ein[0]
            kurz = MIN_ATEMZUG_S
            if len(self._abstaende) >= 2:
                kurz = max(kurz, KURZ_ANTEIL * float(np.median(self._abstaende)))
            schwung = (self._gipfel_wert - wert) if self._gipfel_wert is not None else 0.0
            if abstand < MIN_ATEMZUG_S or (
                abstand < kurz and schwung < MIN_SCHWUNG * self._huelle_jetzt
            ):
                return []
        self._nr += 1
        self._letztes_ein = (t, self._stueck)
        self._aus_offen = True
        self._pending.append(Phase(t, EIN, self._nr))
        return []

    def _ein_bestaetigt(self, t: float) -> None:
        if self._bestaetigt_ein and self._bestaetigt_ein[-1][1] == self._stueck:
            self._abstaende.append(t - self._bestaetigt_ein[-1][0])
        self._bestaetigt_ein.append((t, self._stueck))
        while self._bestaetigt_ein and self._bestaetigt_ein[0][0] < t - 2 * FENSTER_S:
            self._bestaetigt_ein.popleft()

    # -- Fenster ----------------------------------------------------------------------------------

    def _fenster(self, bis: float) -> Fenster:
        von = bis - FENSTER_S
        t = np.fromiter(self._t_ring, dtype=np.float64)
        y = np.fromiter(self._y_ring, dtype=np.float64)
        ruhig = np.fromiter(self._ruhig_ring, dtype=bool)
        ruhe = float(ruhig.mean()) if ruhig.size else 0.0
        ein = [z for z, _ in self._bestaetigt_ein if von <= z <= bis]
        stk = [s for z, s in self._bestaetigt_ein if von <= z <= bis]
        abst = np.array(
            [
                b - a
                for a, b, sa, sb in zip(ein[:-1], ein[1:], stk[:-1], stk[1:], strict=True)
                if sa == sb
            ]
        )
        rate_roh = 60.0 / float(np.median(abst)) if abst.size >= 2 else None
        cv = float(abst.std() / abst.mean()) if abst.size >= 2 and abst.mean() > 0 else None
        gruende: list[str] = []
        yq = y[ruhig]
        amplitude = float(yq.std()) if yq.size else 0.0
        f0_pro_min: float | None = None
        if ruhe < MIN_RUHE_ANTEIL or yq.size < self.fs * 10:
            gruende.append("bewegung")
        else:
            if amplitude < MIN_AMPLITUDE_MG:
                gruende.append("amplitude_klein")
            p = lomb_psd(t[ruhig], yq - yq.mean(), self._freqs)
            f0 = gipfel(self._freqs, p, *SUCH_HZ)
            if f0 is None:
                gruende.append("kein_gipfel")
            else:
                f0_pro_min = f0 * 60.0
                if anteil(self._freqs, p, f0) < MIN_ANTEIL:
                    gruende.append("gipfel_undeutlich")
            bezug = rate_roh if rate_roh is not None else f0_pro_min
            if rate_roh is None or abst.size < noetige_abstaende(bezug or 12.0, FENSTER_S * ruhe):
                gruende.append("zu_wenig_zyklen")
            else:
                if cv is not None and cv > MAX_CV:
                    gruende.append("ungleichmaessig")
                if f0_pro_min is not None and abs(rate_roh - f0_pro_min) > max(
                    MAX_ABWEICHUNG_PRO_MIN, MAX_ABWEICHUNG_REL * f0_pro_min
                ):
                    gruende.append("zyklen_passen_nicht")
        gueltig = not gruende
        return Fenster(
            von_s=round(von, 3),
            bis_s=round(bis, 3),
            rate_pro_min=round(rate_roh, 2) if gueltig and rate_roh is not None else None,
            gueltig=gueltig,
            gruende=tuple(gruende),
            zyklen=int(abst.size),
            ruhe=round(ruhe, 3),
            amplitude_mg=round(amplitude, 2),
            cv=None if cv is None else round(cv, 3),
            gipfel_pro_min=None if f0_pro_min is None else round(f0_pro_min, 2),
            rate_roh=None if rate_roh is None else round(rate_roh, 2),
        )


def atemzuege(
    xyz: np.ndarray, rate_hz: float, t0_s: float = 0.0, rahmen_s: float = 1.0
) -> Atemzuege:
    """Offline-Hülle über `AtemLive`: dieselbe Rechnung, rahmenweise mit ``rahmen_s``.

    >>> rate = 200.0
    >>> t = np.arange(0, 90, 1 / rate)
    >>> welle = -12 * np.cos(2 * np.pi * t / 4.0)                # 15/min
    >>> xyz = np.column_stack([980 + welle, 0 * t, 30 + 0 * t])  # liegend: x steigt beim Einatmen
    >>> a = atemzuege(xyz, rate)
    >>> a.gueltig, round(a.rate_pro_min or 0), len(a.ein_s) >= 20, a.art
    (True, 15, True, 'prototyp')
    """
    v = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
    live = AtemLive(rate_hz)
    schritt = max(1, round(rahmen_s * rate_hz))
    ereignisse: list[Phase | Fenster] = []
    for i in range(0, v.shape[0], schritt):
        ereignisse += live.rahmen(v[i : i + schritt], t0_s + i / rate_hz)
    ereignisse += live.abschluss()
    phasen = sorted((e for e in ereignisse if isinstance(e, Phase)), key=lambda e: e.t_s)
    fenster = tuple(e for e in ereignisse if isinstance(e, Fenster))
    ein = tuple(e.t_s for e in phasen if e.art == EIN)
    aus = tuple(e.t_s for e in phasen if e.art == AUS)
    gueltige = [f.rate_pro_min for f in fenster if f.gueltig and f.rate_pro_min is not None]
    abst = np.array(live._abstaende) if len(live._abstaende) >= 2 else np.empty(0)
    gleich = float(max(0.0, 1.0 - abst.std() / abst.mean())) if abst.size >= 2 else 0.0
    gruende: tuple[str, ...] = ()
    if not gueltige:
        zaehlung: dict[str, int] = {}
        for f in fenster:
            for g in f.gruende:
                zaehlung[g] = zaehlung.get(g, 0) + 1
        gruende = tuple(sorted(zaehlung, key=lambda g: -zaehlung[g])) or ("zu_kurz",)
    return Atemzuege(
        ein_s=ein,
        aus_s=aus,
        rate_pro_min=round(float(np.median(gueltige)), 2) if gueltige else None,
        gleichmaessigkeit=round(gleich, 3),
        gueltig=bool(gueltige),
        gruende=gruende,
        fenster=fenster,
    )


__all__ = [
    "AUS",
    "BAND_HZ",
    "BEWEGUNG_RAND_S",
    "EIN",
    "FENSTER_S",
    "FS_ZIEL",
    "HOCHPASS_S",
    "HUELLE_MIN_MG",
    "HUELLE_S",
    "HYSTERESE",
    "KENNZEICHEN",
    "KURZ_ANTEIL",
    "MAX_CV",
    "MIN_AMPLITUDE_MG",
    "MIN_ATEMZUG_S",
    "MIN_RUHE_ANTEIL",
    "RICHTUNG",
    "SCHRITT_S",
    "SPRUNG_AB_MG",
    "SUCH_HZ",
    "TIEFPASS_S",
    "UNRUHE_AB_MG",
    "AtemLive",
    "Atemzuege",
    "Fenster",
    "Phase",
    "Stand",
    "anteil",
    "atemzuege",
    "gipfel",
    "noetige_abstaende",
]
