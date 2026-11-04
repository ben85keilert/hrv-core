# Vorlage: Befund eines neuen Geräts

Für eine Geräteprobe aus dem Diagnosemodus der trainingsapp (Rohmitschnitt ohne Messung,
`mitschnitt-v1`). Ablage: `docs/geraete/<hersteller>/<gerät>/README.md`. **Nur Befunde und
synthetische Nachbauten** — die Probe selbst bleibt lokal (P115), Messwerte einer anderen
Person stehen hier nie.

## Gerät

| | |
|---|---|
| Hersteller, Modell | |
| Firmware, Hardware (Geräteinformation 0x180A) | |
| Art | Brustgurt · Armband · Uhr · anderes |
| Probe vom | Datum, Dauer, was getan (still, bewegt, Treppe …), Vergleichswert (z. B. „Puls laut Uhr 64“) |

## Dienste und Merkmale

| Dienst | Merkmal | Eigenschaften | Name (`hrv_core.geraete.gatt`) | Befund |
|---|---|---|---|---|
| 0x180D | 0x2A37 | benachrichtigen | Herzfrequenz-Messung | RR ja/nein, Auflösung, Wiederholungen |

## Ströme

Je Strom: Rahmenaufbau, Rate (aus der Gerätezeit, wenn vorhanden), Einheit, Lücken, was
`hrv_core.mitschnitt.stroeme` daraus macht. Herstellereigene Kanäle: Bytes je Paket, Muster.

## Entscheidung

Reifegrad (*erkannt* / *Prototyp* / *geprüft* / *empfohlen*), Treiber-ID, offene Fragen, nächster
Schritt (Prüfung gegen den H10 nach `ble_uebertragung_pruefen.md`).
