"""PROTOTYP — Wiederholungen aus der Beschleunigung des Gurts zählen (nicht Grundlage
gespeicherter Kennzahlen, darf sich ohne ``ALGO_VERSION`` ändern; Regeln: `hrv_core.prototyp`).

Zwei Zähler:

- `WdhLive` (seit 0.11.0): **kausal und rahmenweise** — je Wiederholung ein Ereignis, sobald ihr
  Umkehrpunkt bestätigt ist, ohne Blick in die Zukunft, ohne Fenster über den Satz, Rechenlast
  je Probe unabhängig von der Satzlänge. `zaehlen` ist die Offline-Hülle darüber.
- `zaehlen_fenster` (seit 0.8.0, bis 0.10.0 ``zaehlen``): zählt ein bekanntes **Satzfenster**
  (Satzgrenzen aus der App) auf einmal — Periode aus der Autokorrelation, Gipfel mit
  Mindestabstand. Er braucht etwa drei Wiederholungen, bis eine Periode erkennbar ist, springt
  anfangs, und seine Rechenzeit wächst mit der Satzlänge.

Herkunft: hrv-research ``src/hrv_research/beschleunigung/wiederholungen_live.py`` (Entscheidung
26, 5.11.2026, Forschungspakete F7 und F8) und ``wiederholungen.py`` (Entscheidung 22,
4.11.2026, Konzept B3 in einfachster Form).

Live, je Probe auf ~25 Hz:

1. **Herunterbrechen:** Blockmittel der Rohproben auf ``rate_hz / k`` mit ``k = round(rate_hz /
   FS_ZIEL)`` (50 → 25 Hz, 52 → 26 Hz, 200 → 25 Hz); Zeit = Mitte des Blocks; der Rest eines
   Blocks wandert in den nächsten Rahmen. Dann glätten: nachlaufendes Mittel über `GLAETTEN_S`
   (Zeiten um die halbe Fensterlänge zurückdatiert).
2. **Ausgangslage:** Mittel der ersten `LAGE_S` Sekunden des Stroms (``g0``) — die Lage zu
   Satzbeginn; vorher wird nicht gezählt (die Hauptachse lernt schon mit). Alle Signale rechnen
   *gegen* sie; so stört der Sitz des Gurts weniger (F8).
3. **Signal** nach `Vorlage.signal` (Katalog `VORLAGEN`, Schlüssel in `SIGNALE`):
   ``hauptachse`` — Projektion von ``g − g0`` auf die laufende Hauptachse (Kovarianz der
   hochpassgefilterten Proben über `HOCHPASS_S`, exponentiell über `ACHSE_TAU_S` vergessen, je
   Probe ein Schritt der Potenzmethode, Vorzeichen stetig gehalten); ``betrag`` — ``|g| − |g0|``;
   ``x``/``y``/``z`` — eine feste Achse minus ihre Ausgangslage (gerätebezogen);
   ``neigung_zx``/``neigung_zy`` — der Winkel in der Ebene z–x bzw. z–y gegen die Ausgangslage
   (Grad, fortlaufend ohne Sprung). **Rückfall:** liegt zu Satzbeginn weniger als
   `NEIGUNG_MIN_MG` Schwerkraft in der Ebene, rechnet die Vorlage mit ``hauptachse``, Umkehr
   `UMKEHR_UNTEN`, Mindesthub `MIN_HUB_MG` weiter — sichtbar in `Stand.signal`.
4. **Umkehrpunkte mit Hysterese:** laufendes Minimum/Maximum; ein Umkehrpunkt ist bestätigt,
   wenn das Signal sich ``h`` davon entfernt hat, ``h = HYSTERESE · Bezugshub``. Der Bezugshub
   ist der größte von `Vorlage.min_hub`, dem typischen Hub (Median der letzten `TYPISCH_ANZAHL`
   bestätigten ganzen Wiederholungen) und der laufenden Spanne (Abstand des laufenden Extremums
   zum zuletzt bestätigten Umkehrpunkt, zu Beginn zur Ausgangslage 0). So braucht es keinen
   Blick in die Zukunft, und die Hysterese wächst mit der Bewegung mit. Nach jeder Bestätigung
   beginnt die Suche nach dem Gegenextremum beim aktuellen Wert.
5. **Fortschritt und Ruhe:** das laufende Extremum gilt als gewachsen, wenn es sich um
   ``RUHE_ANTEIL · h`` bewegt hat — sonst lässt Rauschen es endlos wachsen. `STILLSTAND_S` ohne
   Fortschritt und das Signal innerhalb ``h`` am Extremum: ein **Nahpunkt** gilt als bestätigt
   (die Person steht); ein **Fernpunkt** nur bei freier Rollenwahl, bekanntem typischem Hub,
   vollem Hub (≥ `HALB_BIS` × typisch) und ohne offene Wiederholung — dann zählt er, und die
   Rollen tauschen (Punkt 6). Zeit eines so bestätigten Punkts = letzter Fortschritt.
6. **Fern und nah:** Die Umkehrpunkte wechseln sich ab. Der **Fernpunkt** ist der Umkehrpunkt
   weg von der Ausgangslage (Kniebeuge: unten; Rudern: gezogen; Liegestütz: unten), der
   **Nahpunkt** die Rückkehr. Bei freier Rollenwahl (`UMKEHR_UNTEN`, `UMKEHR_OBEN`) gilt der
   erste bestätigte Umkehrpunkt mit genügend Hub (`Vorlage.min_hub`) weg von der Ausgangslage
   (bzw. vom zuletzt bestätigten Wackler) als Fernpunkt — die Person beginnt in der Ausgangslage
   und bewegt sich von ihr weg. Beginnt der Strom erst mitten in der ersten Wiederholung
   (Tipp-Latenz), kann der erste Umkehrpunkt mit genügend Hub die Rückkehr sein — dann sind die
   Rollen vertauscht, gezählt wird eine halbe Periode später, die Zahl stimmt. Das zeigt sich,
   sobald die Person an einem „Fernpunkt“ mit vollem Hub **verharrt** (man ruht in der
   Ausgangslage, nie am fernen Ende): Der Punkt zählt, und die Rollen tauschen (auch die Bezüge
   fern/nah). Hat das Signal ein bekanntes Vorzeichen (feste Achse, Neigung an einem benannten
   Gerät), legt `UMKEHR_TAL`/`UMKEHR_GIPFEL` den Fernpunkt fest (Minimum bzw. Maximum).
   `Vorlage.umkehr` sagt zugleich, wo gezählt wird: am Fernpunkt (Vorgabe) oder mit
   `UMKEHR_OBEN` am Nahpunkt.
7. **Hubregel (B3, Ähnlichkeit):** Hub eines Umkehrpunkts = Abstand zum letzten **echten**
   Umkehrpunkt der anderen Seite; liegt der länger als `PAUSE_S` zurück (nach einer Pause hat
   sich die Lage verschoben), zum zuletzt bestätigten; ohne beides: Fernpunkt gegen die
   Ausgangslage 0, Nahpunkt ohne Fernpunkt = Hub 0. Echt ist er, wenn der Hub mindestens
   `Vorlage.min_hub` beträgt und, sobald ein typischer Hub bekannt ist, mindestens `HALB_VON`
   davon; zwischen `HALB_VON` und `HALB_BIS` ist es eine **halbe** Wiederholung (`ART_HALB`),
   darüber eine ganze (`ART_GANZ`). Kleinere Ausschläge sind Übergänge (Hinstellen, Nachwippen,
   Ausklingen) und bleiben als Bezug außen vor. Wiederholungen, die gemeldet wurden, bevor
   `TYPISCH_ANZAHL` ganze bestätigt waren, werden nachträglich zurückgenommen
   (`GRUND_UEBERGANG`), sobald ihr Hub unter `UEBERGANG_ANTEIL` des typischen liegt — das
   Hinstellen vor dem Satz (die Zahl in der App sinkt einmal).
8. **Gespaltene Wiederholungen:** ein zählender Umkehrpunkt näher als ``max(Vorlage.periode_s[0],
   KURZ_ANTEIL · typische Periode)`` am vorigen zählt nicht (Zittern, Doppelboden) — es sei
   denn, sein Hub ist voll (mindestens `HALB_BIS` des typischen): Ein voller Hub ist eine
   Wiederholung, auch wenn das Tempo gerade gewechselt hat (wie die Schwungregel der Atmung).
   **Pausen im Satz** beenden nichts — die typischen Werte bleiben stehen, bis wieder ähnliche
   Zyklen kommen (B3); wann ein Satz ohne Bewegung endet, entscheidet die App.
9. **Melden und bestätigen:** Eine Wiederholung wird als `Wiederholung` gemeldet, sobald ihr
   Umkehrpunkt bestätigt ist (``t_s`` = Zeit des Extremums, ``gemeldet_s`` = Zeit der Probe, die
   ihn bestätigte; Verzug: Glättung plus der Weg um ``h``, etwa ein Zehntel Zyklus). Bei Zählung
   am Fernpunkt ist sie **bestätigt**, wenn der Rückweg (vorzeichenrichtig zum Bezug hin)
   `RUECKWEG_ANTEIL` ihres Hubs geschafft hat oder der nächste echte Nahpunkt bestätigt ist.
   Vorher wird sie **zurückgenommen** (`Ruecknahme`), wenn die Bewegung abbricht:
   `STILLSTAND_S` ohne Fortschritt des Rückwegs (`GRUND_STILLSTAND`) oder ein neuer Fernpunkt
   mit größerem Hub — die Person ging noch tiefer (`GRUND_UMKEHR`: Rücknahme und neue Meldung
   mit derselben Nummer; ein gleich tiefer Fernpunkt ist ein Doppelboden und wird übergangen).
   Bei Zählung am Nahpunkt (`UMKEHR_OBEN`) ist jede Meldung sofort bestätigt. Typische Periode
   und typischer Hub lernen nur aus bestätigten ganzen Wiederholungen.
10. **Ende** (`WdhLive.abschluss`): Die offene Wiederholung gilt. Ein noch unbestätigter
    Nahpunkt mit genügend Hub wird gemeldet, wenn dort gezählt wird (die letzte Rückkehr endet
    in Ruhe, ohne Abstieg danach). Ein unbestätigter Fernpunkt zählt am Ende nur unter den
    Bedingungen von Punkt 5 (freie Rollenwahl, voller Hub — der Satz endet in Ruhe, also in der
    Ausgangslage, die Rollen waren vertauscht); sonst nie: ohne Rückweg keine Wiederholung.

Nummern: ``nr`` zählt fortlaufend ganze und halbe; nach einer Rücknahme wird die Nummer neu
vergeben (`GRUND_UMKEHR`: derselbe Punkt tiefer) oder bleibt frei (`GRUND_UEBERGANG`). Die App
hängt Korrekturen an die ``nr``. Die Ereignisse eines Rahmens kommen in Zeitreihenfolge; die
Rahmengröße ändert nichts am Ergebnis, 50 und 200 Hz liefern dieselben Ereignisse.

**Umkehrpunkt (F7, aus den Videomarken):** Die Marken am unteren Umkehrpunkt liegen in allen
drei geprüften Sätzen am Minimum von z bzw. der Neigung z–x — am Fernpunkt. Darum ist der
Fernpunkt die Vorgabe: Er wird bestätigt, sobald die Person zurückkommt, was bei jeder
Wiederholung geschieht; der Nahpunkt der letzten Wiederholung dagegen erst mit dem nächsten
Abstieg oder in Ruhe. Zahlen: ``hrv-research/docs/ENTSCHEIDUNGEN.md`` Nr. 26.

**Grenzen** (Entscheidung 26):

- Ein Mensch, ein Tag, ein Gurt (H10 am unteren Brustbein), drei Sätze (Kniebeuge im Takt und
  frei, Rudern); alle Schwellen daran eingestellt. Diagnose-Sätze der trainingsapp fehlen noch.
- `auto` (freie Rollenwahl) zählt beim Rudern am Nachlassen statt am Zug — die Ausgangslage
  liegt dort mitten im Zyklus; ein gerätefreies Vorzeichen gibt es nicht. Die Vorlagen mit
  Neigung z–x (`UMKEHR_TAL`) sind am H10 die genaueren, aber nur für die Brust geprüft.
- Beginnt der Strom im Rückweg der ersten Wiederholung, zählt `auto` bis zur ersten Ruhe eine
  halbe Periode später; die Zahl bleibt richtig.
- Eine Wiederholung, bei der die Person ganz hinuntergeht und dort verharrt, ohne
  zurückzukommen, zählt bei freier Rollenwahl nach `STILLSTAND_S` (sie gilt als Ruhe in der
  Ausgangslage); eine, bei der sie nach einem Teil des Rückwegs stehen bleibt, wird
  zurückgenommen.
- Halbe Wiederholungen (`HALB_VON`–`HALB_BIS`) sind nicht an echten halben geprüft; „halb“
  gegen „zu flache ganze“ ist eine Setzung.
- Neigung z–y ist am Brustgurt unbrauchbar (Rückfall); der Betrag sieht Rudern nicht; feste
  Achsen sind empfindlich gegen den Gurtsitz.
- Keine Daten für Liegestütz, Burpee, Hampelmann (Periode < `PERIODE_MIN_S`), Verity Sense am
  Arm.
- Rechenlast am Rechner im Bereich weniger ms je Sekunde Daten (Python); am Handy ungeprüft.

**Eingang mit Ausnahme** (Entscheidungen 22 und 26 in hrv-research): geprüft an einer Sitzung
(drei Sätze, exakt gegen Video) — dieselben Sätze dienten dem Einstellen der Schwellen; die
zweite Prüfmenge entsteht mit dem Diagnosemodus der trainingsapp (Marken der Leiste), dort wird
der Zähler nur angezeigt, als Prototyp gekennzeichnet. Nur numpy; Rechenlast je Probe konstant
(ein paar laufende Summen, eine 3×3-Kovarianz).

Satzfenster (`zaehlen_fenster`), in einem bekannten Zeitfenster:

1. Schwerkraft weg: je Achse ein gleitendes Mittel über `HOCHPASS_S` abziehen;
2. Hauptachse der Bewegung: erste Hauptkomponente der drei Achsen (Vorzeichen egal);
3. glätten: gleitendes Mittel über `GLAETTEN_S`;
4. Grundperiode aus der Autokorrelation zwischen `PERIODE_MIN_S` und `PERIODE_MAX_S`;
5. zu wenig Hub (`MIN_HUB_MG`): keine Wiederholung;
6. Gipfel zählen: lokale Maxima mit Mindestabstand ``ABSTAND_ANTEIL · Periode`` und
   Mindesthöhe ``HOEHE_ANTEIL · Streuung`` — für beide Vorzeichen; es gilt das Vorzeichen,
   dessen Abstände gleichmäßiger sind.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

import numpy as np

from . import KENNZEICHEN

#: Zielrate der Live-Verarbeitung (Hz); gerechnet wird mit ``rate_hz / round(rate_hz / FS_ZIEL)``
FS_ZIEL = 25.0
#: Schwerkraft weg (Satzfenster) bzw. Hochpass für die Kovarianz der Hauptachse (live): Mittel
#: über so viele Sekunden (s)
HOCHPASS_S = 2.0
#: Glätten (s) — live ein nachlaufendes Mittel, Verzögerung die Hälfte
GLAETTEN_S = 0.25
#: Ausgangslage: Mittel der ersten so vielen Sekunden des Stroms — kurz, damit ein Strom, der
#: mitten in der ersten Wiederholung beginnt, die Lage möglichst früh festhält
LAGE_S = 0.2
#: Zeitkonstante des Vergessens der Kovarianz der Hauptachse (s)
ACHSE_TAU_S = 3.0
#: Hysterese als Anteil des Bezugshubs (Modultext, Punkt 4)
HYSTERESE = 0.3
#: Typische Periode und typischer Hub: Median der letzten so vielen bestätigten ganzen
TYPISCH_ANZAHL = 5
#: Halbe Wiederholung: Hub zwischen `HALB_VON` und `HALB_BIS` des typischen Hubs (B3 nennt
#: 40–75 %; freie Kniebeugen schwanken bis 60 %, darum die obere Grenze tiefer)
HALB_VON = 0.4
HALB_BIS = 0.6
#: Eine frühe Wiederholung (vor dem typischen Hub gemeldet) fällt nachträglich weg, wenn ihr
#: Hub unter diesem Anteil des typischen bleibt — das Hinstellen; tiefer als `HALB_VON`, weil
#: ein Strom, der mitten in der ersten Wiederholung beginnt, deren Hub nur zum Teil sieht
UEBERGANG_ANTEIL = 0.25
#: Ein zählender Umkehrpunkt näher als so viel × typische Periode am vorigen ist gespalten
KURZ_ANTEIL = 0.5
#: Bestätigt, wenn der Rückweg so viel des Hubs geschafft hat
RUECKWEG_ANTEIL = 0.5
#: So lange ohne Fortschritt: eine unbestätigte Wiederholung wird zurückgenommen, ein
#: Nahpunkt in Ruhe bestätigt. Fortschritt ist erst ein Schritt von `RUHE_ANTEIL` × Hysterese —
#: Rauschen lässt das laufende Extremum sonst endlos „wachsen“
STILLSTAND_S = 2.0
RUHE_ANTEIL = 0.1
#: Liegt der letzte echte Umkehrpunkt der anderen Seite länger zurück, misst sich der Hub am
#: zuletzt bestätigten Umkehrpunkt — nach einer Pause hat sich die Lage verschoben
PAUSE_S = 5.0
#: Suchbereich der Periode (s) — von schnellen Hampelmännern bis zu langsamen Kniebeugen;
#: live die Vorgabe der Vorlagen, die obere Grenze dort nur Erwartung
PERIODE_MIN_S = 0.8
PERIODE_MAX_S = 8.0
#: Satzfenster, Gipfel: Mindestabstand als Anteil der Periode, Mindesthöhe als Anteil der Streuung
ABSTAND_ANTEIL = 0.6
HOEHE_ANTEIL = 0.4
#: Unter diesem Hub (mG; Satzfenster: 10.–90. Perzentil der Hauptachse, live: Mindesthub der
#: Vorlagen in mG) ist es keine Bewegung, sondern Rauschen, Atmung oder Herzschlag
MIN_HUB_MG = 100.0
#: Mindesthub für Neigungssignale (Grad)
MIN_HUB_GRAD = 10.0
#: Eine Neigung braucht genug Schwerkraft in ihrer Ebene (mG); sonst (Sensor anders getragen,
#: Simulator mit Schwerkraft auf y) rechnet die Vorlage mit der Hauptachse weiter
NEIGUNG_MIN_MG = 500.0

#: Signale (Modultext, Punkt 3)
SIGNAL_HAUPTACHSE = "hauptachse"
SIGNAL_BETRAG = "betrag"
SIGNAL_X = "x"
SIGNAL_Y = "y"
SIGNAL_Z = "z"
SIGNAL_NEIGUNG_ZX = "neigung_zx"
SIGNAL_NEIGUNG_ZY = "neigung_zy"
#: Einheit je Signal
SIGNALE: dict[str, str] = {
    SIGNAL_HAUPTACHSE: "mG",
    SIGNAL_BETRAG: "mG",
    SIGNAL_X: "mG",
    SIGNAL_Y: "mG",
    SIGNAL_Z: "mG",
    SIGNAL_NEIGUNG_ZX: "°",
    SIGNAL_NEIGUNG_ZY: "°",
}
#: Signale, die eine Achse des Geräts nennen (gerätebezogen, Vorlage nennt das Gerät)
ACHSENSIGNALE = frozenset({SIGNAL_X, SIGNAL_Y, SIGNAL_Z, SIGNAL_NEIGUNG_ZX, SIGNAL_NEIGUNG_ZY})

#: Zähltypen (Konzept B2)
ZAEHLTYP_PERIODISCH = "periodisch"
ZAEHLTYP_ZUSTANDSFOLGE = "zustandsfolge"
#: Wo gezählt wird: am Fernpunkt (`UMKEHR_UNTEN`, Vorgabe) oder am Nahpunkt (`UMKEHR_OBEN`) —
#: die Rollen legt der erste Umkehrpunkt mit genügend Hub fest; oder, wenn das Signal ein
#: bekanntes Vorzeichen hat (feste Achse, Neigung an einem benannten Gerät), fest am Minimum
#: (`UMKEHR_TAL`) oder Maximum (`UMKEHR_GIPFEL`) des Signals
UMKEHR_UNTEN = "unten"
UMKEHR_OBEN = "oben"
UMKEHR_TAL = "tal"
UMKEHR_GIPFEL = "gipfel"
#: Arten einer Wiederholung
ART_GANZ = "ganz"
ART_HALB = "halb"
#: Gründe einer Rücknahme
GRUND_STILLSTAND = "stillstand"
GRUND_UMKEHR = "umkehr"
GRUND_UEBERGANG = "uebergang"


@dataclass(frozen=True, slots=True)
class Vorlage:
    """Signalwahl mit Parametern je Übung — die App speichert nur den Schlüssel."""

    schluessel: str
    name: str
    signal: str
    zaehltyp: str
    #: erwartete Dauer einer Wiederholung (s): untere Grenze = Spaltregel, obere nur Erwartung
    periode_s: tuple[float, float]
    umkehr: str
    #: Mindesthub in der Einheit des Signals (`SIGNALE`)
    min_hub: float
    #: Gerät, dessen Achsen gemeint sind (nur bei `ACHSENSIGNALE`), sonst ``None`` = gerätefrei
    geraet: str | None = None
    #: Zustandsfolge (nur `ZAEHLTYP_ZUSTANDSFOLGE`): Lagen je Wiederholung, Entwurf
    zustaende: tuple[str, ...] = ()
    hinweis: str = ""

    @property
    def verfuegbar(self) -> bool:
        """Kann `WdhLive` damit zählen? (Zustandsfolgen sind Entwurf.)"""
        return self.zaehltyp == ZAEHLTYP_PERIODISCH and self.signal in SIGNALE


#: Katalog — Schlüssel → Vorlage. Die App speichert nur den Schlüssel; unbekannt = `auto`.
#: Feste Achsen und Neigungen sind gerätebezogen (`geraet`); die Achsen anderer Gurte sind
#: nicht geprüft. Die Zählbarkeit „Liegestütz“ ist Erwartung aus der Physik; „Burpee“ ist ein
#: Entwurf (Zustandsautomat, nicht gebaut): Lage aus der Richtung der Schwerkraft im Gurt
#: (stehend längs der Körperachse, hockend dazwischen, Stütz quer), Sprung = Flug (|g| < 0,3 g)
#: gefolgt von Landung (|g| > 2 g), gezählt bei der Landung, ohne Sprung beim Wiederaufrichten.
VORLAGEN: dict[str, Vorlage] = {
    "auto": Vorlage(
        "auto",
        "Automatisch",
        SIGNAL_HAUPTACHSE,
        ZAEHLTYP_PERIODISCH,
        (PERIODE_MIN_S, PERIODE_MAX_S),
        UMKEHR_UNTEN,
        MIN_HUB_MG,
        hinweis="gerätefrei: laufende Hauptachse gegen die Lage zu Satzbeginn; gezählt am "
        "ersten Umkehrpunkt mit genügend Hub (Kniebeuge: unten)",
    ),
    "kniebeuge": Vorlage(
        "kniebeuge",
        "Kniebeuge",
        SIGNAL_NEIGUNG_ZX,
        ZAEHLTYP_PERIODISCH,
        (1.0, 8.0),
        UMKEHR_TAL,
        MIN_HUB_GRAD,
        geraet="polar_h10",
        hinweis="Rumpfneigung in der Ebene z–x; Tal = tiefster Punkt (Videomarken)",
    ),
    "liegestuetz": Vorlage(
        "liegestuetz",
        "Liegestütz",
        SIGNAL_HAUPTACHSE,
        ZAEHLTYP_PERIODISCH,
        (0.8, 6.0),
        UMKEHR_UNTEN,
        60.0,
        hinweis="Erwartung aus der Physik (keine Daten): Hub senkrecht zum Boden um 150 mG, "
        "wenig Neigung; der erste Umkehrpunkt aus dem Stütz ist unten",
    ),
    "rudern": Vorlage(
        "rudern",
        "Rudern mit Band",
        SIGNAL_NEIGUNG_ZX,
        ZAEHLTYP_PERIODISCH,
        (0.8, 6.0),
        UMKEHR_TAL,
        MIN_HUB_GRAD,
        geraet="polar_h10",
        hinweis="der Rumpf wippt mit; Tal = gezogen. Die Ausgangslage liegt mitten im "
        "Zyklus, darum ein festes Vorzeichen statt des ersten Umkehrpunkts",
    ),
    "burpee": Vorlage(
        "burpee",
        "Burpee",
        SIGNAL_BETRAG,
        ZAEHLTYP_ZUSTANDSFOLGE,
        (2.0, 10.0),
        UMKEHR_OBEN,
        MIN_HUB_MG,
        zustaende=("stehen", "hocken", "stuetz", "hocken", "sprung"),
        hinweis="Entwurf ohne Daten: Zustände aus der Richtung der Schwerkraft im Gurt, "
        "Sprung = Flug unter 0,3 g und Landung über 2 g; zählt bei der Landung",
    ),
}


def vorlage(schluessel: str | Vorlage | None) -> Vorlage:
    """Die Vorlage zu einem Schlüssel — unbekannt oder ``None`` ist `auto`.

    >>> vorlage("kniebeuge").name, vorlage("gibt_es_nicht").schluessel, vorlage(None).schluessel
    ('Kniebeuge', 'auto', 'auto')
    """
    if isinstance(schluessel, Vorlage):
        return schluessel
    return VORLAGEN.get(schluessel or "auto", VORLAGEN["auto"])


#: Alias für `WdhLive.__init__`, dessen Parameter ``vorlage`` die Funktion verdeckt
_vorlage_holen = vorlage


def mit_signal(v: Vorlage, signal: str, min_hub: float | None = None) -> Vorlage:
    """Dieselbe Vorlage mit anderem Signal (für Signalvergleiche); der Mindesthub folgt der
    Einheit, wenn keiner genannt ist.

    >>> mit_signal(VORLAGEN["auto"], "neigung_zx").min_hub
    10.0
    """
    if min_hub is None:
        min_hub = MIN_HUB_GRAD if SIGNALE[signal] == "°" else v.min_hub
    return replace(
        v, signal=signal, min_hub=min_hub, geraet="polar_h10" if signal in ACHSENSIGNALE else None
    )


@dataclass(frozen=True, slots=True)
class Wiederholung:
    """Eine gezählte Wiederholung: Zeit ihres Umkehrpunkts, laufende Nummer, Art, Hub seit dem
    vorigen Umkehrpunkt, Abstand zur vorigen (``None`` bei der ersten) und wann sie gemeldet
    wurde (``gemeldet_s − t_s`` ist der Verzug)."""

    t_s: float
    nr: int
    art: str
    hub: float
    periode_s: float | None
    gemeldet_s: float


@dataclass(frozen=True, slots=True)
class Ruecknahme:
    """Eine noch unbestätigte Wiederholung ``nr`` fällt weg (`GRUND_STILLSTAND`, `GRUND_UMKEHR`)
    — oder nachträglich eine frühe (`GRUND_UEBERGANG`)."""

    t_s: float
    nr: int
    grund: str


@dataclass(frozen=True, slots=True)
class Stand:
    """Momentaufnahme für die Anzeige — ``art`` ist immer `hrv_core.prototyp.KENNZEICHEN`."""

    t_s: float
    #: ganze Wiederholungen (was die App zeigt) und halbe daneben
    anzahl: int
    halbe: int
    #: typische Periode und Hub (Median der letzten bestätigten ganzen), ``None`` ohne
    periode_s: float | None
    hub: float | None
    #: die letzte Wiederholung ist noch nicht bestätigt (Rückweg offen)
    unbestaetigt: bool
    #: Signal und Umkehr der Vorlage — nach einem Rückfall (Modultext, Punkt 3) die ersetzten
    signal: str
    umkehr: str
    art: str = KENNZEICHEN


@dataclass(frozen=True, slots=True)
class Zaehlung:
    """Ergebnis eines Satzes (`zaehlen`, `zaehlen_fenster`) — ``art`` ist immer
    `hrv_core.prototyp.KENNZEICHEN`. Die ersten vier Felder gibt es seit 0.8.0; die Felder ab
    ``halbe_s`` füllt nur die Live-Hülle `zaehlen`."""

    anzahl: int
    #: Zeiten der gezählten ganzen Wiederholungen (s, auf der Zeitachse der Eingabe)
    zeiten_s: tuple[float, ...]
    #: Grundperiode (s) — live die typische —, ``None``: keine erkennbar
    periode_s: float | None
    #: 0–1: wie gleichmäßig die Abstände sind (1 − Variationskoeffizient)
    gleichmaessigkeit: float
    #: Zeiten der halben Wiederholungen (s)
    halbe_s: tuple[float, ...] = ()
    #: typischer Hub in der Einheit des Signals, ``None`` ohne
    hub: float | None = None
    #: Verzug je gültiger Wiederholung (s): gemeldet minus Umkehrpunkt
    verzug_s: tuple[float, ...] = ()
    ruecknahmen: int = 0
    art: str = KENNZEICHEN


class _Mittel:
    """Nachlaufendes Mittel über höchstens ``n`` Werte — am Anfang über so viele, wie da sind."""

    __slots__ = ("n", "summe", "werte")

    def __init__(self, n: int) -> None:
        self.n = max(1, int(n))
        self.werte: deque[float] = deque()
        self.summe = 0.0

    def schieben(self, x: float) -> float:
        self.werte.append(x)
        self.summe += x
        if len(self.werte) > self.n:
            self.summe -= self.werte.popleft()
        return self.summe / len(self.werte)


@dataclass(slots=True)
class _Umkehr:
    """Ein bestätigter Umkehrpunkt."""

    wert: float
    t_s: float
    fern: bool


@dataclass(slots=True)
class _Offen:
    """Die zuletzt gemeldete, noch nicht bestätigte Wiederholung (nur Zählung am Fernpunkt)."""

    wdh: Wiederholung
    #: Wert des Umkehrpunkts und Richtung des Rückwegs (+1: das Signal steigt zurück)
    wert: float
    richtung: float
    #: bisher erreichter Rückweg und wann er zuletzt wuchs
    fortschritt: float
    t_fortschritt: float
    #: Zeit der Wiederholung davor (für die Spaltregel nach einer Rücknahme)
    vorher_t: float | None
    bestaetigt: bool = False


class WdhLive:
    """Wiederholungen rahmenweise zählen (Modultext). Zeiten auf der Achse der Eingabe.

    >>> rate = 50.0
    >>> t = np.arange(0, 30, 1 / rate)
    >>> hub = 400 * (1 - np.cos(2 * np.pi * t / 2.5)) / 2    # 12 Kniebeugen à 2,5 s, Beginn oben
    >>> xyz = np.column_stack([-1000 + 0.1 * hub, 0 * t, 100 - hub])
    >>> live = WdhLive(rate)
    >>> ereignisse = []
    >>> for i in range(0, t.size, 10):
    ...     ereignisse += live.rahmen(xyz[i : i + 10], float(t[i]))
    >>> ereignisse += live.abschluss()
    >>> wdh = [e for e in ereignisse if isinstance(e, Wiederholung)]
    >>> len(wdh), [round(w.t_s, 1) for w in wdh[:3]], live.stand().anzahl  # unten bei 1,25 s …
    (12, [1.2, 3.8, 6.2], 12)
    >>> all(0 < w.gemeldet_s - w.t_s < 1.25 for w in wdh)      # Verzug unter einer halben Periode
    True
    >>> live.stand().art
    'prototyp'
    """

    def __init__(self, rate_hz: float, vorlage: str | Vorlage | None = "auto") -> None:
        if rate_hz <= 0:
            raise ValueError("rate_hz muss positiv sein")
        self.vorlage = _vorlage_holen(vorlage)
        if not self.vorlage.verfuegbar:
            raise ValueError(
                f"Vorlage {self.vorlage.schluessel!r} ({self.vorlage.zaehltyp}) ist ein Entwurf"
            )
        self.rate_hz = float(rate_hz)
        self.k = max(1, round(self.rate_hz / FS_ZIEL))
        self.fs = self.rate_hz / self.k
        self.dt = 1.0 / self.fs
        self._rest: list[tuple[float, float, float, float]] = []
        # Glättung und Ausgangslage
        n_g = max(1, round(GLAETTEN_S * self.fs))
        self._glatt = [_Mittel(n_g) for _ in range(3)]
        self._glatt_versatz = (n_g - 1) / 2.0 * self.dt
        self._lage_n = max(1, round(LAGE_S * self.fs))
        self._lage_summe = np.zeros(3)
        self._lage_zahl = 0
        self._g0: np.ndarray | None = None
        # Hauptachse
        self._hp = [_Mittel(max(1, round(HOCHPASS_S * self.fs))) for _ in range(3)]
        self._kov = np.zeros((3, 3))
        self._kov_a = min(1.0, self.dt / ACHSE_TAU_S)
        self._achse: np.ndarray | None = None
        # Neigung fortlaufend
        self._winkel_vorher: float | None = None
        self._winkel = 0.0
        # Umkehrpunkte
        self._richtung = 0  # +1 Signal steigt (nach einem Minimum), −1 fällt, 0 unbekannt
        self._min: tuple[float, float] | None = None  # (Wert, Zeit)
        self._max: tuple[float, float] | None = None
        self._t_fortschritt = 0.0  # wann das laufende Extremum zuletzt wuchs
        self._fortschritt_wert = 0.0
        self._letzte: _Umkehr | None = None  # letzter bestätigter Umkehrpunkt (jede Art)
        self._bezug_fern: tuple[float, float] | None = None  # letzter echter Fernpunkt (Wert, Zeit)
        self._bezug_nah: tuple[float, float] | None = None  # letzter echter Nahpunkt
        self._naechster_fern = True  # Rolle des nächsten bestätigten Umkehrpunkts
        self._rollen_fest = False  # erst ein Umkehrpunkt mit genügend Hub legt die Rollen fest
        # Zählung
        self._nr = 0
        self._ganze = 0
        self._halbe = 0
        self._letzte_wdh_t: float | None = None
        self._offen: _Offen | None = None
        self._hub_typ: deque[float] = deque(maxlen=TYPISCH_ANZAHL)
        self._periode_typ: deque[float] = deque(maxlen=TYPISCH_ANZAHL)
        #: frühe Wiederholungen, die noch gegen den typischen Hub geprüft werden (Punkt 7)
        self._fruehe: list[Wiederholung] = []
        self._t_letzte: float | None = None

    @property
    def zaehlt_fern(self) -> bool:
        """Gezählt wird am Fernpunkt (alles außer `UMKEHR_OBEN`)."""
        return self.vorlage.umkehr != UMKEHR_OBEN

    def _rolle(self, ist_min: bool) -> bool:
        """Ist ein Umkehrpunkt (Minimum oder Maximum) der Fernpunkt? Bei festem Vorzeichen nach
        dem Signal, sonst im Wechsel ab dem ersten mit genügend Hub."""
        if self.vorlage.umkehr == UMKEHR_TAL:
            return ist_min
        if self.vorlage.umkehr == UMKEHR_GIPFEL:
            return not ist_min
        return self._naechster_fern

    # -- Eingabe --------------------------------------------------------------------------------

    def rahmen(self, xyz: np.ndarray, t0_s: float) -> list[Wiederholung | Ruecknahme]:
        """Einen Rahmen Rohproben ``n × 3`` (mG) ab ``t0_s`` verarbeiten; liefert neu gemeldete
        Wiederholungen und Rücknahmen in zeitlicher Folge."""
        v = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
        if v.shape[0] == 0:
            return []
        t = t0_s + np.arange(v.shape[0]) / self.rate_hz
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
        heraus: list[Wiederholung | Ruecknahme] = []
        for i in range(tb.shape[0]):
            heraus += self._probe(float(tb[i]), vb[i])
        return heraus

    def abschluss(self) -> list[Wiederholung | Ruecknahme]:
        """Am Ende des Stroms: die offene Wiederholung gilt; zählt die Vorlage am Nahpunkt, zählt
        ein noch unbestätigter Nahpunkt mit genügend Hub (Modultext, Punkt 10)."""
        if self._t_letzte is None:
            return []
        heraus: list[Wiederholung | Ruecknahme] = []
        if self._offen is not None and not self._offen.bestaetigt:
            heraus += self._bestaetigen()
        kandidat = self._max if self._richtung > 0 else self._min if self._richtung < 0 else None
        if kandidat is not None:
            ist_min = self._richtung < 0
            fern = self._rolle(ist_min)
            if (not fern and not self.zaehlt_fern) or (
                fern and self._ruhe_am_fernpunkt(kandidat[0])
            ):
                heraus += self._umkehrpunkt(kandidat[0], kandidat[1], ist_min)
        return heraus

    def stand(self) -> Stand:
        """Momentaufnahme für die Anzeige — ``anzahl`` sind die ganzen Wiederholungen."""
        return Stand(
            t_s=self._t_letzte if self._t_letzte is not None else 0.0,
            anzahl=self._ganze,
            halbe=self._halbe,
            periode_s=self._typisch(self._periode_typ),
            hub=self._typisch(self._hub_typ),
            unbestaetigt=self._offen is not None and not self._offen.bestaetigt,
            signal=self.vorlage.signal,
            umkehr=self.vorlage.umkehr,
        )

    # -- je Probe ---------------------------------------------------------------------------------

    def _probe(self, t: float, v: np.ndarray) -> list[Wiederholung | Ruecknahme]:
        self._t_letzte = t
        g = np.array([self._glatt[k].schieben(float(v[k])) for k in range(3)])
        if self._g0 is None:
            self._lage_summe += g
            self._lage_zahl += 1
            if self._lage_zahl >= self._lage_n:
                self._g0 = self._lage_summe / self._lage_zahl
                self._rueckfall_pruefen()
            # die Hauptachse lernt schon mit; gezählt wird erst mit bekannter Ausgangslage
            self._hauptachse(v)
            return []
        y = self._signal(g, v)
        return self._umkehrpunkte(t - self._glatt_versatz, y)

    def _rueckfall_pruefen(self) -> None:
        """Eine Neigung ohne Schwerkraft in ihrer Ebene (`NEIGUNG_MIN_MG`) wird zur Hauptachse
        am ersten Fernpunkt — sichtbar in `Stand.signal`."""
        assert self._g0 is not None
        s = self.vorlage.signal
        if s not in (SIGNAL_NEIGUNG_ZX, SIGNAL_NEIGUNG_ZY):
            return
        a, b = (2, 0) if s == SIGNAL_NEIGUNG_ZX else (2, 1)
        if math.hypot(float(self._g0[a]), float(self._g0[b])) < NEIGUNG_MIN_MG:
            self.vorlage = replace(
                self.vorlage,
                signal=SIGNAL_HAUPTACHSE,
                umkehr=UMKEHR_UNTEN,
                min_hub=MIN_HUB_MG,
                geraet=None,
            )

    def _hauptachse(self, v: np.ndarray) -> np.ndarray | None:
        hp = np.array([float(v[k]) - self._hp[k].schieben(float(v[k])) for k in range(3)])
        self._kov += self._kov_a * (np.outer(hp, hp) - self._kov)
        if self._achse is None:
            norm = float(np.linalg.norm(hp))
            if norm < 1e-9:
                return None
            self._achse = hp / norm
        u = self._kov @ self._achse
        norm = float(np.linalg.norm(u))
        if norm > 1e-12:
            u /= norm
            if float(u @ self._achse) < 0:
                u = -u
            self._achse = u
        return self._achse

    def _signal(self, g: np.ndarray, v: np.ndarray) -> float:
        assert self._g0 is not None
        s = self.vorlage.signal
        d = g - self._g0
        if s == SIGNAL_HAUPTACHSE:
            achse = self._hauptachse(v)
            return float(d @ achse) if achse is not None else 0.0
        if s == SIGNAL_BETRAG:
            return float(np.linalg.norm(g) - np.linalg.norm(self._g0))
        if s == SIGNAL_X:
            return float(d[0])
        if s == SIGNAL_Y:
            return float(d[1])
        if s == SIGNAL_Z:
            return float(d[2])
        a, b = (2, 0) if s == SIGNAL_NEIGUNG_ZX else (2, 1)
        w = math.degrees(math.atan2(float(g[b]), float(g[a])))
        if self._winkel_vorher is None:
            w0 = math.degrees(math.atan2(float(self._g0[b]), float(self._g0[a])))
            self._winkel = (w - w0 + 180.0) % 360.0 - 180.0
        else:
            self._winkel += (w - self._winkel_vorher + 180.0) % 360.0 - 180.0
        self._winkel_vorher = w
        return self._winkel

    def _bezugshub(self, laufend: float) -> float:
        typ = self._typisch(self._hub_typ)
        return max(self.vorlage.min_hub, typ if typ is not None else 0.0, laufend)

    def _umkehrpunkte(self, t: float, y: float) -> list[Wiederholung | Ruecknahme]:
        heraus: list[Wiederholung | Ruecknahme] = []
        bezug = self._letzte.wert if self._letzte is not None else 0.0
        if self._min is None or y < self._min[0]:
            self._min = (y, t)
            if self._richtung <= 0:
                self._fortschritt(t, y, bezug)
        if self._max is None or y > self._max[0]:
            self._max = (y, t)
            if self._richtung >= 0:
                self._fortschritt(t, y, bezug)
        assert self._min is not None and self._max is not None
        if self._richtung <= 0:
            h = HYSTERESE * self._bezugshub(abs(bezug - self._min[0]))
            if y >= self._min[0] + h:
                wert, zeit = self._min
                self._richtung = 1
                self._max = (y, t)
                self._t_fortschritt, self._fortschritt_wert = t, y
                heraus += self._umkehrpunkt(wert, zeit, True)
                return heraus + self._rueckweg(t, y)
        if self._richtung >= 0:
            h = HYSTERESE * self._bezugshub(abs(bezug - self._max[0]))
            if y <= self._max[0] - h:
                wert, zeit = self._max
                self._richtung = -1
                self._min = (y, t)
                self._t_fortschritt, self._fortschritt_wert = t, y
                heraus += self._umkehrpunkt(wert, zeit, False)
                return heraus + self._rueckweg(t, y)
        heraus += self._rueckweg(t, y)
        # Ruhe: ein Nahpunkt gilt als bestätigt, wenn die Person dort verharrt; ein „Fernpunkt“
        # mit vollem Hub, an dem sie verharrt, war die Ausgangslage — Rollen tauschen (Punkt 6)
        if self._richtung != 0 and t - self._t_fortschritt >= STILLSTAND_S:
            kandidat = self._max if self._richtung > 0 else self._min
            ist_min = self._richtung < 0
            fern = self._rolle(ist_min)
            if abs(y - kandidat[0]) < HYSTERESE * self._bezugshub(abs(bezug - kandidat[0])) and (
                not fern or self._ruhe_am_fernpunkt(kandidat[0])
            ):
                zeit = self._t_fortschritt  # Ansatz: als das Extremum zuletzt wirklich wuchs
                self._richtung = -self._richtung
                if self._richtung > 0:
                    self._max = (y, t)
                else:
                    self._min = (y, t)
                self._t_fortschritt, self._fortschritt_wert = t, y
                heraus += self._umkehrpunkt(kandidat[0], zeit, ist_min)
                if fern:
                    self._naechster_fern = True
                    self._bezug_fern, self._bezug_nah = self._bezug_nah, self._bezug_fern
        return heraus

    def _ruhe_am_fernpunkt(self, wert: float) -> bool:
        """Darf Ruhe an einem Fernpunkt ihn bestätigen? Nur bei freier Rollenwahl, bekanntem
        typischem Hub, vollem Hub und ohne offene Wiederholung."""
        typ = self._typisch(self._hub_typ)
        if (
            self.vorlage.umkehr not in (UMKEHR_UNTEN, UMKEHR_OBEN)
            or typ is None
            or (self._offen is not None and not self._offen.bestaetigt)
        ):
            return False
        bezug = self._bezug_nah[0] if self._bezug_nah is not None else 0.0
        return abs(wert - bezug) >= HALB_BIS * typ

    def _fortschritt(self, t: float, y: float, bezug: float) -> None:
        """Das laufende Extremum ist gewachsen — Fortschritt, wenn um mehr als das Rauschen."""
        if abs(y - self._fortschritt_wert) >= RUHE_ANTEIL * HYSTERESE * self._bezugshub(
            abs(bezug - y)
        ):
            self._fortschritt_wert = y
            self._t_fortschritt = t

    def _rueckweg(self, t: float, y: float) -> list[Wiederholung | Ruecknahme]:
        """Fortschritt der offenen Wiederholung: bestätigen oder zurücknehmen (Punkt 9)."""
        o = self._offen
        if o is None or o.bestaetigt:
            return []
        weg = (y - o.wert) * o.richtung
        if weg - o.fortschritt >= RUHE_ANTEIL * HYSTERESE * o.wdh.hub:
            o.fortschritt = weg
            o.t_fortschritt = t
        if weg >= RUECKWEG_ANTEIL * o.wdh.hub:
            return self._bestaetigen()
        if t - o.t_fortschritt >= STILLSTAND_S:
            return [self._zuruecknehmen(GRUND_STILLSTAND)]
        return []

    def _umkehrpunkt(
        self, wert: float, zeit: float, ist_min: bool
    ) -> list[Wiederholung | Ruecknahme]:
        """Ein bestätigter Umkehrpunkt (Modultext, Punkte 6–9)."""
        heraus: list[Wiederholung | Ruecknahme] = []
        vorige = self._letzte
        if not self._rollen_fest and self.vorlage.umkehr in (UMKEHR_UNTEN, UMKEHR_OBEN):
            # Der erste Umkehrpunkt mit genügend Hub weg von der Ausgangslage (bzw. vom zuletzt
            # bestätigten Wackler) ist der Fernpunkt; kleinere davor legen nichts fest
            bezug = vorige.wert if vorige is not None else 0.0
            self._letzte = _Umkehr(wert, zeit, True)
            if abs(wert - bezug) < self.vorlage.min_hub:
                return heraus
            self._rollen_fest = True
            self._naechster_fern = True
        fern = self._rolle(ist_min)
        self._naechster_fern = not fern
        self._letzte = _Umkehr(wert, zeit, fern)
        echter = self._bezug_nah if fern else self._bezug_fern
        if echter is not None and zeit - echter[1] <= PAUSE_S:
            bezug = echter[0]
        elif vorige is not None:
            # kein echter Umkehrpunkt der anderen Seite oder zu lange her (Pause): der zuletzt
            # bestätigte
            bezug = vorige.wert
        else:
            # die Ausgangslage (0) für einen Fernpunkt — ein Nahpunkt ohne Fernpunkt ist kein
            # Rückweg
            bezug = 0.0 if fern else wert
        hub = abs(wert - bezug)
        typ_hub = self._typisch(self._hub_typ)
        echt = hub >= self.vorlage.min_hub and (typ_hub is None or hub >= HALB_VON * typ_hub)
        zaehlt_hier = fern == self.zaehlt_fern
        o = self._offen
        if zaehlt_hier and o is not None and not o.bestaetigt:
            # Zurück über den Umkehrpunkt hinaus, bevor der Rückweg geschafft war: der tiefere
            # Punkt ist die Wiederholung (gleiche Nummer); ein gleich tiefer ist ein Doppelboden
            if hub > o.wdh.hub:
                heraus.append(self._zuruecknehmen(GRUND_UMKEHR))
                heraus += self._melden(wert, zeit, hub, typ_hub, bezug)
            return heraus
        if echt:
            if fern:
                self._bezug_fern = (wert, zeit)
            else:
                self._bezug_nah = (wert, zeit)
            if o is not None and not o.bestaetigt:
                heraus += self._bestaetigen()
            if zaehlt_hier:
                heraus += self._melden(wert, zeit, hub, typ_hub, bezug)
        return heraus

    def _melden(
        self, wert: float, zeit: float, hub: float, typ_hub: float | None, bezug: float
    ) -> list[Wiederholung | Ruecknahme]:
        typ_per = self._typisch(self._periode_typ)
        kurz = self.vorlage.periode_s[0]
        if typ_per is not None:
            kurz = max(kurz, KURZ_ANTEIL * typ_per)
        periode = zeit - self._letzte_wdh_t if self._letzte_wdh_t is not None else None
        art = ART_HALB if typ_hub is not None and hub < HALB_BIS * typ_hub else ART_GANZ
        if periode is not None and periode < kurz and (typ_hub is None or art == ART_HALB):
            return []
        self._nr += 1
        if art == ART_GANZ:
            self._ganze += 1
        else:
            self._halbe += 1
        assert self._t_letzte is not None
        w = Wiederholung(zeit, self._nr, art, hub, periode, self._t_letzte)
        self._offen = _Offen(
            w, wert, 1.0 if bezug >= wert else -1.0, 0.0, self._t_letzte, self._letzte_wdh_t
        )
        self._letzte_wdh_t = zeit
        heraus: list[Wiederholung | Ruecknahme] = [w]
        if not self.zaehlt_fern:
            # am Nahpunkt ist die Wiederholung mit der Rückkehr vollendet
            heraus += self._bestaetigen()
        return heraus

    def _bestaetigen(self) -> list[Wiederholung | Ruecknahme]:
        """Die offene Wiederholung gilt; typischer Hub und Periode lernen aus ganzen. Frühe
        Wiederholungen, die sich nun als Übergang erweisen (Hub unter `UEBERGANG_ANTEIL` des
        typischen), fallen nachträglich weg (Punkt 7)."""
        o = self._offen
        assert o is not None and self._t_letzte is not None
        o.bestaetigt = True
        if o.wdh.art != ART_GANZ:
            return []
        self._hub_typ.append(o.wdh.hub)
        if o.wdh.periode_s is not None:
            self._periode_typ.append(o.wdh.periode_s)
        heraus: list[Wiederholung | Ruecknahme] = []
        if len(self._hub_typ) < TYPISCH_ANZAHL:
            self._fruehe.append(o.wdh)
            typ = self._typisch(self._hub_typ)
            assert typ is not None
            for w in list(self._fruehe):
                if w.hub < UEBERGANG_ANTEIL * typ:
                    self._fruehe.remove(w)
                    self._streichen(w)
                    heraus.append(Ruecknahme(self._t_letzte, w.nr, GRUND_UEBERGANG))
        else:
            self._fruehe.clear()
        return heraus

    def _streichen(self, w: Wiederholung) -> None:
        if w.art == ART_GANZ:
            self._ganze -= 1
            if w.hub in self._hub_typ:
                self._hub_typ.remove(w.hub)
        else:
            self._halbe -= 1

    def _zuruecknehmen(self, grund: str) -> Ruecknahme:
        o = self._offen
        assert o is not None and self._t_letzte is not None
        self._offen = None
        self._nr -= 1
        self._streichen(o.wdh)
        self._letzte_wdh_t = o.vorher_t
        return Ruecknahme(self._t_letzte, o.wdh.nr, grund)

    @staticmethod
    def _typisch(werte: deque[float]) -> float | None:
        return float(np.median(werte)) if werte else None


def zaehlen(
    xyz: np.ndarray,
    rate_hz: float,
    t0_s: float = 0.0,
    vorlage: str | Vorlage | None = "auto",
    rahmen_s: float = 1.0,
) -> Zaehlung:
    """Wiederholungen eines Satzes aus der Beschleunigung — Offline-Hülle über `WdhLive`:
    dieselbe Rechnung, rahmenweise mit ``rahmen_s``.

    ``xyz``: Proben ``n × 3`` (mG) in gleichmäßigem Takt ``rate_hz``; ``t0_s``: Zeit der ersten
    Probe (für ``zeiten_s``). Bis 0.10.0 stand hier der Satzfenster-Zähler (`zaehlen_fenster`);
    Signatur und die Felder ``anzahl``, ``zeiten_s``, ``periode_s``, ``gleichmaessigkeit``,
    ``art`` sind geblieben.

    >>> rate = 200.0
    >>> t = np.arange(0, 40, 1 / rate)
    >>> hub = 300 * (1 - np.cos(2 * np.pi * t / 2.0)) / 2            # 20 à 2 s
    >>> xyz = np.column_stack([0.2 * hub, -1000 + hub, 0.1 * hub])
    >>> z = zaehlen(xyz, rate)
    >>> z.anzahl, round(z.periode_s, 1), z.gleichmaessigkeit > 0.9, z.art
    (20, 2.0, True, 'prototyp')
    >>> zaehlen(np.zeros((500, 3)), rate).anzahl
    0
    """
    v = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
    live = WdhLive(rate_hz, vorlage)
    schritt = max(1, round(rahmen_s * rate_hz))
    ereignisse: list[Wiederholung | Ruecknahme] = []
    for i in range(0, v.shape[0], schritt):
        ereignisse += live.rahmen(v[i : i + schritt], t0_s + i / rate_hz)
    ereignisse += live.abschluss()
    return zusammenfassen(ereignisse, live.stand())


def gueltige(ereignisse: list[Wiederholung | Ruecknahme]) -> list[Wiederholung]:
    """Die Wiederholungen, die am Ende stehen bleiben: jede Rücknahme streicht die zuletzt
    gemeldete mit ihrer Nummer.

    >>> w = Wiederholung(1.0, 1, ART_GANZ, 500.0, None, 1.3)
    >>> gueltige([w, Ruecknahme(2.0, 1, GRUND_STILLSTAND)])
    []
    """
    stehen: list[Wiederholung] = []
    for e in ereignisse:
        if isinstance(e, Wiederholung):
            stehen.append(e)
        else:
            for i in range(len(stehen) - 1, -1, -1):
                if stehen[i].nr == e.nr:
                    del stehen[i]
                    break
    return stehen


def zusammenfassen(ereignisse: list[Wiederholung | Ruecknahme], stand: Stand) -> Zaehlung:
    """`Zaehlung` aus den Ereignissen eines Laufs — ``anzahl`` zählt ganze und halbe, die Zeiten
    stehen getrennt in ``zeiten_s`` und ``halbe_s``."""
    wdh = gueltige(ereignisse)
    zeiten = np.array([w.t_s for w in wdh])
    abst = np.diff(zeiten) if zeiten.size >= 2 else np.empty(0)
    gleich = float(max(0.0, 1.0 - abst.std() / abst.mean())) if abst.size >= 2 else 0.0
    return Zaehlung(
        anzahl=len(wdh),
        zeiten_s=tuple(float(w.t_s) for w in wdh if w.art == ART_GANZ),
        periode_s=stand.periode_s,
        gleichmaessigkeit=round(gleich, 3),
        halbe_s=tuple(float(w.t_s) for w in wdh if w.art == ART_HALB),
        hub=stand.hub,
        verzug_s=tuple(round(w.gemeldet_s - w.t_s, 3) for w in wdh),
        ruecknahmen=sum(1 for e in ereignisse if isinstance(e, Ruecknahme)),
    )


# -- Satzfenster (seit 0.8.0) -----------------------------------------------------------------


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
    """Die Bewegung längs ihrer Hauptachse — ohne Schwerkraft, geglättet (Satzfenster)."""
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


def zaehlen_fenster(xyz: np.ndarray, rate_hz: float, t0_s: float = 0.0) -> Zaehlung:
    """Wiederholungen eines bekannten Satzfensters auf einmal (Modultext, Satzfenster) — bis
    0.10.0 ``zaehlen``.

    ``xyz``: Proben ``n × 3`` (mG) in gleichmäßigem Takt ``rate_hz``; ``t0_s``: Zeit der ersten
    Probe (für ``zeiten_s``).

    >>> rate = 100.0
    >>> t = np.arange(0, 24, 1 / rate)
    >>> bewegung = 300 * np.sin(2 * np.pi * t / 2.0)          # 12 Wiederholungen à 2 s
    >>> xyz = np.column_stack([0.2 * bewegung, -1000 + bewegung, 0.1 * bewegung])
    >>> z = zaehlen_fenster(xyz, rate)
    >>> z.anzahl, round(z.periode_s, 1), z.gleichmaessigkeit > 0.9
    (12, 2.0, True)
    >>> zaehlen_fenster(np.zeros((500, 3)), rate).anzahl
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
    "ACHSENSIGNALE",
    "ACHSE_TAU_S",
    "ART_GANZ",
    "ART_HALB",
    "FS_ZIEL",
    "GLAETTEN_S",
    "GRUND_STILLSTAND",
    "GRUND_UEBERGANG",
    "GRUND_UMKEHR",
    "HALB_BIS",
    "HALB_VON",
    "HOCHPASS_S",
    "HOEHE_ANTEIL",
    "HYSTERESE",
    "KENNZEICHEN",
    "KURZ_ANTEIL",
    "LAGE_S",
    "MIN_HUB_GRAD",
    "MIN_HUB_MG",
    "NEIGUNG_MIN_MG",
    "PAUSE_S",
    "PERIODE_MAX_S",
    "PERIODE_MIN_S",
    "RUECKWEG_ANTEIL",
    "RUHE_ANTEIL",
    "SIGNALE",
    "SIGNAL_BETRAG",
    "SIGNAL_HAUPTACHSE",
    "SIGNAL_NEIGUNG_ZX",
    "SIGNAL_NEIGUNG_ZY",
    "SIGNAL_X",
    "SIGNAL_Y",
    "SIGNAL_Z",
    "STILLSTAND_S",
    "TYPISCH_ANZAHL",
    "UEBERGANG_ANTEIL",
    "UMKEHR_GIPFEL",
    "UMKEHR_OBEN",
    "UMKEHR_TAL",
    "UMKEHR_UNTEN",
    "VORLAGEN",
    "ZAEHLTYP_PERIODISCH",
    "ZAEHLTYP_ZUSTANDSFOLGE",
    "Ruecknahme",
    "Stand",
    "Vorlage",
    "WdhLive",
    "Wiederholung",
    "Zaehlung",
    "gueltige",
    "hauptachse",
    "mit_signal",
    "periode",
    "vorlage",
    "zaehlen",
    "zaehlen_fenster",
    "zusammenfassen",
]
