# Decathlon HRM Belt: kein RR, kein EKG

## Produkt

- **Decathlon HRM Belt**, auf der Support-Seite „Pulsgurt Dual ANT+ / Bluetooth“; Decathlon-REF
  8801209, Produktcode 346657. Brustgurt mit abnehmbarem Sender, Elektroden im Textilgurt,
  Bluetooth Smart 4.0 und ANT+, Knopfzelle CR2032, rund 30 €. Offizielle App: Decathlon Coach.
  Ein Firmware-Update erwähnt Decathlon nirgends.
- **Am Gerät gelesen:** Bluetooth-Name „HRM Belt <Nummer>“, Device Information: Hersteller
  „DECATHLON“, Modell „44“, Firmware und Software „0.122“, Hardware „1“. Keine PnP-Kennung.
- Vorgänger: Kalenji „Dual HRM Belt“ (gleiche Bauart). Weitere Decathlon-Produkte:
  [`../README.md`](../README.md).

## Dateien in diesem Ordner

| Datei | Inhalt |
|---|---|
| `README.md` | dieser Befund |
| `erkundung_2026-10-19_roh.jsonl` | Rohmitschnitt von `scripts/ble_erkundung.py`: Kopf, 90 HR-Pakete (Hex, Ankunftszeit), Ereignisse |
| `erkundung_2026-10-19_befund.json` | Dienste und Charakteristiken, Geräteinformation, Kennzahlen des HR-Stroms, Hinweise |

Befund vom 19.10.2026 am Gerät mit `scripts/ble_erkundung.py` (45 s, `--lauschen`) und einer
Aufnahme in praxis_gui (Profil „Brustgurt (Standardprofil)“). Vergleichsgerät: Polar H10.

## Ergebnis in Kürze

- **Der Gurt misst keine RR-Intervalle.** Was er im Feld „RR-Interval“ des Standardprofils
  sendet, ist `floor(60000 / bpm)` — aus der ganzzahligen, geglätteten Herzfrequenz
  zurückgerechnet. In 90 von 90 Paketen der Erkundung und in 189 von 189 Einträgen der
  praxis_gui-Aufnahme stimmt die Formel exakt.
- **Falsche Einheit.** Der Wert steht in Millisekunden; die Bluetooth-Spezifikation verlangt
  1/1024 s. Ein spezifikationsgemäßer Empfänger skaliert mit 1000/1024 und liest alle
  Intervalle 2,3 % zu kurz (Herzfrequenz 2,3 % zu hoch).
- **Zwei Pakete je Sekunde, jedes mit genau einem Wert**, unabhängig von der tatsächlichen
  Schlagfolge. Die Summe der „RR“ läuft der Uhr davon (151 s Intervalle in 94 s Aufnahme),
  benachbarte Werte wiederholen sich zu rund 80 %.
- **Kein EKG.** Kein Polar-PMD-Dienst. Ein herstellereigener Dienst mit zwei Charakteristiken
  (Write, Write ohne Antwort, Notify) sendet ohne Startkommando nichts; er ist nirgends
  dokumentiert und sieht nach einem Kommando- oder Update-Kanal aus.
- **Folge:** Für HRV ist der Gurt unbrauchbar. Jede Kennzahl aus seinen Werten misst die
  Quantisierung einer Ganzzahl, nicht das Herz. Als reiner Herzfrequenzmesser funktioniert er.

## Was am Gerät zu sehen ist

Dienste: Generic Access, Generic Attribute, Device Information, Heart Rate, Battery, dazu der
herstellereigene Dienst `8ce5cc01-0a4d-11e9-ab14-d663bd873d93` mit den Charakteristiken
`8ce5cc02-…` und `8ce5cc03-…` (jeweils `write-without-response, write, notify`). Keine
PnP-Kennung, also kein Hinweis auf den Chiphersteller. Die Seriennummer wird nicht gelesen.

Heart Rate Measurement (0x2A37), Flags `0x16`: Herzfrequenz 8 bit, Hautkontakt unterstützt und
erkannt, RR-Flag gesetzt. Nutzlast immer 4 Byte: Flags, bpm, ein 16-bit-Wert. Beispiel aus dem
Mitschnitt: bpm 69 → Rohwert 869 (= floor(60000/69)); bpm 74 → 810; bpm 78 → 769.

## Wie das Muster zu erkennen ist

Für jedes Paket den Rohwert mit `60000 / bpm` vergleichen (Toleranz 1). Trifft das in fast allen
Paketen zu, sind die Intervalle gerechnet, nicht gemessen. `scripts/ble_erkundung.py` meldet
das als „RR-Rohwert ist 60000/bpm in Millisekunden“. Dieselbe Prüfung wäre in einer App
sinnvoll, bevor eine Messung mit dem Standardprofil wie eine H10-Messung geführt wird
(offen; praxis_gui kennzeichnet solche Aufnahmen bisher nicht).

## Was noch ginge

Der einzige verbleibende Weg zu einem Rohsignal wäre, die Decathlon-App beim Sprechen mit dem
Gurt mitzuschneiden (Android HCI-Snoop-Log) und zu sehen, ob sie über den herstellereigenen
Kanal mehr anstößt als Firmware-Updates. Einschätzung: unwahrscheinlich — eine Firmware, die
nicht einmal Schlagzeiten nach außen gibt, exportiert kaum ein EKG. Blind Kommandos auf den
Kanal zu schreiben ist nicht ratsam (Update-Modus).

## Quellen

- Bluetooth SIG, Heart Rate Service 1.0, Heart Rate Measurement: RR-Interval in 1/1024 s.
- Testberichte ohne Angaben zu GATT oder Chip: [runmorph.com](https://runmorph.com/en/reviews/decathlon-hrm-belt-review),
  [coachweb.com (Kalenji Dual)](https://www.coachweb.com/gear/heart-rate-monitors/kalenji-dual-heart-rate-monitor-review).
- Dieselbe Dienst-UUID an einem anderen Gerät, ohne Deutung:
  [Garmin-Forum](https://forums.garmin.com/developer/connect-iq/f/discussion/289131/garmin-shows-0-0-speed-sent-by-esp32-over-ble?pifragment-1298=2).
