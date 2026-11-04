"""EKG-Beiwerk `ekg.py`: sammeln, Lücken, Journal, schreiben, lesen (trainingsapp, 30.10.2026)."""

from __future__ import annotations

import json

import numpy as np

from hrv_core import ekg
from hrv_core.recording import ist_messdatei


def _rahmen(s: ekg.EkgSammler, k: int, n: int = 73, t0_ns: int = 10**12, luecke_s: float = 0.0):
    """Rahmen k mit n Proben; Gerätezeit fortlaufend, optional mit Lücke davor."""
    t_ns = t0_ns + round((k * n / 130 + luecke_s) * 1e9)
    s.rahmen(t_ns, [k * 1000 + i for i in range(n)], t_wall_s=5.0 + k * n / 130 + luecke_s)


def test_sammler_schreibt_praxis_gui_format_mit_erweiterungen(tmp_path) -> None:
    s = ekg.EkgSammler()
    for k in range(10):
        _rahmen(s, k)
    s.batterie_melden(5.0, 80)
    s.batterie_melden(6.0, 80)  # unverändert: keine Zeile
    s.batterie_melden(7.0, 79)
    messdatei = tmp_path / "sensor_2026-10-30_061500.json"
    pfad = s.schreiben(messdatei)
    assert pfad.name == "sensor_2026-10-30_061500_ecg.json" and not ist_messdatei(pfad)
    doc = json.loads(pfad.read_text(encoding="utf-8"))
    assert doc["sample_rate_hz"] == 130 and doc["n_samples"] == 730 == len(doc["uv"])
    assert doc["frame_offsets"] == [73 * k for k in range(10)]
    assert sum(doc["frame_sample_counts"]) == len(doc["uv"])  # Invariante aus praxis_gui
    assert doc["gaps"] == [] and doc["n_samples_expected"] == 730
    assert doc["batterie"] == [[5.0, 80], [7.0, 79]]
    assert abs(doc["t_wall_start_s"] - (5.0 - 72 / 130)) < 1e-3
    e = ekg.ekg_laden(pfad)
    assert e.n == 730 and e.uv.dtype == np.int32 and e.rate_hz == 130
    t = e.zeit_s()
    assert t.size == 730 and abs(t[0] - e.t_wall_start_s) < 1e-9
    assert np.allclose(np.diff(t), 1 / 130)
    tt, uv = e.ausschnitt(5.5, 6.0)
    assert 60 <= tt.size <= 66 and uv.size == tt.size


def test_luecke_aus_geraetezeit_und_journal(tmp_path) -> None:
    s = ekg.EkgSammler()
    _rahmen(s, 0)
    _rahmen(s, 1)
    _rahmen(s, 2, luecke_s=2.0)  # 2 s fehlen vor Rahmen 2
    assert s.luecken() == [{"nach_probe": 146, "dauer_s": 2.0}]
    journal = tmp_path / ".backup_2026-10-30_061500_ecg.jsonl"
    s.journal_anhaengen(journal)
    _rahmen(s, 3, luecke_s=2.0)
    s.batterie_melden(9.0, 50)
    s.journal_anhaengen(journal)
    s.journal_anhaengen(journal)  # nichts Neues: hängt nichts an
    zeilen = journal.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1 + 4 + 1 and zeilen[0].startswith('["k", 130')
    wieder = ekg.EkgSammler.aus_journal(journal)
    assert wieder.n == s.n and wieder.frame_t_ns == s.frame_t_ns
    assert wieder.batterie == [[9.0, 50]] and wieder.t_wall_start_s == s.t_wall_start_s
    assert wieder.luecken() == s.luecken()
    # Die Zeit je Probe lässt die Lücke stehen
    e = ekg.ekg_laden(wieder.schreiben(tmp_path / "sensor_x.json"))
    t = e.zeit_s()
    assert abs((t[146] - t[145]) - (2.0 + 1 / 130)) < 1e-6
    assert e.dauer_s > 4 * 73 / 130 + 1.9
    assert ekg.ekg_journal_pfad(tmp_path / ".backup_2026-10-30_061500.json") == journal


def test_altes_praxis_gui_beiwerk_ohne_erweiterungen(tmp_path) -> None:
    pfad = tmp_path / "sensor_alt_ecg.json"
    pfad.write_text(json.dumps({"sample_rate_hz": 130, "uv": [1, 2, 3, 4]}), encoding="utf-8")
    e = ekg.ekg_laden(pfad)
    assert e.frame_sample_counts == [4] and e.frame_offsets == [0] and e.frame_t_ns == []
    assert np.allclose(e.zeit_s(), np.arange(4) / 130)


def test_journal_mit_fsync_neuem_pfad_und_halber_zeile(tmp_path, monkeypatch) -> None:
    """Diagnosemodus V6: wie das Journal der Schläge — fsync, ein neuer oder verschwundener
    Pfad bekommt alles samt Kopf, eine halbe Zeile wird abgeschlossen statt fortgesetzt."""
    aufrufe: list[int] = []
    echt = ekg.os.fsync
    monkeypatch.setattr(ekg.os, "fsync", lambda fd: (aufrufe.append(fd), echt(fd)))
    s = ekg.EkgSammler()
    for k in range(3):
        _rahmen(s, k)
    a, b = tmp_path / "a_ecg.jsonl", tmp_path / "b_ecg.jsonl"
    s.journal_anhaengen(a)
    assert len(aufrufe) == 1
    _rahmen(s, 3)
    s.journal_anhaengen(b)  # anderer Ordner: alles noch einmal, mit Kopf
    assert ekg.EkgSammler.aus_journal(b).uv.tolist() == s.uv.tolist()
    b.unlink()  # verschwunden: wieder alles
    _rahmen(s, 4)
    s.journal_anhaengen(b)
    with open(b, "a", encoding="utf-8") as f:
        f.write('["r", 1, [7, 8')  # Abbruch mitten in der Zeile
    _rahmen(s, 5)
    s.journal_anhaengen(b)
    wieder = ekg.EkgSammler.aus_journal(b)
    assert wieder.uv.tolist() == s.uv.tolist() and wieder.n_rahmen == 6
    # Nach dem Wiederaufbau geht es im selben Journal weiter, ohne zweiten Kopf
    _rahmen(wieder, 6)
    wieder.journal_anhaengen(b)
    zeilen = [
        json.loads(z) for z in b.read_text(encoding="utf-8").splitlines() if z.startswith('["k"')
    ]
    assert len(zeilen) == 1 and ekg.EkgSammler.aus_journal(b).n_rahmen == 7
