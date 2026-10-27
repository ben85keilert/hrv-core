"""Crop und Abschnitte einer fertigen Messung — Rechnung und Sidecar wie praxis_gui."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from hrv_core.ausschnitte import (
    GESAMT_ID,
    Abschnitt,
    Grenze,
    abschnitt_spektrum,
    abschnitt_werte,
    achsen_umrechnung,
    aus_grenzen,
    einrasten,
    grenzen_speichern,
    paare_aus_notizen,
    spuren_speichern,
    zusatz_lesen,
    zusatz_speichern,
)
from hrv_core.constants import LANG_AB_S
from hrv_core.ereignisse import Zeitbezug, notiz
from hrv_core.frequency import fensterspektrum, frequenzbereich
from hrv_core.korrektur import (
    Korrigiert,
    SidecarFehler,
    analyse_pfad,
    analyse_speichern,
    zuschneiden,
)
from hrv_core.ppi import schlagzeiten
from hrv_core.recording import laden

GOLDEN = Path(__file__).parent / "fixtures" / "trainingsapp" / "sensor_2026-05-23_125422.json"


def _korrigiert(n: int = 400, atem_hz: float = 0.25) -> tuple[Korrigiert, list[float]]:
    zufall = np.random.default_rng(3)
    t, rr, jetzt = [], [], 0.0
    for _ in range(n):
        wert = 900 + 40 * np.sin(2 * np.pi * atem_hz * jetzt) + zufall.normal(0, 3)
        jetzt += wert / 1000
        t.append(jetzt)
        rr.append(float(wert))
    return Korrigiert(t, rr, ["orig"] * n, [], 0, 0, list(range(n))), t


def test_abschnitte_aus_gewaehlten_grenzen_und_einrasten() -> None:
    """Nur gewählte Grenzen teilen — nichts vor der ersten, zu kurze fallen weg."""
    teile = aus_grenzen([Grenze(30, "A"), Grenze(31, "doppelt"), Grenze(90, "B")], 0, 150)
    assert [(a.name, a.von_s, a.bis_s) for a in teile] == [("doppelt", 31, 90), ("B", 90, 150)]
    assert aus_grenzen([], 0, 150) == []
    assert einrasten(88.0, [90.0], 3.0) == 90.0 and einrasten(80.0, [90.0], 3.0) == 80.0


def test_timer_legt_beim_speichern_abschnitte_an(tmp_path) -> None:
    """Die Abschnitte des Timers stehen nach dem Speichern im Sidecar — wie praxis_gui sie liest."""
    pfad = tmp_path / GOLDEN.name
    shutil.copy(GOLDEN, pfad)
    rec = laden(pfad)
    achse = schlagzeiten(rec)
    zb = Zeitbezug(lambda: rec.beats, rec.start_utc, achse=lambda: achse)

    def marke(x: float, text: str, ende: bool = False) -> tuple[dict, str, bool]:
        name = text.removeprefix("Timer „T“: ")
        return notiz(text, zb.anker(x), rec.start_utc), name, ende

    teile = grenzen_speichern(
        pfad,
        rec,
        [
            marke(60, "Timer „T“: Belastung (Runde 1/2)"),
            marke(90, "Pause (Runde 1/2)"),
            marke(120, "Belastung (Runde 2/2)"),
            marke(150, "Timer fertig", ende=True),
        ],
    )
    namen = ["Belastung (Runde 1/2)", "Pause (Runde 1/2)", "Belastung (Runde 2/2)"]
    assert [a.name for a in teile] == namen
    assert teile[0].farbe == teile[2].farbe != teile[1].farbe
    ausschnitt, gelesen = zusatz_lesen(pfad, float)
    assert ausschnitt is None and [a.name for a in gelesen] == namen
    assert gelesen[0].von_s == pytest.approx(60, abs=1.5)
    assert gelesen[-1].bis_s == pytest.approx(150, abs=1.5)


def test_spuren_schneiden_einander_nicht(tmp_path) -> None:
    """Timer und Kilometer zugleich: Jede Spur teilt nur sich selbst, ein Sidecar für beide."""
    pfad = tmp_path / GOLDEN.name
    shutil.copy(GOLDEN, pfad)
    rec = laden(pfad)
    achse = schlagzeiten(rec)
    zb = Zeitbezug(lambda: rec.beats, rec.start_utc, achse=lambda: achse)

    def grenze(x: float, name: str, ende: bool = False) -> tuple[dict, str, bool]:
        # Das Ereignis steht nicht in ``ereignisse`` — eine stille Grenze reicht
        return notiz(name, zb.anker(x), rec.start_utc), name, ende

    teile = spuren_speichern(
        pfad,
        rec,
        {
            "timer": [
                grenze(60, "Belastung (Runde 1/2)"),
                grenze(90, "Pause (Runde 1/2)"),
                grenze(120, "Belastung (Runde 2/2)"),
                grenze(150, "Timer fertig", ende=True),
            ],
            "km": [grenze(30, "km 1"), grenze(100, "km 2"), grenze(200, "Ende", ende=True)],
        },
    )
    namen = [
        "km 1",
        "Belastung (Runde 1/2)",
        "Pause (Runde 1/2)",
        "km 2",
        "Belastung (Runde 2/2)",
    ]
    assert [a.name for a in teile] == namen
    km1, _, _, km2, belastung2 = teile
    # Der Timer teilt „km 1“ nicht, „km 2“ teilt den Timer nicht
    assert (km1.von_s, km1.bis_s) == (pytest.approx(30, abs=1.5), pytest.approx(100, abs=1.5))
    assert km2.bis_s == pytest.approx(200, abs=1.5)
    assert belastung2.bis_s == pytest.approx(150, abs=1.5)
    assert teile[1].farbe == belastung2.farbe != teile[2].farbe
    _, gelesen = zusatz_lesen(pfad, float)
    assert [a.name for a in gelesen] == namen
    # Eine Spur bleibt, was grenzen_speichern immer war
    assert [a.name for a in grenzen_speichern(pfad, rec, [grenze(60, "A"), grenze(90, "B")])] == [
        "A",
        "B",
    ]


def test_werte_je_abschnitt() -> None:
    korr, t = _korrigiert()
    w = abschnitt_werte(korr, t, 60.0, 300.0, frequenz=True)
    assert w["mean_bpm"] == pytest.approx(60000 / 900, rel=0.02)
    assert w["rmssd"] > 10 and w["sdnn"] > 10
    assert w["atem"] == pytest.approx(15.0, abs=0.5)  # 0,25 Hz
    assert w["lf_hf"] is not None and w["lf_hf"] < 1  # Atmung im HF-Band
    teil = zuschneiden(korr, t, 60.0, 300.0)
    assert w["n"] == len(teil.rr_ms)


def test_abschnitt_rechnet_auf_der_echten_zeitachse() -> None:
    """ALGO 7: Die Herzuhr rückt hinter einer Lücke zusammen; gerechnet wird auf der
    Kurvenachse — wie das Band: Lücke bleibt Lücke, Tabelle und Karte zeigen dasselbe."""
    a, ta = _korrigiert(200, atem_hz=0.25)
    b, tb = _korrigiert(200, atem_hz=0.10)
    t_b = [x + ta[-1] for x in tb]  # Herzuhr: Stück b hängt direkt an a
    korr = Korrigiert(ta + t_b, a.rr_ms + b.rr_ms, ["orig"] * 400, [200], 0, 0)
    zeiten = ta + [x + 30.0 for x in t_b]  # Kurvenachse: 30-s-Lücke dazwischen
    w = abschnitt_werte(korr, zeiten, 0.0, zeiten[-1], frequenz=True)
    # Atem: Median aus beiden Stücken (15/min und 6/min); in der Lücke kein Fenster
    assert w["atem"] is not None and 6.0 <= w["atem"] <= 15.0
    zt = np.asarray(zeiten)
    erwartet = fensterspektrum(zt, np.asarray(korr.rr_ms, float), -1e-6, zeiten[-1])
    assert erwartet is not None
    assert w["lf_hf"] == pytest.approx(erwartet.werte["lf_hf"])
    fs = abschnitt_spektrum(korr, zeiten, 0.0, zeiten[-1])
    assert fs is not None and fs.werte["hf"] == pytest.approx(erwartet.werte["hf"])
    # Eine 5-min-Lücke deckt weniger als 70 % ab: kein Spektrum — in Tabelle und Karte gleich
    weit = ta + [x + 300.0 for x in t_b]
    assert abschnitt_spektrum(korr, weit, 0.0, weit[-1]) is None
    assert abschnitt_werte(korr, weit, 0.0, weit[-1], frequenz=True)["lf_hf"] is None


def test_abschnitt_mit_vielen_naehten_hat_ein_spektrum() -> None:
    """Verity-Aufnahmen setzen alle paar Schläge eine Naht (verworfene Intervalle):
    Teilstücke unter 60 Schlägen — über `frequenzbereich` käme nichts, auf der
    Kurvenachse mit NaN schon (Befund Ben, 15.10.2026: „Frequenzanalyse weg?“)."""
    korr, t = _korrigiert(300, atem_hz=0.25)
    rr = list(korr.rr_ms)
    for i in range(50, 300, 50):
        rr[i] = 0.0  # verworfen → Null, Naht davor
    korr = Korrigiert(t, rr, ["orig"] * 300, list(range(50, 300, 50)), 0, 0)
    assert frequenzbereich(korr.rr_ms, korr.t_s, korr.breaks, mindestdauer=False) is None
    fs = abschnitt_spektrum(korr, t, 0.0, t[-1])
    assert fs is not None and fs.werte["hf"] is not None
    assert abschnitt_werte(korr, t, 0.0, t[-1], frequenz=True)["lf_hf"] is not None


def test_langer_abschnitt_nimmt_den_langen_weg() -> None:
    """Ein Abschnitt über `LANG_AB_S` rechnet LF/HF als Mittel der 5-min-Spektren —
    nicht mehr mit dem gedeckelten Raster (ALGO 5 galt vorher nur für die Gesamtmessung)."""
    korr, t = _korrigiert(5000, atem_hz=0.25)  # ≈ 75 min
    assert t[-1] - t[0] > LANG_AB_S
    fs = abschnitt_spektrum(korr, t, 0.0, t[-1])
    assert fs is not None and fs.werte["hf"] is not None
    fenster = [
        fensterspektrum(t, korr.rr_ms, von, von + 300.0)
        for von in np.arange(t[0], t[-1] - 300.0, 300.0)
    ]
    hf_5min = float(np.mean([f.werte["hf"] for f in fenster if f is not None]))
    assert fs.werte["hf"] == pytest.approx(hf_5min, rel=0.25)
    assert fs.werte["lf_hf"] < 1


def test_unlesbares_sidecar_wird_nicht_ersetzt(tmp_path) -> None:
    """Ein Sidecar, das nicht lesbar ist, könnte praxis_gui-Korrekturen enthalten —
    schreiben bricht ab, die Datei bleibt, wie sie ist (15.10.2026)."""
    pfad = tmp_path / GOLDEN.name
    shutil.copy(GOLDEN, pfad)
    sidecar = analyse_pfad(pfad)
    sidecar.write_text("{ kaputt", encoding="utf-8")
    with pytest.raises(SidecarFehler, match="nicht lesbar"):
        zusatz_speichern(pfad, None, [Abschnitt("Pause", 10.0, 50.0)], float)
    with pytest.raises(SidecarFehler):
        analyse_speichern(pfad, laden(pfad), [])
    assert sidecar.read_text(encoding="utf-8") == "{ kaputt"
    sidecar.unlink()  # ohne Sidecar entsteht wie bisher ein neues
    zusatz_speichern(pfad, None, [Abschnitt("Pause", 10.0, 50.0)], float)
    assert json.loads(sidecar.read_text())["segments"][0]["name"] == "Pause"


def test_sidecar_wie_praxis_gui(tmp_path) -> None:
    """active_crop absolut, Abschnitte relativ zum Crop; Fremdes und „gesamt" bleiben."""
    pfad = tmp_path / GOLDEN.name
    shutil.copy(GOLDEN, pfad)
    analyse_pfad(pfad).write_text(
        json.dumps(
            {
                "schema": "analysis-v1",
                "metric_selection": ["rmssd"],
                "segments": [{"id": GESAMT_ID, "name": "Gesamt", "t_start_s": 0, "t_end_s": 9}],
            }
        )
    )
    gleich = (float, float)
    eigene = [Abschnitt("Pause", 100.0, 150.0, id="seg-1")]
    zusatz_speichern(pfad, (60.0, 300.0), eigene, gleich[0])
    doc = json.loads(analyse_pfad(pfad).read_text())
    assert doc["active_crop"] == {"t_start_s": 60.0, "t_end_s": 300.0}
    assert doc["metric_selection"] == ["rmssd"]  # Fremdes bleibt
    assert [s["id"] for s in doc["segments"]] == [GESAMT_ID, "seg-1"]
    pause = doc["segments"][1]
    assert (pause["t_start_s"], pause["t_end_s"]) == (40.0, 90.0)  # relativ zum Crop
    assert pause["metrics"] is None and pause["visible"] is True

    crop, gelesen = zusatz_lesen(pfad, gleich[1])
    assert crop == (60.0, 300.0)
    assert [(a.id, a.name, a.von_s, a.bis_s) for a in gelesen] == [("seg-1", "Pause", 100.0, 150.0)]

    zusatz_speichern(pfad, None, [], float)  # Crop entfernen, Abschnitt löschen
    doc = json.loads(analyse_pfad(pfad).read_text())
    assert "active_crop" not in doc and [s["id"] for s in doc["segments"]] == [GESAMT_ID]


def test_achsen_umrechnung_verity() -> None:
    """Kurvenachse (alle Intervalle) ↔ Herzuhr der Datei (nur Zeilen) — linear dazwischen."""
    nach_datei, nach_achse = achsen_umrechnung([0.0, 10.0, 30.0], [0.0, 10.0, 20.0])
    assert nach_datei(20.0) == 15.0 and nach_achse(15.0) == 20.0


def test_zusatz_speichern_schreibt_segmente_fort(tmp_path) -> None:
    """Befund F11: `active`/`visible`, `metrics` und Fremdes je Segment bleiben —
    vorher machte ein Crop aus der trainingsapp jeden Abschnitt wieder aktiv."""
    pfad = tmp_path / GOLDEN.name
    shutil.copy(GOLDEN, pfad)
    analyse_pfad(pfad).write_text(
        json.dumps(
            {
                "schema": "analysis-v1",
                "segments": [
                    {"id": GESAMT_ID, "name": "Gesamt", "t_start_s": 0, "t_end_s": 9},
                    {
                        "id": "seg-1",
                        "name": "Pause",
                        "t_start_s": 100.0,
                        "t_end_s": 150.0,
                        "color": "#000000",
                        "metrics": {"rmssd": 44.0},
                        "computed_utc": "2026-10-19T00:00:00Z",
                        "active": False,
                        "visible": False,
                        "praxis_feld": 1,
                    },
                ],
            }
        )
    )
    # unverändert gespeichert (z. B. Crop gesetzt): alles bleibt, Farbe/Name von uns
    zusatz_speichern(
        pfad, None, [Abschnitt("Pause", 100.0, 150.0, id="seg-1", farbe="#111111")], float
    )
    seg = json.loads(analyse_pfad(pfad).read_text())["segments"][1]
    assert seg["active"] is False and seg["visible"] is False and seg["praxis_feld"] == 1
    assert seg["metrics"] == {"rmssd": 44.0} and seg["computed_utc"] == "2026-10-19T00:00:00Z"
    assert seg["color"] == "#111111"

    # Grenzen verschoben: Kennzahlen gälten für einen anderen Bereich — geleert, Rest bleibt
    zusatz_speichern(pfad, None, [Abschnitt("Pause", 100.0, 160.0, id="seg-1")], float)
    seg = json.loads(analyse_pfad(pfad).read_text())["segments"][1]
    assert seg["metrics"] is None and seg["computed_utc"] is None
    assert seg["active"] is False and seg["praxis_feld"] == 1 and seg["t_end_s"] == 160.0

    # neues Segment: heutige Vorgaben
    zusatz_speichern(pfad, None, [Abschnitt("Neu", 10.0, 20.0, id="seg-2")], float)
    segs = json.loads(analyse_pfad(pfad).read_text())["segments"]
    assert [s["id"] for s in segs] == [GESAMT_ID, "seg-2"]
    assert segs[1]["active"] is True and segs[1]["visible"] is True and segs[1]["metrics"] is None


def test_eigener_abschnitt_als_notizpaar_mit_kopf_und_endteil(tmp_path) -> None:
    """trainingsapp 27.10.2026: Ein eigener Abschnitt ist ein Paar Grenz-Notizen mit der
    Kennung als Spur; Kopf und Endteil hängen an der Start-Notiz, das Sidecar bekommt die
    Kennung als ``id`` und die Ränder als ``rand``; der Rechenbereich nimmt sie mit."""
    pfad = tmp_path / GOLDEN.name
    shutil.copy(GOLDEN, pfad)
    rec = laden(pfad)
    achse = schlagzeiten(rec)
    zb = Zeitbezug(lambda: rec.beats, rec.start_utc, achse=lambda: achse)
    start = notiz(
        "Behandlung: Start",
        zb.anker(60),
        rec.start_utc,
        marke={
            "quelle": "person",
            "art": "abschnitt",
            "spur": "seg-1a2b3c4d",
            "name": "Behandlung",
            "kopf_s": -10,
            "endteil_s": 20,
        },
    )
    ende = notiz(
        "Behandlung: Ende",
        zb.anker(150),
        rec.start_utc,
        marke={"quelle": "person", "art": "ende", "spur": "seg-1a2b3c4d", "name": "Behandlung"},
    )
    assert start["marke"]["kopf_s"] == -10 and start["marke"]["endteil_s"] == 20
    # Aus den Notizen (Auswertung, live)
    (a,) = paare_aus_notizen([start, ende, {"text": "frei"}], zb.x, 400.0)
    assert (a.id, a.name, a.kopf_s, a.endteil_s) == ("seg-1a2b3c4d", "Behandlung", -10, 20)
    assert a.von_s == pytest.approx(60, abs=1.5) and a.bis_s == pytest.approx(150, abs=1.5)
    von, bis = a.rechenbereich(0.0, 400.0)
    assert von == pytest.approx(70, abs=1.5) and bis == pytest.approx(170, abs=1.5)
    # Ohne Ende läuft er bis ans Ende (live)
    assert paare_aus_notizen([start], zb.x, 400.0)[0].bis_s == 400.0
    # Beim Speichern der Aufnahme: Spur je Abschnitt, Kennung und Ränder im Sidecar
    teile = spuren_speichern(
        pfad, rec, {"seg-1a2b3c4d": [(start, "Behandlung", False), (ende, "", True)]}
    )
    assert [(t.id, t.kopf_s, t.endteil_s) for t in teile] == [("seg-1a2b3c4d", -10, 20)]
    _, gelesen = zusatz_lesen(pfad, float)
    assert [(t.id, t.kopf_s, t.endteil_s) for t in gelesen] == [("seg-1a2b3c4d", -10, 20)]
    doc = json.loads(analyse_pfad(pfad).read_text())
    assert doc["segments"][0]["rand"] == {"kopf_s": -10, "endteil_s": 20}
    # Ränder weg → das Feld verschwindet wieder
    gelesen[0].kopf_s = gelesen[0].endteil_s = 0.0
    zusatz_speichern(pfad, None, gelesen, float)
    assert "rand" not in json.loads(analyse_pfad(pfad).read_text())["segments"][0]
