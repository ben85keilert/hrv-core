# Beurer PO60 — Erkundung

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Stand: 2026-08-14 · Status: **Exkurs abgeschlossen — kein BLE-Live-Modus,
keine Integration in die Praxis-GUI; Protokollkern am Gerät bestätigt** ·
Fazit & vollständiger Code als Referenz: [`beurer_po60_exkurs.md`](beurer_po60_exkurs.md) ·
Fahrtenbuch der Weiterarbeit: [`beurer_po60_uebergabe.md`](beurer_po60_uebergabe.md)

Der Beurer PO60 ist ein Fingerpulsoximeter mit Bluetooth Low Energy. Dieses
Dokument sammelt, was über sein Protokoll bekannt ist, wie das
Erkundungswerkzeug bedient wird und welche Fragen noch offen sind. Es ist
die Design-Grundlage für eine spätere Integration — **erst kennenlernen,
dann entscheiden**, wie das Gerät zur HRV-Messung dazukommt (Synchronität,
Ablageform usw.).

## 1. Was bekannt ist

Am echten Gerät bestätigt (PO60, FW V7.3, HW 2.00 — Lauf 2, 14.08.2026);
Ausgangspunkt war das öffentliche Reverse Engineering
<https://github.com/Shreyan1/Beurer-PO60-PulseOximeter-Bluetooth-Integration>,
dessen Fragment-Deutung sich als unvollständig erwies (siehe Datensatzlayout).
Umgesetzt in `sensors/devices/po60.py` (Qt- und bleak-frei, Muster `pmd.py`);
die echten Gerätepakete sind als Golden Vectors in `tests/test_po60.py`
eingefroren.

**Die wichtigste Einordnung vorweg:** Der PO60 liefert **keine
Schlag-zu-Schlag-Intervalle** — nur gespeicherte Messungen mit
Minimum/Maximum/Mittelwert von SpO₂ und Puls. Als `intervall_quelle` für die
HRV-Kette kommt er nicht infrage; denkbar ist er als Zusatzinformation
(SpO₂/Puls) neben einer HRV-Messung oder als eigener Messungstyp.

| Wissen | Status |
| --- | --- |
| Datenkanal: Dienst `0xFF12` mit Write `0xFF01`, Notify `0xFF02`; zweiter Vendor-Dienst `0xFF00` mit `0xFF03` (read/write, Funktion unbekannt); alle drei Characteristics lesbar | bestätigt |
| Kein Standard-HR-Service, **kein** Standard-PLX-Dienst (0x1822) | bestätigt |
| Bonding: auf **Linux/BlueZ nicht nötig** (Läufe 2–4, Notify unpaarig); auf **Windows/WinRT nötig** — dort weist der Vitalkanal Notify/Read sonst mit „Insufficient Authentication" ab (Lauf 5) | bestätigt |
| Abruf: `90 05 15` → Antwort `e0 05 <n u16 LE> <n u16 LE> <PS>` (n = Anzahl Datensätze; warum doppelt, ist offen) → `99 00 19` → Datensatzstrom | bestätigt |
| Prüfsumme überall: letztes Byte = `sum(vorherige Bytes) & 0x7F` — gilt für Kommandos, Handshake-Antwort und jeden Datensatz | bestätigt |
| Datensätze: **24 Byte** im **fortlaufenden Bytestrom** (20-Byte-Notifications, Grenzen liegen mitten im Paket!): `[0]`=0xE9 · `[1]`=Nr. (untere 4 Bit) + Bit 6 „letzter" · `[2–7]`=Messbeginn (J−2000,M,T,h,m,s) · `[8–13]`=Messende · `[14–16]`=Abtastanzahl als Basis-128-Zahl (7-Bit-Bytes; = Dauer in s + 1 bei allen 10 Referenzdatensätzen) · `[17–19]`=SpO₂ max/min/Ø · `[20–22]`=Puls max/min/Ø · `[23]`=Prüfsumme | bestätigt |
| Jahres-Byte = Jahr − 2000 (Werksuhr-Messungen: 2019-01-01) | bestätigt |
| Selbsttrennung: ~6 s nach Ende des Speicherabrufs; eine **untätige** Verbindung trennt das Gerät nach ~35 s (deshalb sendet die Lauschphase alle 15 s einen Handshake als Keep-Alive — hält die Verbindung nachweislich über 5 min) | bestätigt |
| FF01/FF02/FF03 per Read: liefern im Ruhezustand nur Null-Puffer (20/20/21 Bytes) | beobachtet |
| **Kein Live-Modus**: 5 min Verbindung mit Finger im Gerät → außer Handshake-Antworten keine einzige Notification. Der PO60 überträgt nur gespeicherte Messungen | bestätigt (Lauf 4) |
| **Abruf löscht nicht**: Datensätze kommen bei Wiederholung byteidentisch; „letzter"-Flag (Bit 6) wandert zum jeweils neuesten Datensatz | bestätigt (Lauf 2 vs. 4) |
| Eine Messung wird beim **Finger-Herausnehmen** gespeichert (Anzahl blieb bei eingelegtem Finger konstant und sprang danach hoch) | beobachtet |
| **Blockabruf**: je Anforderung höchstens 10 Datensätze (15 gemeldet, nur 0–9 geliefert). Hypothese: zweites Kommandobyte = Start-Index (`99 0a 23` → ab Datensatz 10) | offen (Lauf 5) |

## 2. Das Erkundungswerkzeug

`tools/po60_erkundung.py` — Kommandozeile, kein Qt, nutzt `bleak`.
Windows: `.venv/Scripts/python.exe`, Linux: `python3` bzw. `.venv/bin/python`:

```bash
# Standardablauf mit bekannter Adresse (empfohlen):
# Suchen → GATT-Dump → 5 min Lauschen → Speicherabruf
# (Speicherabruf zuletzt, weil das Gerät danach selbst trennt)
python3 tools/po60_erkundung.py alles --adresse F0:...

# Ohne Adresse: Suche über den Gerätenamen (PO60/Beurer)
python3 tools/po60_erkundung.py alles

# Einzelphasen (zum gezielten Wiederholen beim Debuggen)
python3 tools/po60_erkundung.py scan
python3 tools/po60_erkundung.py dienste  --adresse F0:...
python3 tools/po60_erkundung.py speicher --adresse F0:...
python3 tools/po60_erkundung.py lauschen --adresse F0:... --minuten 5
```

Bedienung am Gerät (bewährter Ablauf aus Lauf 4):

1. **Eine Messung machen**, bis ein Wert angezeigt wird, dann den **Finger
   herausnehmen** — daraufhin startet der Sync-Modus (Bluetooth-Symbol).
   Das Sync-Fenster kann deutlich länger offen bleiben als das kurze
   Advertising nach bloßem Tastendruck.
2. Die Suche läuft **live und in Runden**: jedes gesehene Gerät erscheint
   sofort, beim ersten PO60-Treffer greift das Werkzeug unmittelbar zu.
   Läuft eine Runde leer, folgt die nächste; Abbruch mit Strg+C. Direkt
   nach Sync-Start kann die Verbindung ein paarmal kurz abreißen — die
   Wiederverbindungs-Schleife fängt das ab.
3. Während der Lauschphase darf der Finger wieder ins Gerät; eine dabei
   laufende Messung wird erst beim Herausnehmen des Fingers gespeichert.

**Alles** (gesendete Kommandos, jede Notification roh als Hex, GATT-Tabelle,
Verbindungsereignisse) landet in `Logs/po60/po60_<Zeitstempel>.jsonl`
(git-ignoriert, eine JSON-Zeile pro Ereignis, sofort geflusht). Diese Datei
nach dem Test **aufheben** — sie ist der eigentliche Erkundungsertrag.

Kopplung: nicht nötig (bestätigt) — `--koppeln` bleibt als Reserve für den
Fall, dass sich das mit anderer Firmware anders verhält.

`--sondieren` (Vorgabe: aus) schickt zusätzlich eine kleine Liste
spekulativer Kandidatenkommandos (`SONDIER_KOMMANDOS` im Werkzeug) — nur
formal nach der Prüfsummenregel gebaute Opcodes nahe den bekannten,
nichts erkennbar Schreibendes.

## 3. Offene Fragen (Checkliste für die nächsten Läufe)

- [x] **Pull / Einzelwert-Abfrage** (Subkommando `pollen`, Lauf 5):
      **weitgehend widerlegt.** `90 00`…`90 0f` antworten nicht (kein Pull
      über die 0x90-Familie); FF03/FF02/FF01 zeigten kein schwankendes
      Vitalbyte. Vermutliche Ursache: Im Sync-Modus **misst das Gerät nicht**
      (Mess-LED aus). Rest siehe nächster Punkt.
- [x] **Messung UND Sync gleichzeitig? — NEIN, endgültig belegt (Lauf 6).**
      Beide Richtungen getestet: (a) Sync steht → Finger einlegen: LED bleibt
      aus, kein Momentanwert, alle Report-Typen null. (b) Messung läuft
      (LED an) → Verbindung erzwingen (`bluetoothctl connect`): schlägt fehl,
      das Gerät advertised während einer Messung nicht. **Der PO60 hält
      Messung und BLE-Verbindung wechselseitig aus — der Live-Weg ist zu.**
- [x] **Blockabruf — Hypothese widerlegt (Lauf 6).** `99 0a 23` bekam keine
      Antwort; das Gerät liefert je Abruf nur die ältesten 10 Datensätze
      (0–9), der Fallback `99 00 19` wiederholt exakt dieselben. Das zweite
      Kommandobyte ist **kein** Start-Index. Wie die App an Datensätze > 9
      kommt, bleibt offen (Hypothese: Quittungs-/Löschkommando nach Block).
- [ ] Funktion von FF03 (Dienst 0xFF00, read/write) — Read liefert im
      Ruhezustand nur Nullen; vielleicht füllt sie sich während einer
      Übertragung oder Messung.
- [ ] Handshake-Antwort: warum steht die Datensatzanzahl doppelt darin
      (Bytes 2–3 und 4–5)?
- [ ] Datensatz-Index bei > 63 gespeicherten Messungen (Bits 0–5 =
      max. 63, Gerät speichert laut Anleitung bis 100) — läuft er über?
- [ ] Wie stellt man die Geräteuhr per BLE? (Die Beurer-App kann es; ohne
      gestellte Uhr tragen Messungen 2019-01-01.)
- [ ] Wie lange bleibt das Sync-Fenster nach „Messung → Finger raus"
      offen, und wodurch endet es?

Erledigt: PLX nein · Standard-HR nein · Bonding nein · Datensatzlayout
inkl. Puls und Prüfsumme · Jahres-Kodierung · Device-Information ·
**Push-Live-Modus: existiert nicht** (Lauf 4) · **Pull-Live-Modus: existiert
nicht** (Lauf 6) · **Messung und BLE schließen sich aus** (Lauf 6) ·
**Abruf löscht nicht** (Lauf 4) · **Blockabruf-Start-Index: gibt es nicht**
(Lauf 6) · „letzter"-Flag = Bit 6, wandert (Lauf 2 vs. 4) · Idle-Timeout
~35 s, Keep-Alive wirkt (Lauf 4).

## 4. Befunde am Gerät

*(Nach jedem Testlauf ergänzen: Datum, Firmware, Antworten auf die
Checkliste, auffällige Rohpakete aus der JSONL mit Interpretation. Auf
dieser Grundlage wird dann die eigentliche Integration entworfen:
Geräteprofil ja/nein, Ablageform, Bezug zur HRV-Messung/Sitzung.)*

### Lauf 1 — 13.08.2026, Linux (ThinkPad T480)

Erster Versuch mit `alles` (damals: 15-s-Blockscan). **Kein PO60 gesehen** —
34 Fremdgeräte im Umfeld, keines mit PO60-/Beurer-Namen; Abbruch vor dem
Verbinden. Wahrscheinliche Ursache: Der Blockscan zeigte seine Liste erst
nach Ablauf, der Tastendruck traf das kurze Advertising-Fenster nicht.
Konsequenz: Werkzeug auf Live-Scan mit Sofortzugriff und Runden-Schleife
umgebaut; die Geräteadresse ist inzwischen bekannt und wird künftig direkt
per `--adresse` genutzt.

### Lauf 2 — 14.08.2026 07:00, Linux (ThinkPad T480) — Durchbruch

`alles --adresse C9:49:AC:1E:4B:00`. Gerät nach ~25 s Scan gefunden
(Name „PO60", RSSI −53), sofort verbunden, **ohne Kopplung** voll nutzbar.

**Device Information (0x180A):** FW „V7.3", HW „2.00", SW „4.00",
Modell „BLE 1.0", Seriennr. „1.0.0", Hersteller „Manufacturer Name"
(Platzhalter), PnP-ID `023a09050a0200`. Beworbene Dienste: 0x1800, 0x1801,
0x180A, 0xFF00, 0xFF12; Herstellerdaten-ID 1553 → `01`.

**Speicherabruf:** Handshake-Antwort `e0 05 0a 00 0a 00 79` (10 Datensätze,
Prüfsumme ok), danach 240 Bytes in zwölf 20-Byte-Notifications = exakt
10 Datensätze à 24 Byte, alle Prüfsummen gültig, null Restbytes. Damit war
das ursprünglich angenommene „Kopfpaket + Fortsetzungspaket"-Modell
widerlegt und das 24-Byte-Stromlayout aus §1 etabliert (der Parser wurde
entsprechend auf einen Strom-Resynchronisierer umgestellt). Die Bytes 14–16
entpuppten sich als Basis-128-Abtastanzahl (= Dauer + 1 s, 1 Hz).

Dekodierter Speicherinhalt (Beleg; Werte SpO₂/Puls jeweils min–max, Ø):

| # | Beginn | Ende | Dauer | SpO₂ | Puls |
|---|---|---|---|---|---|
| 0 | 2019-01-01 00:00:14 | 00:01:02 | 48 s | 97–97, Ø 97 | 68–74, Ø 72 |
| 1 | 2019-01-01 01:15:36 | 01:19:00 | 204 s | 95–98, Ø 95 | 69–83, Ø 73 |
| 2 | 2026-08-13 22:00:25 | 22:02:25 | 120 s | 95–98, Ø 96 | 70–73, Ø 71 |
| 3 | 2026-08-13 22:05:00 | 22:05:16 | 16 s | 96–96, Ø 96 | 70–74, Ø 70 |
| 4 | 2026-08-13 22:07:23 | 22:09:40 | 137 s | 96–96, Ø 96 | 69–74, Ø 71 |
| 5 | 2026-08-13 22:10:10 | 22:12:18 | 128 s | 95–98, Ø 96 | 68–74, Ø 70 |
| 6 | 2026-08-13 22:25:02 | 22:25:33 | 31 s | 97–99, Ø 97 | 74–80, Ø 75 |
| 7 | 2026-08-14 06:57:36 | 06:58:13 | 37 s | 98–99, Ø 98 | 54–55, Ø 54 |
| 8 | 2026-08-14 06:59:21 | 06:59:23 | 2 s | 98–98, Ø 98 | 50–50, Ø 50 |
| 9 | 2026-08-14 06:59:54 | 07:00:00 | 6 s | 98–98, Ø 98 | 57–57, Ø 57 |

(Datensätze 0–1 stammen aus der Zeit vor dem Stellen der Geräteuhr.)

**Selbsttrennung:** ~6 s nach dem letzten Datensatz trennte das Gerät die
Verbindung; die anschließende Lauschphase lief deshalb ins Leere
(`start_notify` → „Unlikely Error"). Konsequenz: Phasenreihenfolge in
`alles` geändert (Lauschen vor Speicherabruf), FF01–FF03 werden beim
GATT-Dump zusätzlich per Read ausgelesen.

### Lauf 3 — 14.08.2026 07:15, Linux (ThinkPad T480)

`alles` mit neuer Phasenreihenfolge (Dienste → Lauschen → Speicher).
Verbindung nach ~23 s Scan, GATT-Dump inkl. der neuen Vendor-Reads:
**FF01, FF02 und FF03 liefern im Ruhezustand nur Null-Puffer** (20, 20
bzw. 21 Bytes) — vermutlich leere Übertragungspuffer.

**Kernbefund: Idle-Timeout.** Die Lauschphase (nur Abonnieren, keine
Schreibzugriffe) endete nach **33 s** durch Selbsttrennung des Geräts —
ohne eine einzige Notification. Der Speicherabruf kam dadurch nicht mehr
zum Zug. Der PO60 hält eine Verbindung also nur bei Protokollaktivität;
eine passive Lauschphase über Minuten ist unmöglich.

Konsequenz (ab Lauf 4): Die Lauschphase sendet alle 15 s den Handshake
als **Keep-Alive** (harmlos, bestätigt; Antwort meldet nebenbei die
Datensatzanzahl — steigt sie, wurde während der Verbindung eine Messung
gespeichert). Zusätzlich verbindet `alles` nach einer Selbsttrennung
automatisch neu (mit Taste-drücken-Ansage) und wiederholt die
unterbrochene Phase einmal, statt die Restphasen ausfallen zu lassen.

### Lauf 4 — 14.08.2026 07:26–07:33, Linux (ThinkPad T480)

Bedienablauf des Nutzers: Messung machen → Finger raus → Sync-Modus
startet → Finger wieder rein; das Sync-Fenster blieb diesmal lange offen.
Direkt nach Sync-Start rissen drei Verbindungsversuche binnen Sekunden ab
— die Wiederverbindungs-Schleife fing das ab, danach stand die Verbindung.

**Keep-Alive bestätigt:** Die Lauschphase hielt die vollen 5 Minuten
(19 Handshake-Antworten im 15-s-Takt, `lauschen_durchgehalten: true`).

**Kein Live-Modus:** Trotz eingelegtem Finger über die gesamte Lauschphase
kam außer den Handshake-Antworten keine einzige Notification — auf FF02
wie auf 0x2A05. Die gemeldete Datensatzanzahl blieb dabei konstant 14 und
sprang erst nach der Lauschphase auf 15: **Messungen werden beim
Finger-Herausnehmen gespeichert**, nicht laufend.

**Abruf löscht nicht + Flag-Semantik bestätigt:** Der Speicherabruf
lieferte die Datensätze 0–9 byteidentisch zu Lauf 2 — einzige Abweichung:
Datensatz 9 trug sein Bit-6-Flag nicht mehr (Byte 1: 0x49 → 0x09,
Prüfsumme 0x68 → 0x28), weil er nicht mehr der letzte im Speicher ist.

**Blockgrenze entdeckt:** Handshake meldete 15 Datensätze, geliefert
wurden nur 0–9, danach Stille und Selbsttrennung
(`befund_speicher: {datensaetze: 10, gemeldet: 15}`). Je Anforderung
kommt offenbar höchstens ein Block von 10 Datensätzen. Konsequenz
(Runde 5): `phase_speicher` fordert automatisch blockweise nach
(`99 <start_index>`-Hypothese, Fallback erneuter Abruf ab 0 mit
Deduplizierung), bis die gemeldete Anzahl erreicht ist oder ein Datensatz
das „letzter"-Flag trägt.

### Lauf 5 — 14.08.2026 13:28–13:35, Windows 11 (`pollen`-Subkommando)

Erster Lauf des Pull-Experiments (`pollen --adresse C9:49:AC:1E:4B:00`),
mehrere Anläufe. Logs: `Logs/po60/po60_20260814_132837.jsonl` (ohne Bond)
und `…_133258.jsonl` (nach Bond). Vier klare Befunde:

**a) Windows/WinRT verlangt einen Bond — anders als Linux.** Der erste
Anlauf verband zwar (RSSI −61/−66), aber `start_notify` **und** jeder `read`
prallten ab: `Could not start notify on 000D: Access Denied` bzw.
`GATT Protocol Error: (5) Insufficient Authentication` (7× beim Read).
Ergebnis: `Abonniert: nichts (!)`. **Das widerlegt für Windows das bisherige
„Kopplung nicht nötig"** — dieser Satz galt für die Läufe 1–4 auf Linux/BlueZ.
Auf Windows braucht der verschlüsselte Vitalkanal ein OS-seitiges Bonding
(bzw. `--koppeln`). Nach dem Pairing lief Notify auf FF02 durch.

**b) Handshake nach Bond sauber, aber kein Live-Wert.** FF02 abonniert,
`HandshakeAntwort anzahl_datensaetze=34, pruefsumme_ok=True` kam mehrfach an
(Rohframe `e0 05 22 00 22 00 29`, `0x22 = 34`). Sonst enthielten alle
Notifications nur Leerlauf (`00 00 00 00 00 00 00`); **kein einziges Byte
schwankte** in SpO₂-/Puls-Grenzen. FF03/FF02/FF01-Reads: nur Nullen. Eine
Characteristic `000D` blieb selbst nach Bond gesperrt („Access Denied") —
für den Speicherabruf aber irrelevant.

**c) Kein Pull über die 0x90-Familie.** Die Entdeckungsrunde sendete
`90 00`…`90 0f` je einmal — **keine einzige Antwort**. Ein Pull des
Momentanwerts über einen anderen 0x90-Report-Typ existiert damit nicht.

**d) Wahrscheinliche Ursache (Nutzerbeobachtung): Im Sync-Modus ist die
Mess-LED des Sensors AUS — das Gerät misst währenddessen gar nicht.** Damit
gibt es im BLE-/Sync-Zustand schlicht keinen Momentanwert, den man abfragen
könnte: Der PO60 misst und synchronisiert offenbar **nicht gleichzeitig**.
Das erklärt zwanglos, warum sowohl Push (Lauf 4) als auch Pull (dieser Lauf)
leer ausgingen. **Einziger noch offener Test:** eine Messung erzwingen,
*während* die Sync-Verbindung steht (Finger einlegen bei blinkendem
BT-Symbol/laufendem Sync) — und prüfen, ob die LED angeht und dann doch ein
Wert durchkommt. Kann das Gerät beides nicht parallel, ist der Live-Weg
endgültig zu.

### Lauf 6 — 14.08.2026 ~14:37–14:46, Linux (ThinkPad T480) — Live-Weg endgültig zu

Der in Lauf 5 offen gebliebene Test durchgeführt, in zwei Phasen; Logs:
`po60_20260814_143725.jsonl` (Speicher) und `po60_20260814_144…jsonl`
(Pollen). Dazu der von Lauf 5 offene Blockabruf.

**a) Blockabruf-Hypothese widerlegt.** Das Gerät meldet inzwischen 36 bzw.
38 Datensätze (`e0 05 24 …` = 0x24, später `0x26`), liefert je Abruf aber
weiterhin nur die ältesten **10** (0–9, byteidentisch zu Lauf 2/4). Auf die
Fortsetzung `99 0a 23` kam **keine Antwort** (3-s-Fenster leer); der Fallback
`99 00 19` in derselben Verbindung wiederholte exakt 0–9. Das zweite
Kommandobyte ist damit **kein Start-Index**. Folge: Datensatz 14 (der
retrospektive Beleg, ob Lauf 4 während stehender Verbindung gemessen hat)
blieb unerreichbar. Wie die Beurer-App an > 9 Datensätze kommt, bleibt offen
— plausibelste Hypothese jetzt: ein Quittungs-/Löschkommando pro Block
(nicht auf Verdacht ausprobiert).

**b) 0x90-Report-Typen antworten auf Linux — anders als Windows (Lauf 5).**
Der Pull-Sweep bei stehender Verbindung: `90 00`–`90 04` **antworten** je mit
einem 7-Byte-Nullrahmen (`00 00 00 00 00 00 00`, Prüfsumme formal stimmig),
`90 05` ist der Handshake (0x26 = 38 Datensätze), `90 06`–`90 0f` schweigen.
Unter Windows/WinRT (Lauf 5, mit Bond) hatte **kein** 0x90-Kommando
geantwortet — Linux/BlueZ verhält sich hier durchlässiger. Es sind aber reine
Lese-/Report-Typen: kein Steuerbefehl, keiner startet eine Messung.

**c) Pull leer — Gerät misst bei stehender Verbindung nicht.** Finger die
gesamte Pollphase im Gerät, **Mess-LED blieb aus** (Nutzerbeobachtung),
FF01/FF02/FF03-Reads und die fünf antwortenden Report-Typen blieben über alle
Runden komplett null. Kein einziges Byte schwankte.

**d) Umkehrtest — die endgültige Antwort.** Danach die Gegenrichtung: Finger
rein, Messung **physisch gestartet** (LED an), und *während* sie lief per
`bluetoothctl connect` eine Verbindung erzwingen wollen — **schlägt fehl**.
Das Gerät ist während einer laufenden Messung über BLE nicht erreichbar
(advertised nicht). Zusammen mit (c) ist damit lückenlos belegt: **Der PO60
hält Messung und BLE-Verbindung wechselseitig aus.** Es gibt keinen Zustand
mit leuchtender LED *und* stehender Verbindung — also keinen abgreifbaren
Momentanwert. **Der Live-Weg ist endgültig zu**; der PO60 bleibt reines
Speicher-Sync-Gerät (SpO₂/Puls-Aggregate, kein Schlag-zu-Schlag). Damit ist
der Exkurs abgeschlossen (vgl. `beurer_po60_exkurs.md`).
