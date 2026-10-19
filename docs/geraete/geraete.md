# Sensoren: welche Geräte laufen, was sie liefern

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Die Sensorik war bis Version 0.1 auf ein Gerät festgelegt — den Polar H10.
Inzwischen entscheidet ein **Geräteprofil**, was ein Sensor kann und wie seine
Messungen behandelt werden. Neue Geräte kommen über ein Profil hinzu, nicht über
Sonderfälle im Widget.

Code: `src/praxislab/sensors/devices/` (Qt-frei) · Profile in `profiles.py`

**Der Polar H10 ist das Standardgerät und der Goldstandard.** Alles Weitere ist
Zusatz und wird relativ zu ihm dokumentiert:

- Polar Verity Sense → [`verity_sense/`](verity_sense/README.md)
- mehrere Geräte gleichzeitig → [`mehrgeraetebetrieb.md`](mehrgeraetebetrieb.md)
- ein neues Gerät prüfen → [`ble_uebertragung_pruefen.md`](ble_uebertragung_pruefen.md)

---

## 1. Unterstützte Geräte

| Gerät | Intervalle | Rohdaten | Ablage | Stand |
|---|---|---|---|---|
| **Polar H10** | RR aus dem EKG | EKG 130 Hz | `Messungen/PolarH10/` | erprobt |
| **Polar H9** | RR aus dem EKG | — | `Messungen/PolarH9/` | nach Profil, ungetestet |
| **Polar Verity Sense** | PPI aus dem PPG | — (PPG ohne Decoder) | `Messungen/VeritySense/` | PPI am Gerät geprüft und gegen den H10 abgeglichen; Zeitachse in Arbeit → [`verity_sense/`](verity_sense/README.md) |
| **Brustgurt (Standardprofil)** | RR aus dem EKG | — | `Messungen/Brustgurt/` | nach Profil, ungetestet |

Unter „Brustgurt (Standardprofil)" läuft jeder Gurt, der die Bluetooth-Standard-
Charakteristik „Heart Rate Measurement" (`0x2A37`) mit RR-Intervallen sendet —
Garmin HRM, Wahoo TICKR, Coospo, Decathlon/Geonaute, Magene, Suunto und andere.
Die Namensmuster in `profiles.py` sind nur eine Bequemlichkeit für die
Vorauswahl, **keine Zulassungsliste**: ein unbekannter Gurt läuft ebenso, er
bekommt nur nicht automatisch den passenden Namen vorgeschlagen.

---

## 2. Der wichtigste Unterschied: PPI ist nicht RR

Ein Brustgurt misst die **elektrische Erregung** des Herzens und liefert
RR-Intervalle. Ein optischer Sensor misst die **Pulswelle** am Oberarm und
liefert PP-Intervalle. Das ist kein Namensunterschied:

- Die **Pulswellenlaufzeit** schwankt mit Blutdruck, Gefäßtonus und Atmung. PPI
  trägt damit ein zusätzliches Signal, das RR nicht hat — kein Messfehler,
  sondern andere Physiologie.
- **RMSSD** liegt am PPG in Ruhe systematisch höher als am EKG.
- **Bewegung** stört das optische Signal deutlich stärker. Der Oberarm ist
  besser als das Handgelenk, aber kein Ersatz für den Gurt.
- **RSA-Amplitude, Atemfrequenz, pNN50 und DFA α1** sind zwischen beiden
  Verfahren nicht vergleichbar.

Deshalb trägt **jede** gespeicherte Messung ihre Herkunft:

```jsonc
"geraet": "Polar Verity Sense",
"geraet_profil": "verity_sense",
"intervall_quelle": "ppg_ppi"      // oder "ekg_rr"
```

Bestandsmessungen ohne dieses Feld gelten als `ekg_rr` — sie stammen alle vom
H10, der Rückfall ist also belegt und nicht geraten.

**In der Oberfläche:** der Vergleich zeigt hinter Datum und Uhrzeit ein Kürzel
(`EKG` / `PPG`). Sind beide Modalitäten gleichzeitig ausgewählt, erscheint ein
Hinweisstreifen über dem Chart. Verboten ist die Mischung nicht — der direkte
Vergleich H10 gegen Verity am selben Menschen ist oft genau das Ziel —, aber sie
soll niemandem entgehen.

⚠ **Das Feld muss in jedem Schreibpfad stehen.** `raw-v1` entsteht an vier
unabhängigen Stellen (Messdatei, Crash-Backup, Generator-Datensatz,
Generator-Widget), die korrigierte Datei ist eine fünfte. `tests/test_geraete_
provenienz.py` prüft alle fünf.

---

## 3. Was das Profil steuert

| Angabe | Wirkung |
|---|---|
| `intervall_quelle` | landet in jeder Datei, steuert Kennzeichnung und Warnung |
| `ordner` | Ablageordner unter `<patient>/Messungen/` |
| `faehigkeiten` | ob der EKG-Bereich erscheint, welche PMD-Ströme angefordert werden |
| `ersttelegramm_s` | Wartefrist des Watchdogs bis zum ersten Paket |
| `hinweis_kein_signal` | „Gurt anfeuchten" wäre am Armband der falsche Rat |
| `kopplung_noetig` | Bluetooth-Bonding beim Verbinden (Verity Sense): `pair=True` + eigener BlueZ-Agent |
| `ausreisser_schwelle` | 0,20 ist auf EKG-RR kalibriert; PPI streut physiologisch stärker und bekommt 0,30. ⚠ **Bisher ohne Wirkung** — keine Codestelle liest das Feld |

Der Ablageordner ist **nicht** kosmetisch: `analysis_io.MEASUREMENT_FOLDERS`
leitet sich aus dem Katalog ab. Ein Profil ohne eigenen Ordner legte seine
Messungen zwischen die des H10 und wäre dort nicht mehr zu trennen; ein Ordner,
der nicht in der Liste steht, wäre in Vergleich, Verlauf und Workbench
unsichtbar. Beides ist durch einen Test abgedeckt.

**Profilerkennung:** beim Verbinden wird aus dem Bluetooth-Namen ein Profil
vorgeschlagen. Das ist eine Heuristik. Was das Gerät nach dem Verbinden über
seine PMD-Messtypen meldet, hat Vorrang — heißt ein Gerät „H10", meldet aber PPI
und PPG, gilt das Gerät. Und wer gar kein PMD anbietet, bekommt kein Profil, das
Rohdaten verspricht; sonst stünde der EKG-Bereich da und liefe ins Leere.

---

## 4. Polar Measurement Data (PMD)

Die Polar-Geräte bieten neben dem Standardprofil einen eigenen Dienst für
Rohdaten. `src/praxislab/sensors/devices/pmd.py` setzt ihn um — Qt-frei und ohne Hardware
prüfbar, weil die Tests synthetische Rahmen bauen.

| Typ | Strom | Beiwerk |
|---|---|---|
| `0x00` | EKG, 130 Hz, 14 bit | `_ecg.json` |
| `0x01` | PPG, 55 Hz, 22 bit, 4 Kanäle (3 optisch + Umgebungslicht) | `_ppg.json` |
| `0x03` | PPI: Intervall, Fehlerschätzung, Hautkontakt- und Blocker-Bit | fließt in `rr_ms` |

Der PPI-Strom ist die **Intervallquelle** des Verity Sense und läuft in dieselbe
Kette wie RR — die gesamte HRV-Rechnung bleibt unverändert. Intervalle mit
gesetztem Blocker-Bit erreichen sie gar nicht erst: die Fehlerschätzung des
Geräts ist bei optischer Messung verlässlicher als jede nachgelagerte
Ausreißerheuristik.

Was am Verity Sense im Einzelnen anders läuft — Kopplung, PPI-Start,
Lebenszeichen-Regel, Bündelung, fehlender PPG-Decoder — steht in
[`verity_sense/verity_sense.md`](verity_sense/verity_sense.md).

⚠ **Komprimierte Rahmen werden verworfen.** Ist im Frame-Typ-Byte Bit 7 gesetzt
(delta-komprimiert, so schickt der Verity Sense sein PPG), liefert
`parse_frame` `None`. Als Rohwerte gelesen ergäbe ein solcher Rahmen Zahlen, die
wie Messwerte aussehen.

⚠ **Steuerantworten:** Aufbau `[0xF0, Opcode, Messtyp, Fehler]` — auswerten über
`pmd.parse_control`, nie von Hand indizieren (das Fehlerbyte stand einmal an der
Stelle des Messtyps und war nur beim EKG zufällig 0).

### Stand der Verifikation

Der **EKG-Pfad ist am Polar H10 erprobt**. Die Auslagerung ins eigene Modul ist
durch einen Test abgesichert, der Startkommando und Rahmenzerlegung byteweise
gegen den bisherigen Stand hält.

Der **PPI-Pfad ist am Verity Sense geprüft** (19.09.2026): Rahmenlänge,
Frame-Typ, Startbestätigung und Byte-Layout stimmen, die Intervalle decken sich
mit dem H10 (→ [`verity_sense/messprotokoll.md`](verity_sense/messprotokoll.md)).

**PPG ist nur nach Spezifikation umgesetzt** — und am echten Gerät nicht
nutzbar, weil es delta-komprimiert kommt und der Decoder fehlt. Die Tests dazu
fangen Programmierfehler, keine Spezifikationsirrtümer.

---

## 5. Betriebssysteme

**Verbinden und Datenempfang** laufen über `bleak` und sind auf Linux, Windows
und macOS tragfähig. Was **nicht** über bleak läuft, ist das Auflisten und
Entkoppeln gekoppelter Geräte — dafür ruft das Programm Systemwerkzeuge:

| | Auflisten | Entkoppeln | Stand |
|---|---|---|---|
| Linux | `bluetoothctl devices` | `bluetoothctl remove` | erprobt |
| Windows | PowerShell `Get-PnpDevice` | `Remove-PnpDevice` | eingebaut, **ungetestet** |
| macOS | `system_profiler -json` | `blueutil` (`brew install blueutil`) | **ungetestet**, zwei bekannte Mängel |

**macOS — zwei Befunde, beide behandelt:**

1. **Behoben.** `connected = "connected" in category_key` traf auch auf
   `"device_not_connected"` zu — der Teilstring steckt darin. Dort galt damit
   jedes Gerät als verbunden. Geprüft wird jetzt auf `"not_connected"`.
2. **Umgangen.** CoreBluetooth kennt keine MAC-Adressen, sondern vergibt je Mac
   eine eigene UUID. `bleak` liefert diese UUID, `system_profiler` dagegen die
   Bluetooth-MAC — beide passen nicht zusammen. Deshalb gibt es im
   Kopplungsdialog den echten BLE-Scan: er liefert genau die Kennung, mit der
   `bleak` auch verbinden kann. Unter macOS ist er der Weg, nicht die
   Systemliste.

Beides ist **von der Entwicklungsmaschine aus nicht prüfbar** — die Änderungen
sind nach Aktenlage richtig, verifizieren muss sie jemand mit einem Mac.

**Linux — Verbindungsstrategie (BleakWorker):** Der zuverlässigste Einstieg ist
erfahrungsgemäß eine Verbindung, die BlueZ bereits hält (in GNOME verbinden,
dann in der App). Der Worker bildet genau das ab:

1. **Nur ein Verbindungsversuch gleichzeitig** (`_connect_guarded`): zwei
   parallele `_do_connect`-Läufe teilen sich `self._client` und zerlegen sich
   gegenseitig (`org.bluez.Error.InProgress`, `br-connection-canceled`,
   `services=None`). `connect_to()` ist der einzige erlaubte Einstieg —
   `_do_connect` nie direkt einplanen.
2. **Bestehende BlueZ-Verbindung übernehmen statt trennen:** ist das Gerät beim
   ersten Versuch schon verbunden, hängt sich bleak an (bleak überspringt
   `Connect` dann ausdrücklich). Aufgelöst wird ohne Scan über den
   deterministischen D-Bus-Pfad (`_bledevice_ohne_scan`) — ein verbundenes
   Gerät sendet keine Advertisements und ist für den Scanner unsichtbar.
3. **System-Connect als Fallback ab Versuch 2** (`_bluez_connect`): scheitert
   der direkte bleak-Connect (typisch: Sofort-Disconnect beim Aufbau), wird
   getrennt, über `bluetoothctl connect` verbunden — derselbe Weg wie
   GNOME-Bluetooth — und dann angehängt. Das automatisiert den früher nötigen
   manuellen Workaround.

---

## 6. Ein Gerät hinzufügen

1. Profil in `src/praxislab/sensors/devices/profiles.py` anlegen und in `PROFILE` eintragen.
2. Falls es einen eigenen Datenstrom mitbringt: Messtyp und Parser in `pmd.py`.
3. Fertig. Ablageordner, Messungslisten, Watchdog-Fristen und Hinweistexte
   folgen dem Profil; `analysis_io.MEASUREMENT_FOLDERS` leitet sich ab.

**Nicht** ins Widget schreiben. Jede Fallunterscheidung nach Gerätenamen dort
ist ein Fehler — dafür gibt es die Fähigkeiten.

---

## 7. Gerät koppeln

Der Kopplungsdialog (`src/praxislab/sensors/devices/pairing_dialog.py`) führt eine **eigene
Geräteliste**, unabhängig vom Bluetooth-Pairing des Betriebssystems.

```
Meine Geräte
  ● Polar H10       Polar H10 · 24:AC:AC:15:8D:1F · heute        [EKG] [Verbinden] ⋮
  ○ Verity Sense    Polar Verity Sense · A0:9E:… · vor 3 Tagen   [PPG] [Verbinden] ⋮

Länger nicht benutzt
  ○ Wahoo TICKR     Brustgurt (Standardprofil) · F1:22:… · vor 9 Monaten

Gefunden, nicht in meiner Liste
    Bose QC   BB:22:…                                            [Hinzufügen]
```

**Warum die Liste getrennt vom System-Pairing steht:** eine klemmende
BLE-Verbindung lässt sich oft nur lösen, indem man das Gerät im Betriebssystem
entkoppelt. Danach soll es hier weiterhin stehen — mit Name, Adresse und
Profil —, damit man es ohne Suchen wieder verbinden kann. Im Menü ⋮ sind das
deshalb zwei getrennte Einträge:

- **Aus dem System entkoppeln** — löscht das Bluetooth-Pairing, der Eintrag
  bleibt
- **Aus meiner Liste nehmen** — löscht nur den Eintrag, das Pairing bleibt

Ebenfalls im Menü: Profil ändern und Umbenennen. Wer länger als 60 Tage nicht
verbunden war, rutscht nach „Länger nicht benutzt", verschwindet aber nicht.

**Zwei Wege zur Geräteliste**, beide nötig:

| | findet | Dauer |
|---|---|---|
| ↺ Systemliste | im Betriebssystem gekoppelte Geräte | sofort |
| 🔍 In der Nähe suchen | alles, was gerade sendet — auch nie Gekoppeltes | ~6 s |

Unter macOS ist der BLE-Scan der einzig verlässliche Weg: CoreBluetooth vergibt
je Mac eigene UUIDs statt MAC-Adressen, die Systemliste ist dort nicht
anschlussfähig.

Gespeichert wird unter `[Plugins]/devices` in der **lokalen** settings.ini —
Geräte sind Hardware am jeweiligen Rechner. Der alte Einzelschlüssel
`polar_h10_address` wird beim ersten Start einmalig übernommen.

---

## 8. Mehrgerätebetrieb

Mehrere Geräte zeichnen gleichzeitig in dieselbe Sitzung: je Gerät eine
gewöhnliche `raw-v1` im eigenen Profilordner, geklammert durch eine kleine
`sitzung-v1`, alle mit demselben `t_wall_s`-Nullpunkt. Im Kopplungsdialog nimmt
„＋ Zusätzlich" ein Gerät dazu, ohne das Hauptgerät zu ersetzen. Kein
Autoconnect, kein Hinzunehmen während einer Aufnahme.

→ [`mehrgeraetebetrieb.md`](mehrgeraetebetrieb.md)

---

## 9. Übertragung prüfen

Jedes neue Gerät durchläuft dieselbe Prüfung in vier Ebenen (Datenblöcke,
Zeitstempel, Kette, Goldstandard gegen den H10): Rohmitschnitt mit
`PRAXIS_BLE_ROHLOG=1`, Auswertung mit `tools/ble_pruefbericht.py`.

→ [`ble_uebertragung_pruefen.md`](ble_uebertragung_pruefen.md)

---

## 10. Was noch offen ist

- **Wellenform-Korrektur** für EKG und PPG. Für Intervalle arbeitet die
  vorhandene Korrektur bei PPI unverändert — es ist dieselbe Datenform.
- **Polar H9 und „Brustgurt (Standardprofil)"** sind nach Profil umgesetzt und
  an keinem Gerät erprobt. Vor dem ersten Einsatz:
  [`ble_uebertragung_pruefen.md`](ble_uebertragung_pruefen.md).
- **`ausreisser_schwelle`** des Profils liest keine Codestelle.
- Offene Punkte je Thema: Verity Sense →
  [`verity_sense/verity_sense.md`](verity_sense/verity_sense.md) (Abschnitt 7) ·
  Mehrgerätebetrieb → [`mehrgeraetebetrieb.md`](mehrgeraetebetrieb.md).
