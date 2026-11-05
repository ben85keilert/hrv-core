"""Prototypen nach moderater Reife — **gekennzeichnet, nicht Grundlage gespeicherter Zahlen.**

Ben, 4.11.2026: „In HRV-core können gerne Prototypen mit rein nach moderater Reife.“ Hier liegen
Verfahren, die in hrv-research (dem Entwicklungszentrum) so weit gekommen sind, dass die Apps
sie zeigen dürfen — als Prototyp beschriftet, neben den Daten, aus denen sie entstehen.

Regeln:

- **Eingang:** in hrv-research an mindestens zwei Sitzungen geprüft, die nicht zum Einstellen
  dienten, mit Befund in ``hrv-research/docs/ENTSCHEIDUNGEN.md``; dazu Tests hier.
- **Nie Grundlage gespeicherter Kennzahlen oder Caches.** Ein Prototyp darf sich ohne
  ``ALGO_VERSION`` ändern und hat noch keinen Golden Master; die Apps zeigen sein Ergebnis nur
  an (und schreiben es höchstens in eigene, als Prototyp gekennzeichnete Felder).
- **Keine Bewertung** — wie überall in hrv-core: Zahlen, kein Rat.
- **Ausgang:** nach ``hrv-research/docs/UEBERNAHME.md`` in ein Stammmodul, dann mit Golden
  Master, Eintrag in ``docs/hrv_algorithmen.md`` und, wenn sich Zahlen ändern, ``ALGO_VERSION``.

Module:

- `wiederholungen` — Wiederholungen aus der Beschleunigung: `zaehlen_fenster` über ein
  bekanntes Satzfenster (seit 0.8.0, bis 0.10.0 ``zaehlen``; Eingang mit Ausnahme, Entscheidung
  22 in hrv-research) und `WdhLive`, kausal und rahmenweise mit Vorlagenkatalog `VORLAGEN`
  (Kniebeuge, Rudern, Liegestütz …), Meldung je Wiederholung samt Rücknahme, `zaehlen` als
  Offline-Hülle darüber (seit 0.11.0; Eingang mit Ausnahme, Entscheidung 26 in hrv-research).
- `atemzuege` — Atemzüge und Atemphasen live aus der Beschleunigung, kausal mit Gültigkeit je
  Fenster (seit 0.9.0; Eingang mit Ausnahme, Entscheidung 24 in hrv-research; Ergebnis im
  Beiwerk `atem-v1`).
- `atem_hrv` — Atem-HRV je Atemzug aus Atemphasen und RR-Abständen: Spanne, Sinus, Phasenlage,
  RR je Phase, Gültigkeit mit Gründen, Zusammenfassung; live wie offline (seit 0.10.0; Eingang
  mit Ausnahme, Entscheidung 25 in hrv-research; liest `phasen[]` und `fenster[]` aus `atem-v1`
  oder einen Takt).

Nächster Kandidat: Takt und RSA als zweite Stufe der Atmung für Haltungen, die der festen
Richtung fehlen (Seiten-, Bauchlage, Sensor am Arm; K4, Entscheidung 21).
"""

from __future__ import annotations

#: Steht in jedem Ergebnis eines Prototyps, damit keine App es mit einer Kennzahl verwechselt
KENNZEICHEN: str = "prototyp"

__all__ = ["KENNZEICHEN"]
