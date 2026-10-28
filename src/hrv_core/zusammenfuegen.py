"""Mehrere Messdateien zu einer zusammenfügen (Ben, 28.10.2026).

Lange Aufnahmen lassen sich in Teilen speichern („Teil speichern & weiter“ in der
trainingsapp) — hinterher setzt `zusammenfuegen` die Teile wieder zu **einer** `raw-v1`-
Datei zusammen, am Rechner oder in der App:

    python -m hrv_core.zusammenfuegen teil1.json teil2.json [teil3.json …] [-o ziel.json]

Regeln:

- Die Teile werden nach ``start_utc`` geordnet; der erste gibt Kopf, Gerät, Titel vor.
- **Wanduhr** (``t_wall_s``) läuft über den Start des ersten Teils: Eine Lücke zwischen
  zwei Teilen bleibt als Lücke sichtbar — wie eine Verbindungslücke (Vertrag §3a).
- **Herzuhr** (``t_s``) zählt weiter: Die Herzuhr kennt keine Lücken (sie ist die Summe
  der gültigen RR-Intervalle), darum wird die des nächsten Teils an die letzte des
  vorigen gehängt.
- **Notizen** rücken mit: ``beat_index`` um die Schläge davor, ``t_s`` und ``t_wall_s`` um
  die Versätze; ``wall_time`` ist eine Uhrzeit und bleibt. An jeder Naht steht eine
  Notiz „Teil n“ mit Marke ``{"quelle": "zusammenfuegen", "art": "teil"}``.
- **PPI-Pakete** (Verity) rücken auf der Wanduhr mit.
- ``notiz`` der Teile wird zusammengehängt, wenn sie sich unterscheiden.

Die Teile selbst bleiben unverändert (Rohdaten); die neue Datei heißt nach dem Start des
ersten Teils mit dem Zusatz ``_zusammen``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .recording import Beat, Recording, json_atomar_schreiben, laden

MARKE_QUELLE = "zusammenfuegen"
MARKE_ART = "teil"


def zusammenfuegen(teile: Sequence[Recording]) -> Recording:
    """Die Teile als eine Messung — der Reihe nach, Notizen und Pakete versetzt.

    >>> from datetime import UTC, datetime, timedelta
    >>> s = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
    >>> a = Recording(beats=[Beat(0.8, 800, 75, 0.8), Beat(1.6, 800, 75, 1.6)], start_utc=s,
    ...               titel="Nacht", ereignisse=[{"beat_index": 1, "t_s": 1.6, "t_wall_s": 1.6,
    ...               "text": "x"}])
    >>> b = Recording(beats=[Beat(0.9, 900, 70, 0.9)], start_utc=s + timedelta(seconds=10))
    >>> z = zusammenfuegen([b, a])  # Reihenfolge nach start_utc
    >>> [(x.t_s, x.t_wall_s) for x in z.beats]
    [(0.8, 0.8), (1.6, 1.6), (2.5, 10.9)]
    >>> [(e["text"], e["beat_index"], e["t_wall_s"]) for e in z.ereignisse]
    [('x', 1, 1.6), ('Teil 2', 2, 10.9)]
    >>> z.titel, z.start_utc == s
    ('Nacht', True)
    """
    geordnet = sorted(teile, key=lambda r: r.start_utc or _OHNE)
    if not geordnet:
        raise ValueError("Keine Teile.")
    erster = geordnet[0]
    if erster.start_utc is None or any(r.start_utc is None for r in geordnet):
        raise ValueError("Jeder Teil braucht eine Startzeit (start_utc).")
    beats: list[Beat] = []
    ereignisse: list[dict[str, Any]] = []
    ppi: list[dict[str, Any]] | None = None
    notizen: list[str] = []
    for nr, teil in enumerate(geordnet, start=1):
        assert teil.start_utc is not None and erster.start_utc is not None
        wand_versatz = (teil.start_utc - erster.start_utc).total_seconds()
        herz_versatz = beats[-1].t_s if beats else 0.0
        davor = len(beats)
        for b in teil.beats:
            beats.append(
                Beat(
                    t_s=round(b.t_s + herz_versatz, 3),
                    rr_ms=b.rr_ms,
                    hf_bpm=b.hf_bpm,
                    t_wall_s=None if b.t_wall_s is None else round(b.t_wall_s + wand_versatz, 3),
                    tw_src=b.tw_src,
                )
            )
        if nr > 1 and teil.beats:
            erster_beat = beats[davor]
            ereignisse.append(
                {
                    "beat_index": davor,
                    "dt_s": 0.0,
                    "t_wall_s": erster_beat.t_wall_s,
                    "t_s": erster_beat.t_s,
                    "wall_time": teil.start_utc.astimezone().strftime("%H:%M:%S"),
                    "text": f"Teil {nr}",
                    "marke": {"quelle": MARKE_QUELLE, "art": MARKE_ART, "teil": nr},
                }
            )
        for e in teil.ereignisse:
            ereignisse.append(_versetzt(e, davor, herz_versatz, wand_versatz))
        if teil.ppi_pakete is not None:
            ppi = ppi or []
            for p in teil.ppi_pakete:
                q = dict(p)
                if isinstance(q.get("t_wall_s"), int | float):
                    q["t_wall_s"] = round(float(q["t_wall_s"]) + wand_versatz, 3)
                ppi.append(q)
        if teil.notiz and teil.notiz.strip() and teil.notiz.strip() not in notizen:
            notizen.append(teil.notiz.strip())
    return replace(
        erster,
        beats=beats,
        ereignisse=ereignisse,
        ppi_pakete=ppi,
        notiz="\n".join(notizen),
        titel=next((r.titel for r in geordnet if r.titel), ""),
    )


_OHNE = datetime.min.replace(tzinfo=UTC)


def _versetzt(e: dict[str, Any], davor: int, herz: float, wand: float) -> dict[str, Any]:
    out = dict(e)
    if isinstance(out.get("beat_index"), int):
        out["beat_index"] = out["beat_index"] + davor
    for feld, versatz in (("t_s", herz), ("t_wall_s", wand)):
        if isinstance(out.get(feld), int | float):
            out[feld] = round(float(out[feld]) + versatz, 3)
    return out


def zieldatei(teile: Sequence[Path], ziel: Path | None = None) -> Path:
    """Wohin die zusammengefügte Datei kommt — neben den ersten Teil, ``_zusammen``."""
    if ziel is not None:
        return ziel
    erster = sorted(teile)[0]
    return erster.with_name(erster.stem + "_zusammen.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Messdateien (raw-v1) zusammenfügen.")
    parser.add_argument("teile", nargs="+", type=Path, help="die Teile (sensor_*.json)")
    parser.add_argument("-o", "--ziel", type=Path, default=None, help="Zieldatei")
    args = parser.parse_args(argv)
    try:
        teile = [laden(p) for p in args.teile]
        ganz = zusammenfuegen(teile)
    except (OSError, ValueError) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1
    ziel = zieldatei(args.teile, args.ziel)
    if ziel.exists():
        print(f"Fehler: {ziel} gibt es schon.", file=sys.stderr)
        return 1
    json_atomar_schreiben(ziel, ganz.to_dict())
    print(f"{ziel}: {len(ganz.beats)} Schläge aus {len(teile)} Teilen")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["MARKE_ART", "MARKE_QUELLE", "main", "zieldatei", "zusammenfuegen"]
