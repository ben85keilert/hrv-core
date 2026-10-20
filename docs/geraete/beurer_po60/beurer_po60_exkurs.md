# Beurer PO60 — Exkurs

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Stand: 2026-08-14 · Status: **Live-Weg endgültig zu (Push UND Pull widerlegt).
Lauf 6 hat auch den letzten offenen Test — Messung und Sync gleichzeitig —
beidseitig verneint: Messung und BLE-Verbindung schließen sich am PO60
wechselseitig aus. Kein Code in der Praxis-GUI.** ·
Arbeitsbranch: `claude/beurer-po60-hrv-in6wvk` (Side-Branch, nicht integriert)

> **Abschluss (2026-08-14, nach Lauf 6).** Der in Lauf 5 offen gebliebene Test
> ist geführt und der Live-Weg damit **endgültig** zu. Beide Richtungen am
> Gerät geprüft: (a) bei stehender Sync-Verbindung startet **keine** Messung
> (LED aus, `90 00`–`90 04` antworten nur mit Nullrahmen); (b) während einer
> laufenden Messung (LED an) lässt sich das Gerät **nicht** verbinden — es
> advertised nicht. **Der PO60 hält Messung und BLE-Verbindung wechselseitig
> aus**; es gibt keinen Zustand mit leuchtender LED *und* stehender Verbindung,
> also keinen abgreifbaren Momentanwert. Zusätzlich in Lauf 6 widerlegt: der
> vermutete Blockabruf-Start-Index (`99 0a`) existiert nicht — je Abruf kommen
> nur die ältesten 10 von inzwischen 38 Datensätzen. Voller Befund:
> [`beurer_po60_erkundung.md`](beurer_po60_erkundung.md) §4 (Lauf 6). Die
> Entscheidung „nicht integrieren" ist damit lückenlos belegt.
>
> **Plattform-Nachtrag (Lauf 5, Windows):** Auf Windows/WinRT braucht der
> Vitalkanal ein **Bonding** — ohne OS-Pairing weist er Notify/Read mit
> „Insufficient Authentication" ab. Das „Bonding nicht nötig" aus §3 galt für
> Linux/BlueZ (Läufe 2–4). Nachtrag Lauf 6: `90 00`–`90 04` antworten auf
> Linux/BlueZ (Nullrahmen), unter Windows/WinRT schwiegen sie — reine
> Lese-/Report-Typen, keiner startet eine Messung.

Dieses Dokument ist der **Schlussstein** des PO60-Ausflugs. Es steht für sich
allein und ist bewusst so geschrieben, dass sich das gesamte Vorhaben daraus
**wiederherstellen** lässt, falls der Side-Branch später verworfen wird: Es
enthält die Erkenntnisse (Verbindungsaufbau, Natur der Verbindung, Protokoll),
die Entscheidung samt Begründung und **den vollständigen Quelltext** aller drei
Dateien als Referenz.

Zwei ältere Dokumente bleiben als Fahrtenbuch bestehen, sind aber diesem hier
untergeordnet:
- [`beurer_po60_erkundung.md`](beurer_po60_erkundung.md) — Lauf-für-Lauf-Befunde (§4)
- [`beurer_po60_uebergabe.md`](beurer_po60_uebergabe.md) — die (nun gegenstandslose) „Nächste-Schritte-für-Live"-Liste

---

## 1. Fazit vorweg (die Entscheidung)

Der Beurer PO60 sollte die HRV-Messung der Praxis-GUI um SpO₂/Puls ergänzen.
Nach vier Erkundungsläufen am echten Gerät und einer Klärung über die
offizielle App steht fest:

1. **Der PO60 gibt über Bluetooth keinen Live-Datenstrom her.** Er überträgt
   ausschließlich *gespeicherte* Messungen, und eine Messung wird erst beim
   **Herausnehmen des Fingers** angelegt.
2. **Selbst wenn es einen Live-Modus gäbe**, wären es SpO₂/Puls im
   ~1-Hz-Raster (gerätegemittelt) — **keine Schlag-zu-Schlag-Intervalle**. Als
   `intervall_quelle` der HRV-Kette (`ekg_rr`/`ppg_ppi`) kommt der PO60 damit
   ohnehin nie infrage.
3. **Eine einzelne Aggregatzahl** (SpO₂/Puls min/max/Ø über ein Messfenster)
   rechtfertigt keine BLE-Integration — ein Blick aufs Gerätedisplay und ein
   notierter Wert leisten dasselbe. Der einzige Mehrwert, den ein Blick nicht
   böte, wäre eine **kontinuierliche SpO₂-Kurve zeitlich auf der HRV-Messung** —
   und genau das kann der PO60 nicht liefern.

**Konsequenz:** Der PO60 wird **nicht** in die Praxis-GUI integriert. Der
reverse-engineerte Protokollkern bleibt als sauber getestete Referenz erhalten
(dieses Dokument), verändert aber keinen Produktivcode. Wer künftig eine
SpO₂-Kurve neben der HRV will, sollte ein **kontinuierlich streamendes**
Oximeter wählen (siehe §7), nicht den PO60.

---

## 2. Die Beweiskette „kein Live-Modus"

| Beleg | Aussage |
| --- | --- |
| Lauf 4 (14.08.2026): 5 min Verbindung mit Finger im Gerät | Außer Handshake-Antworten **keine einzige Notification** — auf FF02 wie auf jeder anderen notify-/indicate-fähigen Characteristic. |
| Datensatzanzahl während eingelegtem Finger | Blieb konstant (14) und sprang erst **nach** dem Finger-Herausnehmen auf 15 → Messung wird beim Herausnehmen committet, nicht laufend. |
| FF03 (Vendor, read/write) im Ruhezustand | Liefert nur Null-Puffer; kein Live-Kanal erkennbar. |
| Analogie PO80 (widerlegt) | Der PO80 streamt live, aber über einen **USB-Funk-Dongle** an die PC-Software „SpO2 Assistant" — **kein BLE**. Taugt nicht als Indiz für einen BLE-Live-Modus des PO60. |
| **Offizielle App „Beurer HealthManager Pro"** | Bietet beim PO60 **nur Synchronisierung** gespeicherter Messungen, **keine Live-Ansicht**. Ein Hersteller versteckt keinen Live-Modus, den seine eigene App nicht nutzt. → entscheidender Beleg. |

Das betrifft den **Push** — das Gerät sendet nichts von sich aus. **Offen
bleibt der Pull:** ob ein Kommando den *aktuellen* Messwert *auf Anforderung*
zurückgibt. Getestet wurde das nie während einer laufenden Messung; die
frühere Sondierung lief mit leerem Finger und nur fünf Kommandos.

Naheliegende Hypothese war: Das zweite Handshake-Byte ist ein **Report-Typ**
(`90 05` → gespeicherte Anzahl, Antwort `e0 05 …`) — vielleicht liefert ein
anderer Report-Typ der 0x90-Familie den Momentanwert. Das prüfte das
Subkommando `pollen` (§9.4): es sendet `90 00`…`90 0f` und liest zyklisch
FF03/FF02/FF01, jeweils mit Markierung geänderter Bytes.

**Ergebnis (Lauf 5, 14.08.2026, `beurer_po60_erkundung.md` §4):** Der Pull ist
weitgehend widerlegt.

| Beleg (Lauf 5) | Aussage |
| --- | --- |
| `90 00`…`90 0f` je einmal gesendet | **keine einzige Antwort** → kein Pull über die 0x90-Familie. |
| FF03/FF02/FF01 zyklisch gelesen, FF02-Notifications | nur Nullen bzw. Handshake-Echo (`e0 05 22 00 22 00 29`, 34 Datensätze); **kein schwankendes Vitalbyte**. |
| **Mess-LED im Sync-Modus** (Nutzerbeobachtung) | **aus** — das Gerät misst im Sync-/BLE-Zustand gar nicht. Also existiert kein Momentanwert zum Abfragen. |

Damit ist auch das stärkste Indiz gegen einen nützlichen Pull erklärt: Die
offizielle App zeigt keinen Momentanwert, **weil das Gerät beim Syncen nicht
misst.** Der einzige verbleibende Live-Test: Messung und Sync **gleichzeitig**
erzwingen (Finger einlegen, während die Sync-Verbindung steht — geht die LED
an?). Gelingt das nicht, ist der Live-Weg endgültig zu. Selbst ein dann
gefundener Wert bliebe SpO₂/Puls im ~1-Hz-Raster (nie `intervall_quelle`).

---

## 3. Verbindungsaufbau (so koppelt man sich an)

Falls das Gerät später doch noch einmal ausgelesen werden soll (z. B. um
gespeicherte Messungen zu importieren), ist hier der erprobte Ablauf. Alles
davon steckt fertig im Erkundungswerkzeug (§9).

**Gerät:** Adresse `C9:49:AC:1E:4B:00`, Name „PO60", FW V7.3, HW 2.00.
Beworbene Dienste: `0x1800`, `0x1801`, `0x180A`, `0xFF00`, `0xFF12`.
Herstellerdaten-ID 1553 → `01`.

- **Bonding je nach Plattform:** Auf **Linux/BlueZ** nicht nötig — Notify
  funktioniert unpaarig (Läufe 2–4). Auf **Windows/WinRT** dagegen **nötig**:
  ohne OS-Pairing weist der Vitalkanal Notify/Read mit „Insufficient
  Authentication / Access Denied" ab (Lauf 5). Dort also zuerst `--koppeln`
  oder das Gerät in den Windows-Bluetooth-Einstellungen koppeln.
- **Sichtbarkeitsfenster:** Der PO60 advertised nur wenige Sekunden nach
  Tastendruck. Deshalb **live scannen** (Detection-Callback, kein Blockscan)
  und die Taste drücken, *während* der Scan läuft — beim ersten Treffer sofort
  verbinden. Bewährter Bedienablauf, der ein **langes** Fenster öffnet:
  **Messung machen bis ein Wert steht → Finger herausnehmen → Sync-Modus
  startet (Bluetooth-Symbol) → Finger wieder hinein.**
- **Verbindungsabrisse direkt nach Sync-Start:** 2–3× kurz hintereinander —
  das ist normal; eine **Wiederverbindungs-Schleife** fängt es ab.
- **Verbindung ohne impliziten Scan:** mit einem echten `BLEDevice`-Objekt
  verbinden (nicht mit einem Adress-String), GATT-Cache aus
  (`use_cached_services=False` unter Windows/WinRT).

---

## 4. Natur der Verbindung (was das Gerät tut und lässt)

Das ist der eigentliche Erkenntniskern — die Eigenheiten, an denen jeder naive
Verbindungsversuch scheitert:

- **Idle-Timeout ~35 s:** Eine **untätige** Verbindung (nur Abonnieren, keine
  Schreibzugriffe) trennt das Gerät nach ~33–35 s von selbst — ohne jede
  Notification. Eine passive Lauschphase über Minuten ist damit unmöglich.
  → **Keep-Alive:** alle 15 s den Handshake senden (harmlos, bestätigt; hielt
  die Verbindung nachweislich über 5 min). Seine Antwort meldet nebenbei die
  Datensatzanzahl — steigt sie, wurde während der Verbindung eine Messung
  gespeichert.
- **Selbsttrennung nach Speicherabruf:** ~6 s nach dem letzten Datensatz
  trennt das Gerät. Deshalb im Kombilauf **erst lauschen, dann Speicher
  abrufen** (der Abruf beendet die Sitzung faktisch).
- **Messung wird beim Finger-Herausnehmen angelegt** — nicht laufend.
- **Abruf löscht nicht:** Datensätze kommen bei Wiederholung byteidentisch;
  nur das „letzter"-Flag (Bit 6) wandert zum jeweils neuesten Datensatz.
- **Blockgrenze:** je Anforderung höchstens **10 Datensätze**. Bei mehr
  (Lauf 4: 15 gemeldet, 0–9 geliefert, dann Stille) muss blockweise
  nachgefordert werden. Hypothese: zweites Kommandobyte = Start-Index
  (`99 0a` = ab Datensatz 10) — **unbestätigt** (offener Lauf 5); das Werkzeug
  fordert automatisch nach, mit Fallback „erneut ab 0 + Deduplizierung".
- **FF01/FF02/FF03 per Read im Ruhezustand:** nur Null-Puffer (20/20/21 Bytes).

---

## 5. Protokoll (vollständig, am Gerät bestätigt)

```
Prüfsumme  : letztes Byte = sum(vorherige Bytes) & 0x7F
             — gilt für Kommandos, Handshake-Antwort UND jeden Datensatz.
             (Das Gerät hält alle Datenbytes 7-bittig → 0x7F-Masken,
              Basis-128-Kodierung der Abtastanzahl.)

Handshake  : Write FF01  90 05 15
             Notify FF02  e0 05 <n u16 LE> <n u16 LE> <PS>
             n = Datensatzanzahl (steht doppelt drin; warum, ist offen —
             evtl. Anzahl + Kapazität)

Abruf      : Write FF01  99 00 19
             Notify FF02  FORTLAUFENDER Bytestrom in 20-Byte-Notifications,
             Datensätze à 24 Byte — die Grenzen liegen MITTEN in den Paketen.

Datensatz (24 Byte):
  [0]      0xE9
  [1]      Bits 0–5: Datensatznummer (bis 63; Gerät speichert lt. Anleitung
           bis 100 — Überlauf offen). Bit 6 (0x40): letzter im Speicher,
           wandert mit neuen Messungen.
  [2–7]    Messbeginn: Jahr−2000, Monat, Tag, Stunde, Minute, Sekunde
  [8–13]   Messende:   gleiche Kodierung
  [14–16]  Abtastanzahl als Basis-128-Zahl (7-Bit-Bytes, big-endian);
           = Messdauer in s + 1 (1-Hz-Abtastung, Endpunkte inklusive)
  [17–19]  SpO₂  max / min / Mittel   (jeweils & 0x7F)
  [20–22]  Puls  max / min / Mittel   (jeweils & 0x7F)
  [23]     Prüfsumme = sum(Bytes 0–22) & 0x7F

Jahres-Byte: Jahr − 2000. Ungestellte Werksuhr → 2019-01-01.

Kanäle:
  Dienst 0xFF12 → FF01 (Write), FF02 (Notify)
  Dienst 0xFF00 → FF03 (Read/Write, Funktion unbekannt — Ruhezustand: Nullen)
  KEIN Standard-HR (0x2A37), KEIN Standard-PLX (0x1822).
```

**Offene Protokollfragen** (für einen etwaigen späteren Import belanglos, der
Vollständigkeit halber notiert): Blockabruf-Start-Index (`99 <index>`);
Funktion von FF03; warum die Datensatzanzahl doppelt in der Handshake-Antwort
steht; Index-Verhalten bei > 63 Datensätzen; Stellen der Geräteuhr per BLE.

---

## 6. Die Läufe in Kürze (Rohdetails: `beurer_po60_erkundung.md` §4)

| Lauf | Datum | Ergebnis |
| --- | --- | --- |
| 1 | 13.08. | PO60 nicht gesehen (Blockscan verfehlte das Advertising-Fenster) → Werkzeug auf Live-Scan mit Sofortzugriff umgebaut. |
| 2 | 14.08. 07:00 | **Durchbruch.** Verbunden ohne Kopplung; Speicherabruf lieferte 10 Datensätze à 24 B ohne Restbytes → 24-Byte-Stromlayout etabliert, Basis-128-Abtastanzahl erkannt. Device Info: FW V7.3, HW 2.00. |
| 3 | 14.08. 07:15 | **Idle-Timeout** entdeckt (33 s Selbsttrennung ohne Aktivität) → Keep-Alive eingeführt; FF01–FF03-Reads im Ruhezustand = Nullen. |
| 4 | 14.08. 07:26 | **Kein Live-Modus** (5 min Finger im Gerät, nur Handshakes). **Abruf löscht nicht**, Flag wandert. **Blockgrenze** 10 Datensätze entdeckt. Keep-Alive hielt 5 min. |
| 5 | 14.08. 13:28 | **Pull widerlegt** (`pollen`, Windows): `90 00`…`90 0f` ohne Antwort, kein schwankendes Vitalbyte. Ursache: **Mess-LED im Sync-Modus aus** → Gerät misst beim Syncen nicht. **Windows braucht Bonding** (sonst „Insufficient Authentication"). Offen: Messung + Sync gleichzeitig. |

Die echten Gerätepakete aus Lauf 2/4 sind als **Golden Vectors** in
`tests/test_po60.py` eingefroren (§9).

---

## 7. Möglichkeiten (die Gabelung)

**A) Kontinuierliche SpO₂-Kurve über der HRV ist das Ziel.**
Dann ist der PO60 das falsche Gerät. Richtig wäre ein Oximeter mit
**kontinuierlichem Strom** — Standard-**PLX Continuous** (`0x2A5F`) oder ein
Vendor-Sekundenstrom (Viatom/Wellue: O2Ring, Checkme O2). Die liefern
SpO₂ + Puls (+ teils Perfusionsindex/Plethysmogramm) im 1-Hz-Raster live über
BLE und ließen sich als **Overlay-Kurve** ins vorhandene Kurven-Paradigma
einhängen (Rolling/Fixed/Overlap auf dem Tachogramm). Weiterhin **nie**
`intervall_quelle` (1 Hz ist nicht schlagweise), aber als aufgelegte Kurve
inhaltlich wertvoll. → **Neues Gerät über ein Profil**
(`sensors/devices/profiles.py`), keine Namens-Fallunterscheidung im Widget
(CLAUDE.md).

**B) SpO₂ war nur ein gelegentlicher Kontrollwert.**
Dann ist der Exkurs hier zu Ende: Blick aufs Display genügt, keine
Integration. **Das ist die getroffene Entscheidung für den PO60.**

**Falls jemals „gespeicherte PO60-Messungen importieren" gewünscht ist:** Das
ginge mit dem vorhandenen Code, ganz ohne Live. Wichtig für die Ablage —
ein PO60-Satz ist **kein zweiter Strom** und gehört **nicht** ins
`sitzung-v1`-Mehrgeräteschema (das setzt parallele Schlag-zu-Schlag-Ströme mit
gemeinsamem Nullpunkt voraus; der PO60 ist asynchron, aggregiert, mit eigenem
Zeitfenster). Er wäre eine **ergänzende Annotation** an einer Messung/Akte
(„SpO₂ Ø97 %, Puls Ø72, 14:32–14:34, Quelle PO60"), nie ein Co-Stream — genau
das, wovor CLAUDE.md warnt („ein Gerät wird nie während einer laufenden
Aufnahme hinzugenommen — sein Strom hätte einen anderen Nullpunkt").

---

## 8. Wiederherstellung des Projekts

Um den Stand aus diesem Dokument zu rekonstruieren:

| Datei | Zweck | Abhängigkeiten |
| --- | --- | --- |
| `sensors/devices/po60.py` | Protokollmodul (Qt-/bleak-frei, Muster `pmd.py`) | nur stdlib |
| `tools/po60_erkundung.py` | CLI-Erkundungswerkzeug | `bleak`, `po60.py` |
| `tests/test_po60.py` | 19 Golden-Vector-/Rand-Tests | `pytest`, `po60.py` |

- Ausführen: `python -m pytest tests/test_po60.py -v`
- Erkunden: `.venv/Scripts/python.exe tools/po60_erkundung.py alles --adresse C9:49:AC:1E:4B:00`
- `Logs/po60/` ist git-ignoriert (JSONL-Rohprotokolle je Lauf).
- **Grundsätze**, falls doch weitergearbeitet wird: alles roh loggen,
  Unbekanntes nie verwerfen; nur `kommando()`-gebaute, nicht erkennbar
  schreibende Opcodes sondieren; bei jeder Protokollkorrektur die echten
  Gerätebytes als **neuen** Golden Vector einfrieren, nie einen bestehenden
  „anpassen".

Der folgende §9 enthält den kompletten Quelltext, sodass die drei Dateien
auch ohne den Branch wiederherstellbar sind.

---

## 9. Quelltext (Referenz — Stand des Side-Branch)

### 9.1 `sensors/devices/po60.py`

```python
"""
po60.py
-------
Beurer PO60 (Fingerpulsoximeter) — Kommandos und Datensatz-Parser.

Reines Python, keine Qt- und keine BLE-Abhängigkeit — dasselbe Muster wie
`pmd.py`: das Protokoll lässt sich ohne Gerät prüfen, die Tests bauen
synthetische Ströme und vergleichen, was herauskommt.

Stand der Verifikation
======================
**Am echten Gerät bestätigt** (PO60, Firmware V7.3, Hardware 2.00,
Erkundungslauf vom 14.08.2026, siehe `docs/beurer_po60_erkundung.md`):
Kommandos samt Prüfsummenregel, Handshake-Antwort, das komplette
24-Byte-Datensatzlayout inklusive beider Zeitstempel — alle zehn
Speicherdatensätze des Testgeräts dekodierten ohne Restbytes, alle
Prüfsummen gültig. Die Tests in `tests/test_po60.py` halten die echten
Gerätepakete als Golden Vectors fest.

Weitere Befunde vom Gerät (Lauf 4): Es gibt **keinen Live-Modus** — fünf
Minuten Verbindung mit Finger im Gerät lieferten außer Handshake-Antworten
keine einzige Notification. Der Abruf **löscht nichts** (Datensätze kommen
bei Wiederholung byteidentisch). Bit 6 im Index-Byte markiert den letzten
Datensatz des gesamten Speichers und wandert mit, wenn neue Messungen
dazukommen. Je Anforderung sendet das Gerät höchstens einen Block von 10
Datensätzen (Fortsetzung siehe `kommando_speicher_abruf`).

Noch offen: die Funktion der dritten Vendor-Characteristic FF03 und die
Bestätigung des Blockabrufs per Start-Index.
Ausgangspunkt des Reverse Engineerings war
https://github.com/Shreyan1/Beurer-PO60-PulseOximeter-Bluetooth-Integration

Wichtig für die Einordnung: Der PO60 liefert **keine
Schlag-zu-Schlag-Intervalle**, sondern gespeicherte Messungen mit
Minimum/Maximum/Mittelwert von SpO₂ und Puls. Als Intervallquelle für die
HRV-Kette (`intervall_quelle`) kommt er nicht infrage.

Übertragungsablauf (bestätigt)
==============================
    Schreiben auf FF01:  90 05 15        (Handshake)
    Antwort auf FF02:    e0 05 <Anzahl u16 LE> <Anzahl u16 LE> <Prüfsumme>
    Schreiben auf FF01:  99 00 19        (Speicherabruf)
    Notifications auf FF02: ein FORTLAUFENDER Bytestrom in 20-Byte-Stücken;
    die Datensatzgrenzen liegen meist mitten in einer Notification.
    ~6 s nach dem letzten Datensatz trennt das Gerät die Verbindung selbst.

Datensatz (24 Byte, bestätigt an 10 echten Datensätzen)
=======================================================
    [0]     0xE9
    [1]     Bits 0–5: Datensatznummer (beobachtet bis 14; das Gerät
            speichert laut Anleitung bis zu 100 — ob der Index dann
            überläuft, ist offen); Bit 6 (0x40) markiert den letzten
            Datensatz des gesamten Speichers und wandert mit, wenn
            neue Messungen dazukommen (Lauf 2 vs. Lauf 4 bestätigt)
    [2–7]   Messbeginn: Jahr−2000, Monat, Tag, Stunde, Minute, Sekunde
    [8–13]  Messende:   gleiche Kodierung
    [14–16] Abtastanzahl als Basis-128-Zahl (7-Bit-Bytes, big-endian) —
            bei allen zehn Referenzdatensätzen exakt Messdauer in
            Sekunden + 1 (1-Hz-Abtastung, beide Endpunkte inklusive)
    [17–19] SpO₂ max / min / Mittel   (jeweils & 0x7F)
    [20–22] Puls max / min / Mittel   (jeweils & 0x7F)
    [23]    Prüfsumme = sum(Bytes 0–22) & 0x7F

Das Gerät hält die Datenbytes durchgehend 7-bittig — daher die 0x7F-Masken
und die Basis-128-Kodierung der Abtastanzahl.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Dienste und Charakteristiken (GATT-Dump vom 14.08.2026)
# ---------------------------------------------------------------------------
# Datenkanal: Dienst 0xFF12 mit FF01 (write) und FF02 (notify).
DATEN_SERVICE_UUID = "0000ff12-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

# Zweiter Vendor-Dienst 0xFF00 mit FF03 (read/write) — Funktion unbekannt.
VENDOR2_SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
FF03_UUID = "0000ff03-0000-1000-8000-00805f9b34fb"

# Standard-Pulsoximeter-Dienst (PLX) — am PO60 NICHT vorhanden (bestätigt);
# die Konstanten bleiben für die gezielte Prüfung im GATT-Dump.
PLX_SERVICE_UUID = "00001822-0000-1000-8000-00805f9b34fb"
PLX_SPOT_CHECK_UUID = "00002a5e-0000-1000-8000-00805f9b34fb"
PLX_CONTINUOUS_UUID = "00002a5f-0000-1000-8000-00805f9b34fb"

# Rahmenköpfe
KOPF_SPEICHER = 0xE9  # ein gespeicherter Messdatensatz
KOPF_HANDSHAKE = 0xE0  # Antwort auf CMD_HANDSHAKE

DATENSATZ_LAENGE = 24
HANDSHAKE_LAENGE = 7

# Namensmuster, an denen ein PO60 im Scan erkannt wird (Gerät meldet "PO60").
NAMENS_MUSTER = ("po60", "po 60", "beurer")


def sieht_nach_po60_aus(name: str | None) -> bool:
    """Heuristik über den beworbenen Bluetooth-Namen (vgl.
    `profiles.profil_fuer_namen`). Namenlose Geräte fallen durch — im
    Zweifel hilft nur die bekannte Adresse."""
    return any(m in (name or "").lower() for m in NAMENS_MUSTER)


# ---------------------------------------------------------------------------
# Kommandos bauen
# ---------------------------------------------------------------------------


def pruefsumme(daten: bytes) -> int:
    """Prüfsumme: Summe der vorherigen Bytes, auf 7 Bit gekürzt.

    Ursprünglich eine Hypothese aus den zwei bekannten Kommandos — am Gerät
    bestätigt: auch die Handshake-Antwort und jeder Speicherdatensatz enden
    auf genau diese Summe.
    """
    return sum(daten) & 0x7F


def kommando(*bytes_: int) -> bytes:
    """Kommando samt angehängter Prüfsumme."""
    rumpf = bytes(bytes_)
    return rumpf + bytes([pruefsumme(rumpf)])


def kommando_speicher_abruf(start_index: int = 0) -> bytes:
    """Speicherabruf ab einem Datensatz-Index.

    Das Gerät liefert je Anforderung höchstens einen Block von 10
    Datensätzen (Lauf 4: 15 gemeldet, nur 0–9 gesendet, dann Stille).
    Hypothese für die Fortsetzung: das zweite Kommandobyte ist der
    Start-Index — `99 00` = ab Datensatz 0, `99 0a` = ab Datensatz 10.
    Am Gerät zu bestätigen (Lauf 5).
    """
    return kommando(0x99, start_index & 0x7F)


# Die beiden bestätigten Kommandos. Die Tests frieren die Hex-Werte ein,
# damit die Prüfsummenregel nie stillschweigend das Gesendete ändert.
CMD_HANDSHAKE = kommando(0x90, 0x05)  # 90 05 15
CMD_SPEICHER_ABRUF = kommando_speicher_abruf(0)  # 99 00 19

# Empfohlene Pause zwischen Handshake und Speicherabruf.
HANDSHAKE_PAUSE_S = 0.5


# ---------------------------------------------------------------------------
# Rahmen
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HandshakeAntwort:
    """Antwort auf CMD_HANDSHAKE: e0 05 <n u16 LE> <n u16 LE> <Prüfsumme>.

    `anzahl_datensaetze` stimmte am Testgerät exakt mit dem Speicherinhalt
    überein (10 gemeldet, 10 geliefert). Warum die Zahl doppelt im Paket
    steht (Bytes 2–3 und 4–5), ist offen — vielleicht Anzahl und Kapazität.
    """

    anzahl_datensaetze: int
    pruefsumme_ok: bool
    roh: bytes


@dataclass(frozen=True)
class PO60Messung:
    """Ein gespeicherter Messdatensatz (24 Byte, dekodiert)."""

    index: int  # Bits 0–5 von Byte 1
    letzter: bool  # Bit 6 von Byte 1: letzter im Speicher
    beginn: datetime | None  # None = unplausibel, nie eine Exception
    ende: datetime | None
    abtastungen: int  # Basis-128-Zahl aus Byte 14–16
    spo2_max: int
    spo2_min: int
    spo2_mittel: int
    puls_max: int
    puls_min: int
    puls_mittel: int
    roh: bytes

    @property
    def dauer_s(self) -> float | None:
        if self.beginn is None or self.ende is None:
            return None
        return (self.ende - self.beginn).total_seconds()


@dataclass(frozen=True)
class UnbekannterRahmen:
    """Zusammenhängendes Reststück, das kein bekannter Rahmen ist.

    Wird bewusst NIE verworfen: sollte der PO60 einen Live-Modus haben,
    tauchen dessen Bytes genau hier auf — sie sind der wertvollste
    Erkundungsertrag, nicht Müll.
    """

    kopf: int | None  # erstes Byte, None bei leerem Stück
    laenge: int
    roh: bytes


def _zeitstempel(b: bytes) -> datetime | None:
    """6 Bytes (Jahr−2000, M, T, h, m, s) → datetime; unplausibel → None.

    Die Kodierung „Jahr ab 2000" ist am Gerät bestätigt: Messungen mit
    ungestellter Werksuhr tragen 2019-01-01, echte das korrekte Datum.
    """
    jahr, monat, tag, stunde, minute, sekunde = b[:6]
    if jahr > 99:
        return None
    try:
        return datetime(2000 + jahr, monat, tag, stunde, minute, sekunde)
    except ValueError:
        return None


def _basis128(b: bytes) -> int:
    """Big-endian-Zahl aus 7-Bit-Bytes (Bit 7 wird ignoriert)."""
    wert = 0
    for x in b:
        wert = (wert << 7) | (x & 0x7F)
    return wert


def parse_datensatz(daten: bytes) -> PO60Messung | None:
    """Exakt 24 Bytes ab einem 0xE9-Kopf → Messung; None bei ungültiger
    Prüfsumme oder falscher Länge (der Aufrufer sucht dann weiter)."""
    b = bytes(daten)
    if len(b) != DATENSATZ_LAENGE or b[0] != KOPF_SPEICHER:
        return None
    if pruefsumme(b[:23]) != b[23]:
        return None
    return PO60Messung(
        index=b[1] & 0x3F,
        letzter=bool(b[1] & 0x40),
        beginn=_zeitstempel(b[2:8]),
        ende=_zeitstempel(b[8:14]),
        abtastungen=_basis128(b[14:17]),
        spo2_max=b[17] & 0x7F,
        spo2_min=b[18] & 0x7F,
        spo2_mittel=b[19] & 0x7F,
        puls_max=b[20] & 0x7F,
        puls_min=b[21] & 0x7F,
        puls_mittel=b[22] & 0x7F,
        roh=b,
    )


def parse_handshake(daten: bytes) -> HandshakeAntwort | None:
    """Exakt 7 Bytes ab einem 0xE0-Kopf → Handshake-Antwort; sonst None."""
    b = bytes(daten)
    if len(b) != HANDSHAKE_LAENGE or b[0] != KOPF_HANDSHAKE:
        return None
    return HandshakeAntwort(
        anzahl_datensaetze=int.from_bytes(b[2:4], "little"),
        pruefsumme_ok=pruefsumme(b[:6]) == b[6],
        roh=b,
    )


# ---------------------------------------------------------------------------
# Datensätze aus dem Notification-Strom sammeln
# ---------------------------------------------------------------------------


class SpeicherSammler:
    """Setzt den fortlaufenden FF02-Bytestrom wieder zu Rahmen zusammen.

    Die 24-Byte-Datensätze kommen in 20-Byte-Notifications — die Grenzen
    liegen also meist mitten im Paket. Der Sammler puffert deshalb alles
    und sucht an jeder Position nach einem gültigen Rahmen; gültig heißt:
    bekannter Kopf UND passende Prüfsumme (verhindert Fehltreffer auf ein
    0xE9 in Nutzdaten). Unpassende Bytes rücken als zusammenhängende
    Reststücke nach `unbekannt` — nichts wird verworfen.

    Rein synchron, damit byteweise testbar.
    """

    def __init__(self) -> None:
        self.messungen: list[PO60Messung] = []
        self.handshakes: list[HandshakeAntwort] = []
        self.unbekannt: list[UnbekannterRahmen] = []
        self._puffer = bytearray()
        self._rest = bytearray()

    def aufnehmen(self, daten) -> list:
        """Eine Notification (oder beliebige Bytes) verarbeiten.

        Gibt die dabei fertig gewordenen Rahmen zurück (Messungen und
        Handshake-Antworten), damit der Aufrufer live mitprotokollieren
        kann.
        """
        self._puffer.extend(bytes(daten or b""))
        fertig: list = []

        while self._puffer:
            kopf = self._puffer[0]
            if kopf == KOPF_SPEICHER:
                if len(self._puffer) < DATENSATZ_LAENGE:
                    break  # Rest kommt mit dem nächsten Paket
                m = parse_datensatz(bytes(self._puffer[:DATENSATZ_LAENGE]))
                if m is not None:
                    self._rest_abschliessen()
                    self.messungen.append(m)
                    fertig.append(m)
                    del self._puffer[:DATENSATZ_LAENGE]
                    continue
            elif kopf == KOPF_HANDSHAKE:
                if len(self._puffer) < HANDSHAKE_LAENGE:
                    break
                h = parse_handshake(bytes(self._puffer[:HANDSHAKE_LAENGE]))
                if h is not None:
                    self._rest_abschliessen()
                    self.handshakes.append(h)
                    fertig.append(h)
                    del self._puffer[:HANDSHAKE_LAENGE]
                    continue
            # Kein gültiger Rahmen an dieser Position — ein Byte weiter.
            self._rest.append(self._puffer.pop(0))

        return fertig

    def _rest_abschliessen(self) -> None:
        if self._rest:
            self.unbekannt.append(
                UnbekannterRahmen(kopf=self._rest[0], laenge=len(self._rest), roh=bytes(self._rest))
            )
            self._rest.clear()

    def abschliessen(self) -> None:
        """Strom zu Ende — was noch im Puffer liegt, wird Reststück."""
        self._rest.extend(self._puffer)
        self._puffer.clear()
        self._rest_abschliessen()
```

> **Hinweis:** Der in §9.2 eingebettete Tool-Code ist der Stand **vor** der
> `pollen`-Erweiterung. Deren Zusatzcode steht in §9.4; maßgeblich ist immer
> die Datei im Repo.

### 9.2 `tools/po60_erkundung.py`

```python
#!/usr/bin/env python3
"""
po60_erkundung.py
-----------------
Beurer PO60 kennenlernen: verbinden, GATT-Tabelle dumpen, gespeicherte
Messungen abrufen, auf spontane (Live-)Pakete lauschen — und ALLES roh in
eine JSONL-Datei protokollieren. Kein Qt; nur `bleak` und das Qt-freie
Protokollmodul `sensors/devices/po60.py`.

Zweck: Das PO60-Protokoll ist reverse-engineered und unverifiziert. Dieses
Werkzeug sammelt die Befunde am echten Gerät, aus denen danach die eigentliche
Integration entworfen wird (siehe docs/beurer_po60_erkundung.md).

Beispiele (aus dem Projektordner; Windows: .venv/Scripts/python.exe,
Linux: python3 bzw. .venv/bin/python)
------------------------------------------
    python3 tools/po60_erkundung.py alles --adresse F0:...   # Adresse bekannt
    python3 tools/po60_erkundung.py alles                    # per Namens-Scan
    python3 tools/po60_erkundung.py scan
    python3 tools/po60_erkundung.py dienste --adresse F0:...
    python3 tools/po60_erkundung.py speicher --adresse F0:...
    python3 tools/po60_erkundung.py lauschen --adresse F0:... --minuten 5

Wichtig am Gerät: Der PO60 ist nur wenige Sekunden nach Tastendruck über
Bluetooth sichtbar. Deshalb scannt das Werkzeug LIVE und in Runden: die
Taste einfach drücken, WÄHREND der Scan läuft — sobald der PO60 auftaucht,
greift das Werkzeug sofort zu. Läuft eine Runde leer, kommt die nächste
(Abbruch mit Strg+C).
Alle Roh-Daten landen in Logs/po60/po60_<Zeitstempel>.jsonl (git-ignoriert).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Bewusst nur das Qt-freie Protokollmodul — kein PySide6-Import.
from sensors.devices import po60  # noqa: E402

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # pragma: no cover
    print(
        "bleak ist nicht installiert — bitte in der venv der Anwendung "
        "starten (.venv/Scripts/python.exe).",
        file=sys.stderr,
    )
    sys.exit(2)

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"  # Standard-HR
DEVICE_INFO_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb"

# Kandidatenkommandos für --sondieren: naheliegende Opcodes rund um die zwei
# bekannten (0x90 Handshake, 0x99 Speicherabruf), formal korrekt über
# `po60.kommando()` gebaut. AUSDRÜCKLICH SPEKULATIV — nichts davon ist
# dokumentiert; die Auswahl meidet alles, was nach Schreiben/Löschen aussieht
# (deshalb bewusst KEINE Varianten mit gesetzten Datenbytes). Default ist AUS.
SONDIER_KOMMANDOS: tuple[bytes, ...] = (
    po60.kommando(0x90, 0x00),
    po60.kommando(0x90, 0x01),
    po60.kommando(0x91, 0x00),
    po60.kommando(0x98, 0x00),
    po60.kommando(0x9A, 0x00),
)

SONDIER_ANTWORTFENSTER_S = 2.0
SPEICHER_RUHE_S = 3.0  # so lange Stille = Speicherabruf ist fertig


# ---------------------------------------------------------------------------
# JSONL-Protokoll
# ---------------------------------------------------------------------------


class Protokoll:
    """Eine JSONL-Datei, zeilenweise geflusht — bei einem Verbindungsabriss
    darf nichts verloren gehen."""

    def __init__(self, verzeichnis: str) -> None:
        os.makedirs(verzeichnis, exist_ok=True)
        name = f"po60_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        self.pfad = os.path.join(verzeichnis, name)
        self._f = open(self.pfad, "w", encoding="utf-8")

    def zeile(
        self, art: str, quelle: str = "", roh: bytes | None = None, dekodiert=None, **extra
    ) -> None:
        eintrag = {
            "t_mono": time.monotonic(),
            "t_wall": datetime.now().astimezone().isoformat(),
            "art": art,
        }
        if quelle:
            eintrag["quelle"] = quelle
        if roh is not None:
            eintrag["roh_hex"] = bytes(roh).hex()
        if dekodiert is not None:
            eintrag["dekodiert"] = dekodiert
        eintrag.update(extra)
        self._f.write(json.dumps(eintrag, ensure_ascii=False, default=str) + "\n")
        self._f.flush()

    def schliessen(self) -> None:
        try:
            self._f.close()
        except Exception:
            pass


def _dekodiert_dict(rahmen) -> dict:
    """Geparsten Rahmen fürs Protokoll und die Konsole aufbereiten."""
    d = {"typ": type(rahmen).__name__}
    for feld, wert in vars(rahmen).items():
        if feld == "roh":
            continue
        d[feld] = wert.isoformat() if isinstance(wert, datetime) else wert
    return d


# ---------------------------------------------------------------------------
# Verbinden
# ---------------------------------------------------------------------------


def _taste_druecken_hinweis(erneut: bool = False) -> None:
    print()
    wort = "erneut kurz" if erneut else "kurz"
    print(f"»  Jetzt die Funktionstaste am PO60 {wort} drücken — das")
    print("»  Bluetooth-Symbol im Display muss blinken. Der Scan läuft:")
    print("»  sobald der PO60 auftaucht, wird sofort zugegriffen.")
    print()


def _adv_eintrag(dev, adv) -> dict:
    return {
        "name": dev.name,
        "adresse": dev.address,
        "rssi": adv.rssi,
        "dienste": list(adv.service_uuids or []),
        "hersteller_daten": {
            str(k): bytes(v).hex() for k, v in (adv.manufacturer_data or {}).items()
        },
        "service_daten": {str(k): bytes(v).hex() for k, v in (adv.service_data or {}).items()},
        "lokaler_name": adv.local_name,
    }


async def _live_scan(
    log: Protokoll,
    dauer: float,
    *,
    ziel_adresse: str | None = None,
    stopp_bei_kandidat: bool = False,
) -> list:
    """Eine Scan-Runde mit Sofortanzeige.

    Der PO60 ist nur wenige Sekunden sichtbar — deshalb kein Blockscan
    (dessen Liste erst nach Ablauf erscheint), sondern ein Detection-
    Callback: jedes neu gesehene Gerät wird sofort gedruckt und geloggt.
    Liefert BlueZ den Namen erst mit der Scan-Response nach, wird die
    Zeile erneut gedruckt und die Kandidatenprüfung wiederholt. Mit
    `stopp_bei_kandidat` endet die Runde beim ersten Treffer sofort.

    Rückgabe: Liste der Kandidaten als echte BLEDevice-Objekte.
    """
    gesehen: dict[str, str | None] = {}  # Adresse → zuletzt gezeigter Name
    kandidaten: dict[str, object] = {}
    treffer = asyncio.Event()

    def _gefunden(dev, adv) -> None:
        adresse = dev.address
        name = dev.name or adv.local_name
        neu = adresse not in gesehen
        name_nachgeliefert = (not neu) and name and not gesehen[adresse]
        if not (neu or name_nachgeliefert):
            return
        gesehen[adresse] = name
        log.zeile("gatt", quelle="scan", dekodiert=_adv_eintrag(dev, adv))
        ist_kandidat = (
            ziel_adresse is not None and adresse.lower() == ziel_adresse.lower()
        ) or po60.sieht_nach_po60_aus(name)
        marker = "  ← PO60-Kandidat" if ist_kandidat else ""
        print(f"  {adv.rssi or '?':>4}  {adresse}  {name or '(ohne Namen)'}{marker}")
        if ist_kandidat and adresse not in kandidaten:
            kandidaten[adresse] = dev
            if stopp_bei_kandidat:
                treffer.set()

    scanner = BleakScanner(detection_callback=_gefunden)
    await scanner.start()
    try:
        try:
            await asyncio.wait_for(treffer.wait(), timeout=dauer)
        except asyncio.TimeoutError:
            pass
    finally:
        await scanner.stop()
    return list(kandidaten.values())


async def _geraet_suchen(log: Protokoll, adresse: str | None, dauer: float, runden: int | None):
    """In Runden scannen, bis der PO60 auftaucht (Strg+C bricht ab).

    `adresse` gesetzt → Suche nach genau diesem Gerät; sonst nach dem
    Namensmuster. Rückgabe: das BLEDevice aus dem Scan — damit verbindet
    der Aufrufer sofort, solange das Sichtbarkeitsfenster noch offen ist.
    """
    ziel = adresse or "PO60 (über den Namen)"
    runde = 0
    while runden is None or runde < runden:
        runde += 1
        _taste_druecken_hinweis(erneut=runde > 1)
        print(f"Scan-Runde {runde} ({dauer:.0f} s) — suche {ziel} …")
        gefunden = await _live_scan(log, dauer, ziel_adresse=adresse, stopp_bei_kandidat=True)
        if gefunden:
            return gefunden[0]
        print("  … in dieser Runde nicht gesehen — gleich folgt die nächste (Abbruch: Strg+C).")
    log.zeile("fehler", meldung=f"{ziel} nach {runde} Runde(n) nicht gefunden")
    raise SystemExit(f"{ziel} nicht gefunden (Rundenlimit erreicht).")


async def _verbinden(geraet, log: Protokoll, *, koppeln: bool) -> BleakClient:
    """Verbindung nach dem im Repo erprobten Muster: mit einem echten
    BLEDevice (vermeidet den impliziten Scan von BleakClient bei
    Adressstrings), ohne GATT-Cache."""
    dev = geraet

    trennung = asyncio.Event()

    def _getrennt(_client) -> None:
        # Selbstabschaltung ist beim PO60 ein erwartbares (und
        # dokumentierenswertes) Verhalten — Log statt Stacktrace.
        log.zeile("status", meldung="Verbindung getrennt (vom Gerät oder OS)")
        print("⚠  Verbindung getrennt.")
        trennung.set()

    winrt = {"use_cached_services": False} if sys.platform == "win32" else {}
    client = BleakClient(dev, disconnected_callback=_getrennt, timeout=30.0, winrt=winrt)
    client._po60_trennung = trennung  # fürs Warten in den Phasen
    await client.connect()
    log.zeile("status", meldung=f"verbunden mit {dev.name} ({dev.address})")
    print(f"Verbunden: {dev.name} ({dev.address})")

    if koppeln:
        try:
            ergebnis = await client.pair()
            log.zeile("status", meldung=f"pair() -> {ergebnis}")
            print(f"Kopplung: {'ok' if ergebnis else 'fehlgeschlagen'}")
        except Exception as exc:  # Ergebnis ist selbst ein Befund
            log.zeile("fehler", meldung=f"pair() fehlgeschlagen: {exc}")
            print(f"Kopplung fehlgeschlagen: {exc}")

    return client


def _ist_zugriffsfehler(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        s in text
        for s in (
            "access",
            "denied",
            "authentication",
            "encryption",
            "authorization",
            "att error",
            "insufficient",
        )
    )


def _pairing_hinweis() -> None:
    print()
    print("Das sieht nach fehlender Kopplung aus. Zwei Wege:")
    print(" 1. Werkzeug erneut mit --koppeln starten, oder")
    print(" 2. den PO60 zuerst im Betriebssystem koppeln, während das")
    print("    Bluetooth-Symbol blinkt (Windows: Bluetooth-Einstellungen →")
    print("    Gerät hinzufügen; Linux: bluetoothctl, dort `pair <Adresse>`)")
    print("    und das Werkzeug danach erneut starten.")
    print()


# ---------------------------------------------------------------------------
# Phase: GATT-Dump
# ---------------------------------------------------------------------------


async def phase_dienste(client: BleakClient, log: Protokoll) -> None:
    print("\n— GATT-Tabelle —")
    hat = {"ff01": False, "ff02": False, "plx": False, "hr": False}

    for service in client.services:
        s_uuid = str(service.uuid).lower()
        print(f"Dienst {service.uuid}  {service.description or ''}")
        if s_uuid == po60.PLX_SERVICE_UUID:
            hat["plx"] = True
        for ch in service.characteristics:
            c_uuid = str(ch.uuid).lower()
            props = ",".join(ch.properties)
            print(f"   {ch.uuid}  [{props}]  {ch.description or ''}")
            deskriptoren = []
            for d in ch.descriptors:
                deskriptoren.append({"uuid": str(d.uuid), "beschreibung": d.description})
            log.zeile(
                "gatt",
                quelle=c_uuid,
                dekodiert={
                    "dienst": s_uuid,
                    "properties": list(ch.properties),
                    "beschreibung": ch.description,
                    "deskriptoren": deskriptoren,
                },
            )
            if c_uuid == po60.WRITE_UUID:
                hat["ff01"] = True
            if c_uuid == po60.NOTIFY_UUID:
                hat["ff02"] = True
            if c_uuid == HR_MEASUREMENT_UUID:
                hat["hr"] = True
            # Device Information (0x180A) direkt auslesen — Hersteller,
            # Modell, Firmware sind fürs Befund-Dokument Gold wert. Die
            # drei Vendor-Characteristics sind ebenfalls lesbar; besonders
            # FF03 (Funktion unbekannt) kann so etwas verraten.
            lesenswert = s_uuid == DEVICE_INFO_SERVICE or c_uuid in (
                po60.WRITE_UUID,
                po60.NOTIFY_UUID,
                po60.FF03_UUID,
            )
            if lesenswert and "read" in ch.properties:
                try:
                    wert = await client.read_gatt_char(ch)
                    text = wert.decode("utf-8", errors="replace").strip("\x00")
                    print(f"      = {bytes(wert).hex()}  ({text!r})")
                    log.zeile("gatt", quelle=c_uuid, roh=wert, dekodiert={"text": text})
                except Exception as exc:
                    log.zeile("fehler", quelle=c_uuid, meldung=f"Lesen fehlgeschlagen: {exc}")

    print("\nBefund:")
    print(f"  Proprietär FF01 (Write):  {'ja' if hat['ff01'] else 'NEIN'}")
    print(f"  Proprietär FF02 (Notify): {'ja' if hat['ff02'] else 'NEIN'}")
    print(f"  Standard-PLX 0x1822:      {'JA (!)' if hat['plx'] else 'nein'}")
    print(f"  Standard-HR 0x2A37:       {'JA (!)' if hat['hr'] else 'nein'}")
    log.zeile("status", dekodiert={"befund_dienste": hat})


# ---------------------------------------------------------------------------
# Phase: Speicherabruf
# ---------------------------------------------------------------------------


async def phase_speicher(client: BleakClient, log: Protokoll, pause: float) -> bool:
    print("\n— Speicherabruf —")
    print("Hinweis: Nach dem Abruf trennt der PO60 die Verbindung von selbst — das ist normal.")
    sammler = po60.SpeicherSammler()
    letzte_notification = [time.monotonic()]

    def _empfang(_ch, daten: bytearray) -> None:
        letzte_notification[0] = time.monotonic()
        fertig = sammler.aufnehmen(bytes(daten))
        log.zeile(
            "notify",
            quelle="ff02",
            roh=bytes(daten),
            dekodiert=[_dekodiert_dict(r) for r in fertig] or None,
        )
        for r in fertig:
            if isinstance(r, po60.HandshakeAntwort):
                print(
                    f"  Gerät meldet {r.anzahl_datensaetze} gespeicherte "
                    f"Datensätze (Prüfsumme "
                    f"{'ok' if r.pruefsumme_ok else 'FALSCH'})"
                )
            elif isinstance(r, po60.PO60Messung):
                print(f"  Datensatz {r.index}{' (letzter)' if r.letzter else ''} dekodiert")

    try:
        await client.start_notify(po60.NOTIFY_UUID, _empfang)
    except Exception as exc:
        log.zeile("fehler", meldung=f"start_notify(FF02): {exc}")
        print(f"Notify auf FF02 fehlgeschlagen: {exc}")
        if _ist_zugriffsfehler(exc):
            _pairing_hinweis()
        return False

    async def _schreiben(cmd: bytes, **log_extra) -> None:
        log.zeile("write", quelle="ff01", roh=cmd, dekodiert=log_extra or None)
        print(f"  > schreibe {cmd.hex()}")
        await client.write_gatt_char(po60.WRITE_UUID, cmd, response=False)

    async def _ruhe_abwarten() -> None:
        while time.monotonic() - letzte_notification[0] < SPEICHER_RUHE_S:
            await asyncio.sleep(0.2)
            if client._po60_trennung.is_set():
                return

    def _eindeutig() -> dict:
        """Messungen nach (index, beginn) dedupliziert, Reihenfolge stabil.

        Der Fallback (Abruf erneut ab 0) kann Duplikate in den Sammler
        spülen — die zählen nicht als Fortschritt und erscheinen nicht
        doppelt in der Ausgabe; im Log bleiben sie sichtbar.
        """
        aus = {}
        for m in sammler.messungen:
            aus.setdefault((m.index, m.beginn), m)
        return aus

    await _schreiben(po60.CMD_HANDSHAKE)
    await asyncio.sleep(pause)
    await _schreiben(po60.CMD_SPEICHER_ABRUF)
    await asyncio.sleep(pause)
    await _ruhe_abwarten()

    # Blockabruf: das Gerät liefert je Anforderung höchstens 10 Datensätze
    # (Befund Lauf 4). Solange die gemeldete Anzahl nicht erreicht ist und
    # kein Datensatz das „letzter"-Flag trägt, ab dem nächsten Index weiter
    # anfordern; bringt eine Fortsetzung nichts Neues, einmalig ab 0 erneut
    # (Duplikate zählen nicht als Fortschritt).
    fortsetzungen = 0
    fallback_benutzt = False
    while not client._po60_trennung.is_set():
        gemeldet_bisher = sammler.handshakes[0].anzahl_datensaetze if sammler.handshakes else None
        bekannt = _eindeutig()
        if gemeldet_bisher is None or len(bekannt) >= gemeldet_bisher:
            break
        if any(m.letzter for m in bekannt.values()):
            break
        vorher = len(bekannt)
        if fortsetzungen < 32:
            fortsetzungen += 1
            await _schreiben(po60.kommando_speicher_abruf(vorher), fortsetzung=vorher)
        elif not fallback_benutzt:
            fallback_benutzt = True
            await _schreiben(po60.CMD_SPEICHER_ABRUF, fallback=True)
        else:
            break
        letzte_notification[0] = time.monotonic()
        await asyncio.sleep(pause)
        await _ruhe_abwarten()
        if len(_eindeutig()) == vorher:
            if fallback_benutzt:
                break
            # Start-Index-Hypothese griff nicht — einmal Fallback ab 0.
            fortsetzungen = 32
    sammler.abschliessen()

    try:
        await client.stop_notify(po60.NOTIFY_UUID)
    except Exception:
        pass

    gemeldet = sammler.handshakes[0].anzahl_datensaetze if sammler.handshakes else None
    messungen = list(_eindeutig().values())
    print(
        f"\nErgebnis: {len(messungen)} Datensätze dekodiert"
        + (f" (Gerät meldete {gemeldet})" if gemeldet is not None else "")
        + (f", {fortsetzungen} Fortsetzungsanforderung(en)" if fortsetzungen else "")
        + f", {len(sammler.unbekannt)} unbekannte Reststücke (siehe Log)"
    )
    if messungen:
        print(f"  {'Beginn':<20} {'Ende':<9} {'Dauer':>6}  {'SpO2 min/max/Ø':<15} Puls min/max/Ø")
        for m in messungen:
            beginn = m.beginn.strftime("%d.%m.%Y %H:%M:%S") if m.beginn else "(unlesbar)"
            ende = m.ende.strftime("%H:%M:%S") if m.ende else "?"
            dauer = f"{m.dauer_s:.0f} s" if m.dauer_s is not None else "?"
            print(
                f"  {beginn:<20} {ende:<9} {dauer:>6}  "
                f"{m.spo2_min:>3}/{m.spo2_max:>3}/{m.spo2_mittel:>3}      "
                f"{m.puls_min:>3}/{m.puls_max:>3}/{m.puls_mittel:>3}"
            )
    log.zeile(
        "status",
        dekodiert={
            "befund_speicher": {
                "datensaetze": len(messungen),
                "gemeldet": gemeldet,
                "fortsetzungen": fortsetzungen,
                "unbekannt": len(sammler.unbekannt),
            }
        },
    )
    # Vollständig, wenn die Anzahl zur Gerätemeldung passt (oder das Gerät
    # gar nichts meldete und wenigstens der Ablauf ungestört durchlief).
    if gemeldet is not None:
        return len(messungen) >= gemeldet
    return not client._po60_trennung.is_set() or bool(messungen)


# ---------------------------------------------------------------------------
# Phase: Lauschen (Live-Modus-Detektion)
# ---------------------------------------------------------------------------


async def phase_lauschen(
    client: BleakClient, log: Protokoll, minuten: float, sondieren: bool, keepalive_s: float
) -> bool:
    print(f"\n— Lauschen ({minuten:g} min) —")
    print("»  Finger jetzt in den PO60 einlegen und am besten eine ganze")
    print("»  Messung durchlaufen lassen. Jede spontan eintreffende")
    print("»  Notification wird protokolliert — genau so würde ein")
    print("»  Live-Modus sichtbar. Über die Keep-Alive-Antworten ist auch")
    print("»  zu sehen, ob die Datensatzanzahl im Speicher steigt.")
    zaehler = {"gesamt": 0}
    letzte_anzahl = [None]
    sammler_je_uuid: dict[str, po60.SpeicherSammler] = {}

    def _empfang_fuer(uuid: str):
        # Je Quelle ein eigener Strom-Sammler: falls ein Live-Modus die
        # bekannten Rahmen nutzt, wird er sofort dekodiert; alles andere
        # bleibt als Roh-Hex im Log.
        sammler_je_uuid[uuid] = po60.SpeicherSammler()

        def _cb(_ch, daten: bytearray) -> None:
            zaehler["gesamt"] += 1
            fertig = sammler_je_uuid[uuid].aufnehmen(bytes(daten))
            log.zeile(
                "notify",
                quelle=uuid,
                roh=bytes(daten),
                dekodiert=[_dekodiert_dict(r) for r in fertig] or None,
            )
            print(
                f"  [{uuid[:8]}] {bytes(daten).hex()}"
                + (f"  → {', '.join(type(r).__name__ for r in fertig)}" if fertig else "")
            )
            for r in fertig:
                if isinstance(r, po60.HandshakeAntwort):
                    if letzte_anzahl[0] is not None and r.anzahl_datensaetze != letzte_anzahl[0]:
                        print(
                            f"  ★ Datensatzanzahl geändert: "
                            f"{letzte_anzahl[0]} → {r.anzahl_datensaetze} "
                            f"— eine Messung wurde gespeichert!"
                        )
                    letzte_anzahl[0] = r.anzahl_datensaetze

        return _cb

    # FF02 plus jede weitere notify-fähige Characteristic abonnieren — das
    # ist billig und maximiert den Erkundungsertrag (z. B. ein etwaiger
    # PLX-Continuous-Strom).
    abonniert = []
    for service in client.services:
        for ch in service.characteristics:
            if "notify" in ch.properties or "indicate" in ch.properties:
                try:
                    await client.start_notify(ch, _empfang_fuer(str(ch.uuid)))
                    abonniert.append(str(ch.uuid))
                except Exception as exc:
                    log.zeile("fehler", quelle=str(ch.uuid), meldung=f"start_notify: {exc}")
    print(f"Abonniert: {', '.join(abonniert) or 'nichts (!)'}")
    log.zeile("status", dekodiert={"lauschen_abonniert": abonniert})

    if sondieren:
        print("Sondiere Kandidatenkommandos (spekulativ, siehe Quelltext) …")
        for cmd in SONDIER_KOMMANDOS:
            if client._po60_trennung.is_set():
                break
            log.zeile("write", quelle="ff01", roh=cmd, dekodiert={"sondierung": True})
            print(f"  > sondiere {cmd.hex()}")
            try:
                await client.write_gatt_char(po60.WRITE_UUID, cmd, response=False)
            except Exception as exc:
                log.zeile("fehler", meldung=f"Sondierung {cmd.hex()}: {exc}")
            await asyncio.sleep(SONDIER_ANTWORTFENSTER_S)

    # Keep-Alive: Der PO60 trennt eine untätige Verbindung nach ~35 s von
    # selbst (Befund Lauf 3). Der Handshake ist die harmloseste bekannte
    # Aktivität — und seine Antwort meldet nebenbei die Datensatzanzahl.
    ende = time.monotonic() + minuten * 60.0
    naechster_keepalive = time.monotonic() + keepalive_s
    durchgehalten = True
    try:
        while time.monotonic() < ende:
            if client._po60_trennung.is_set():
                print(
                    "Gerät hat getrennt — Lauschphase endet. (Wann das "
                    "passiert, ist selbst ein Befund — steht im Log.)"
                )
                durchgehalten = False
                break
            if keepalive_s > 0 and time.monotonic() >= naechster_keepalive:
                naechster_keepalive += keepalive_s
                log.zeile(
                    "write", quelle="ff01", roh=po60.CMD_HANDSHAKE, dekodiert={"keepalive": True}
                )
                try:
                    await client.write_gatt_char(
                        po60.WRITE_UUID, po60.CMD_HANDSHAKE, response=False
                    )
                except Exception as exc:
                    log.zeile("fehler", meldung=f"Keep-Alive: {exc}")
            await asyncio.sleep(0.5)
    finally:
        for uuid in abonniert:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass

    print(f"Lauschen beendet: {zaehler['gesamt']} Notification(s) empfangen.")
    log.zeile(
        "status",
        dekodiert={
            "lauschen_empfangen": zaehler["gesamt"],
            "lauschen_durchgehalten": durchgehalten,
        },
    )
    return durchgehalten


# ---------------------------------------------------------------------------
# Subkommandos
# ---------------------------------------------------------------------------


async def _mit_verbindung(args, log: Protokoll, phasen) -> None:
    """Phasen nacheinander ausführen; bricht die Verbindung ab (der PO60
    trennt untätige Verbindungen selbst), wird neu gesucht, neu verbunden
    und die unterbrochene Phase EINMAL wiederholt."""
    client = None

    async def _neu_verbinden():
        nonlocal client
        geraet = await _geraet_suchen(log, args.adresse, args.dauer, args.runden)
        client = await _verbinden(geraet, log, koppeln=args.koppeln)

    await _neu_verbinden()
    try:
        i = 0
        wiederholt: set[int] = set()
        while i < len(phasen):
            if client._po60_trennung.is_set():
                print("\nVerbindung ist weg — der PO60 muss neu geweckt werden.")
                log.zeile("status", meldung="Wiederverbindung wird versucht")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                await _neu_verbinden()
            vollstaendig = await phasen[i](client)
            if vollstaendig is False and client._po60_trennung.is_set() and i not in wiederholt:
                wiederholt.add(i)  # unterbrochene Phase einmal wiederholen
                continue
            i += 1
    except Exception as exc:
        log.zeile("fehler", meldung=str(exc))
        if _ist_zugriffsfehler(exc):
            _pairing_hinweis()
        raise
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def cmd_scan(args, log: Protokoll) -> None:
    """Reine Bestandsaufnahme: volle Rundendauer, kein Frühabbruch."""
    _taste_druecken_hinweis()
    print(f"Scanne {args.dauer:.0f} s (live) …")
    kandidaten = await _live_scan(log, args.dauer)
    if kandidaten:
        print(f"\n{len(kandidaten)} PO60-Kandidat(en): " + ", ".join(d.address for d in kandidaten))
    else:
        print(
            "\nKein Gerät mit PO60-typischem Namen gesehen. Falls die "
            "Adresse bekannt ist: nächsten Schritt mit --adresse aufrufen."
        )


async def cmd_dienste(args, log: Protokoll) -> None:
    await _mit_verbindung(args, log, [lambda c: phase_dienste(c, log)])


async def cmd_speicher(args, log: Protokoll) -> None:
    await _mit_verbindung(args, log, [lambda c: phase_speicher(c, log, args.pause)])


async def cmd_lauschen(args, log: Protokoll) -> None:
    await _mit_verbindung(
        args, log, [lambda c: phase_lauschen(c, log, args.minuten, args.sondieren, args.keepalive)]
    )


async def cmd_alles(args, log: Protokoll) -> None:
    # Lauschen VOR dem Speicherabruf: der Abruf provoziert die
    # Selbsttrennung des Geräts (Befund Lauf 2) — danach ist keine
    # Live-Modus-Erkundung mehr möglich.
    await _mit_verbindung(
        args,
        log,
        [
            lambda c: phase_dienste(c, log),
            lambda c: phase_lauschen(c, log, args.minuten, args.sondieren, args.keepalive),
            lambda c: phase_speicher(c, log, args.pause),
        ],
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(
        description="Beurer PO60 erkunden: GATT-Dump, Speicherabruf, "
        "Live-Modus-Detektion. Alles landet roh in einer "
        "JSONL-Datei."
    )
    ap.add_argument(
        "--log-verzeichnis",
        default=os.path.join(repo_root, "Logs", "po60"),
        help="Ablage der JSONL-Protokolle (Vorgabe: Logs/po60/, git-ignoriert)",
    )
    sub = ap.add_subparsers(dest="befehl", required=True)

    def _mit_geraet(p):
        p.add_argument("--adresse", required=True, help="Bluetooth-Adresse des PO60 (siehe scan)")
        p.add_argument(
            "--koppeln",
            action="store_true",
            help="nach dem Verbinden eine Kopplung versuchen (bei Zugriffsfehlern nötig)",
        )
        p.add_argument(
            "--dauer",
            type=float,
            default=20.0,
            help="Dauer einer Scan-Runde in Sekunden (Vorgabe: 20)",
        )
        p.add_argument(
            "--runden",
            type=int,
            default=None,
            help="Obergrenze der Scan-Runden (Vorgabe: unbegrenzt, Abbruch mit Strg+C)",
        )

    p = sub.add_parser("scan", help="Umgebung live scannen, PO60-Kandidaten sofort zeigen")
    p.add_argument("--dauer", type=float, default=20.0, help="Scandauer in Sekunden (Vorgabe: 20)")

    p = sub.add_parser("dienste", help="GATT-Tabelle des Geräts dumpen")
    _mit_geraet(p)

    p = sub.add_parser("speicher", help="Gespeicherte Messungen abrufen")
    _mit_geraet(p)
    p.add_argument(
        "--pause",
        type=float,
        default=po60.HANDSHAKE_PAUSE_S,
        help="Pause zwischen Handshake und Abruf (Vorgabe: 0,5 s)",
    )

    p = sub.add_parser(
        "lauschen",
        help="Verbunden bleiben und spontane Pakete protokollieren (Live-Modus-Detektion)",
    )
    _mit_geraet(p)
    p.add_argument("--minuten", type=float, default=5.0, help="Lauschdauer (Vorgabe: 5 min)")
    p.add_argument(
        "--sondieren",
        action="store_true",
        help="zusätzlich spekulative Kandidatenkommandos senden (Vorgabe: aus)",
    )
    p.add_argument(
        "--keepalive",
        type=float,
        default=15.0,
        help="Keep-Alive-Handshake alle N Sekunden — der PO60 "
        "trennt untätige Verbindungen nach ~35 s "
        "(Vorgabe: 15; 0 = aus)",
    )

    p = sub.add_parser(
        "alles",
        help="Suchen → GATT-Dump → Lauschen → Speicherabruf "
        "in einem Durchgang (Standard am Gerät; der "
        "Speicherabruf kommt zuletzt, weil das Gerät "
        "danach selbst trennt)",
    )
    p.add_argument(
        "--adresse",
        default=None,
        help="bekannte Adresse des PO60 (empfohlen); ohne Angabe wird über den Gerätenamen gesucht",
    )
    p.add_argument(
        "--koppeln", action="store_true", help="nach dem Verbinden eine Kopplung versuchen"
    )
    p.add_argument(
        "--dauer", type=float, default=20.0, help="Dauer einer Scan-Runde (s, Vorgabe: 20)"
    )
    p.add_argument(
        "--runden", type=int, default=None, help="Obergrenze der Scan-Runden (Vorgabe: unbegrenzt)"
    )
    p.add_argument(
        "--pause",
        type=float,
        default=po60.HANDSHAKE_PAUSE_S,
        help="Pause zwischen Handshake und Abruf",
    )
    p.add_argument("--minuten", type=float, default=5.0, help="Lauschdauer")
    p.add_argument(
        "--sondieren", action="store_true", help="spekulative Kandidatenkommandos senden"
    )
    p.add_argument(
        "--keepalive",
        type=float,
        default=15.0,
        help="Keep-Alive-Handshake alle N Sekunden in der Lauschphase (Vorgabe: 15; 0 = aus)",
    )

    args = ap.parse_args(argv)

    log = Protokoll(args.log_verzeichnis)
    print(f"Protokoll: {log.pfad}")
    log.zeile(
        "status",
        meldung=f"Start: {args.befehl}",
        dekodiert={k: v for k, v in vars(args).items() if k not in ("befehl",)},
    )

    laeufer = {
        "scan": cmd_scan,
        "dienste": cmd_dienste,
        "speicher": cmd_speicher,
        "lauschen": cmd_lauschen,
        "alles": cmd_alles,
    }[args.befehl]
    try:
        asyncio.run(laeufer(args, log))
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        log.zeile("status", meldung="Abbruch durch Benutzer")
    except SystemExit as exc:
        if exc.code not in (0, None):
            print(exc)
            log.zeile("fehler", meldung=str(exc))
            return 1
    except Exception as exc:
        # Ein kaputter/fehlender Bluetooth-Stack ist am fremden Rechner der
        # häufigste Fall — der Anwender braucht eine Ansage, keinen Traceback.
        print(f"\nFehler: {exc}")
        print("Ist Bluetooth am Rechner eingeschaltet und verfügbar?")
        if _ist_zugriffsfehler(exc):
            _pairing_hinweis()
        log.zeile("fehler", meldung=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        log.zeile("status", meldung="Ende")
        log.schliessen()
        print(f"\nProtokoll gespeichert: {log.pfad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 9.3 `tests/test_po60.py`

```python
"""
tests/test_po60.py
------------------
Beurer PO60 — Kommandos und Datensatz-Parser.

Kommandos, Prüfsummenregel und das 24-Byte-Datensatzlayout sind am echten
Gerät bestätigt (FW V7.3, Erkundungslauf 14.08.2026). Die Golden-Vector-
Tests unten verwenden die Original-Notifications dieses Laufs — ändert
sich am Parser etwas, das diese Bytes anders liest, ist das ein Fehler,
kein Refactoring. Befunde und offene Fragen: `docs/beurer_po60_erkundung.md`.

Run:  python -m pytest tests/test_po60.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensors.devices import po60  # noqa: E402


# ---------------------------------------------------------------------------
# Golden Vectors: die 12 Speicherabruf-Notifications vom echten Gerät
# (PO60 FW V7.3, 14.08.2026) — 240 Bytes = 10 Datensätze à 24 Byte.
# ---------------------------------------------------------------------------

GERAETE_NOTIFICATIONS = [
    "e90013010100000e130101000102000031616161",
    "4a44484ee901130101010f241301010113000001",
    "4d625f5f5345492be9021a080d1600191a080d16",
    "0219000079625f6049464719e9031a080d160500",
    "1a080d1605100000116060604a464617e9041a08",
    "0d1607171a080d16092800010a6060604a454747",
    "e9051a080d160a0a1a080d160c12000101625f60",
    "4a444621e9061a080d1619021a080d1619210000",
    "20636161504a4b78e9071a080e0639241a080e06",
    "3a0d00002663626237363670e9081a080e063b15",
    "1a080e063b170000036262623232323ee9491a08",
    "0e063b361a080e07000000000762626239393968",
]

GERAETE_HANDSHAKE = "e0050a000a0079"


def _sammler_mit_geraetestrom() -> po60.SpeicherSammler:
    s = po60.SpeicherSammler()
    for hexpaket in GERAETE_NOTIFICATIONS:
        s.aufnehmen(bytes.fromhex(hexpaket))
    s.abschliessen()
    return s


# ---------------------------------------------------------------------------
# Kommandos
# ---------------------------------------------------------------------------


def test_kommandos_sind_byteweise_eingefroren():
    """Die beiden bestätigten Kommandos dürfen sich nie still ändern.

    Die Prüfsumme wird berechnet — ändert jemand die Prüfsummenregel,
    ändert sich das Gesendete, und genau das sollen diese Bytes verhindern.
    """
    assert po60.CMD_HANDSHAKE.hex() == "900515"
    assert po60.CMD_SPEICHER_ABRUF.hex() == "990019"


def test_pruefsumme_ist_summe_und_7bit_maske():
    assert po60.pruefsumme(bytes([0x90, 0x05])) == 0x15
    assert po60.pruefsumme(bytes([0x99, 0x00])) == 0x19
    # Überlauf über 0x7F hinaus wird gekappt, nicht moduliert o. Ä.
    assert po60.pruefsumme(bytes([0xFF, 0xFF])) == (0xFF + 0xFF) & 0x7F
    assert po60.kommando(0x90, 0x05) == bytes([0x90, 0x05, 0x15])


def test_speicher_abruf_mit_start_index():
    """Blockabruf-Hypothese (Lauf 4): zweites Byte = Start-Index."""
    assert po60.kommando_speicher_abruf(0).hex() == "990019"
    assert po60.kommando_speicher_abruf(0) == po60.CMD_SPEICHER_ABRUF
    assert po60.kommando_speicher_abruf(10).hex() == "990a23"


# ---------------------------------------------------------------------------
# Namens-Heuristik
# ---------------------------------------------------------------------------


def test_namens_heuristik():
    for name in ("PO60", "po60", "PO 60", "Beurer PO60", "beurer po 60"):
        assert po60.sieht_nach_po60_aus(name)
    for name in (None, "", "Polar H10", "[TV] Samsung 7 Series (55)"):
        assert not po60.sieht_nach_po60_aus(name)


# ---------------------------------------------------------------------------
# Handshake-Antwort
# ---------------------------------------------------------------------------


def test_handshake_antwort_vom_geraet():
    h = po60.parse_handshake(bytes.fromhex(GERAETE_HANDSHAKE))
    assert h is not None
    assert h.anzahl_datensaetze == 10
    assert h.pruefsumme_ok
    assert h.roh == bytes.fromhex(GERAETE_HANDSHAKE)


def test_handshake_falsche_laenge_oder_kopf_ergibt_none():
    assert po60.parse_handshake(b"") is None
    assert po60.parse_handshake(bytes.fromhex("e0050a000a00")) is None
    assert po60.parse_handshake(bytes.fromhex("e1050a000a0079")) is None


# ---------------------------------------------------------------------------
# Datensatz-Parser am echten Strom
# ---------------------------------------------------------------------------


def test_geraetestrom_liefert_alle_zehn_datensaetze():
    s = _sammler_mit_geraetestrom()
    assert len(s.messungen) == 10
    assert [m.index for m in s.messungen] == list(range(10))
    # Prüfsummen-Filter hat gearbeitet und nichts blieb übrig:
    assert not s.unbekannt
    # Nur der letzte Datensatz trägt das Ende-Flag (Byte 1 = 0x49).
    assert [m.letzter for m in s.messungen] == [False] * 9 + [True]


def test_geraetestrom_stichprobe_datensatz_0():
    """Werksuhr-Messung: Jahr-Byte 0x13 → 2019 (Uhr war nie gestellt)."""
    m = _sammler_mit_geraetestrom().messungen[0]
    assert m.beginn == datetime(2019, 1, 1, 0, 0, 14)
    assert m.ende == datetime(2019, 1, 1, 0, 1, 2)
    assert (m.spo2_max, m.spo2_min, m.spo2_mittel) == (97, 97, 97)
    assert (m.puls_max, m.puls_min, m.puls_mittel) == (74, 68, 72)
    assert m.dauer_s == 48.0
    assert m.abtastungen == 49  # Dauer + 1 (1 Hz, Endpunkte inkl.)


def test_geraetestrom_stichprobe_datensatz_5():
    """Echte Messung vom Vorabend des Erkundungslaufs."""
    m = _sammler_mit_geraetestrom().messungen[5]
    assert m.beginn == datetime(2026, 8, 13, 22, 10, 10)
    assert m.ende == datetime(2026, 8, 13, 22, 12, 18)
    assert (m.spo2_max, m.spo2_min, m.spo2_mittel) == (98, 95, 96)
    assert (m.puls_max, m.puls_min, m.puls_mittel) == (74, 68, 70)
    # Abtastanzahl ist BASIS-128-kodiert (7-Bit-Bytes): 0x01 0x01 → 129.
    assert m.dauer_s == 128.0
    assert m.abtastungen == 129


def test_abtastanzahl_ist_dauer_plus_eins_bei_allen_datensaetzen():
    for m in _sammler_mit_geraetestrom().messungen:
        assert m.abtastungen == m.dauer_s + 1


def test_letzter_flag_wandert_mit_dem_speicherstand():
    """Golden Vector aus Lauf 4: derselbe Datensatz 9 kam erneut, aber OHNE
    „letzter"-Flag (Byte 1: 0x49 → 0x09, Prüfsumme 0x68 → 0x28), weil der
    Speicher inzwischen 15 Datensätze hatte. Das Flag ist Zustands-, nicht
    Inhaltsbestandteil — beide Varianten müssen identische Werte liefern."""
    mit_flag = _sammler_mit_geraetestrom().messungen[9]

    ohne_flag_hex = "e9091a080e063b361a080e07000000000762626239393928"
    ohne_flag = po60.parse_datensatz(bytes.fromhex(ohne_flag_hex))
    assert ohne_flag is not None
    assert not ohne_flag.letzter and mit_flag.letzter
    for feld in (
        "index",
        "beginn",
        "ende",
        "abtastungen",
        "spo2_max",
        "spo2_min",
        "spo2_mittel",
        "puls_max",
        "puls_min",
        "puls_mittel",
    ):
        assert getattr(ohne_flag, feld) == getattr(mit_flag, feld)


def test_handshake_mitten_im_strom_wird_erkannt():
    s = po60.SpeicherSammler()
    s.aufnehmen(bytes.fromhex(GERAETE_HANDSHAKE))
    for hexpaket in GERAETE_NOTIFICATIONS:
        s.aufnehmen(bytes.fromhex(hexpaket))
    s.abschliessen()
    assert len(s.handshakes) == 1
    assert s.handshakes[0].anzahl_datensaetze == 10
    assert len(s.messungen) == 10


# ---------------------------------------------------------------------------
# Ränder und Störungen (synthetisch)
# ---------------------------------------------------------------------------


def _datensatz(index=0, letzter=False) -> bytes:
    """Einen gültigen 24-Byte-Datensatz bauen (Prüfsumme berechnet)."""
    b = bytearray(24)
    b[0] = po60.KOPF_SPEICHER
    b[1] = (index & 0x0F) | (0x40 if letzter else 0)
    b[2:8] = bytes([26, 8, 14, 7, 0, 0])
    b[8:14] = bytes([26, 8, 14, 7, 0, 30])
    b[14:17] = bytes([0, 0, 31])
    b[17:20] = bytes([98, 95, 96])
    b[20:23] = bytes([74, 68, 70])
    b[23] = po60.pruefsumme(bytes(b[:23]))
    return bytes(b)


def test_datensatz_byteweise_gestueckelt():
    """Auch bei 1-Byte-Häppchen (extremste Chunk-Grenze) kommt alles an."""
    s = po60.SpeicherSammler()
    for byte in _datensatz(index=3):
        s.aufnehmen(bytes([byte]))
    s.abschliessen()
    assert len(s.messungen) == 1
    assert s.messungen[0].index == 3
    assert not s.unbekannt


def test_kaputte_pruefsumme_wird_nicht_zum_datensatz():
    kaputt = bytearray(_datensatz())
    kaputt[23] ^= 0x01
    s = po60.SpeicherSammler()
    s.aufnehmen(bytes(kaputt))
    s.abschliessen()
    assert not s.messungen
    assert len(s.unbekannt) == 1
    assert s.unbekannt[0].roh == bytes(kaputt)


def test_muell_zwischen_datensaetzen_bleibt_erhalten():
    s = po60.SpeicherSammler()
    s.aufnehmen(b"\xaa\xbb" + _datensatz(index=1) + b"\xcc" + _datensatz(index=2, letzter=True))
    s.abschliessen()
    assert [m.index for m in s.messungen] == [1, 2]
    assert s.messungen[1].letzter
    assert [u.roh for u in s.unbekannt] == [b"\xaa\xbb", b"\xcc"]


def test_e9_in_nutzdaten_verschiebt_die_suche_nur_um_ein_byte():
    """Ein 0xE9 im Müll darf keinen Datensatz verschlucken, der direkt
    dahinter beginnt."""
    s = po60.SpeicherSammler()
    s.aufnehmen(bytes([0xE9, 0x00, 0x00]) + _datensatz(index=4))
    s.abschliessen()
    assert [m.index for m in s.messungen] == [4]
    assert len(s.unbekannt) == 1
    assert s.unbekannt[0].roh == bytes([0xE9, 0x00, 0x00])


def test_leerer_und_kaputter_zeitstempel():
    assert po60.parse_datensatz(b"") is None
    kaputt = bytearray(_datensatz())
    kaputt[3] = 13  # Monat 13
    kaputt[23] = po60.pruefsumme(bytes(kaputt[:23]))
    m = po60.parse_datensatz(bytes(kaputt))
    assert m is not None
    assert m.beginn is None  # None statt Exception
    assert m.dauer_s is None


def test_unvollstaendiger_datensatz_wird_beim_abschliessen_rest():
    s = po60.SpeicherSammler()
    s.aufnehmen(_datensatz()[:10])
    assert not s.messungen and not s.unbekannt  # wartet noch auf Bytes
    s.abschliessen()
    assert len(s.unbekannt) == 1
    assert s.unbekannt[0].laenge == 10


# ---------------------------------------------------------------------------
# Abhängigkeiten
# ---------------------------------------------------------------------------


def test_importiert_ohne_bleak_und_ohne_pyside():
    """Das Modul ist reines Python — Voraussetzung dafür, dass es später
    unverändert unter ein Geräteprofil wandern kann (Muster `pmd.py`)."""
    import inspect

    quelle = inspect.getsource(po60)
    assert "import bleak" not in quelle
    assert "PySide6" not in quelle
```

### 9.4 `pollen`-Erweiterung von `tools/po60_erkundung.py`

Das Pull-Experiment (Einzelwert-Abfrage während einer laufenden Messung).
Aufruf: `.venv/Scripts/python.exe tools/po60_erkundung.py pollen --adresse C9:49:AC:1E:4B:00`
(Vorgabe: 3 min, alle 10 s; `--poll-intervall 15` für den Handshake-Takt).

> **Ergebnis (Lauf 5, 14.08.2026 — siehe §2 und `beurer_po60_erkundung.md` §4):**
> Pull weitgehend widerlegt. `90 00`…`90 0f` blieben ohne Antwort, kein
> Read/Notify trug ein schwankendes Vitalbyte. Vermutliche Ursache: Im
> Sync-Modus ist die Mess-LED aus — das Gerät misst nicht. Auf Windows war
> zudem ein Bonding nötig (`--koppeln`/OS-Pairing), sonst „Insufficient
> Authentication". Der Code unten ist der Stand, mit dem dieser Befund
> entstand.

**Idee:** Das zweite Handshake-Byte ist vermutlich ein „Report-Typ"
(`90 05` → gespeicherte Anzahl). Das Werkzeug sendet daher `90 00`…`90 0f`
je einmal (Entdeckung), pollt danach die antwortenden Kommandos zyklisch und
liest zusätzlich FF03/FF02/FF01 — jeweils mit Markierung geänderter Bytes.
Ein SpO₂-/Puls-Byte schwankt von Runde zu Runde, ein statisches Register
nicht. Bewusst **nur die 0x90-Familie** (read-only bekannt), nichts, was
löschen/schreiben/zurücksetzen könnte.

Folgender Code kommt zum Stand aus §9.2 hinzu:

**Konstanten** (nach `SPEICHER_RUHE_S`):

```python
# Kandidaten für die Einzelwert-Abfrage (Pull, Subkommando `pollen`).
# Hypothese: das zweite Byte des Handshakes ist ein „Report-Typ" — 0x90 05
# liefert die gespeicherte Anzahl (Antwort e0 05 …), also liefert vielleicht
# ein anderer Report-Typ den AKTUELLEN Messwert. Deshalb die 0x90-Familie
# durchprobieren. BEWUSST nur diese eine, als read-only bekannte
# Kommandofamilie (0x90 05 ist der harmlose Handshake) — keine fremden
# Opcodes, die löschen/schreiben/zurücksetzen könnten.
POLL_KOMMANDOS: tuple[bytes, ...] = tuple(po60.kommando(0x90, n) for n in range(0x10))
POLL_ANTWORTFENSTER_S = 0.8  # Wartezeit auf eine Antwort nach dem Senden
```

**Phase und Hilfsfunktion** (vor dem Abschnitt „Subkommandos"):

```python
def _aenderungen(neu: bytes, alt) -> list:
    """Bytepositionen, die sich gegenüber der letzten Antwort geändert haben.

    Das ist das eigentliche Suchsignal: ein SpO₂-/Puls-Byte schwankt von
    Abfrage zu Abfrage, ein statisches Register (Version, Nullpuffer) nicht.
    """
    if alt is None:
        return []
    return [f"[{i}] {alt[i]}→{neu[i]}" for i in range(min(len(neu), len(alt))) if neu[i] != alt[i]]


async def phase_pollen(
    client: BleakClient, log: Protokoll, minuten: float, poll_intervall: float
) -> bool:
    print(f"\n— Pollen / Einzelwert-Abfrage ({minuten:g} min, alle {poll_intervall:g}s) —")
    print("»  Finger in den PO60 legen und eine Messung LAUFEN lassen. Ziel:")
    print("»  herausfinden, ob sich der AKTUELLE Wert abfragen lässt (Pull).")
    print("»  Tipp: zwischendurch tief durchatmen / den Finger leicht bewegen,")
    print("»  damit SpO₂/Puls schwanken — nur so verrät sich ein Vitalwert-Byte.")
    print("»  Orientierung in Hex: SpO₂ 97 = 0x61, Puls 72 = 0x48.")

    empfangen = []  # (uuid, roh) je Notification

    def _mk(uuid: str):
        samm = po60.SpeicherSammler()

        def _cb(_ch, daten: bytearray) -> None:
            b = bytes(daten)
            fertig = samm.aufnehmen(b)
            empfangen.append((uuid, b))
            log.zeile(
                "notify", quelle=uuid, roh=b, dekodiert=[_dekodiert_dict(r) for r in fertig] or None
            )

        return _cb

    abonniert = []
    for service in client.services:
        for ch in service.characteristics:
            if "notify" in ch.properties or "indicate" in ch.properties:
                try:
                    await client.start_notify(ch, _mk(str(ch.uuid)))
                    abonniert.append(str(ch.uuid))
                except Exception as exc:
                    log.zeile("fehler", quelle=str(ch.uuid), meldung=f"start_notify: {exc}")
    print(f"Abonniert: {', '.join(abonniert) or 'nichts (!)'}")

    # FF03 (Vendor, Funktion unbekannt) ist der Hauptverdächtige fürs
    # Read-Polling; FF02/FF01 lieferten im Ruhezustand nur Nullen — vielleicht
    # füllen sie sich während einer Messung.
    read_uuids = [po60.FF03_UUID, po60.NOTIFY_UUID, po60.WRITE_UUID]
    letzte_reads: dict = {}
    letzte_antwort: dict = {}

    async def _warten(sekunden: float) -> None:
        ziel = time.monotonic() + sekunden
        while time.monotonic() < ziel and not client._po60_trennung.is_set():
            await asyncio.sleep(min(0.4, max(0.05, ziel - time.monotonic())))

    async def _senden_sammeln(cmd: bytes) -> bytes:
        vor = len(empfangen)
        log.zeile("write", quelle="ff01", roh=cmd, dekodiert={"poll": True})
        try:
            await client.write_gatt_char(po60.WRITE_UUID, cmd, response=False)
        except Exception as exc:
            log.zeile("fehler", meldung=f"Poll {cmd.hex()}: {exc}")
            return b""
        await _warten(POLL_ANTWORTFENSTER_S)
        return b"".join(b for _, b in empfangen[vor:])

    async def _reads() -> None:
        for uuid in read_uuids:
            try:
                wert = bytes(await client.read_gatt_char(uuid))
            except Exception as exc:
                log.zeile("fehler", quelle=uuid, meldung=f"read: {exc}")
                continue
            aend = _aenderungen(wert, letzte_reads.get(uuid))
            log.zeile("read", quelle=uuid, roh=wert, dekodiert={"aenderungen": aend or None})
            hinweis = f"  ★ {', '.join(aend)}" if aend else ""
            print(f"    read {uuid[:8]} = {wert.hex()}{hinweis}")
            letzte_reads[uuid] = wert

    # --- Entdeckung: welcher 0x90-Report-Typ antwortet überhaupt? ---
    print("\n[Entdeckung] 0x90-Report-Varianten je einmal senden …")
    kandidaten = []
    for cmd in POLL_KOMMANDOS:
        if client._po60_trennung.is_set():
            break
        antwort = await _senden_sammeln(cmd)
        if antwort:
            kandidaten.append(cmd)
            letzte_antwort[cmd.hex()] = antwort
            print(f"  {cmd.hex()} → {antwort.hex()}")
        else:
            print(f"  {cmd.hex()} → (keine Antwort)")
    log.zeile("status", dekodiert={"poll_kandidaten": [c.hex() for c in kandidaten]})
    if kandidaten:
        print(f"\nAntwortende Kommandos: {', '.join(c.hex() for c in kandidaten)}")
    else:
        print("\nKein 0x90-Kommando antwortet — ein Pull über die 0x90-Familie")
        print("existiert damit nicht. Es bleibt der Read-Weg (FF03 & Co.),")
        print("der unten weiter beobachtet wird.")

    # --- Poll-Schleife: Reads + antwortende Kommandos zyklisch, Änderungen
    #     markiert. Die Poll-Schreibzugriffe halten die Verbindung zugleich
    #     wach (< 35 s Idle-Timeout, Befund Lauf 3) — kein eigenes Keep-Alive
    #     nötig, solange poll_intervall klein genug bleibt. ---
    if poll_intervall > 30:
        print(
            "⚠  poll-intervall > 30 s — das Gerät könnte zwischendurch wegen Idle-Timeout trennen."
        )
    ende = time.monotonic() + minuten * 60.0
    durchgehalten = True
    try:
        while time.monotonic() < ende:
            if client._po60_trennung.is_set():
                durchgehalten = False
                print("Gerät hat getrennt — Pollphase endet.")
                break
            runde_start = time.monotonic()
            print(f"\n— {datetime.now():%H:%M:%S} —")
            await _reads()
            for cmd in kandidaten or [po60.CMD_HANDSHAKE]:
                if client._po60_trennung.is_set():
                    break
                antwort = await _senden_sammeln(cmd)
                if not antwort:
                    print(f"    {cmd.hex()} → (keine Antwort)")
                    continue
                aend = _aenderungen(antwort, letzte_antwort.get(cmd.hex()))
                letzte_antwort[cmd.hex()] = antwort
                hinweis = f"  ★ ändert sich: {', '.join(aend)}" if aend else ""
                print(f"    {cmd.hex()} → {antwort.hex()}{hinweis}")
            rest = poll_intervall - (time.monotonic() - runde_start)
            if rest > 0:
                await _warten(rest)
    finally:
        for uuid in abonniert:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass

    print("\nPollen beendet. Auswertung: Ein Byte (in einem Read ODER in einer")
    print("Kommandoantwort), das über die Runden in plausiblen Grenzen")
    print("schwankt (SpO₂ ~90–100, Puls ~40–180), ist der gesuchte Live-Wert.")
    print("Alles roh im JSONL-Protokoll.")
    log.zeile("status", dekodiert={"poll_durchgehalten": durchgehalten})
    return durchgehalten
```

**Subkommando** (neben `cmd_lauschen`):

```python
async def cmd_pollen(args, log: Protokoll) -> None:
    await _mit_verbindung(
        args, log, [lambda c: phase_pollen(c, log, args.minuten, args.poll_intervall)]
    )
```

**Parser** (neben den anderen `sub.add_parser`-Blöcken) und Dispatch:

```python
    p = sub.add_parser("pollen",
                       help="Während einer laufenden Messung versuchen, den "
                            "AKTUELLEN Wert abzufragen (Pull-Experiment): "
                            "0x90-Report-Sweep + zyklische Reads von FF03 & Co., "
                            "geänderte Bytes markiert")
    _mit_geraet(p)
    p.add_argument("--minuten", type=float, default=3.0,
                   help="Dauer der Pollphase (Vorgabe: 3 min)")
    p.add_argument("--poll-intervall", type=float, default=10.0,
                   help="Abstand der Abfragen in Sekunden (Vorgabe: 10; "
                        "15 = Handshake-Takt ist auch ok)")

# … und im laeufer-dict:  "pollen": cmd_pollen,
```