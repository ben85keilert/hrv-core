# Beurer PO60 — Übergabe an die lokale Weiterarbeit

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

> **Überholt (2026-08-14).** Der Live-Versuch ist abgeschlossen und ergebnislos:
> Der PO60 gibt über BLE keinen Live-Datenstrom her. **Lauf 6 hat den letzten
> offenen Test (Messung ⇄ Sync gleichzeitig) beidseitig geführt und verneint:**
> im Sync misst das Gerät nicht (LED aus, Report-Typen null), und während einer
> laufenden Messung lässt es sich gar nicht erst verbinden. Messung und
> BLE-Verbindung schließen sich aus. Auch der Blockabruf-Start-Index (`99 0a`)
> ist widerlegt. Die unten stehende „Nächste-Schritte-für-Live"-Liste ist damit
> **gegenstandslos**. Details: [`beurer_po60_erkundung.md`](beurer_po60_erkundung.md)
> §4 (Lauf 6). Maßgeblich für die Entscheidung ist der Schlussstein
> [`beurer_po60_exkurs.md`](beurer_po60_exkurs.md). Dieses Dokument bleibt nur
> als Fahrtenbuch bestehen.

> **Weiterarbeit ab hier — Linux T480 (Stand nach Lauf 5, 14.08.2026).** Der
> Pull-Versuch (`pollen`) auf Windows ist gelaufen und **weitgehend widerlegt**:
> `90 00`…`90 0f` antworten nicht, kein Read/Notify trägt ein schwankendes
> Vitalbyte. Der entscheidende Grund: **im Sync-Modus ist die Mess-LED des
> Sensors aus — das Gerät misst dann nicht.** Es bleibt genau **ein** offener
> Live-Test: eine Messung erzwingen, *während* die Sync-Verbindung steht (Finger
> einlegen bei laufendem Sync / blinkendem BT-Symbol) und prüfen, ob die LED
> angeht und dann doch ein Momentanwert durchkommt. Kann das Gerät beides nicht
> parallel, ist der Live-Weg endgültig zu.
>
> Zwei Plattform-Notizen für die Linux-Fortsetzung: (1) **Bonding** war unter
> Windows/WinRT nötig (sonst „Insufficient Authentication"); unter **Linux/BlueZ
> lief Notify unpaarig** (Läufe 2–4) — falls es dort doch klemmt: `--koppeln`
> oder `bluetoothctl → pair C9:49:AC:1E:4B:00`. (2) Aufruf auf Linux mit
> `python3` bzw. `.venv/bin/python` statt `.venv/Scripts/python.exe`.
> Vollständiger Lauf-5-Befund: [`beurer_po60_erkundung.md`](beurer_po60_erkundung.md) §4.

Stand: 2026-08-14 · Herkunft: Remote-Erkundungssitzung
(<https://claude.ai/code/session_014iMA3vocxcfpzHuoRXnMB4>, Läufe 1–4 am
echten Gerät) · Arbeitsbranch: `claude/beurer-po60-hrv-in6wvk`

Dieses Dokument ist der Einstiegspunkt für die Fortsetzung mit lokalem
Claude Code (PyCharm, Gerät direkt am Rechner). Es fasst zusammen, was
erreicht ist, wo alles liegt und welche Schritte für den **Versuch einer
Live-Anbindung** übrig sind. Es liest sich eigenständig — die Chat-Historie
der Remote-Sitzung wird nicht benötigt.

## Auftrag und Stand in drei Sätzen

Der Beurer PO60 (Fingerpulsoximeter) soll die HRV-Messung der Praxis-GUI
ergänzen; in vier Erkundungsläufen am echten Gerät wurde sein proprietäres
BLE-Protokoll fast vollständig entschlüsselt (Speicherabruf inkl.
Byte-Layout, Prüfsummen, Zeitstempeln — alles Golden-Vector-getestet).
**Einen spontanen Live-Datenstrom gibt es nach jetzigem Befund nicht**:
5 Minuten gehaltene Verbindung mit Finger im Gerät lieferten außer
Handshake-Antworten keine einzige Notification. Der verbleibende Weg zu
„live" ist die Suche nach einem unbekannten Triggerkommando (Sondierung)
bzw. die Beobachtung von FF03 während einer laufenden Messung — plus als
letzte offene Protokollfrage die Bestätigung des blockweisen Speicherabrufs.

## Dateikarte

| Datei | Inhalt |
| --- | --- |
| `sensors/devices/po60.py` | Qt-/bleak-freies Protokollmodul: UUIDs, Kommandos (`kommando()`, Prüfsumme `sum & 0x7F`), `parse_datensatz`, `parse_handshake`, `SpeicherSammler` (Strom-Resynchronisierer). Verifikationsstand im Docstring |
| `tests/test_po60.py` | 19 Tests; die echten Gerätepakete aus Lauf 2/4 sind als Golden Vectors eingefroren |
| `tools/po60_erkundung.py` | CLI-Erkundungswerkzeug: `scan` / `dienste` / `speicher` / `lauschen` / `alles`; Live-Scan mit Sofortzugriff, Runden-Schleife, Keep-Alive, automatische Wiederverbindung, blockweiser Speicherabruf, `--sondieren`; JSONL-Rohprotokoll je Lauf |
| `docs/beurer_po60_erkundung.md` | **Die Langfassung**: bestätigtes Protokoll (§1), Bedienung (§2), offene Checkliste (§3), Befunde der Läufe 1–4 mit dekodierten Daten (§4). Jede neue Geräteerkenntnis dort in §4 nachtragen |
| `Logs/po60/po60_*.jsonl` | Rohprotokolle der Läufe (lokal, git-ignoriert) — jede Notification/jedes Kommando als Hex mit Zeitstempeln |

## Gerät und Bedienung

- Adresse **`C9:49:AC:1E:4B:00`**, Name „PO60", FW V7.3, HW 2.00. Kein
  Standard-HR-, kein PLX-Dienst; Kanal: Dienst 0xFF12 mit FF01 (Write) /
  FF02 (Notify), dazu FF03 (Read/Write, Funktion unbekannt) in 0xFF00.
  Keine Kopplung nötig.
- **Bewährter Sync-Ablauf:** Messung machen, bis ein Wert angezeigt wird →
  Finger herausnehmen → Sync-Modus startet (langes Fenster) → Finger
  wieder hinein. Direkt nach Sync-Start reißt die Verbindung gern 2–3×
  kurz ab; das Werkzeug verbindet automatisch neu.
- **Idle-Timeout ~35 s** → alle 15 s Handshake als Keep-Alive senden
  (macht die Lauschphase automatisch; hielt 5 min nachweislich).
- Messungen werden **beim Finger-Herausnehmen** gespeichert; der Abruf
  **löscht nichts**.

## Protokoll-Spickzettel (Langfassung: beurer_po60_erkundung.md §1)

```
Kommando  = Bytes + Prüfsumme (sum & 0x7F) — gilt auch für alle Antworten
Handshake : 90 05 15  → Antwort e0 05 <n u16LE> <n u16LE> <PS>, n = Datensatzanzahl
Abruf     : 99 00 19  → fortlaufender Bytestrom in 20-B-Notifications,
            Datensätze à 24 B (Grenzen liegen MITTEN in den Paketen!)
Datensatz : [0]=E9 · [1]=Index Bits0–5, Bit6=„letzter im Speicher" ·
            [2–7]=Beginn (J−2000,M,T,h,m,s) · [8–13]=Ende ·
            [14–16]=Abtastanzahl (Basis-128, = Dauer+1 s) ·
            [17–19]=SpO₂ max/min/Ø · [20–22]=Puls max/min/Ø · [23]=PS
Block     : je Anforderung max. 10 Datensätze (Lauf 4: 15 gemeldet, 0–9
            geliefert). Hypothese: 99 <start> = ab Datensatz <start>
            (99 0a 23 → ab 10) — UNBESTÄTIGT, Werkzeug fordert automatisch nach
```

## Nächste Schritte für den Live-Versuch (priorisiert)

1. **Blockabruf bestätigen** (ein Gerätelauf, alles steht bereit):
   `python3 tools/po60_erkundung.py alles --adresse C9:49:AC:1E:4B:00 --minuten 1`
   → erwartet: alle Datensätze in zwei Blöcken, letzter mit Bit-6-Flag.
   Ergebnis in `beurer_po60_erkundung.md` §4 als Lauf 5 dokumentieren.
2. **Sondierung während laufender Messung**: `lauschen --sondieren` mit
   Finger im Gerät. `SONDIER_KOMMANDOS` in `tools/po60_erkundung.py`
   gezielt erweitern (nur `kommando()`-gebaute Opcodes; bisher probiert:
   90 00 / 90 01 / 91 00 / 98 00 / 9A 00 — noch nie während einer
   laufenden Messung). Jede Reaktion landet dekodiert im JSONL.
3. **FF03 während einer Messung zyklisch lesen** (im Ruhezustand nur
   Nullen — vielleicht füllt sie sich, wenn das Gerät misst). Kleiner
   Umbau: Lauschphase liest FF03 z. B. alle 5 s mit und loggt Änderungen.
4. Ergibt (2)+(3) nichts: **Beurer-HealthManager-App + BLE-Sniffer**
   (Android-HCI-Snoop-Log oder nRF-Sniffer) — falls die App einen
   Live-Modus kennt, zeigt der Mitschnitt das Triggerkommando.

## Grenze, die bestehen bleibt

Auch ein gefundener Live-Modus lieferte SpO₂/Puls (≈1 Hz gerätegemittelt),
**keine Schlag-zu-Schlag-Intervalle**. Als `intervall_quelle` der
HRV-Kette (`ekg_rr`/`ppg_ppi`) kommt der PO60 damit nie infrage — das
Integrationsziel bleibt Zusatzinformation (SpO₂/Puls neben einer
HRV-Messung) bzw. Import gespeicherter Messungen in die Akte. Für die
spätere Integration gelten die CLAUDE.md-Regeln: neues Gerät über ein
Profil (`sensors/devices/profiles.py`), keine Namens-Fallunterscheidungen
im Widget; das Protokollmodul `po60.py` ist bewusst so geschnitten, dass
es unverändert unter ein Profil wandern kann.

## Arbeitskonventionen

- Branch: `claude/beurer-po60-hrv-in6wvk` (dort liegt der gesamte Stand)
- Tests: `python -m pytest tests/test_po60.py -v` — bei jeder
  Protokollkorrektur die echten Gerätebytes als neuen Golden Vector
  einfrieren, nie bestehende Golden Vectors „anpassen"
- Befunde: jeden Gerätelauf mit Datum in `beurer_po60_erkundung.md` §4
  nachtragen und die Checkliste in §3 pflegen; JSONL-Logs aufheben
- Werkzeug-Grundsatz: alles roh loggen, Unbekanntes nie verwerfen, nur
  `kommando()`-gebaute, nicht erkennbar schreibende Opcodes sondieren
