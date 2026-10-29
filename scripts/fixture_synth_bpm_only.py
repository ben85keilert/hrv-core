"""Synthetische Messung eines reinen Pulsgebers (``bpm_only``) für Golden Master und Tests.

    uv run python scripts/fixture_synth_bpm_only.py   # schreibt tests/fixtures/synthetisch/

Reproduzierbar (fester Seed, feste Startzeit, Schreiber `hrv_core.aufnahme.Aufnahme`).
Eine Uhr im Broadcast-Modus sendet nur die Herzfrequenz, nie RR-Intervalle: jede Zeile hat
``rr_ms = 0``, die Herzuhr ``t_s`` bleibt 0, die Wanduhr läuft (Entscheidung 16, hrv-research).
Verlauf über 15 min: 3 min Ruhe (≈ 62 bpm), 5 min Anstieg auf 150, 3 min Halten, 4 min
Erholung — mit einer Marke am Ende der Belastung (``person/erholung``), 1-s-Takt, kleines
Rauschen, eine Lücke von 12 s (Kontaktverlust).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "src"))

from hrv_core.aufnahme import Aufnahme  # noqa: E402
from hrv_core.ereignisse import anker_aus_wand, notiz  # noqa: E402

SEED = 3
START_UTC = datetime(2026, 10, 29, 6, 30, 0, tzinfo=UTC)
ZIEL = HIER.parent / "tests" / "fixtures" / "synthetisch" / "sensor_synth_bpm_only_900.json"
DAUER_S = 900
#: Lücke: ab dieser Sekunde kommen 12 s lang keine Pakete
LUECKE_AB_S = 500
LUECKE_S = 12
#: Ende der Belastung (Marke)
BELASTUNG_ENDE_S = 660


def verlauf() -> np.ndarray:
    zufall = np.random.default_rng(SEED)
    t = np.arange(DAUER_S, dtype=float)
    hf = np.where(
        t < 180,
        62.0,
        np.where(
            t < 480,
            62.0 + (150.0 - 62.0) * (t - 180) / 300,
            np.where(
                t < BELASTUNG_ENDE_S, 150.0, 62.0 + 88.0 * np.exp(-(t - BELASTUNG_ENDE_S) / 60)
            ),
        ),
    )
    return np.round(hf + zufall.normal(0, 1.0, DAUER_S)).astype(int)


def main() -> int:
    a = Aufnahme(
        geraet="Uhr (Broadcast)",
        geraet_profil="watch_broadcast",
        intervall_quelle="ekg_rr",
        start_mono=1000.0,
        start_utc=START_UTC,
    )
    a.titel = "Synthetisch: reiner Pulsgeber, Belastung und Erholung"
    a.notiz = "Erzeugt mit scripts/fixture_synth_bpm_only.py (Seed 3)."
    for s, hf in enumerate(verlauf()):
        if LUECKE_AB_S <= s < LUECKE_AB_S + LUECKE_S:
            continue
        a.schlag(0, int(hf), 1000.0 + s + 0.2, "m")
    a.ereignisse.append(
        notiz(
            "Belastung beendet, stehend",
            anker_aus_wand(a.beats, float(BELASTUNG_ENDE_S)),
            start_utc=START_UTC,
            marke={"quelle": "person", "art": "erholung", "kontext": "dauer", "haltung": "steht"},
        )
    )
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    pfad = a.speichern(ZIEL.parent)
    if pfad != ZIEL:
        pfad.replace(ZIEL)
    print("geschrieben:", ZIEL, len(a.beats), "Zeilen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
