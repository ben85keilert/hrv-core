"""Synthetische Messung über `LANG_AB_S` (4000 s) für den Golden Master des langen Spektralwegs.

    uv run python scripts/fixture_synth_lang.py        # schreibt tests/fixtures/synthetisch/

Reproduzierbar (fester Seed, feste Startzeit, Schreiber `hrv_core.aufnahme.Aufnahme`).
Deckt ab, was die kürzeren Fixtures nicht erreichen (docs/OFFENE_PUNKTE.md T6):
`frequency._spektrum_lang` (ULF/VLF/LF-HF in drei Teilen), `_lomb_hann`,
`_mittelreihe`, `vlf_fenster`, `fensterspektrum` über `LANG_AB_S` (ALGO_VERSION 8),
dazu Randartefakt, Ketten aller drei Arten, Nullen, eine Messlücke und Notizen
mit Marke. Bekannte Bänder (ms²): ULF 1800 (0,0015 Hz — bei 75 min noch gesperrt),
VLF 312 (0,01 Hz), LF 450 (0,1 Hz), HF 800 (0,25 Hz), Rauschen σ = 8 ms.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "src"))

from hrv_core.aufnahme import Aufnahme  # noqa: E402
from hrv_core.ereignisse import anker_aus_wand, notiz  # noqa: E402

DAUER_S = 5000.0
SEED = 1
START_UTC = datetime(2026, 10, 19, 4, 0, 0, tzinfo=UTC)
ZIEL = HIER.parent / "tests" / "fixtures" / "synthetisch" / "sensor_synth_lang_5000.json"

#: Eingriffe in die Reihe: Index → RR (ms). Am Anfang ein Randartefakt (R21),
#: eine kurze, eine unsichere (3) und gegen Ende eine lange Kette (7), dazu
#: Nullen („kein RR“, H10 unter 60 bpm). Lücke und lange Kette liegen so, dass
#: das Teilstück dazwischen über `LANG_AB_S` bleibt — sonst nähme auch die
#: Gesamtmessung nie den langen Weg.
EINGRIFFE: dict[int, int] = {
    0: 3000,
    500: 1500,
    1200: 2100,
    1201: 2150,
    1202: 2050,
    5100: 2200,
    5101: 2300,
    5102: 2100,
    5103: 2250,
    5104: 2150,
    5105: 2400,
    5106: 2050,
    3300: 0,
    3301: 0,
    3900: 600,
}
#: Messlücke: vor diesem Schlag stehen 8 s Wanduhr, die kein Intervall füllt (Naht).
LUECKE_VOR = 300
LUECKE_S = 8.0


def reihe() -> np.ndarray:
    """RR wie `tests/test_frequenz._lange_reihe` (Seed 1), gerundet auf ganze ms."""
    zufall = np.random.default_rng(SEED)
    n = int(DAUER_S / 0.92)
    rr = np.empty(n)
    jetzt = 0.0
    for i in range(n):
        rr[i] = (
            920
            + 40 * np.sin(2 * np.pi * 0.25 * jetzt)
            + 30 * np.sin(2 * np.pi * 0.1 * jetzt)
            + 25 * np.sin(2 * np.pi * 0.01 * jetzt)
            + 60 * np.sin(2 * np.pi * 0.0015 * jetzt)
            + zufall.normal(0, 8)
        )
        jetzt += rr[i] / 1000
    return np.round(rr).astype(int)


def main() -> int:
    rr = reihe()
    for i, wert in EINGRIFFE.items():
        rr[i] = wert
    a = Aufnahme(
        geraet="Generator",
        geraet_profil="polar_h10",
        intervall_quelle="ekg_rr",
        start_mono=0.0,
        start_utc=START_UTC,
        simulation=True,
    )
    a.titel = "Synthetisch 75 min (langer Spektralweg)"
    a.notiz = "scripts/fixture_synth_lang.py, Seed 1"
    wand = 1.0
    for i, x in enumerate(rr):
        if i == LUECKE_VOR:
            wand += LUECKE_S
        wand += x / 1000.0 if 300 <= x <= 2000 else 0.9
        a.schlag(int(x), round(60000 / x) if x else 65, wand, "m")
    beats = a.beats
    a.ereignisse = [
        notiz(
            "Start",
            anker_aus_wand(beats, 30.0),
            START_UTC,
            marke={"quelle": "timer", "art": "start", "spur": "timer", "name": "Ruhe"},
        ),
        notiz(
            "Lücke gleich", anker_aus_wand(beats, beats[LUECKE_VOR - 1].t_wall_s or 0.0), START_UTC
        ),
        notiz(
            "Ende",
            anker_aus_wand(beats, DAUER_S - 30.0),
            START_UTC,
            marke={"quelle": "timer", "art": "ende", "spur": "timer", "name": "Ruhe"},
        ),
    ]
    doc = a.recording().to_dict()
    doc["generator_config"] = {
        "quelle": "scripts/fixture_synth_lang.py",
        "seed": SEED,
        "dauer_s": DAUER_S,
        "baender_ms2": {"ulf": 1800, "vlf": 312, "lf": 450, "hf": 800},
        "eingriffe": {str(k): v for k, v in EINGRIFFE.items()},
        "luecke": {"vor_index": LUECKE_VOR, "s": LUECKE_S},
    }
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    with open(ZIEL, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    print("geschrieben:", ZIEL, len(beats), "Schläge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
