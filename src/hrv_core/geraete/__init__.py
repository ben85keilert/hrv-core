"""Gerätewissen als Code — Dekoder und Kommandos, ohne Bluetooth und ohne App.

Was ein Gerät sendet und wie man es ihm sagt, ist für praxis_gui und trainingsapp dasselbe;
verschieden ist nur der Transport (bleak am Rechner, ``flet_ble`` auf dem Handy). Darum liegt
hier, was ohne Transport geht: Bytes → Proben mit Gerätezeit, Kommandos als Bytes,
Steuerantworten lesen. Die Apps führen den Ablauf aus (abonnieren, schreiben, neu verbinden).

Module:

- `pmd` — Polar Measurement Data: EKG, PPI, Beschleunigung, Einstellungen und Merkmalsliste
  (am Polar H10 und Verity Sense erprobt; vorher ``trainingsapp/devices/pmd.py`` und die
  Beschleunigung aus der Brustgurt-Diagnose in hrv-research).

Ausblick (Plan Diagnosemodus der trainingsapp, Stufe 7): Profile und Treiber je Gerät mit
Reifegrad (*erkannt*, *Prototyp*, *geprüft*, *empfohlen*). Gerätewissen in Worten:
``docs/geraete/``.
"""

from __future__ import annotations

__all__: list[str] = []
