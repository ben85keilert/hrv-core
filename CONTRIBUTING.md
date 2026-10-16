# Mitwirken

Danke für dein Interesse! Bitte lies vor einem Pull Request die folgenden Punkte.

## Lizenzvereinbarung für Beiträge (CLA)

Dieses Projekt steht unter der [AGPL-3.0](LICENSE), soll aber für den Projektinhaber **dual-lizenzierbar** bleiben (z. B. für eine kommerzielle Lizenz). Deshalb gilt:

**Mit dem Einreichen eines Beitrags (Pull Request, Patch) erklärst du dich einverstanden, dass:**

1. dein Beitrag unter der AGPL-3.0 veröffentlicht wird, **und**
2. du dem Projektinhaber (Benjamin Ebert) ein unwiderrufliches, weltweites, unentgeltliches Recht einräumst, deinen Beitrag auch **unter anderen Lizenzbedingungen** zu verwenden und weiterzulizenzieren (Dual Licensing),
3. du bestätigst, dass du der Urheber des Beitrags bist bzw. das Recht hast, ihn unter diesen Bedingungen einzureichen.

Wer damit nicht einverstanden ist, kann das Projekt selbstverständlich trotzdem unter den Bedingungen der AGPL-3.0 forken.

## Technische Konventionen

- **Nur numpy zur Laufzeit.** scipy und neurokit2 gibt es auf Android/iOS nicht; sie dienen
  ausschließlich den Vergleichstests (`uv sync --group referenz`, `tests/referenz/`).
  `tests/test_import_regel.py` erzwingt das.
- **Keine Patientendaten**, auch nicht de-identifiziert — siehe README, Abschnitt Datenschutz.
  Versioniert sind nur `tests/fixtures/` und `tests/golden/`.
- **Algorithmusänderungen** brauchen einen Eintrag in `docs/hrv_algorithmen.md` bzw.
  `docs/korrektur.md`, eine neue `ALGO_VERSION` und begründet erneuerte Golden-Master
  (`scripts/golden_erneuern.py`). Beide Apps müssen danach dieselben Zahlen liefern.
- **Datenformat** `raw-v1`/`analysis-v1` bleibt byte-kompatibel zu praxis_gui.
- **Sprache:** Code und Bezeichner englisch, wenn es die verbreitete Schreibweise ist;
  Kommentare, Docstrings und Dokumentation deutsch. Feldnamen des Austauschformats bleiben,
  wie praxis_gui sie schreibt.

## Vor dem Pull Request

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
