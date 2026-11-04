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

Erste Kandidaten (Plan Diagnosemodus der trainingsapp, §8.2): der Wiederholungszähler mit
Satzgrenzen und die Atmung aus Beschleunigung und RSA (K4).
"""

from __future__ import annotations

#: Steht in jedem Ergebnis eines Prototyps, damit keine App es mit einer Kennzahl verwechselt
KENNZEICHEN: str = "prototyp"

__all__ = ["KENNZEICHEN"]
