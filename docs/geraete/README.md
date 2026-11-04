# Geräte: was die Sensoren liefern, was geprüft ist

Gesammeltes Wissen über die Geräte, die praxis_gui und trainingsapp über Bluetooth Low Energy
anbinden — und über die, bei denen es nicht ging. Beide Apps hängen von hrv-core ab, deshalb
liegt das Gerätewissen hier und nicht in einer App. Die Dokumente stammen aus `praxis_gui/docs/`
(verschoben am 19.10.2026); Codepfade darin beziehen sich auf praxis_gui.

**Der Polar H10 ist das Standardgerät und der Goldstandard.** Jedes andere Gerät wird relativ
zu ihm beschrieben und gegen ihn geprüft.

| Gerät | Intervalle | Rohsignal | Stand | Dokument |
|---|---|---|---|---|
| Polar H10 | RR aus dem EKG, 1/1024 s | EKG 130 Hz (PMD) | erprobt, Referenz | [`geraete.md`](geraete.md) |
| Polar H9 | RR aus dem EKG | — | nach Profil, ungetestet | [`geraete.md`](geraete.md) |
| Polar Verity Sense | PPI aus dem PPG (PMD) | PPG komprimiert, kein Decoder | Intervalle gegen H10 geprüft, Zeitachse schwach | [`verity_sense/`](verity_sense/README.md) |
| Decathlon HRM Belt | **keine** — sendet 60000/bpm in ms | — (herstellereigener Kanal, stumm) | am Gerät geprüft, **für HRV unbrauchbar** | [`decathlon/hrm_belt/`](decathlon/hrm_belt/README.md) |
| Beurer PO60 | keine (nur gespeicherte Mittelwerte) | — | Protokoll entschlüsselt, keine Anbindung | [`beurer_po60/`](beurer_po60/README.md) |
| Brustgurt nach Standardprofil | RR aus 0x2A37, wenn der Gurt sie sendet | — | je Gerät prüfen | [`geraete.md`](geraete.md), [`ble_uebertragung_pruefen.md`](ble_uebertragung_pruefen.md) |

## Die Dokumente

| Datei | Inhalt |
|---|---|
| [`geraete.md`](geraete.md) | Gerätekatalog und Profilvertrag (praxis_gui): was ein Profil steuert, PMD, Betriebssysteme, Kopplung |
| [`ble_uebertragung_pruefen.md`](ble_uebertragung_pruefen.md) | Prüfmethode für jedes neue Gerät in vier Ebenen; Goldstandard ist der H10 |
| [`mehrgeraetebetrieb.md`](mehrgeraetebetrieb.md) | Mehrere Sensoren in einer Sitzung mit gemeinsamem Zeit-Nullpunkt (`sitzung-v1`) |
| [`verity_sense/`](verity_sense/README.md) | Polar Verity Sense als Abweichung vom H10, mit Messprotokoll |
| [`decathlon/`](decathlon/README.md) | Decathlon-Herzfrequenzprodukte; darunter [`hrm_belt/`](decathlon/hrm_belt/README.md): kein RR, kein EKG — Befund, Rohmitschnitt, Erkundungsergebnis |
| [`beurer_po60/`](beurer_po60/README.md) | Beurer PO60 Fingerpulsoximeter: Protokoll, Erkundungsläufe, Entscheidung gegen die Anbindung |

Einstufung weiterer Gurte, Uhren und Wearables nach Aktenlage (ohne Test am Gerät):
`trainingsapp/docs/geraete_kompatibilitaet.md`.

## Ein unbekanntes Gerät erkunden

```bash
uv run --with bleak python scripts/ble_erkundung.py                 # Geräte in der Nähe
uv run --with bleak python scripts/ble_erkundung.py ADRESSE --dauer 120 --lauschen
```

`scripts/ble_erkundung.py` zählt Dienste und Charakteristiken auf, liest die Geräteinformation,
prüft auf Polar-PMD, hört den Standardstrom „Heart Rate Measurement“ ab und beurteilt den
RR-Strom: RR-Flag, Einheit, Rückrechnung aus der Herzfrequenz, Auflösung, Wiederholungen,
Zeitbilanz. Es schreibt nie auf das Gerät. Rohpakete und Befund landen unter
`ausgaben/ble_erkundung/` (gitignoriert). Hängt sich auch an ein Gerät, das BlueZ bereits hält.

Was danach kommt — Rohmitschnitt in der App, Prüfbericht, Doppelmessung gegen den H10 — steht
in [`ble_uebertragung_pruefen.md`](ble_uebertragung_pruefen.md).

## Gerätewissen als Code

Seit 0.6.0 (4.11.2026) liegt, was ohne Bluetooth geht, in `hrv_core.geraete`:

- `geraete.pmd` — Polar Measurement Data (EKG, PPI, Beschleunigung, Einstellungen, Merkmalsliste);
- `geraete.gatt` — Namen der Standarddienste und -merkmale, Dekoder 0x2A37 und Akkustand;
- `geraete.treiber` — je Gerät Erkennung, Ströme und Reifegrad (seit 0.7.0).

Der gemeinsame Rohmitschnitt aller Apps ist `hrv_core.mitschnitt` (`mitschnitt-v1`,
`docs/formate.md`); aus Mitschnitten entsteht der Dekoder eines neuen Geräts.

**Reifegrade** (die trainingsapp zeigt sie im Sensorblatt und in der Gerätesuche):

| Reifegrad | heißt | Beispiel |
|---|---|---|
| erkannt | Dienste bekannt, nur Standardströme, nicht eigens geprüft | Polar H9, Gurte nach Standardprofil |
| Prototyp | Dekoder an einer Geräteprobe getestet | — |
| geprüft | an zwei Geräten oder zwei Personen gegen den H10 geprüft (`ble_uebertragung_pruefen.md`) | Verity Sense |
| empfohlen | geprüft und als Referenz oder für HRV geeignet | Polar H10 |

**Weg einer Geräteprobe zum Treiber:**

1. Im Diagnosemodus der trainingsapp das Gerät ohne Messung roh mitschneiden (Geräte suchen →
   „Rohmitschnitt“) und die **Geräteprobe** teilen — als Datei, kein Hochladen aus der App.
2. Die Probe bleibt bei Ben; **Proben anderer Personen kommen nie in ein Repo** (Ben, 4.11.2026,
   P115) — sie dienen lokal der Entschlüsselung und Korrekturrechnung.
3. Befund unter `docs/geraete/<gerät>/` (wie Decathlon, Beurer) nach
   [`VORLAGE_NEUES_GERAET.md`](VORLAGE_NEUES_GERAET.md).
4. Treiber in `geraete/treiber.py` als *Prototyp*, Test an einem **synthetischen Nachbau** nach
   dem entschlüsselten Protokoll (nie an der Probe selbst, wenn sie nicht Bens eigene ist).
5. Mit der Prüfung gegen den H10 steigt der Reifegrad; die Apps heben `hrv-core.ref`.

Eine Eingangsvorlage für die Community gibt es erst nach rechtlicher Klärung (P115).
