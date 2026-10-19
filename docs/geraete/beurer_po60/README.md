# Beurer PO60 — Dokumentation

> Verschoben aus `praxis_gui/docs/` (19.10.2026): Gerätewissen gilt für praxis_gui und trainingsapp gleichermaßen und liegt deshalb in hrv-core. Codepfade (`src/praxislab/…`, `tools/…`, `tests/…`) beziehen sich auf praxis_gui, soweit nicht anders angegeben.

Zusammengetragenes Wissen aus dem Versuch, das Fingerpulsoximeter **Beurer
PO60** über Bluetooth Low Energy an die Praxis-GUI anzubinden. Der Ausflug ist
**abgeschlossen** (Stand 2026-08-14, sechs Erkundungsläufe am echten Gerät).
Diese Dateien sind der bleibende Wissensspeicher; **Code liegt bewusst nicht
auf `main`** — der reverse-engineerte Protokollkern samt Tests und Werkzeug
existiert nur auf dem Side-Branch `claude/beurer-po60-hrv-in6wvk` und ist als
vollständiger Quelltext im Exkurs eingebettet (Wiederherstellung jederzeit
möglich).

## Ergebnis in Kürze

- **Der PO60 gibt über BLE keinen Live-Datenstrom her.** Weder Push (das Gerät
  sendet von sich aus nichts) noch Pull (kein abfragbarer Momentanwert).
- **Messung und BLE-Verbindung schließen sich wechselseitig aus** (Lauf 6,
  beidseitig belegt): Im Sync-/Verbindungszustand ist die Mess-LED aus, das
  Gerät misst nicht; während einer laufenden Messung lässt es sich nicht
  verbinden. Es gibt keinen Zustand mit leuchtender LED *und* stehender
  Verbindung.
- **Der PO60 überträgt nur gespeicherte Messungen** — SpO₂/Puls als
  Min/Max/Mittelwert über ein Messfenster, **keine Schlag-zu-Schlag-
  Intervalle**. Als `intervall_quelle` der HRV-Kette (`ekg_rr`/`ppg_ppi`) kommt
  er damit ohnehin nie infrage.
- **Konsequenz: keine Integration in die Praxis-GUI.** Eine einzelne
  Aggregatzahl rechtfertigt keine BLE-Anbindung; das leistet ein Blick aufs
  Display genauso.
- **Protokollkern ist entschlüsselt und Golden-Vector-getestet** (Speicher-
  abruf, Byte-Layout, Prüfsummen, Zeitstempel) — als Referenz erhalten, falls
  das Gerät später doch einmal gebraucht wird (z. B. Import gespeicherter
  Messungen in die Akte).

## Die Dokumente

| Datei | Inhalt |
| --- | --- |
| [`beurer_po60_exkurs.md`](beurer_po60_exkurs.md) | **Der Schlussstein.** Steht für sich allein: Entscheidung samt Begründung, alle Erkenntnisse (Verbindung, Protokoll) und der vollständige Quelltext aller drei Code-Dateien als Referenz. Hier zuerst lesen. |
| [`beurer_po60_erkundung.md`](beurer_po60_erkundung.md) | Die Langfassung: bestätigtes Protokoll (§1), Bedienung des Werkzeugs (§2), Checkliste (§3), Lauf-für-Lauf-Befunde 1–6 mit dekodierten Gerätedaten (§4). |
| [`beurer_po60_uebergabe.md`](beurer_po60_uebergabe.md) | Fahrtenbuch der Weiterarbeit; die einst offene „Nächste-Schritte-für-Live"-Liste, jetzt gegenstandslos. |
