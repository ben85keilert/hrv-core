#!/usr/bin/env python
"""Vorher/Nachher für praxis_gui: alte scipy/NK2-Rechnung gegen hrv-core (trainingsapp-Standard).

Liest tests/golden/praxis_gui/ (Vorher, ``praxis_gui/scripts/export_referenz.py``) und
tests/golden/trainingsapp/ (hrv-core) und schreibt docs/VERGLEICH_ZAHLEN.md.

    uv run python scripts/vergleich_praxis_gui.py

praxis_gui interpolierte Nullen (``rr_ms = 0``) immer; hrv-core nicht (Vorgabe) — darum
stehen beide hrv-core-Varianten daneben: ``vorgabe`` (neuer Standard) und ``nullen``
(praxis_gui-Verhalten, zum Abgleich der übrigen Unterschiede).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
PG = HIER.parent / "tests" / "golden" / "praxis_gui"
TA = HIER.parent / "tests" / "golden" / "trainingsapp"
ZIEL = HIER.parent / "docs" / "VERGLEICH_ZAHLEN.md"


def g(d, *pfad):
    for k in pfad:
        if d is None:
            return None
        d = d.get(k) if isinstance(d, dict) else None
    return d


def f(x, n=1):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{n}f}".replace(".", ",")
    return str(x)


def delta(a, b):
    if a is None or b is None or not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or a == 0:
        return "—"
    return f"{100 * (b - a) / a:+.1f} %".replace(".", ",")


#: (Titel, praxis_gui-Pfad im Stand "automatik", hrv-core-Pfad in der Variante, Nachkomma)
ZEILEN = [
    ("n Schläge", ("n",), ("korrigiert", "rr_ms"), 0),
    ("interpoliert", ("ergebnis", "applied"), ("korrigiert", "interpoliert"), 0),
    ("RMSSD ms", ("time_domain", "rmssd"), ("kennzahlen", "rmssd"), 3),
    ("SDNN ms", ("time_domain", "sdnn"), ("kennzahlen", "sdnn"), 3),
    ("pNN50 %", ("time_domain", "pnn50"), ("kennzahlen", "pnn50"), 3),
    ("Ø RR ms", ("time_domain", "mean_rr"), ("kennzahlen", "mean_rr"), 3),
    ("LF ms² (lomb)", ("frequenz_lomb_subspectra", "lf"), ("frequenz", "lomb", "lf"), 3),
    ("HF ms² (lomb)", ("frequenz_lomb_subspectra", "hf"), ("frequenz", "lomb", "hf"), 3),
    ("VLF ms² (lomb)", ("frequenz_lomb_subspectra", "vlf"), ("frequenz", "lomb", "vlf"), 3),
    ("LF/HF (lomb)", ("frequenz_lomb_subspectra", "lf_hf"), ("frequenz", "lomb", "lf_hf"), 3),
    ("LF ms² (welch)", ("frequenz_welch_subspectra", "lf"), ("frequenz", "welch", "lf"), 3),
    ("HF ms² (welch)", ("frequenz_welch_subspectra", "hf"), ("frequenz", "welch", "hf"), 3),
    ("SD1 ms", ("poincare", "sd1"), ("poincare", "sd1"), 3),
    ("SD2 ms", ("poincare", "sd2"), ("poincare", "sd2"), 3),
    ("DFA α1 (praxis: Kubios)", ("dfa_kubios", "dfa_alpha1"), ("dfa_alpha1", "dfa_alpha1"), 4),
    ("DFA α1 (praxis: ohne Kubios)", ("dfa_ohne_kubios", "dfa_alpha1"), ("dfa_alpha1", "dfa_alpha1"), 4),
    ("SampEn", ("sampen",), ("sampen",), 4),
    ("Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt)", ("resp_rate_rest", "resp_rate_bpm"), ("_atmung", "rate_pro_min"), 2),
    ("RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms)", ("rsa_rest", "rsa_amp_median_ms"), ("_atmung", "rsa_ms"), 1),
]


def wert_pg(d, pfad):
    v = g(d, "automatik", *pfad)
    return len(v) if isinstance(v, list) else v


def wert_ta(d, variante, pfad):
    if pfad[0] == "_atmung":
        return g(d, "atmung_gesamt", "ruhe", pfad[1]) if g(d, "atmung_gesamt", "ruhe") else g(d, "atmung_gesamt", "RUHE", pfad[1])
    v = g(d, "varianten", variante, *pfad)
    return len(v) if isinstance(v, list) else v


def main() -> int:
    teile = ["# Vorher/Nachher praxis_gui → hrv-core (Zahlen)\n",
             "Erzeugt mit `scripts/vergleich_praxis_gui.py` aus `tests/golden/`. Vorher = praxis_gui nach",
             "`auto_correct_runs` (Nullen interpoliert, Malik 0,20, scipy-Lomb, Kubios vor DFA). Nachher =",
             "hrv-core Variante **vorgabe** (Nullen keine Artefakte, Malik 0,20/0,30, numpy-Lomb, kein Kubios);",
             "**nullen** = hrv-core mit `Korrekturregeln(nullen=True)` — zeigt, welcher Teil der Differenz allein",
             "von der Nullen-Regel kommt. Δ ist vorgabe gegen vorher.\n",
             "**Frequenzbereich — Zeitachse ist der Hauptunterschied.** praxis_gui rechnete auf der",
             "„echten“ Zeitachse `effective_rr_true()` (Wanduhr = Paketankunft, bei mehreren RR je Paket",
             "zurückgerechnet). Am H10 kommen Pakete im 1-s-Takt; die Ankunft ist nicht der Schlagzeitpunkt.",
             "Das wirkt als Zeitjitter und hebt HF: Generator „Kohärenzatmung 6/min“ (Wahrheit HF 67,5 ms²,",
             "LF 6177 ms²) — praxis_gui Wanduhr HF 670 (10×), hrv-core Herzuhr HF 44,6; „Ruhe liegend“",
             "praxis_gui 1115 gegen hrv-core 939 (+19 %). praxis_gui mit seiner eigenen Herzuhr-Option",
             "(`frequenz_lomb_herzuhr` in den Golden-Dateien) liefert dieselben Werte wie hrv-core (ppm).",
             "hrv-core rechnet je lückenfreiem Teilstück auf der Herzuhr (`Korrigiert.t_s`); Lücken trennen",
             "die Teilstücke, die Wanduhr bestimmt nur, **wo** getrennt wird. Siehe docs/OFFENE_PUNKTE.md R11.\n"]
    for pg in sorted(PG.glob("*.json")):
        ta = TA / pg.name
        if not ta.is_file():
            continue
        a = json.loads(pg.read_text(encoding="utf-8"))
        b = json.loads(ta.read_text(encoding="utf-8"))
        teile.append(f"\n## {pg.stem}\n")
        teile.append(f"Schläge roh {a['n_beats']}, Quelle `{a.get('intervall_quelle') or 'ekg_rr (Altdatei)'}`, "
                     f"Nullen roh: {sum(1 for x in a['roh']['rr_ms'] if x == 0)}, "
                     f"praxis_gui-Ketten: {g(a, 'automatik', 'ergebnis', 'runs')}, hrv-core-Ketten vorgabe/nullen: "
                     f"{len(g(b, 'varianten', 'vorgabe', 'ketten') or [])}/{len(g(b, 'varianten', 'nullen', 'ketten') or [])}\n")
        teile.append("| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |")
        teile.append("|---|---|---|---|---|")
        for titel, ppfad, tpfad, nk in ZEILEN:
            v0 = wert_pg(a, ppfad)
            v1 = wert_ta(b, "vorgabe", tpfad)
            v2 = wert_ta(b, "nullen", tpfad)
            teile.append(f"| {titel} | {f(v0, nk)} | {f(v1, nk)} | {delta(v0, v1)} | {f(v2, nk)} |")
    ZIEL.write_text("\n".join(teile) + "\n", encoding="utf-8")
    print("geschrieben:", ZIEL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
