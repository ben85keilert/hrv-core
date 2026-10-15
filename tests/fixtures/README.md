# Fixtures

Alle Dateien sind durch `hrv_core.deid` gelaufen (`patient_id`/`behandlung_id` = null) und mit
`scripts/pruefe_daten.py tests/fixtures --ohne-ordnerregel` geprüft (0 Ablehnungen, 15.10.2026).

| Ordner | Herkunft |
|---|---|
| `praxis_gui/` | `praxis_gui/Data/RR/` — eigene Aufnahmen von Ben (Polar H10, 2026-04/05), anonymisiert laut `docs/code_pruefplan.md`; Sidecars `_analyzed`/`_ecg` byteweise kopiert (`source_file_sha1` passt nach dem Nullen nicht mehr zur Rohdatei). `sensor_2026-04-28_142332.json` (anderer Patient) bewusst nicht übernommen |
| `generator/` | `praxis_gui/DataEvaluation/validierung_daten/generator/` — synthetisch, mit `truth-v1` |
| `physionet/` | PhysioNet NSR nsr001/nsr002, öffentlich, im raw-v1-Format |
| `trainingsapp/` | `trainingsapp/tests/golden/rr/` — siehe deren README (Golden-Sollwerte in den trainingsapp-Tests) |
