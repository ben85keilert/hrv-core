# Vorher/Nachher praxis_gui → hrv-core (Zahlen)

Erzeugt mit `scripts/vergleich_praxis_gui.py` aus `tests/golden/`. Vorher = praxis_gui nach
`auto_correct_runs` (Nullen interpoliert, Malik 0,20, scipy-Lomb, Kubios vor DFA). Nachher =
hrv-core Variante **vorgabe** (Nullen keine Artefakte, Malik 0,20/0,30, numpy-Lomb, kein Kubios);
**nullen** = hrv-core mit `Korrekturregeln(nullen=True)` — zeigt, welcher Teil der Differenz allein
von der Nullen-Regel kommt. Δ ist vorgabe gegen vorher.

**Frequenzbereich — Zeitachse ist der Hauptunterschied.** praxis_gui rechnete auf der
„echten“ Zeitachse `effective_rr_true()` (Wanduhr = Paketankunft, bei mehreren RR je Paket
zurückgerechnet). Am H10 kommen Pakete im 1-s-Takt; die Ankunft ist nicht der Schlagzeitpunkt.
Das wirkt als Zeitjitter und hebt HF: Generator „Kohärenzatmung 6/min“ (Wahrheit HF 67,5 ms²,
LF 6177 ms²) — praxis_gui Wanduhr HF 670 (10×), hrv-core Herzuhr HF 44,6; „Ruhe liegend“
praxis_gui 1115 gegen hrv-core 939 (+19 %). praxis_gui mit seiner eigenen Herzuhr-Option
(`frequenz_lomb_herzuhr` in den Golden-Dateien) liefert dieselben Werte wie hrv-core (ppm).
hrv-core rechnet je lückenfreiem Teilstück auf der Herzuhr (`Korrigiert.t_s`); Lücken trennen
die Teilstücke, die Wanduhr bestimmt nur, **wo** getrennt wird. Siehe docs/OFFENE_PUNKTE.md R11.


## generator__sensor_kohaerente_atmung_1001

Schläge roh 899, Quelle `ekg_rr`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 0/0

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 899 | 899 | +0,0 % | 899 |
| interpoliert | 0 | 0 | — | 0 |
| RMSSD ms | 50,342 | 50,342 | -0,0 % | 50,342 |
| SDNN ms | 84,770 | 84,770 | +0,0 % | 84,770 |
| pNN50 % | 43,096 | 43,096 | -0,0 % | 43,096 |
| Ø RR ms | 999,393 | 999,393 | -0,0 % | 999,393 |
| LF ms² (lomb) | 6110,357 | 6175,785 | +1,1 % | 6175,785 |
| HF ms² (lomb) | 670,209 | 44,564 | -93,4 % | 44,564 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 9,117 | 138,582 | +1420,0 % | 138,582 |
| LF ms² (welch) | 5878,724 | 5979,698 | +1,7 % | 5979,698 |
| HF ms² (welch) | 83,517 | 42,460 | -49,2 % | 42,460 |
| SD1 ms | 35,597 | 35,597 | -0,0 % | 35,597 |
| SD2 ms | 114,476 | 114,476 | +0,0 % | 114,476 |
| DFA α1 (praxis: Kubios) | 1,1950 | 1,1642 | -2,6 % | 1,1642 |
| DFA α1 (praxis: ohne Kubios) | 1,1640 | 1,1642 | +0,0 % | 1,1642 |
| SampEn | 0,6774 | 0,6774 | -0,0 % | 0,6774 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | — | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 231,0 | — | — | — |

## generator__sensor_ruhe_liegend_1000

Schläge roh 869, Quelle `ekg_rr`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 0/0

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 869 | 869 | +0,0 % | 869 |
| interpoliert | 0 | 0 | — | 0 |
| RMSSD ms | 46,767 | 46,767 | -0,0 % | 46,767 |
| SDNN ms | 53,616 | 53,616 | -0,0 % | 53,616 |
| pNN50 % | 33,180 | 33,180 | -0,0 % | 33,180 |
| Ø RR ms | 1034,083 | 1034,083 | -0,0 % | 1034,083 |
| LF ms² (lomb) | 745,969 | 756,836 | +1,5 % | 756,836 |
| HF ms² (lomb) | 1115,250 | 938,791 | -15,8 % | 938,791 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 0,669 | 0,806 | +20,5 % | 0,806 |
| LF ms² (welch) | 765,514 | 752,390 | -1,7 % | 752,390 |
| HF ms² (welch) | 612,292 | 626,991 | +2,4 % | 626,991 |
| SD1 ms | 33,069 | 33,069 | +0,0 % | 33,069 |
| SD2 ms | 68,233 | 68,233 | +0,0 % | 68,233 |
| DFA α1 (praxis: Kubios) | 0,7970 | 0,7330 | -8,0 % | 0,7330 |
| DFA α1 (praxis: ohne Kubios) | 0,7330 | 0,7330 | -0,0 % | 0,7330 |
| SampEn | 1,7801 | 1,7801 | -0,0 % | 1,7801 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 14,53 | 13,80 | -5,0 % | 13,80 |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 92,1 | 84,0 | -8,8 % | 84,0 |

## generator__sensor_ruhe_sitzend_1002

Schläge roh 988, Quelle `ekg_rr`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 0/0

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 988 | 988 | +0,0 % | 988 |
| interpoliert | 0 | 0 | — | 0 |
| RMSSD ms | 27,652 | 27,652 | -0,0 % | 27,652 |
| SDNN ms | 44,282 | 44,282 | -0,0 % | 44,282 |
| pNN50 % | 5,370 | 5,370 | -0,0 % | 5,370 |
| Ø RR ms | 909,028 | 909,028 | +0,0 % | 909,028 |
| LF ms² (lomb) | 869,603 | 873,593 | +0,5 % | 873,593 |
| HF ms² (lomb) | 427,681 | 293,383 | -31,4 % | 293,383 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 2,033 | 2,978 | +46,5 % | 2,978 |
| LF ms² (welch) | 864,254 | 869,101 | +0,6 % | 869,101 |
| HF ms² (welch) | 212,792 | 219,689 | +3,2 % | 219,689 |
| SD1 ms | 19,553 | 19,553 | -0,0 % | 19,553 |
| SD2 ms | 59,493 | 59,493 | -0,0 % | 59,493 |
| DFA α1 (praxis: Kubios) | 1,0340 | 1,0403 | +0,6 % | 1,0403 |
| DFA α1 (praxis: ohne Kubios) | 1,0400 | 1,0403 | +0,0 % | 1,0403 |
| SampEn | 1,5756 | 1,5756 | -0,0 % | 1,5756 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 14,49 | 14,05 | -3,1 % | 14,05 |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 74,4 | 61,0 | -18,1 % | 61,0 |

## physionet__sensor_nsr001

Schläge roh 1448, Quelle `ekg_rr`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 0/0

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 1448 | 1448 | +0,0 % | 1448 |
| interpoliert | 0 | 0 | — | 0 |
| RMSSD ms | 14,264 | 14,258 | -0,0 % | 14,258 |
| SDNN ms | 37,313 | 37,342 | +0,1 % | 37,342 |
| pNN50 % | 0,276 | 0,276 | +0,2 % | 0,276 |
| Ø RR ms | 621,385 | 620,930 | -0,1 % | 620,930 |
| LF ms² (lomb) | 218,962 | 219,532 | +0,3 % | 219,532 |
| HF ms² (lomb) | 32,484 | 32,486 | +0,0 % | 32,486 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 6,741 | 6,758 | +0,2 % | 6,758 |
| LF ms² (welch) | 239,737 | 239,627 | -0,0 % | 239,627 |
| HF ms² (welch) | 31,558 | 31,408 | -0,5 % | 31,408 |
| SD1 ms | 10,086 | 10,082 | -0,0 % | 10,082 |
| SD2 ms | 51,796 | 51,838 | +0,1 % | 51,838 |
| DFA α1 (praxis: Kubios) | 1,4220 | 1,4075 | -1,0 % | 1,4075 |
| DFA α1 (praxis: ohne Kubios) | 1,4080 | 1,4075 | -0,0 % | 1,4075 |
| SampEn | 1,6870 | 1,2152 | -28,0 % | 1,2152 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 10,14 | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 33,1 | — | — | — |

## physionet__sensor_nsr002

Schläge roh 1136, Quelle `ekg_rr`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 0/0

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 1136 | 1136 | +0,0 % | 1136 |
| interpoliert | 0 | 0 | — | 0 |
| RMSSD ms | 18,384 | 18,391 | +0,0 % | 18,391 |
| SDNN ms | 54,915 | 54,910 | -0,0 % | 54,910 |
| pNN50 % | 1,410 | 1,410 | -0,0 % | 1,410 |
| Ø RR ms | 791,806 | 791,338 | -0,1 % | 791,338 |
| LF ms² (lomb) | 758,444 | 757,622 | -0,1 % | 757,622 |
| HF ms² (lomb) | 50,490 | 50,690 | +0,4 % | 50,690 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 15,022 | 14,946 | -0,5 % | 14,946 |
| LF ms² (welch) | 774,767 | 777,620 | +0,4 % | 777,620 |
| HF ms² (welch) | 46,114 | 46,151 | +0,1 % | 46,151 |
| SD1 ms | 13,000 | 13,005 | +0,0 % | 13,005 |
| SD2 ms | 76,566 | 76,558 | -0,0 % | 76,558 |
| DFA α1 (praxis: Kubios) | 1,5930 | 1,5862 | -0,4 % | 1,5862 |
| DFA α1 (praxis: ohne Kubios) | 1,5870 | 1,5862 | -0,0 % | 1,5862 |
| SampEn | 0,9150 | 0,9150 | +0,0 % | 0,9150 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 8,77 | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 53,7 | — | — | — |

## praxis_gui__sensor_2026-04-24_204808

Schläge roh 126, Quelle `ekg_rr (Altdatei)`, Nullen roh: 1, praxis_gui-Ketten: 1, hrv-core-Ketten vorgabe/nullen: 0/1

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 126 | 126 | +0,0 % | 126 |
| interpoliert | 1 | 0 | -100,0 % | 1 |
| RMSSD ms | 55,588 | 56,033 | +0,8 % | 55,588 |
| SDNN ms | 78,522 | 78,118 | -0,5 % | 78,522 |
| pNN50 % | 33,600 | 34,146 | +1,6 % | 33,600 |
| Ø RR ms | 915,833 | 914,888 | -0,1 % | 915,833 |
| LF ms² (lomb) | — | — | — | — |
| HF ms² (lomb) | — | — | — | — |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | — | — | — | — |
| LF ms² (welch) | — | — | — | — |
| HF ms² (welch) | — | — | — | — |
| SD1 ms | 39,307 | 39,622 | +0,8 % | 39,307 |
| SD2 ms | 103,857 | 103,126 | -0,7 % | 103,857 |
| DFA α1 (praxis: Kubios) | — | — | — | — |
| DFA α1 (praxis: ohne Kubios) | — | — | — | — |
| SampEn | 1,4313 | 1,4123 | -1,3 % | 1,4313 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | — | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 168,8 | — | — | — |

## praxis_gui__sensor_2026-05-14_100223

Schläge roh 1102, Quelle `ekg_rr (Altdatei)`, Nullen roh: 6, praxis_gui-Ketten: 6, hrv-core-Ketten vorgabe/nullen: 0/6

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 1102 | 1102 | +0,0 % | 1102 |
| interpoliert | 6 | 0 | -100,0 % | 6 |
| RMSSD ms | 35,906 | 35,961 | +0,2 % | 35,906 |
| SDNN ms | 101,125 | 100,528 | -0,6 % | 101,125 |
| pNN50 % | 10,808 | 10,744 | -0,6 % | 10,808 |
| Ø RR ms | 817,912 | 817,017 | -0,1 % | 817,912 |
| LF ms² (lomb) | 1732,481 | 1527,468 | -11,8 % | 1566,319 |
| HF ms² (lomb) | 549,406 | 382,863 | -30,3 % | 374,496 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 3,153 | 3,990 | +26,5 % | 4,182 |
| LF ms² (welch) | 1365,606 | 1408,259 | +3,1 % | 1512,986 |
| HF ms² (welch) | 191,232 | 306,113 | +60,1 % | 307,808 |
| SD1 ms | 25,390 | 25,428 | +0,2 % | 25,390 |
| SD2 ms | 140,741 | 139,876 | -0,6 % | 140,741 |
| DFA α1 (praxis: Kubios) | 1,3660 | 1,3499 | -1,2 % | 1,3499 |
| DFA α1 (praxis: ohne Kubios) | 1,3500 | 1,3499 | -0,0 % | 1,3499 |
| SampEn | 0,8447 | 0,8436 | -0,1 % | 0,8447 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 9,11 | 8,93 | -2,0 % | 8,93 |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 84,6 | 83,0 | -1,9 % | 83,0 |

## praxis_gui__sensor_2026-05-14_190743

Schläge roh 234, Quelle `ekg_rr (Altdatei)`, Nullen roh: 8, praxis_gui-Ketten: 8, hrv-core-Ketten vorgabe/nullen: 0/8

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 234 | 234 | +0,0 % | 234 |
| interpoliert | 9 | 0 | -100,0 % | 8 |
| RMSSD ms | 61,487 | 64,230 | +4,5 % | 62,249 |
| SDNN ms | 121,164 | 122,944 | +1,5 % | 121,848 |
| pNN50 % | 39,056 | 40,092 | +2,7 % | 38,197 |
| Ø RR ms | 963,887 | 963,690 | -0,0 % | 964,662 |
| LF ms² (lomb) | — | — | — | — |
| HF ms² (lomb) | 2208,085 | 911,181 | -58,7 % | 854,540 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | — | — | — | — |
| LF ms² (welch) | — | — | — | — |
| HF ms² (welch) | 1019,896 | 956,920 | -6,2 % | 837,911 |
| SD1 ms | 43,478 | 45,417 | +4,5 % | 44,017 |
| SD2 ms | 165,744 | 167,833 | +1,3 % | 166,603 |
| DFA α1 (praxis: Kubios) | 1,1360 | 1,1094 | -2,3 % | 1,1229 |
| DFA α1 (praxis: ohne Kubios) | 1,1280 | 1,1094 | -1,7 % | 1,1229 |
| SampEn | 1,1050 | 1,1072 | +0,2 % | 1,1141 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 9,39 | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 168,8 | — | — | — |

## praxis_gui__sensor_2026-05-15_080834

Schläge roh 3129, Quelle `ekg_rr (Altdatei)`, Nullen roh: 1, praxis_gui-Ketten: 2, hrv-core-Ketten vorgabe/nullen: 1/2

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 3129 | 3129 | +0,0 % | 3129 |
| interpoliert | 2 | 1 | -50,0 % | 2 |
| RMSSD ms | 29,291 | 29,300 | +0,0 % | 29,291 |
| SDNN ms | 75,263 | 75,179 | -0,1 % | 75,263 |
| pNN50 % | 7,769 | 7,774 | +0,1 % | 7,769 |
| Ø RR ms | 843,720 | 843,652 | -0,0 % | 843,720 |
| LF ms² (lomb) | 2155,842 | 2189,832 | +1,6 % | 2193,133 |
| HF ms² (lomb) | 600,567 | 213,845 | -64,4 % | 213,495 |
| VLF ms² (lomb) | 1871,581 | 1860,798 | -0,6 % | 1869,569 |
| LF/HF (lomb) | 3,590 | 10,240 | +185,2 % | 10,273 |
| LF ms² (welch) | 2079,437 | 2077,111 | -0,1 % | 2083,835 |
| HF ms² (welch) | 170,048 | 160,659 | -5,5 % | 160,467 |
| SD1 ms | 20,712 | 20,718 | +0,0 % | 20,712 |
| SD2 ms | 104,403 | 104,281 | -0,1 % | 104,403 |
| DFA α1 (praxis: Kubios) | 1,4280 | 1,4417 | +1,0 % | 1,4417 |
| DFA α1 (praxis: ohne Kubios) | 1,4420 | 1,4417 | -0,0 % | 1,4417 |
| SampEn | 1,0148 | 1,0148 | -0,0 % | 1,0148 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 9,99 | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 92,3 | — | — | — |

## praxis_gui__sensor_2026-05-15_081631

Schläge roh 334, Quelle `ekg_rr (Altdatei)`, Nullen roh: 18, praxis_gui-Ketten: 19, hrv-core-Ketten vorgabe/nullen: 1/19

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 334 | 334 | +0,0 % | 334 |
| interpoliert | 20 | 2 | -90,0 % | 20 |
| RMSSD ms | 34,189 | 35,973 | +5,2 % | 34,189 |
| SDNN ms | 94,796 | 96,532 | +1,8 % | 94,796 |
| pNN50 % | 10,811 | 12,121 | +12,1 % | 10,811 |
| Ø RR ms | 1026,681 | 1024,854 | -0,2 % | 1026,681 |
| LF ms² (lomb) | 2508,386 | 2543,143 | +1,4 % | 2413,646 |
| HF ms² (lomb) | 1078,639 | 570,807 | -47,1 % | 540,196 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 2,326 | 4,455 | +91,5 % | 4,468 |
| LF ms² (welch) | 1343,473 | 1390,409 | +3,5 % | 1408,934 |
| HF ms² (welch) | 224,997 | 213,090 | -5,3 % | 224,760 |
| SD1 ms | 24,175 | 25,437 | +5,2 % | 24,175 |
| SD2 ms | 131,864 | 134,126 | +1,7 % | 131,864 |
| DFA α1 (praxis: Kubios) | 1,0750 | 1,0180 | -5,3 % | 1,0509 |
| DFA α1 (praxis: ohne Kubios) | 1,0510 | 1,0180 | -3,1 % | 1,0509 |
| SampEn | 0,9102 | 0,9219 | +1,3 % | 0,9102 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 10,89 | 9,84 | -9,7 % | 9,84 |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 90,7 | 81,0 | -10,7 % | 81,0 |

## praxis_gui__sensor_2026-05-18_100259

Schläge roh 1792, Quelle `ekg_rr (Altdatei)`, Nullen roh: 13, praxis_gui-Ketten: 13, hrv-core-Ketten vorgabe/nullen: 2/13

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 1792 | 1792 | +0,0 % | 1792 |
| interpoliert | 16 | 2 | -87,5 % | 15 |
| RMSSD ms | 54,855 | 55,178 | +0,6 % | 55,168 |
| SDNN ms | 92,278 | 92,085 | -0,2 % | 92,439 |
| pNN50 % | 25,572 | 25,496 | -0,3 % | 25,572 |
| Ø RR ms | 872,632 | 872,576 | -0,0 % | 872,730 |
| LF ms² (lomb) | 5337,811 | 5323,726 | -0,3 % | 5327,417 |
| HF ms² (lomb) | 1225,706 | 705,901 | -42,4 % | 694,515 |
| VLF ms² (lomb) | 1422,832 | 1419,925 | -0,2 % | 1476,923 |
| LF/HF (lomb) | 4,355 | 7,542 | +73,2 % | 7,671 |
| LF ms² (welch) | 5308,023 | 5331,732 | +0,4 % | 5443,359 |
| HF ms² (welch) | 592,889 | 574,221 | -3,1 % | 551,885 |
| SD1 ms | 38,789 | 39,017 | +0,6 % | 39,010 |
| SD2 ms | 124,604 | 124,245 | -0,3 % | 124,773 |
| DFA α1 (praxis: Kubios) | 1,0540 | 1,0476 | -0,6 % | 1,0476 |
| DFA α1 (praxis: ohne Kubios) | 1,0480 | 1,0476 | -0,0 % | 1,0476 |
| SampEn | 1,1295 | 1,1277 | -0,2 % | 1,1296 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 11,46 | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 139,5 | — | — | — |

## praxis_gui__sensor_2026-05-23_125422

Schläge roh 314, Quelle `ekg_rr (Altdatei)`, Nullen roh: 9, praxis_gui-Ketten: 9, hrv-core-Ketten vorgabe/nullen: 0/9

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 314 | 314 | +0,0 % | 314 |
| interpoliert | 9 | 0 | -100,0 % | 9 |
| RMSSD ms | 44,816 | 45,818 | +2,2 % | 44,816 |
| SDNN ms | 90,123 | 90,634 | +0,6 % | 90,123 |
| pNN50 % | 24,601 | 26,102 | +6,1 % | 24,601 |
| Ø RR ms | 990,393 | 989,239 | -0,1 % | 990,393 |
| LF ms² (lomb) | 2265,503 | 2581,372 | +13,9 % | 2632,615 |
| HF ms² (lomb) | 1038,046 | 526,828 | -49,2 % | 524,352 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 2,182 | 4,900 | +124,6 % | 5,021 |
| LF ms² (welch) | 1723,265 | 1762,091 | +2,3 % | 1759,488 |
| HF ms² (welch) | 292,469 | 259,969 | -11,1 % | 275,026 |
| SD1 ms | 31,690 | 32,398 | +2,2 % | 31,690 |
| SD2 ms | 123,450 | 124,014 | +0,5 % | 123,450 |
| DFA α1 (praxis: Kubios) | 1,4850 | 1,4573 | -1,9 % | 1,4613 |
| DFA α1 (praxis: ohne Kubios) | 1,4610 | 1,4573 | -0,3 % | 1,4613 |
| SampEn | 1,3160 | 1,2929 | -1,8 % | 1,3160 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 18,93 | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 67,5 | — | — | — |

## trainingsapp__sensor_2026-05-23_125422

Schläge roh 314, Quelle `ekg_rr (Altdatei)`, Nullen roh: 9, praxis_gui-Ketten: 9, hrv-core-Ketten vorgabe/nullen: 0/9

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 314 | 314 | +0,0 % | 314 |
| interpoliert | 9 | 0 | -100,0 % | 9 |
| RMSSD ms | 44,816 | 45,818 | +2,2 % | 44,816 |
| SDNN ms | 90,123 | 90,634 | +0,6 % | 90,123 |
| pNN50 % | 24,601 | 26,102 | +6,1 % | 24,601 |
| Ø RR ms | 990,393 | 989,239 | -0,1 % | 990,393 |
| LF ms² (lomb) | 2265,503 | 2581,372 | +13,9 % | 2632,615 |
| HF ms² (lomb) | 1038,046 | 526,828 | -49,2 % | 524,352 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 2,182 | 4,900 | +124,6 % | 5,021 |
| LF ms² (welch) | 1723,265 | 1762,091 | +2,3 % | 1759,488 |
| HF ms² (welch) | 292,469 | 259,969 | -11,1 % | 275,026 |
| SD1 ms | 31,690 | 32,398 | +2,2 % | 31,690 |
| SD2 ms | 123,450 | 124,014 | +0,5 % | 123,450 |
| DFA α1 (praxis: Kubios) | 1,4850 | 1,4573 | -1,9 % | 1,4613 |
| DFA α1 (praxis: ohne Kubios) | 1,4610 | 1,4573 | -0,3 % | 1,4613 |
| SampEn | 1,3160 | 1,2929 | -1,8 % | 1,3160 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 18,93 | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 67,5 | — | — | — |

## trainingsapp__sensor_2026-10-13_000000

Schläge roh 274, Quelle `ppg_ppi`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 1/1

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 274 | 274 | +0,0 % | 274 |
| interpoliert | 0 | 2 | — | 2 |
| RMSSD ms | 22,906 | 21,737 | -5,1 % | 21,737 |
| SDNN ms | 35,649 | 35,632 | -0,0 % | 35,632 |
| pNN50 % | 1,099 | 0,000 | -100,0 % | 0,000 |
| Ø RR ms | 849,613 | 849,577 | -0,0 % | 849,577 |
| LF ms² (lomb) | — | — | — | — |
| HF ms² (lomb) | 20,556 | — | — | — |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | — | — | — | — |
| LF ms² (welch) | — | — | — | — |
| HF ms² (welch) | 7,147 | — | — | — |
| SD1 ms | 16,197 | 15,371 | -5,1 % | 15,371 |
| SD2 ms | 47,743 | 47,989 | +0,5 % | 47,989 |
| DFA α1 (praxis: Kubios) | 1,1620 | 1,1576 | -0,4 % | 1,1576 |
| DFA α1 (praxis: ohne Kubios) | 1,1570 | 1,1576 | +0,0 % | 1,1576 |
| SampEn | 0,0300 | 0,0300 | +0,1 % | 0,0300 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | — | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 101,2 | — | — | — |

## trainingsapp__sensor_synth_kohaerente_atmung_7

Schläge roh 358, Quelle `ekg_rr`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 0/0

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 358 | 358 | +0,0 % | 358 |
| interpoliert | 0 | 0 | — | 0 |
| RMSSD ms | 43,959 | 43,959 | +0,0 % | 43,959 |
| SDNN ms | 74,136 | 74,136 | +0,0 % | 74,136 |
| pNN50 % | 31,933 | 31,933 | -0,0 % | 31,933 |
| Ø RR ms | 999,402 | 999,402 | +0,0 % | 999,402 |
| LF ms² (lomb) | 4457,533 | 4740,691 | +6,4 % | 4740,691 |
| HF ms² (lomb) | 581,414 | 58,918 | -89,9 % | 58,918 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 7,667 | 80,463 | +949,5 % | 80,463 |
| LF ms² (welch) | 4699,243 | 4658,122 | -0,9 % | 4658,122 |
| HF ms² (welch) | 80,771 | 32,207 | -60,1 % | 32,207 |
| SD1 ms | 31,084 | 31,084 | +0,0 % | 31,084 |
| SD2 ms | 100,131 | 100,131 | -0,0 % | 100,131 |
| DFA α1 (praxis: Kubios) | 1,1610 | 1,1646 | +0,3 % | 1,1646 |
| DFA α1 (praxis: ohne Kubios) | 1,1650 | 1,1646 | -0,0 % | 1,1646 |
| SampEn | 0,7559 | 0,7559 | -0,0 % | 0,7559 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | — | — | — | — |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 202,0 | — | — | — |

## trainingsapp__sensor_synth_ruhe_sitzend_11

Schläge roh 395, Quelle `ekg_rr`, Nullen roh: 0, praxis_gui-Ketten: 0, hrv-core-Ketten vorgabe/nullen: 0/0

| Kennzahl | vorher praxis_gui | hrv-core vorgabe | Δ | hrv-core nullen |
|---|---|---|---|---|
| n Schläge | 395 | 395 | +0,0 % | 395 |
| interpoliert | 0 | 0 | — | 0 |
| RMSSD ms | 27,664 | 27,664 | +0,0 % | 27,664 |
| SDNN ms | 49,112 | 49,112 | +0,0 % | 49,112 |
| pNN50 % | 5,584 | 5,584 | -0,0 % | 5,584 |
| Ø RR ms | 908,443 | 908,443 | +0,0 % | 908,443 |
| LF ms² (lomb) | 884,142 | 833,779 | -5,7 % | 833,779 |
| HF ms² (lomb) | 399,530 | 282,480 | -29,3 % | 282,480 |
| VLF ms² (lomb) | — | — | — | — |
| LF/HF (lomb) | 2,213 | 2,952 | +33,4 % | 2,952 |
| LF ms² (welch) | 821,428 | 802,241 | -2,3 % | 802,241 |
| HF ms² (welch) | 210,737 | 215,376 | +2,2 % | 215,376 |
| SD1 ms | 19,562 | 19,562 | -0,0 % | 19,562 |
| SD2 ms | 66,644 | 66,644 | -0,0 % | 66,644 |
| DFA α1 (praxis: Kubios) | 1,1070 | 1,1242 | +1,6 % | 1,1242 |
| DFA α1 (praxis: ohne Kubios) | 1,1240 | 1,1242 | +0,0 % | 1,1242 |
| SampEn | 1,6088 | 1,6088 | -0,0 % | 1,6088 |
| Atemrate /min (praxis: Median 60-s-Fenster; hrv-core: ein Fenster gesamt) | 14,56 | 14,15 | -2,8 % | 14,15 |
| RSA ms (praxis: Spline/Hilbert Median; hrv-core: atmung.rsa_ms) | 67,2 | 58,0 | -13,6 % | 58,0 |
