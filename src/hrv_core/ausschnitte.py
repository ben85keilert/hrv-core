"""Ausschnitte einer fertigen Messung: Crop und Abschnitte — wie praxis_gui.

**Crop** (`active_crop`): Nur ein Teil der Messung zählt — der Anfang, bevor
der Gurt saß, oder das Ende, nachdem man aufgestanden ist, fällt aus allen
Kennzahlen. **Die Rohdatei bleibt unangetastet**; der Crop steht im Sidecar
``sensor_<ts>_analyzed.json`` und lässt sich jederzeit entfernen.

**Abschnitte** (`segments`): benannte Zeitbereiche, für die die App Werte
rechnet (Ø HF, RMSSD, SDNN, Atemfrequenz, LF/HF) — etwa Belastung gegen Pause,
um Trainingsbereiche gegeneinanderzuhalten. Abschnitte sind **eigenständig**
(Ben, 14.10.2026): gespeichert wie in praxis_gui (`segments`), jederzeit
verschieb- und löschbar. Notizen sind dafür nicht nötig — eine Notiz kann
mitten in einer Übung stehen („tiefer atmen"), ohne etwas zu teilen. Notizen
helfen nur:

- als **Rastpunkte**: Eine Grenze in ihrer Nähe rastet an ihr ein (`einrasten`);
- als **gewählte Grenzen**: Wer will, macht ausgewählte Notizen zu Grenzen
  (`aus_grenzen`) — jede beginnt einen Abschnitt, benannt nach ihr.

Der **Timer** legt seine Abschnitte beim Speichern der Aufnahme selbst an
(`grenzen_speichern`) — „Belastung (Runde 2/8)", „Pause (Runde 2/8)" … —,
danach sind es Abschnitte wie alle anderen. Laufen mehrere Abläufe zugleich
(Timer, Übungen eines Plans, Kilometer), hat jeder seine **Spur**
(`spuren_speichern`): Abschnitte entstehen je Spur, so schneidet ein km-Wechsel
keinen Timer-Abschnitt; Abschnitte verschiedener Spuren dürfen sich überlappen.

**Zeitachsen.** Die App rechnet auf ihrer Kurvenachse (Sekunden ab Start; bei
der Verity Sense die Herzuhr aller Intervalle). praxis_gui speichert Zeiten auf
der Herzuhr der Rohdatei, Abschnitte bei aktivem Crop relativ zu dessen Anfang.
Die Umrechnung reicht der Aufrufer herein (``nach_datei``/``nach_achse``).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from .atmung import RUHE
from .atmung import fenster as atem_fenster
from .constants import LANG_AB_S
from .ereignisse import Zeitbezug
from .frequency import Fensterspektrum, fensterspektrum, frequenzbereich
from .korrektur import (
    Korrigiert,
    _json_lesen,
    _json_lesen_strikt,
    _sha1,
    analyse_pfad,
    zuschneiden,
)
from .ppi import schlagzeiten
from .recording import Recording, json_atomar_schreiben
from .time_domain import compute_time_domain

#: Farben neuer Abschnitte (wie praxis_gui `SEGMENT_COLORS`, der Reihe nach)
FARBEN: tuple[str, ...] = (
    "#e67e22",
    "#3498db",
    "#2ecc71",
    "#9b59b6",
    "#e74c3c",
    "#1abc9c",
    "#f39c12",
    "#34495e",
)
#: praxis_gui legt diesen Abschnitt selbst an (ganze Messung) — wir lassen ihn stehen
GESAMT_ID = "gesamt"
#: Kürzere Abschnitte aus Grenzen fallen weg (zwei Grenzen kurz hintereinander)
MIN_ABSCHNITT_S = 10.0


#: Kennung eines Abschnitts — im Sidecar seine ``id``, in der Messdatei die ``spur`` seiner
#: Grenz-Notizen (eigene Abschnitte der Person, trainingsapp 27.10.2026)
KENNUNG_PRAEFIX = "seg-"


def neue_kennung() -> str:
    """``seg-`` und acht Hexzeichen — wie praxis_gui seine Segmente benennt.

    >>> k = neue_kennung(); k.startswith(KENNUNG_PRAEFIX), len(k)
    (True, 12)
    """
    return f"{KENNUNG_PRAEFIX}{uuid.uuid4().hex[:8]}"


@dataclass
class Abschnitt:
    """Ein benannter Zeitbereich auf der Kurvenachse der App.

    ``kopf_s``/``endteil_s`` (trainingsapp, 27.10.2026): Kopf und Endteil — der
    **Rechenbereich** reicht so viele Sekunden über die getippten Grenzen hinaus (positiv:
    davor bzw. danach) oder beginnt dahinter (negativ: innerhalb). ``von_s``/``bis_s``
    bleiben die getippten Grenzen (praxis_gui sieht sie als Abschnitt).

    >>> a = Abschnitt("Behandlung", 600, 1800, kopf_s=-120, endteil_s=300)
    >>> a.dauer_s, a.rechenbereich(0, 2000), a.rechenbereich(700, 1900)
    (1200, (720, 2000), (720, 1900))
    """

    name: str
    von_s: float
    bis_s: float
    id: str = field(default_factory=neue_kennung)
    farbe: str = FARBEN[0]
    kopf_s: float = 0.0
    endteil_s: float = 0.0

    @property
    def dauer_s(self) -> float:
        return self.bis_s - self.von_s

    def rechenbereich(self, anfang: float, ende: float) -> tuple[float, float]:
        """``(von, bis)`` mit Kopf und Endteil, begrenzt auf ``anfang``…``ende`` und
        mindestens `MIN_ABSCHNITT_S` breit (ein Kopf, der den Abschnitt auffräße, wird
        gekappt)."""
        von = max(anfang, min(self.von_s - self.kopf_s, ende - MIN_ABSCHNITT_S))
        bis = min(ende, max(self.bis_s + self.endteil_s, von + MIN_ABSCHNITT_S))
        return von, bis


@dataclass(frozen=True, slots=True)
class Grenze:
    """Ein gewählter Abschnittsanfang: Zeit auf der Kurvenachse und Name.

    ``schluss``: beendet nur den laufenden Abschnitt und beginnt keinen
    („Timer fertig"). ``id``, ``kopf_s``, ``endteil_s``: Kennung und Ränder des
    Abschnitts, den sie beginnt (`Abschnitt`) — ohne ``id`` eine neue Kennung.
    """

    x: float
    name: str
    schluss: bool = False
    id: str | None = None
    kopf_s: float = 0.0
    endteil_s: float = 0.0


def grundname(name: str) -> str:
    """Der Name ohne Zusatz in Klammern am Ende — gleiche Grundnamen, gleiche Farbe.

    >>> grundname("Pause (Runde 2/8)"), grundname("Belastung")
    ('Pause', 'Belastung')
    """
    return re.sub(r"\s*\([^()]*\)\s*$", "", name).strip() or name


def farben_nach_namen(abschnitte: Sequence[Abschnitt], vergeben: int = 0) -> None:
    """Gleicher Grundname → gleiche Farbe, in der Reihenfolge des ersten Auftretens.

    So stehen beim Timer alle „Belastung" in einer Farbe und alle „Pause" in
    einer anderen. ``vergeben``: so viele Farben sind schon in Gebrauch.
    """
    farbe_von: dict[str, str] = {}
    for a in abschnitte:
        g = grundname(a.name)
        if g not in farbe_von:
            farbe_von[g] = FARBEN[(vergeben + len(farbe_von)) % len(FARBEN)]
        a.farbe = farbe_von[g]


def aus_grenzen(grenzen: Sequence[Grenze], anfang: float, ende: float) -> list[Abschnitt]:
    """Abschnitte zwischen gewählten Grenzen — jede beginnt einen, benannt nach ihr.

    Der letzte reicht bis ``ende``, außer eine `Grenze` mit ``schluss`` beendet
    ihn. Vor der ersten Grenze entsteht nichts; kürzer als `MIN_ABSCHNITT_S`
    fällt weg. Gleiche Grundnamen bekommen gleiche Farben.

    >>> teile = aus_grenzen(
    ...     [Grenze(60, "Belastung (Runde 1/2)"), Grenze(90, "Pause (Runde 1/2)"),
    ...      Grenze(120, "Belastung (Runde 2/2)"), Grenze(150, "fertig", schluss=True)], 0, 200)
    >>> [(a.von_s, a.bis_s) for a in teile], teile[1].name
    ([(60, 90), (90, 120), (120, 150)], 'Pause (Runde 1/2)')
    >>> teile[0].farbe == teile[2].farbe != teile[1].farbe
    True
    >>> [(a.name, a.bis_s) for a in aus_grenzen([Grenze(10, "A")], 0, 100)]
    [('A', 100)]
    """
    punkte = sorted((g for g in grenzen if anfang <= g.x <= ende), key=lambda g: g.x)
    out: list[Abschnitt] = []
    for a, b in pairwise([*punkte, Grenze(ende, "", schluss=True)]):
        if not a.schluss and b.x - a.x >= MIN_ABSCHNITT_S:
            teil = Abschnitt(
                a.name.strip() or "Abschnitt", a.x, b.x, kopf_s=a.kopf_s, endteil_s=a.endteil_s
            )
            if a.id:
                teil.id = a.id
            out.append(teil)
    farben_nach_namen(out)
    return out


def grenze_aus_notiz(x: float, eintrag: Mapping[str, Any], name: str, schluss: bool) -> Grenze:
    """Die `Grenze` zu einer Grenz-Notiz: Kennung und Ränder aus ihrer Marke.

    Eigene Abschnitte der Person tragen ihre Kennung als ``spur`` (``seg-…``); Kopf und
    Endteil stehen an der Start-Notiz jedes Abschnitts (`ereignisse.MARKE_FELDER`).

    >>> m = {"marke": {"quelle": "person", "art": "abschnitt", "spur": "seg-1a2b3c4d",
    ...                "name": "Behandlung", "kopf_s": -120, "endteil_s": 300}}
    >>> g = grenze_aus_notiz(600.0, m, "Behandlung", False)
    >>> g.id, g.kopf_s, g.endteil_s
    ('seg-1a2b3c4d', -120.0, 300.0)
    >>> grenze_aus_notiz(60.0, {"marke": {"spur": "timer", "kopf_s": 30}}, "Belastung", False)
    Grenze(x=60.0, name='Belastung', schluss=False, id=None, kopf_s=30.0, endteil_s=0.0)
    """
    marke = eintrag.get("marke") if isinstance(eintrag, Mapping) else None
    marke = marke if isinstance(marke, Mapping) else {}
    spur = str(marke.get("spur") or "")
    return Grenze(
        x,
        name,
        schluss,
        id=spur if spur.startswith(KENNUNG_PRAEFIX) else None,
        kopf_s=_zahl(marke.get("kopf_s")),
        endteil_s=_zahl(marke.get("endteil_s")),
    )


def _zahl(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return f if np.isfinite(f) else 0.0


def paare_aus_notizen(
    ereignisse: Sequence[Mapping[str, Any]],
    x_von: Callable[[Mapping[str, Any]], float | None],
    ende: float,
) -> list[Abschnitt]:
    """Eigene Abschnitte der Person aus ihren Grenz-Notizen (trainingsapp, 27.10.2026).

    Ein Abschnitt ist das Paar ``person/abschnitt`` (Start) und ``person/ende`` mit derselben
    ``spur`` = Kennung. Ohne Ende reicht er bis ``ende`` (live: er läuft noch). Name, Kopf
    und Endteil kommen von der Start-Notiz; ``x_von`` liefert die Stelle einer Notiz auf
    der Kurvenachse (``None``: nicht verankert — dann zählt sie nicht).

    >>> def m(x, art, spur, **rest):
    ...     return {"x": x, "marke": {"quelle": "person", "art": art, "spur": spur, **rest}}
    >>> teile = paare_aus_notizen(
    ...     [m(600, "abschnitt", "seg-aaaaaaaa", name="Behandlung", kopf_s=-120),
    ...      m(1800, "ende", "seg-aaaaaaaa"), m(2000, "abschnitt", "seg-bbbbbbbb", name="Ruhe"),
    ...      {"x": 100, "text": "ohne Marke"}, m(50, "abschnitt", "timer", name="nicht eigen")],
    ...     lambda e: e.get("x"), 2600)
    >>> [(a.id, a.name, a.von_s, a.bis_s, a.kopf_s) for a in teile]
    [('seg-aaaaaaaa', 'Behandlung', 600, 1800, -120.0), ('seg-bbbbbbbb', 'Ruhe', 2000, 2600, 0.0)]
    """
    starts: dict[str, Grenze] = {}
    enden: dict[str, float] = {}
    for e in ereignisse:
        marke = e.get("marke") if isinstance(e, Mapping) else None
        if not isinstance(marke, Mapping) or marke.get("quelle") != "person":
            continue
        spur = str(marke.get("spur") or "")
        if not spur.startswith(KENNUNG_PRAEFIX) or (x := x_von(e)) is None:
            continue
        art = marke.get("art")
        if art == "abschnitt" and spur not in starts:
            name = str(marke.get("name") or e.get("text") or "Abschnitt")
            starts[spur] = grenze_aus_notiz(x, e, name, False)
        elif art == "ende" and spur not in enden:
            enden[spur] = x
    out: list[Abschnitt] = []
    for spur, g in starts.items():
        bis = enden.get(spur, ende)
        if bis - g.x >= MIN_ABSCHNITT_S:
            out.append(Abschnitt(g.name, g.x, bis, id=spur, kopf_s=g.kopf_s, endteil_s=g.endteil_s))
    out.sort(key=lambda a: (a.von_s, a.bis_s))
    farben_nach_namen(out)
    return out


def einrasten(x: float, ziele: Sequence[float], toleranz: float) -> float:
    """Zur nächsten Notiz, wenn sie näher als ``toleranz`` liegt — sonst bleibt ``x``.

    >>> einrasten(58.0, [60.0, 120.0], 5.0), einrasten(50.0, [60.0], 5.0)
    (60.0, 50.0)
    """
    if not ziele:
        return x
    naechste = min(ziele, key=lambda z: abs(z - x))
    return float(naechste) if abs(naechste - x) <= toleranz else x


# ---------------------------------------------------------------------------
# Werte je Abschnitt
# ---------------------------------------------------------------------------


def abschnitt_werte(
    korr: Korrigiert,
    zeiten: Sequence[float],
    von: float,
    bis: float,
    *,
    pnn_ms: float = 50.0,
    frequenz: bool = False,
    atem_modus: str = RUHE,
) -> dict[str, Any]:
    """Kennzahlen eines Abschnitts: Ø HF, RMSSD, SDNN, Atemfrequenz (Median), LF/HF.

    LF/HF nur auf Wunsch (``frequenz``) und ab 2 min; die Atemfrequenz als
    Median der gültigen Minutenfenster (nur bei deutlicher Atmung).
    """
    teil = zuschneiden(korr, zeiten, von, bis)
    td = compute_time_domain(teil.rr_ms, pnn_threshold_ms=pnn_ms, breaks=teil.breaks) or {}
    werte: dict[str, Any] = {
        "dauer_s": bis - von,
        "n": len(teil.rr_ms),
        "mean_bpm": td.get("mean_bpm"),
        "rmssd": td.get("rmssd"),
        "sdnn": td.get("sdnn"),
        "atem": None,
        "lf_hf": None,
    }
    if len(teil.rr_ms) < 2:
        return werte
    # Auf der **Kurvenachse** (echte Zeit, ALGO 7): ``t_s`` ist die Herzuhr, die hinter
    # einer ausgeschlossenen Kette oder Messlücke zusammenrückt — dort sähe ein
    # Minutenfenster eine Atmung, die es nicht gab. Auf der echten Zeit bleibt die
    # Lücke eine Lücke, verworfene Intervalle sind fehlende Stützstellen (NaN).
    zt, rr = _echte_zeit(teil, zeiten, von, bis)
    raten = [
        float(a.rate_pro_min)
        for _, a in atem_fenster(zt, rr, modus=atem_modus)
        if a.gueltig and a.rate_pro_min is not None
    ]
    werte["atem"] = float(np.median(raten)) if raten else None
    if frequenz and bis - von >= 120.0:
        fs = abschnitt_spektrum(korr, zeiten, von, bis)
        werte["lf_hf"] = fs.werte.get("lf_hf") if fs is not None else None
    return werte


def _echte_zeit(
    teil: Korrigiert, zeiten: Sequence[float], von: float, bis: float
) -> tuple[np.ndarray, np.ndarray]:
    """Die Werte des Ausschnitts auf der Kurvenachse; Nullen (verworfen) als NaN."""
    zt = np.asarray([x for x in zeiten if von <= x <= bis], float)[: len(teil.rr_ms)]
    rr = np.asarray(teil.rr_ms, dtype=float)[: zt.size]
    return zt, np.where(rr > 0, rr, np.nan)


def abschnitt_spektrum(
    korr: Korrigiert, zeiten: Sequence[float], von: float, bis: float
) -> Fensterspektrum | None:
    """Spektrum eines Abschnitts (ALGO 7) — wie das Band in der Analysekarte.

    Bis `LANG_AB_S` ein Lomb auf der **Kurvenachse** (`fensterspektrum`): echte
    Zeit, Lücken bleiben Lücken, verworfene Intervalle sind fehlende Stützstellen
    — so zeigen Tabelle und Analysekarte dasselbe, auch bei Verity-Aufnahmen mit
    vielen Nähten (Teilstücke unter 60 Schlägen ergäben sonst gar nichts).
    Darüber der lange Weg der Gesamtmessung (`frequenzbereich` mit Nähten,
    `_spektrum_lang`) — vorher lief ein einzelner Lomb in den Deckel
    `MAX_GRID_BINS`, den ALGO 5 für die Gesamtmessung behoben hatte (LF/HF bei
    4 h um das 3,6-Fache zu hoch). Mindestdauern je Band gelten hier nicht —
    der Abschnitt ist bewusst gewählt; `Fensterspektrum.reif` sagt, ob er reicht.
    """
    teil = zuschneiden(korr, zeiten, von, bis)
    if len(teil.rr_ms) < 2:
        return None
    if bis - von <= LANG_AB_S:
        zt, rr = _echte_zeit(teil, zeiten, von, bis)
        return fensterspektrum(zt, rr, float(von) - 1e-6, float(bis))
    return Fensterspektrum.aus_frequenzbereich(
        frequenzbereich(teil.rr_ms, teil.t_s, teil.breaks, mindestdauer=False)
    )


# ---------------------------------------------------------------------------
# Sidecar: active_crop und segments wie praxis_gui
# ---------------------------------------------------------------------------


def zusatz_lesen(
    rec_pfad: Path, nach_achse: Callable[[float], float]
) -> tuple[tuple[float, float] | None, list[Abschnitt]]:
    """Crop und selbst markierte Abschnitte aus dem Sidecar — auf der Kurvenachse.

    praxis_gui speichert Abschnitte bei aktivem Crop relativ zu dessen Anfang;
    den ganzen Abschnitt („gesamt") legt es selbst an — er zählt hier nicht.
    Ob das Sidecar noch zur Messdatei passt, sagt `korrektur.sidecar_veraltet`
    (Befund R16) — die Zeiten hier stehen auf der Herzuhr der Rohdatei.
    """
    doc = _json_lesen(analyse_pfad(Path(rec_pfad))) or {}
    crop = doc.get("active_crop")
    ausschnitt: tuple[float, float] | None = None
    versatz = 0.0
    if isinstance(crop, dict):
        try:
            lo, hi = float(crop["t_start_s"]), float(crop["t_end_s"])
        except (KeyError, TypeError, ValueError):
            lo = hi = 0.0
        if hi > lo:
            ausschnitt = (nach_achse(lo), nach_achse(hi))
            versatz = lo
    abschnitte: list[Abschnitt] = []
    for d in doc.get("segments") or []:
        if not isinstance(d, dict) or d.get("id") == GESAMT_ID:
            continue
        try:
            von = nach_achse(float(d["t_start_s"]) + versatz)
            bis = nach_achse(float(d["t_end_s"]) + versatz)
        except (KeyError, TypeError, ValueError):
            continue
        if bis > von:
            rand = d.get("rand") if isinstance(d.get("rand"), dict) else {}
            abschnitte.append(
                Abschnitt(
                    str(d.get("name") or "Abschnitt"),
                    von,
                    bis,
                    id=str(d.get("id") or neue_kennung()),
                    farbe=str(d.get("color") or FARBEN[len(abschnitte) % len(FARBEN)]),
                    kopf_s=_zahl(rand.get("kopf_s")),
                    endteil_s=_zahl(rand.get("endteil_s")),
                )
            )
    return ausschnitt, abschnitte


def zusatz_speichern(
    rec_pfad: Path,
    ausschnitt: tuple[float, float] | None,
    abschnitte: Sequence[Abschnitt],
    nach_datei: Callable[[float], float],
) -> Path:
    """Crop und Abschnitte ins Sidecar — alles andere darin bleibt.

    Gibt es noch kein Sidecar (keine Korrektur gespeichert), entsteht ein
    knappes mit Schema, Quelle und Prüfsumme. Zeiten auf der Herzuhr der
    Rohdatei, Abschnitte bei Crop relativ zu dessen Anfang (wie praxis_gui).
    Abschnitte, die praxis_gui selbst führt („gesamt"), bleiben stehen.

    Je Abschnitt wird das **gelesene Segment fortgeschrieben** (gleiche ``id``):
    nur ``name``, ``t_start_s``, ``t_end_s`` und ``color`` werden gesetzt;
    ``active``/``visible`` (praxis_gui blendet damit aus), ``metrics``,
    ``computed_utc`` und unbekannte Felder bleiben (Befund F11 — vorher machte
    ein Crop aus der trainingsapp jeden Abschnitt wieder aktiv und sichtbar und
    warf praxis_guis Kennzahlen weg). Verschieben sich die Grenzen, werden
    ``metrics``/``computed_utc`` geleert: Die Zahlen gälten sonst für einen
    Bereich, den es nicht mehr gibt. Neue Segmente bekommen die heutigen
    Vorgaben (aktiv, sichtbar, keine Kennzahlen).
    """
    rec_pfad = Path(rec_pfad)
    ziel = analyse_pfad(rec_pfad)
    doc = _json_lesen_strikt(ziel) or {  # unlesbar → SidecarFehler, nichts überschreiben
        "schema": "analysis-v1",
        "source_file": rec_pfad.name,
        "source_file_sha1": _sha1(rec_pfad),
    }
    versatz = 0.0
    if ausschnitt is not None:
        lo, hi = nach_datei(ausschnitt[0]), nach_datei(ausschnitt[1])
        doc["active_crop"] = {"t_start_s": round(lo, 3), "t_end_s": round(hi, 3)}
        versatz = lo
    else:
        doc.pop("active_crop", None)
    gelesen = [d for d in doc.get("segments") or [] if isinstance(d, dict)]
    behalten = [d for d in gelesen if d.get("id") == GESAMT_ID]
    nach_id = {str(d.get("id")): d for d in gelesen if d.get("id") != GESAMT_ID}
    neu: list[dict[str, Any]] = []
    for a in abschnitte:
        von, bis = round(nach_datei(a.von_s) - versatz, 3), round(nach_datei(a.bis_s) - versatz, 3)
        alt = nach_id.get(a.id)
        if alt is None:
            seg: dict[str, Any] = {
                "id": a.id,
                "name": a.name,
                "t_start_s": von,
                "t_end_s": bis,
                "color": a.farbe,
                "metrics": None,
                "computed_utc": None,
                "active": True,
                "visible": True,
            }
        else:
            seg = dict(alt)
            if (seg.get("t_start_s"), seg.get("t_end_s")) != (von, bis):
                seg["metrics"] = None
                seg["computed_utc"] = None
            seg.update({"name": a.name, "t_start_s": von, "t_end_s": bis, "color": a.farbe})
        # Kopf und Endteil (trainingsapp): nur, wenn gesetzt — praxis_gui kennt das Feld
        # nicht und ließe es beim eigenen Speichern fallen; die Wahrheit ist die Marke
        if a.kopf_s or a.endteil_s:
            seg["rand"] = {"kopf_s": round(a.kopf_s, 3), "endteil_s": round(a.endteil_s, 3)}
        else:
            seg.pop("rand", None)
        neu.append(seg)
    doc["segments"] = behalten + neu
    doc["updated_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return json_atomar_schreiben(ziel, doc)


def grenzen_speichern(
    rec_pfad: Path, rec: Recording, grenzen: Sequence[tuple[dict, str, bool]]
) -> list[Abschnitt]:
    """Abschnitte aus Notizen einer frisch gespeicherten Aufnahme ins Sidecar.

    Für den Timer: ``grenzen`` sind (Notiz, Abschnittsname, beendet nur?) — die
    Notizen, die er beim Abschnittswechsel in die Aufnahme schrieb. Ihre
    Stelle kommt aus dem Anker der Notiz. Ohne Abschnitte bleibt alles, wie es ist.
    Eine einzige Spur — mehrere: `spuren_speichern`.
    """
    return spuren_speichern(rec_pfad, rec, {"": grenzen})


def spuren_speichern(
    rec_pfad: Path, rec: Recording, spuren: Mapping[str, Sequence[tuple[dict, str, bool]]]
) -> list[Abschnitt]:
    """Abschnitte mehrerer Spuren (Timer, Übungen, Kilometer …) in **einem** Zug ins Sidecar.

    Jede Spur bildet ihre Abschnitte für sich (`aus_grenzen`): Eine Grenze der
    einen Spur teilt keinen Abschnitt der anderen, und Abschnitte verschiedener
    Spuren dürfen sich überlappen (praxis_gui führt Abschnitte als unabhängige
    Bereiche). Gespeichert wird einmal — ein zweites `zusatz_speichern` ersetzte
    die erste Spur. Die Abschnitte stehen nach ihrem Anfang geordnet; gleiche
    Grundnamen bekommen über alle Spuren dieselbe Farbe. Der Name einer Spur
    dient nur hier: Im Sidecar hätte ein eigenes Feld praxis_gui nicht überlebt.

    Eine Grenze ist (Anker-Ereignis, Abschnittsname, beendet nur?) — das
    Ereignis muss nicht in ``ereignisse`` stehen (eine „stille“ Grenze, etwa
    das Ende einer Spur, die vor der Aufnahme endet).
    """
    achse = schlagzeiten(rec)
    if not achse:
        return []
    nach_datei, _ = achsen_umrechnung(achse, [b.t_s for b in rec.beats])
    zb = Zeitbezug(lambda: rec.beats, rec.start_utc, achse=lambda: achse)
    ende = float(achse[-1])
    teile: list[Abschnitt] = []
    for grenzen in spuren.values():
        punkte = [
            grenze_aus_notiz(x, eintrag, name, schluss)
            for eintrag, name, schluss in grenzen
            if (x := zb.x(eintrag)) is not None
        ]
        teile.extend(aus_grenzen(punkte, 0.0, ende))
    teile.sort(key=lambda a: (a.von_s, a.bis_s))
    farben_nach_namen(teile)
    if teile:
        zusatz_speichern(rec_pfad, None, teile, nach_datei)
    return teile


def achsen_umrechnung(
    achse: Sequence[float], datei_t: Sequence[float]
) -> tuple[Callable[[float], float], Callable[[float], float]]:
    """``(nach_datei, nach_achse)`` zwischen Kurvenachse und Herzuhr der Rohdatei.

    Beide je Rohschlag; dazwischen linear. Beim Brustgurt sind beide gleich.

    >>> nach_datei, nach_achse = achsen_umrechnung([1.0, 3.0], [1.0, 2.0])
    >>> nach_datei(2.0), nach_achse(1.5)
    (1.5, 2.0)
    """
    a = np.asarray(achse, dtype=float)
    d = np.asarray(datei_t, dtype=float)
    if a.size < 2 or a.size != d.size:
        return (float, float)

    def nach_datei(x: float) -> float:
        return float(np.interp(x, a, d))

    def nach_achse(x: float) -> float:
        return float(np.interp(x, d, a))

    return nach_datei, nach_achse


__all__ = [
    "FARBEN",
    "GESAMT_ID",
    "KENNUNG_PRAEFIX",
    "MIN_ABSCHNITT_S",
    "Abschnitt",
    "Grenze",
    "abschnitt_spektrum",
    "abschnitt_werte",
    "achsen_umrechnung",
    "aus_grenzen",
    "einrasten",
    "farben_nach_namen",
    "grenze_aus_notiz",
    "grenzen_speichern",
    "grundname",
    "neue_kennung",
    "paare_aus_notizen",
    "spuren_speichern",
    "zusatz_lesen",
    "zusatz_speichern",
]
