# Runbook: Was spricht die Decathlon-Coach-App mit dem HRM Belt?

**Frage:** Benutzt die App den herstellereigenen Dienst `8ce5cc01-…` (Charakteristiken
`8ce5cc02`/`8ce5cc03`, Write + Notify), und wenn ja, womit — und kommt darüber mehr zurück als
über das Standardprofil? Nur dann gäbe es überhaupt einen Weg zu einem Rohsignal.

**Methode:** Das Telefon schneidet seinen eigenen Bluetooth-Verkehr mit (Android, HCI-Snoop-
Protokoll). Wir lesen nur mit, schreiben nichts auf den Gurt und dekompilieren nichts.
Rechtlich: Beobachten und Testen eines Programms durch den rechtmäßigen Nutzer (§ 69d Abs. 3
UrhG), eigene Geräte, eigene Daten.

**Erwartung vorab:** Mit 70–80 % zeigt der Mitschnitt nur das Standardprofil (0x2A37, Batterie,
Geräteinformation). Dann ist die Frage endgültig beantwortet, Aufwand etwa zwei Stunden.

**Zeitplan:** Vorbereitung 30 min · Mitschnitt 15 min · Auswertung 30–60 min.

---

## 0. Voraussetzungen (Stand 19.10.2026 abends, Rechner ben_T480)

| Was | Stand | Erledigen |
|---|---|---|
| Android-Telefon mit Decathlon Coach, Konto angelegt, Gurt dort schon einmal gekoppelt | ? | Ben |
| USB-Kabel, am Telefon USB-Debugging | ? | Ben |
| `adb` auf dem Rechner | **fehlt** | `sudo dnf install android-tools` |
| Wireshark + tshark | **fehlt** | `sudo dnf install wireshark wireshark-cli`, dann `sudo usermod -aG wireshark ben`, neu anmelden |
| Handle-Tabelle des Gurts | noch nicht erhoben | Schritt 1.3 |
| Gurt nicht mit dem Laptop verbunden | prüfen | Schritt 1.4 |

Falls kein Android, sondern iPhone: Apple-Weg nur über ein Konfigurationsprofil
„Bluetooth Logging“ und einen Mac mit PacketLogger. Dann stattdessen Abschnitt 5 (nRF Sniffer).

## 1. Vorbereitung

1.1 Pakete installieren (siehe Tabelle), Rechner-Gruppe `wireshark` wirkt erst nach Neuanmeldung.

1.2 Telefon: *Einstellungen → Über das Telefon → siebenmal auf Build-Nummer* schaltet die
Entwickleroptionen frei. Darin:
- **USB-Debugging** an.
- **Bluetooth-HCI-Snoop-Protokoll** auf „Aktiviert“ (bei manchen Herstellern „Aktiviert, gefiltert“
  vermeiden — es kürzt Nutzdaten).
- Danach **Bluetooth aus- und wieder einschalten** (sonst beginnt die Datei nicht).

1.3 Handle-Tabelle des Gurts erheben — im HCI-Mitschnitt stehen nur ATT-Handles, keine UUIDs.
Gurt anlegen (ohne Hautkontakt sendet er nicht), am Laptop:

```bash
cd ~/workspace_git/hrv-core
uv run --with bleak python scripts/ble_erkundung.py E2:B4:CC:3F:08:44 --dauer 10
```

Die Ausgabe zeigt je Charakteristik `UUID  0xHANDLE  Eigenschaften`. Die Zeilen für `2a37`,
`8ce5cc02` und `8ce5cc03` notieren (oder das Befund-JSON unter `ausgaben/ble_erkundung/`
aufheben). Falls „Device … was not found“: Gurt ist nicht angelegt, oder er hängt noch an einem
anderen Gerät.

1.4 Gurt vom Laptop lösen, sonst bekommt das Telefon ihn nicht:

```bash
bluetoothctl disconnect E2:B4:CC:3F:08:44
bluetoothctl power off        # für die Dauer des Mitschnitts am einfachsten
```

1.5 Kabel anschließen, am Telefon „USB-Debugging zulassen“ bestätigen, dann:

```bash
adb devices        # muss das Telefon mit "device" zeigen, nicht "unauthorized"
```

## 2. Mitschnitt (etwa 15 Minuten)

Alles, was die App mit dem Gurt sprechen könnte, soll im Protokoll landen. Dafür die App
**frisch starten** (vorher aus dem Task-Switcher wischen), damit sie die Dienste neu abfragt.

| Schritt | Tun | Uhrzeit notieren |
|---|---|---|
| 2.1 | Gurt anlegen, befeuchten | |
| 2.2 | Decathlon Coach starten, Sensor-/Geräte-Einstellungen öffnen, Gurt verbinden | |
| 2.3 | Alle Menüs rund um den Gurt öffnen: Gerätedetails, Batterie, Einstellungen, falls vorhanden „Firmware“/„Aktualisieren“ | |
| 2.4 | Aktivität starten (z. B. „Laufen“ oder „Indoor“), **3 Minuten** ruhig sitzen, danach 1 Minute Arme bewegen | |
| 2.5 | Aktivität beenden und speichern; falls die App eine Herzfrequenz-Analyse oder „HRV“/„Erholung“ anbietet, öffnen | |
| 2.6 | Gurt in der App trennen, App schließen | |

Die Uhrzeiten helfen beim Zuordnen; der Mitschnitt hat eigene Zeitstempel.

## 3. Protokoll vom Telefon holen

Seit Android 9 liegt die Datei nur im Bugreport:

```bash
mkdir -p ~/workspace_git/hrv-research/ausgaben/decathlon_app && cd $_
adb bugreport bugreport.zip                 # dauert 1–3 Minuten
unzip -o bugreport.zip 'FS/data/misc/bluetooth/logs/*' 2>/dev/null || unzip -l bugreport.zip | grep -i snoop
ls -la FS/data/misc/bluetooth/logs/
```

Erwartet: `btsnoop_hci.log` (und ggf. `btsnoop_hci.log.last`). Fehlt sie, war das HCI-Protokoll
nicht aktiv oder Bluetooth wurde nicht neu gestartet → zurück zu 1.2. Bei Samsung heißt der
Pfad gelegentlich anders; `unzip -l bugreport.zip | grep -i snoop` findet ihn.

Der Ordner liegt in hrv-research unter `ausgaben/` (gitignoriert). Der Bugreport enthält weit
mehr als Bluetooth (Apps, Konten, Logs) — **nicht committen, nicht in hrv-core kopieren**; am
Ende nur die aufbereiteten Protokollfakten übernehmen.

## 4. Auswertung

4.1 Überblick: Welche ATT-Operationen gab es, auf welchen Handles?

```bash
tshark -r btsnoop_hci.log -Y "btatt" -T fields -e frame.time_relative -e btatt.opcode -e btatt.handle -e btatt.value \
  | awk '{print $2, $3}' | sort | uniq -c | sort -rn | head -40
```

Opcodes zum Lesen der Liste: `0x12` Write Request, `0x52` Write Command, `0x1b` Notification,
`0x1d` Indication, `0x0a` Read Request, `0x0b` Read Response, `0x10`/`0x11` Dienstsuche.

4.2 Handles den UUIDs zuordnen: entweder aus der Tabelle von Schritt 1.3 oder aus dem
Mitschnitt selbst, wenn die App die Dienste neu abgefragt hat:

```bash
tshark -r btsnoop_hci.log -Y "btatt.opcode == 0x11 || btatt.opcode == 0x09 || btatt.opcode == 0x05" -V \
  | grep -E "Handle|UUID" | head -80
```

4.3 **Die entscheidende Frage** — schreibt die App auf die herstellereigenen Charakteristiken?
`HANDLE_02` und `HANDLE_03` aus 1.3 einsetzen (plus 1 für den jeweiligen CCCD, falls die App
Notifications dort abonniert):

```bash
tshark -r btsnoop_hci.log -Y "btatt.handle == HANDLE_02 || btatt.handle == HANDLE_03" \
  -T fields -e frame.time_relative -e btatt.opcode -e btatt.value
```

| Ergebnis | Bedeutung | Nächster Schritt |
|---|---|---|
| **keine Zeile** | Die App benutzt den Kanal nicht. Standardprofil ist alles. | Befund ins README, Thema abgeschlossen |
| nur CCCD-Write (Wert `0100`) und einzelne Notifications nach dem Verbinden | Statusmeldung oder Versionsabfrage, kein Strom | Inhalt notieren, Thema praktisch abgeschlossen |
| Writes mit Nutzdaten, danach Notifications in dichtem Takt (mehrere je Sekunde) | **Ein Datenstrom** — der einzige interessante Fall | Abschnitt 4.5 |

4.4 Zum Vergleich der Standardstrom, um zu sehen, ob die App dieselben 4-Byte-Pakete bekommt
wie wir (`16 bpm rr_lo rr_hi`):

```bash
tshark -r btsnoop_hci.log -Y "btatt.opcode == 0x1b && btatt.handle == HANDLE_2A37" \
  -T fields -e frame.time_relative -e btatt.value | head -20
```

4.5 Nur wenn ein Strom gefunden wurde: Bytes der Start-Writes und die ersten 50 Notifications
in eine Datei ziehen, Paketlänge und Takt bestimmen (Abtastrate = Werte je Sekunde), Byte-
Layout wie beim Beurer PO60 (Prüfsummen, Zähler, Vorzeichen) zerlegen. Danach die Start-Writes
mit bleak vom Laptop wiederholen und prüfen, ob der Gurt gegenüber uns genauso antwortet. Das
ist ein eigener Tag; vorher entscheiden, ob sich das lohnt — ein Strom mit weniger als 100 Hz
oder in „Herzfrequenz-Zahlen“ statt Abtastwerten wäre kein EKG.

## 5. Ausweichweg ohne Telefon-Logs: nRF Sniffer

Falls das HCI-Protokoll nicht zu bekommen ist (iPhone, gesperrte Entwickleroptionen):
nRF52840-Dongle (etwa 10–15 €), Nordic „nRF Sniffer for Bluetooth LE“ als Wireshark-Plugin.
Der Dongle hört die Verbindung aus der Luft mit; der Gurt pairt nicht, also ist nichts
verschlüsselt. Einrichtung ein halber Tag, Auswertung dann wie in Abschnitt 4.

## 6. Ergebnis festhalten

In `README.md` dieses Ordners, Abschnitt „Was noch ginge“, durch den Befund ersetzen: Datum,
App-Version (Decathlon Coach → Einstellungen → Über), Android-Version, was auf `8ce5cc02/03`
passierte (nichts / Status / Strom), mit den Hex-Bytes der relevanten Pakete. Dazu die
Handle-Tabelle aus 1.3. Der Bugreport selbst bleibt unter `ausgaben/`.

## Ergebnisse (ausfüllen)

- Datum, App-Version, Android-Version:
- Handles: `2a37` = · `8ce5cc02` = · `8ce5cc03` = ·
- Operationen auf 8ce5cc02/03 (Zahl, Art):
- Befund in einem Satz:
