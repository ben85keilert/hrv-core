"""PROTOTYP — Atem-HRV je Atemzug aus Atemphasen und RR-Abständen (nicht Grundlage
gespeicherter Kennzahlen, darf sich ohne ``ALGO_VERSION`` ändern; Regeln: `hrv_core.prototyp`).

Herkunft: hrv-research ``src/hrv_research/beschleunigung/atem_hrv.py`` (Entscheidung 25,
5.11.2026; Forschungspaket F5). Eingang sind die Phasen (Beginn „ein“ / „aus“, etwa aus
`hrv_core.prototyp.atemzuege` bzw. dem Beiwerk ``atem-v1`` oder aus dem Takt) und die Schläge
(Zeit und RR) **auf derselben Achse**. Je **vollständigem Atemzug** (ein → aus → nächstes ein)
entstehen die Größen aus `trainingsapp/docs/plan_beschleunigung.md` §7.1 — beschreibend, ohne
Bewertung:

1. **Schläge zuordnen:** Jeder Schlag liegt auf der **Mitte** seines Intervalls
   (``t − rr/2``), wie das Tachogramm in `hrv_core.atmung`; zum Atemzug gehören die Schläge mit
   Mitte in ``[ein, ende)``, zur Phase „ein“ die mit Mitte in ``[ein, aus)``, zu „aus“ der Rest.
   Schläge ohne plausibles RR (NaN, außerhalb `RR_MIN_MS`–`RR_MAX_MS`) zählen nicht und machen
   den Atemzug ungültig (``artefakt``).
2. **Trendbereinigung** (`lewis2012metrics`: die Gipfel-Tal-Spanne ist von allen RSA-Maßen am
   stärksten durch Nichtstationarität verzerrt, nach Trendentfernung nicht mehr): Der Trend
   innerhalb eines Atemzugs ist die **Gerade durch die mittleren RR des vorigen und dieses
   Atemzugs** (jeweils an der Mitte des Atemzugs). Das Mittel über einen vollen Atemzug löscht
   die Atemschwingung selbst (ein Mittel über genau eine Periode hat bei dieser Frequenz den
   Gewinn null) und behält, was langsamer ist: Erholung, Drift, Mayer-Welle, soweit sie in
   zwei Atemzügen linear ist. Ein Polynom **innerhalb** des Atemzugs schiede aus — eine Kubik
   über eine Sinusperiode nimmt den größten Teil der Schwingung mit; ein längeres Fenster
   (Porges–Bohrer, gleitendes Polynom) folgte einer Erholung nach Belastung schlechter und
   brauchte Zukunft. Fehlt der Vorgänger (erster Atemzug, Lücke davor, Vorgänger ohne Schläge),
   ist der Trend die Konstante des eigenen Mittels. **Kausal:** nur Vergangenheit — darum liefern
   Live- und Offline-Fassung dieselben Zahlen.
3. **Atemspanne** = Gipfel − Tal des trendbereinigten Rests: `spanne_ms` (RR, längster minus
   kürzester) und `spanne_bpm` (Herzfrequenz ``60000/rr``, dieselbe Gerade auf der HF). Dazu
   `sinus_bpm`: Spitze–Tal eines an den HF-Rest angepassten Sinus mit der Periode des Atemzugs
   (Kleinste Quadrate, ``a·cos + b·sin + c``) — bei wenigen Schlägen je Atemzug (20/min bei
   75 bpm: knapp vier) unterschätzt das rohe Gipfel–Tal die Schwingung, der Sinus nicht.
4. **Phasenlage** (`eckberg1983sinus`: der Phasenwinkel wandert linear mit dem Atemintervall):
   `winkel_grad` ist die Lage des HF-Maximums des angepassten Sinus ab Beginn „ein“ (0–360°,
   feiner als ein Schlagabstand), `phasenlage_s` die Zeit vom Ende des Einatmens (``aus_s``)
   bis zu diesem Gipfel, **zirkulär** in ``(−dauer/2, dauer/2]`` (negativ: der Gipfel liegt
   noch im Einatmen), `phasenlage_anteil` dasselbe als Anteil der Atemzugdauer. Der Sinus
   statt des höchsten Schlags, weil der Gipfel bei 12–20/min nahe am Beginn des Einatmens
   liegt (die Herzfrequenz folgt der Atmung mit mehreren Sekunden Verzug) — der höchste
   Schlag springt dann zufällig zwischen Anfang und Ende des Atemzugs. `gipfel_s`/`tal_s`
   (Mitte des Schlags mit höchstem bzw. tiefstem HF-Rest) bleiben zur Anzeige.
5. **RR je Phase:** `rr_ein_ms`, `rr_aus_ms` = Mittel des trendbereinigten Rests je Phase plus
   das Mittel des Atemzugs; `rr_differenz_ms = rr_aus_ms − rr_ein_ms` (positiv, wenn das
   Ausatmen die längeren Abstände hat). `ein_aus` ist die Dauer des Ausatmens je Dauer des
   Einatmens (wie die Karte der App: „1 : 1,4“).
6. **Gültigkeit** je Atemzug, Gründe als snake_case in Prüfreihenfolge: ``zu_kurz`` /
   ``zu_lang`` (Dauer außerhalb des Atembands `hrv_core.atmung.ATEM_BAND_HZ`, 3–42/min),
   ``artefakt`` (Schlag ohne plausibles RR), ``luecke`` (zwei aufeinanderfolgende Schlagzeiten
   im oder um den Atemzug weiter als `MAX_LUECKE_S` auseinander — länger als jedes plausible
   RR, also fehlt ein Schlag), ``zu_wenig_schlaege`` (unter `MIN_SCHLAEGE_JE_ATEMZUG`, aus
   `hrv_core.atmung`: darunter tastet der Herzschlag die Atmung nicht ab), ``phase_ohne_schlag``
   (eine Phase ohne Schlag — RR je Phase und Phasenlage wären geraten), ``dauer_untypisch``
   (Dauer unter `KURZ_ANTEIL` oder über `LANG_ANTEIL` des Medians der letzten
   `TYPISCH_ANZAHL` gültigen Atemzüge, ab `MIN_TYPISCH` davon: ein verpasster Atemzug macht
   aus zweien einen doppelt langen, ein gespaltener zwei halbe — beide Spannen wären falsch),
   ``fenster_ungueltig`` (nur mit Prüffenstern des Phasen-Prototyps, `AtemHrvLive.fenster`:
   das **erste Fenster, das nach dem Atemzug endet**, war nicht gültig — unter Bewegung liefert
   der Sensor Phasen, die keine Atemzüge sind, und die Schläge dazu sehen harmlos aus; ein
   festes Fenster statt „irgendein gültiges, das den Atemzug deckt“, damit live und offline
   dieselbe Antwort geben).
   Zahlen gibt es auch für ungültige Atemzüge (zur Diagnose); die Zusammenfassung nimmt nur
   gültige.
7. **Zusammenfassung** je Bereich (`zusammenfassen`): Median und Quartile der Spannen, Mittel
   von ``ln(spanne_ms)`` für Verläufe (`lewis2012metrics`: logarithmische Skala, sobald über
   Sitzungen verglichen wird), Median der Phasenlage, zirkuläres Mittel des Winkels, Median
   Ein:Aus und RR-Differenz, Rate aus dem Median der Dauern, Anteil gültiger Atemzüge, Gründe
   nach Häufigkeit.

**Live** (`AtemHrvLive`): Phasen und Schläge kommen, wie sie eintreffen; ein Atemzug wird
gerechnet, sobald sein Ende (das nächste „ein“) bekannt ist **und** ein Schlag bis dorthin
reicht — egal, ob die Phase nach den Schlägen kommt (Sensor, Verzug ein bis zwei Sekunden) oder
vor ihnen (Takt, im Voraus bekannt). Werden Prüffenster gemeldet, wartet er zusätzlich auf das
erste Fenster, das nach dem Atemzug endet (höchstens `SCHRITT_S` des Phasen-Prototyps plus
dessen Verzug); `abschluss` rechnet, was am Ende eines Laufs noch wartet, mit dem letzten
bekannten Fenster. `atem_hrv` ist die Offline-Hülle darüber: dieselben Zahlen.

**Bekannte Grenzen:** ein Mensch, ein Tag, ein Gurt; geprüft nur an einer Sitzung mit Takt und
einer unter Störung. Ohne Phasen keine Zahl; mit Phasen aus dem Sensor hängt alles an deren
Güte — darum die Fensterprüfung, und mit ihr hinkt die Live-Spanne bis zu `SCHRITT_S` des
Phasen-Prototyps (`hrv_core.prototyp.atemzuege`) plus dessen Verzug nach. Bei vier Schlägen je
Atemzug ist das rohe Gipfel–Tal grob (der Sinus ist die zweite Zahl). Ein verpasster
(doppelt langer) und ein gespaltener (halber) Atemzug fallen über ``dauer_untypisch`` heraus;
der verkürzte Atemzug vor einer Spaltung (etwa drei Viertel des Typischen) bleibt gültig.
Es gibt keine Bewertung: Zahlen, Phasen, Gültigkeit mit Gründen — kein Rat.

**Eingang mit Ausnahme** (Entscheidung 25 in hrv-research): geprüft an einer Sitzung mit Takt
(Simulator und Mensch) und einer unter Störung eines Menschen, nicht an zwei unabhängigen
Sitzungen. Nur numpy (``np.linalg.lstsq`` für den Sinus). Keine Konstante wurde an den Daten
eingestellt: Atemband und Mindestschläge aus `hrv_core.atmung`, RR-Grenzen aus
`hrv_core.constants`, die Dauerregel aus dem Phasen-Prototyp.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ..atmung import ATEM_BAND_HZ, MIN_SCHLAEGE_JE_ATEMZUG
from ..constants import RR_MAX_MS, RR_MIN_MS
from . import KENNZEICHEN

#: Die beiden Phasen, wie `atem-v1` sie schreibt
EIN = "ein"
AUS = "aus"

#: Dauer eines Atemzugs (s): das Atemband von `hrv_core.atmung` (3–42/min)
MIN_DAUER_S = 1.0 / ATEM_BAND_HZ[1]
MAX_DAUER_S = 1.0 / ATEM_BAND_HZ[0]
#: Zwei Schlagzeiten weiter auseinander als das längste plausible RR: ein Schlag fehlt
MAX_LUECKE_S = RR_MAX_MS / 1000.0
#: Untypische Dauer: unter `KURZ_ANTEIL` bzw. über `LANG_ANTEIL` des Medians der letzten
#: `TYPISCH_ANZAHL` gültigen Atemzüge — ein verpasster Atemzug verdoppelt, ein gespaltener
#: halbiert die Dauer; spontane Atmung streut um 20–30 %, Seufzer fallen heraus (gewollt).
#: Geprüft erst ab `MIN_TYPISCH` gültigen Atemzügen.
KURZ_ANTEIL = 0.55
LANG_ANTEIL = 1.6
TYPISCH_ANZAHL = 8
MIN_TYPISCH = 3
#: Zeitgleich bis auf Rundung (3 Nachkommastellen im Beiwerk)
_EPS = 1e-6

#: Gründe in Prüfreihenfolge
ZU_KURZ = "zu_kurz"
ZU_LANG = "zu_lang"
ARTEFAKT = "artefakt"
LUECKE = "luecke"
ZU_WENIG_SCHLAEGE = "zu_wenig_schlaege"
PHASE_OHNE_SCHLAG = "phase_ohne_schlag"
DAUER_UNTYPISCH = "dauer_untypisch"
FENSTER_UNGUELTIG = "fenster_ungueltig"


@dataclass(frozen=True, slots=True)
class Atemzug:
    """Die Größen eines vollständigen Atemzugs ``ein → aus → ende`` (= nächstes „ein“).

    Zahlen stehen auch bei ``gueltig=False`` (soweit rechenbar) — zur Diagnose, nie zur Anzeige
    als Kennzahl. ``art`` ist immer `KENNZEICHEN`.
    """

    ein_s: float
    aus_s: float
    ende_s: float
    #: Schläge mit plausiblem RR im Atemzug
    n: int
    #: Gipfel − Tal nach Trendbereinigung: RR (ms) und Herzfrequenz (bpm)
    spanne_ms: float | None
    spanne_bpm: float | None
    #: Spitze–Tal eines Sinus mit der Periode des Atemzugs, an den HF-Rest angepasst
    sinus_bpm: float | None
    #: Mitte des Schlags mit dem höchsten bzw. tiefsten HF-Rest
    gipfel_s: float | None
    tal_s: float | None
    #: Zeit vom Ende des Einatmens bis zum HF-Gipfel (s; negativ: Gipfel im Einatmen) …
    phasenlage_s: float | None
    #: … und als Anteil der Dauer des Atemzugs
    phasenlage_anteil: float | None
    #: Lage des HF-Maximums des Sinus ab Beginn „ein“ (0–360°)
    winkel_grad: float | None
    #: Mittleres RR des Atemzugs (ms) und je Phase (trendbereinigt um das Mittel gelegt)
    rr_mittel_ms: float | None
    rr_ein_ms: float | None
    rr_aus_ms: float | None
    #: ``rr_aus_ms − rr_ein_ms``
    rr_differenz_ms: float | None
    #: Steigung der Trendgeraden (ms je s); 0, wenn kein Vorgänger
    trend_ms_je_s: float
    gueltig: bool
    gruende: tuple[str, ...]
    art: str = KENNZEICHEN

    @property
    def dauer_s(self) -> float:
        return self.ende_s - self.ein_s

    @property
    def ein_dauer_s(self) -> float:
        return self.aus_s - self.ein_s

    @property
    def aus_dauer_s(self) -> float:
        return self.ende_s - self.aus_s

    @property
    def ein_aus(self) -> float | None:
        """Dauer des Ausatmens je Dauer des Einatmens („1 : 1,4“)."""
        return self.aus_dauer_s / self.ein_dauer_s if self.ein_dauer_s > 0 else None


@dataclass(frozen=True, slots=True)
class AtemHrv:
    """Zusammenfassung über die gültigen Atemzüge eines Bereichs — ``None`` ohne gültigen."""

    n: int
    n_gueltig: int
    #: 60 / Median der Dauern (gültige Atemzüge)
    rate_pro_min: float | None
    spanne_ms_median: float | None
    spanne_ms_q25: float | None
    spanne_ms_q75: float | None
    spanne_bpm_median: float | None
    spanne_bpm_q25: float | None
    spanne_bpm_q75: float | None
    sinus_bpm_median: float | None
    #: Mittel von ``ln(spanne_ms)`` — die Skala für Verläufe (`lewis2012metrics`)
    ln_spanne_ms: float | None
    phasenlage_s_median: float | None
    phasenlage_anteil_median: float | None
    #: zirkuläres Mittel der Winkel (0–360°)
    winkel_grad: float | None
    ein_aus_median: float | None
    rr_differenz_ms_median: float | None
    #: Gründe der ungültigen Atemzüge, häufigste zuerst
    gruende: tuple[str, ...]
    art: str = KENNZEICHEN

    @property
    def anteil_gueltig(self) -> float | None:
        return self.n_gueltig / self.n if self.n else None


@dataclass(frozen=True, slots=True)
class _Vorgaenger:
    """Was vom vorigen Atemzug für den Trend bleibt."""

    mitte_s: float
    ende_s: float
    rr_mittel: float
    hf_mittel: float


def _gerade(
    mitte: np.ndarray, werte: np.ndarray, vorher: tuple[float, float] | None, mitte_s: float
) -> tuple[np.ndarray, float]:
    """Trendgerade durch (Mitte, Mittel) des Vorgängers und dieses Atemzugs — ohne Vorgänger
    die Konstante. Liefert den Rest und die Steigung."""
    mittel = float(werte.mean())
    if vorher is None or abs(mitte_s - vorher[0]) < _EPS:
        return werte - mittel, 0.0
    steigung = (mittel - vorher[1]) / (mitte_s - vorher[0])
    return werte - (mittel + steigung * (mitte - mitte_s)), float(steigung)


def _sinus(tau: np.ndarray, rest: np.ndarray, dauer: float) -> tuple[float, float] | None:
    """Sinus mit der Periode ``dauer`` an den Rest anpassen: (Spitze–Tal, Winkel des Maximums
    in Grad ab τ = 0)."""
    if tau.size < 3:
        return None
    omega = 2.0 * math.pi / dauer
    a = np.column_stack([np.cos(omega * tau), np.sin(omega * tau), np.ones_like(tau)])
    koeff = np.linalg.lstsq(a, rest, rcond=None)[0]
    amplitude = float(math.hypot(koeff[0], koeff[1]))
    winkel = math.degrees(math.atan2(koeff[1], koeff[0])) % 360.0
    return 2.0 * amplitude, winkel


class AtemHrvLive:
    """Atemzüge rechnen, sobald sie vollständig sind (Modultext). Phasen über `phase`, Schläge
    über `schlag`; beide geben fertige `Atemzug` zurück. `letzter` ist der zuletzt gerechnete.

    >>> live = AtemHrvLive()
    >>> _ = live.phase(0.0, "ein"); _ = live.phase(2.0, "aus")
    >>> fertig = []
    >>> for k in range(12):                       # 75 bpm, RSA ±40 ms (Periode 5 s)
    ...     t = 0.8 * (k + 1)
    ...     rr = 800 - 40 * math.cos(2 * math.pi * (t - 0.4 - 1.0) / 5.0)
    ...     fertig += live.schlag(t, rr)
    >>> fertig += live.phase(5.0, "ein")           # Ende des ersten Atemzugs bekannt …
    >>> fertig += live.schlag(10.4, 800.0)         # … und ein Schlag reicht darüber hinaus
    >>> z = fertig[0]
    >>> z.n, z.gueltig, z.art, round(z.dauer_s, 1), round(z.ein_aus, 1)
    (6, True, 'prototyp', 5.0, 1.5)
    >>> 60 < z.spanne_ms < 85 and z.rr_differenz_ms is not None
    True
    """

    def __init__(self) -> None:
        self._ein: float | None = None
        self._aus: float | None = None
        #: vollständige Atemzüge, deren Schläge noch nicht bis zum Ende reichen
        self._wartend: deque[tuple[float, float, float]] = deque()
        #: Schlagzeiten (Ende des Intervalls) und RR, ab dem Schlag vor dem ältesten offenen
        self._t: deque[float] = deque()
        self._rr: deque[float] = deque()
        self._vorher: _Vorgaenger | None = None
        self._dauern: deque[float] = deque(maxlen=TYPISCH_ANZAHL)
        #: Prüffenster ``(von, bis, gueltig)`` ab dem ältesten offenen Atemzug; ``None``, solange
        #: keines gemeldet wurde (dann gibt es keine Fensterprüfung)
        self._fenster: deque[tuple[float, float, bool]] | None = None
        self.letzter: Atemzug | None = None

    def phase(self, t_s: float, art: str) -> list[Atemzug]:
        """Beginn einer Phase (`EIN` oder `AUS`), zeitlich aufsteigend."""
        t = float(t_s)
        if art == EIN:
            if self._ein is not None and self._aus is not None and t > self._aus:
                self._wartend.append((self._ein, self._aus, t))
            self._ein, self._aus = t, None
        elif art == AUS and self._ein is not None and self._aus is None and t > self._ein:
            self._aus = t
        return self._abarbeiten()

    def schlag(self, t_s: float, rr_ms: float) -> list[Atemzug]:
        """Ein Schlag: Zeit (Ende des Intervalls) und RR (NaN = ausgeschlossen)."""
        self._t.append(float(t_s))
        self._rr.append(float(rr_ms))
        return self._abarbeiten()

    def fenster(self, von_s: float, bis_s: float, gueltig: bool) -> list[Atemzug]:
        """Ein Prüffenster des Phasen-Prototyps (`atem-v1`: ``fenster[]``), zeitlich aufsteigend.
        Ab dem ersten gilt: ein Atemzug ist nur gültig, wenn das erste Fenster, das nach ihm
        endet, gültig ist."""
        if self._fenster is None:
            self._fenster = deque()
        self._fenster.append((float(von_s), float(bis_s), bool(gueltig)))
        return self._abarbeiten()

    def abschluss(self) -> list[Atemzug]:
        """Ende eines Laufs: was noch auf ein Fenster wartet, wird mit dem letzten bekannten
        Fenster gerechnet (überlappt es den Atemzug nicht, gilt ``fenster_ungueltig``)."""
        return self._abarbeiten(schluss=True)

    def _fenster_gueltig(self, ein: float, ende: float, schluss: bool) -> bool | None:
        """Gültigkeit des ersten Fensters, das nach ``ende`` endet — ``None``: noch keins da."""
        if self._fenster is None:
            return True
        for von, bis, gueltig in self._fenster:
            if bis >= ende:
                return gueltig and von <= ein
        if schluss and self._fenster:
            von, bis, gueltig = self._fenster[-1]
            return gueltig and bis > ein
        return None

    def _abarbeiten(self, schluss: bool = False) -> list[Atemzug]:
        fertig: list[Atemzug] = []
        while self._wartend and self._t and self._t[-1] >= self._wartend[0][2]:
            ein, aus, ende = self._wartend[0]
            im_fenster = self._fenster_gueltig(ein, ende, schluss)
            if im_fenster is None:
                break
            self._wartend.popleft()
            z = self._rechnen(ein, aus, ende, im_fenster)
            fertig.append(z)
            self.letzter = z
        self._aufraeumen()
        return fertig

    def _aufraeumen(self) -> None:
        """Schläge vor dem ältesten noch offenen Atemzug vergessen — einen davor behalten."""
        grenze = self._wartend[0][0] if self._wartend else self._ein
        if grenze is None:
            grenze = self._t[-1] if self._t else None
        if grenze is None:
            return
        while len(self._t) >= 2 and self._t[1] < grenze:
            self._t.popleft()
            self._rr.popleft()
        if self._fenster:
            while len(self._fenster) >= 2 and self._fenster[0][1] < grenze:
                self._fenster.popleft()

    def _rechnen(self, ein: float, aus: float, ende: float, im_fenster: bool = True) -> Atemzug:
        t = np.fromiter(self._t, dtype=float)
        rr = np.fromiter(self._rr, dtype=float)
        dauer = ende - ein
        gruende: list[str] = []
        if dauer < MIN_DAUER_S:
            gruende.append(ZU_KURZ)
        elif dauer > MAX_DAUER_S:
            gruende.append(ZU_LANG)
        # Lücke: Schlagzeiten vom letzten vor „ein“ bis zum ersten ab „ende“
        davor = np.flatnonzero(t < ein)
        ab = np.flatnonzero(t >= ende)
        start = int(davor[-1]) if davor.size else 0
        stop = int(ab[0]) if ab.size else t.size - 1
        kette = t[start : stop + 1]
        if np.any(np.diff(kette) > MAX_LUECKE_S) or (not davor.size and t[0] - ein > MAX_LUECKE_S):
            luecke = True
        else:
            luecke = False
        # Mitte des Intervalls; ohne RR (NaN) die Mitte zwischen den Schlagzeiten
        davor_t = np.concatenate(([t[0] - MAX_LUECKE_S / 2.0], t[:-1]))
        mitte_alle = np.where(np.isfinite(rr), t - rr / 2000.0, (t + davor_t) / 2.0)
        im = (mitte_alle >= ein) & (mitte_alle < ende)
        plausibel = np.isfinite(rr) & (rr >= RR_MIN_MS) & (rr <= RR_MAX_MS)
        if np.any(im & ~plausibel):
            gruende.append(ARTEFAKT)
        if luecke:
            gruende.append(LUECKE)
        gut = im & plausibel
        n = int(gut.sum())
        if n < MIN_SCHLAEGE_JE_ATEMZUG:
            gruende.append(ZU_WENIG_SCHLAEGE)
        mitte = mitte_alle[gut]
        r = rr[gut]
        in_ein = mitte < aus
        if n and (not in_ein.any() or in_ein.all()):
            gruende.append(PHASE_OHNE_SCHLAG)
        if len(self._dauern) >= MIN_TYPISCH:
            typisch = float(np.median(self._dauern))
            if dauer < KURZ_ANTEIL * typisch or dauer > LANG_ANTEIL * typisch:
                gruende.append(DAUER_UNTYPISCH)
        if not im_fenster:
            gruende.append(FENSTER_UNGUELTIG)

        werte: dict[str, float | None] = dict.fromkeys(
            (
                "spanne_ms",
                "spanne_bpm",
                "sinus_bpm",
                "gipfel_s",
                "tal_s",
                "phasenlage_s",
                "phasenlage_anteil",
                "winkel_grad",
                "rr_mittel_ms",
                "rr_ein_ms",
                "rr_aus_ms",
                "rr_differenz_ms",
            )
        )
        steigung = 0.0
        mitte_s = ein + dauer / 2.0
        if n >= 2:
            hf = 60000.0 / r
            vorher = self._vorher
            if vorher is not None and abs(vorher.ende_s - ein) > _EPS:
                vorher = None
            rest_rr, steigung = _gerade(
                mitte, r, None if vorher is None else (vorher.mitte_s, vorher.rr_mittel), mitte_s
            )
            rest_hf, _ = _gerade(
                mitte, hf, None if vorher is None else (vorher.mitte_s, vorher.hf_mittel), mitte_s
            )
            k_max, k_min = int(np.argmax(rest_hf)), int(np.argmin(rest_hf))
            rr_mittel = float(r.mean())
            werte["spanne_ms"] = round(float(rest_rr.max() - rest_rr.min()), 1)
            werte["spanne_bpm"] = round(float(rest_hf[k_max] - rest_hf[k_min]), 2)
            werte["gipfel_s"] = round(float(mitte[k_max]), 3)
            werte["tal_s"] = round(float(mitte[k_min]), 3)
            werte["rr_mittel_ms"] = round(rr_mittel, 1)
            if in_ein.any() and not in_ein.all():
                r_ein = rr_mittel + float(rest_rr[in_ein].mean())
                r_aus = rr_mittel + float(rest_rr[~in_ein].mean())
                werte["rr_ein_ms"] = round(r_ein, 1)
                werte["rr_aus_ms"] = round(r_aus, 1)
                werte["rr_differenz_ms"] = round(r_aus - r_ein, 1)
            sinus = _sinus(mitte - ein, rest_hf, dauer)
            if sinus is not None:
                werte["sinus_bpm"] = round(sinus[0], 2)
                werte["winkel_grad"] = round(sinus[1], 1)
                # Gipfel des Sinus ab „aus“, zirkulär in (−dauer/2, dauer/2]
                lage = (ein + sinus[1] / 360.0 * dauer - aus + dauer / 2.0) % dauer - dauer / 2.0
                werte["phasenlage_s"] = round(float(lage), 3)
                werte["phasenlage_anteil"] = round(float(lage / dauer), 3)
            self._vorher = _Vorgaenger(mitte_s, ende, rr_mittel, float(hf.mean()))
        else:
            self._vorher = None
        gueltig = not gruende
        if gueltig:
            self._dauern.append(dauer)
        return Atemzug(
            ein_s=ein,
            aus_s=aus,
            ende_s=ende,
            n=n,
            spanne_ms=werte["spanne_ms"],
            spanne_bpm=werte["spanne_bpm"],
            sinus_bpm=werte["sinus_bpm"],
            gipfel_s=werte["gipfel_s"],
            tal_s=werte["tal_s"],
            phasenlage_s=werte["phasenlage_s"],
            phasenlage_anteil=werte["phasenlage_anteil"],
            winkel_grad=werte["winkel_grad"],
            rr_mittel_ms=werte["rr_mittel_ms"],
            rr_ein_ms=werte["rr_ein_ms"],
            rr_aus_ms=werte["rr_aus_ms"],
            rr_differenz_ms=werte["rr_differenz_ms"],
            trend_ms_je_s=round(steigung, 3),
            gueltig=gueltig,
            gruende=tuple(gruende),
        )


def atem_hrv(
    phasen: Sequence[tuple[float, str]],
    t_s: Sequence[float] | np.ndarray,
    rr_ms: Sequence[float] | np.ndarray,
    fenster: Sequence[tuple[float, float, bool]] | None = None,
) -> list[Atemzug]:
    """Offline-Hülle über `AtemHrvLive`: Phasen ``[(t_s, "ein"|"aus")]`` und Schläge (Zeit =
    Ende des Intervalls, RR in ms; NaN = ausgeschlossen) auf derselben Achse, in Zeitfolge
    eingespeist, wahlweise die Prüffenster ``[(von_s, bis_s, gueltig)]`` des Phasen-Prototyps
    — dieselben Zahlen wie live.

    >>> t = np.cumsum(np.full(60, 0.8))                       # 75 bpm, 48 s
    >>> rr = 800 - 40 * np.cos(2 * np.pi * (t - 0.4 - 1.0) / 5.0)   # RSA ±40 ms, Periode 5 s
    >>> phasen = [(5.0 * k + p, art) for k in range(10) for p, art in ((0.0, "ein"), (2.0, "aus"))]
    >>> zuege = atem_hrv(phasen, t, rr)
    >>> len(zuege), all(z.gueltig for z in zuege), zuege[0].art
    (9, True, 'prototyp')
    >>> z = zusammenfassen(zuege)
    >>> z.n, z.rate_pro_min, 60 < z.spanne_ms_median < 85, round(z.ein_aus_median, 1)
    (9, 12.0, True, 1.5)
    """
    t = np.asarray(t_s, dtype=float)
    r = np.asarray(rr_ms, dtype=float)
    ereignisse: list[tuple[float, int, float, str]] = [
        (float(p[0]), 0, 0.0, str(p[1])) for p in phasen
    ]
    ereignisse += [(float(tk), 1, float(rk), "") for tk, rk in zip(t, r, strict=True)]
    ereignisse += [(float(bis), 2, float(von), "1" if ok else "") for von, bis, ok in fenster or ()]
    ereignisse.sort(key=lambda e: (e[0], e[1]))
    live = AtemHrvLive()
    zuege: list[Atemzug] = []
    for zeit, art_nr, wert, art in ereignisse:
        if art_nr == 0:
            zuege += live.phase(zeit, art)
        elif art_nr == 1:
            zuege += live.schlag(zeit, wert)
        else:
            zuege += live.fenster(wert, zeit, art == "1")
    return zuege + live.abschluss()


def _rund(x: float | None, k: int) -> float | None:
    return None if x is None else round(x, k)


def _median(werte: list[float]) -> float | None:
    return float(np.median(werte)) if werte else None


def _quartil(werte: list[float], q: float) -> float | None:
    return float(np.percentile(werte, q)) if werte else None


def zusammenfassen(zuege: Sequence[Atemzug]) -> AtemHrv:
    """Zusammenfassung über die gültigen Atemzüge (Modultext, Schritt 7).

    >>> z = zusammenfassen([])
    >>> z.n, z.n_gueltig, z.rate_pro_min, z.anteil_gueltig, z.art
    (0, 0, None, None, 'prototyp')
    """
    gueltig = [z for z in zuege if z.gueltig]
    spanne_ms = [z.spanne_ms for z in gueltig if z.spanne_ms is not None]
    spanne_bpm = [z.spanne_bpm for z in gueltig if z.spanne_bpm is not None]
    sinus = [z.sinus_bpm for z in gueltig if z.sinus_bpm is not None]
    lage = [z.phasenlage_s for z in gueltig if z.phasenlage_s is not None]
    anteil = [z.phasenlage_anteil for z in gueltig if z.phasenlage_anteil is not None]
    winkel = [z.winkel_grad for z in gueltig if z.winkel_grad is not None]
    ein_aus = [z.ein_aus for z in gueltig if z.ein_aus is not None]
    diff = [z.rr_differenz_ms for z in gueltig if z.rr_differenz_ms is not None]
    dauern = [z.dauer_s for z in gueltig]
    positiv = [s for s in spanne_ms if s > 0]
    zaehlung: dict[str, int] = {}
    for z in zuege:
        for g in z.gruende:
            zaehlung[g] = zaehlung.get(g, 0) + 1
    w_mittel: float | None = None
    if winkel:
        rad = np.radians(winkel)
        w_mittel = math.degrees(math.atan2(float(np.sin(rad).mean()), float(np.cos(rad).mean())))
        w_mittel %= 360.0
    return AtemHrv(
        n=len(zuege),
        n_gueltig=len(gueltig),
        rate_pro_min=_rund(60.0 / float(np.median(dauern)), 2) if dauern else None,
        spanne_ms_median=_rund(_median(spanne_ms), 1),
        spanne_ms_q25=_rund(_quartil(spanne_ms, 25), 1),
        spanne_ms_q75=_rund(_quartil(spanne_ms, 75), 1),
        spanne_bpm_median=_rund(_median(spanne_bpm), 2),
        spanne_bpm_q25=_rund(_quartil(spanne_bpm, 25), 2),
        spanne_bpm_q75=_rund(_quartil(spanne_bpm, 75), 2),
        sinus_bpm_median=_rund(_median(sinus), 2),
        ln_spanne_ms=_rund(float(np.log(positiv).mean()), 3) if positiv else None,
        phasenlage_s_median=_rund(_median(lage), 3),
        phasenlage_anteil_median=_rund(_median(anteil), 3),
        winkel_grad=_rund(w_mittel, 1),
        ein_aus_median=_rund(_median(ein_aus), 3),
        rr_differenz_ms_median=_rund(_median(diff), 1),
        gruende=tuple(sorted(zaehlung, key=lambda g: -zaehlung[g])),
    )


__all__ = [
    "ARTEFAKT",
    "AUS",
    "DAUER_UNTYPISCH",
    "EIN",
    "FENSTER_UNGUELTIG",
    "KENNZEICHEN",
    "KURZ_ANTEIL",
    "LANG_ANTEIL",
    "LUECKE",
    "MAX_DAUER_S",
    "MAX_LUECKE_S",
    "MIN_DAUER_S",
    "MIN_SCHLAEGE_JE_ATEMZUG",
    "MIN_TYPISCH",
    "PHASE_OHNE_SCHLAG",
    "TYPISCH_ANZAHL",
    "ZU_KURZ",
    "ZU_LANG",
    "ZU_WENIG_SCHLAEGE",
    "AtemHrv",
    "AtemHrvLive",
    "Atemzug",
    "atem_hrv",
    "zusammenfassen",
]
