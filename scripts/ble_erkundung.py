#!/usr/bin/env python
"""Was bietet ein Brustgurt über Bluetooth an? Dienste, Hersteller, HR-Strom, Rohdaten-Kandidaten.

    uv run --with bleak python scripts/ble_erkundung.py                    # Geräte in der Nähe
    uv run --with bleak python scripts/ble_erkundung.py ADRESSE            # Dienste + 60 s HR-Strom
    uv run --with bleak python scripts/ble_erkundung.py ADRESSE --dauer 180 --lauschen

Gedacht für die Frage „liefert dieser Gurt mehr als Herzfrequenz und RR, etwa ein EKG wie der
Polar H10?“. Das Skript verbindet sich, zählt alle GATT-Dienste und -Charakteristiken auf,
liest die Geräteinformation (Hersteller, Modell, Firmware, PnP-Kennung des Chipherstellers),
prüft gezielt auf den Polar-PMD-Dienst und hört ``--dauer`` Sekunden den Standardstrom
„Heart Rate Measurement“ (0x2A37) ab. Daraus entsteht ein Befund zum RR-Strom: Sind RR-Werte
überhaupt dabei, wie viele je Paket, mit welcher Auflösung, sind sie aus der Herzfrequenz
zurückgerechnet, gehen Schläge verloren?

``--lauschen`` abonniert zusätzlich jede herstellereigene Charakteristik, die Notify oder
Indicate kann, und zählt, was ohne Startkommando von sich aus hereinkommt. Das Skript schreibt
nie auf das Gerät.

Alle Pakete landen roh (Hex + Ankunftszeit) in ``ausgaben/ble_erkundung/`` (git-ignoriert),
dazu der Befund als JSON. Das Skript braucht Hardware und läuft deshalb bei Ben, nicht in einer
Claude-Sitzung. Die Seriennummer (0x2A25) wird bewusst nicht gelesen.
Befunde je Gerät: ``docs/geraete/``.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import math
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakDeviceNotFoundError
except ImportError:  # pragma: no cover - Hinweis statt Traceback
    sys.exit("bleak fehlt — Aufruf mit `uv run --with bleak python scripts/ble_erkundung.py …`")

REPO = Path(__file__).resolve().parents[1]

SCHEMA = "ble-erkundung-v1"

HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"
PMD_SERVICE = "fb005c80-02e7-f387-1cad-8acd2d8df0c8"
PMD_CONTROL = "fb005c81-02e7-f387-1cad-8acd2d8df0c8"

# Bekannte Dienste. Alles, was hier nicht steht und eine 128-bit-UUID trägt, ist
# herstellereigen — und damit der einzige Ort, an dem ein Rohsignal stecken könnte.
BEKANNTE_DIENSTE = {
    "1800": "Generic Access",
    "1801": "Generic Attribute",
    "180a": "Device Information",
    "180d": "Heart Rate",
    "180f": "Battery",
    "1814": "Running Speed and Cadence",
    "1816": "Cycling Speed and Cadence",
    "181c": "User Data",
    "fe59": "Nordic Secure DFU",
    "fb005c80-02e7-f387-1cad-8acd2d8df0c8": "Polar Measurement Data (PMD) — Rohdaten",
    "6217ff4b-fb31-1140-ad5a-a45545d7ecf3": "Polar (herstellereigen, Einstellungen)",
}
# Geräteinformation: Charakteristik → Bezeichnung. Seriennummer (2a25) absichtlich nicht dabei.
GERAETEINFO = {
    "2a29": "Hersteller",
    "2a24": "Modell",
    "2a26": "Firmware",
    "2a27": "Hardware",
    "2a28": "Software",
    "2a50": "PnP-Kennung",
}
# PMD-Steuercharakteristik, Lesen liefert [0x0F, Fähigkeiten, …]; Bits laut Polar-SDK.
PMD_FAEHIGKEITEN = {0: "EKG", 1: "PPG", 2: "ACC", 3: "PPI", 5: "Gyro", 6: "Magnetometer"}
# Bluetooth-SIG-Firmenkennungen, die bei Brustgurten vorkommen (PnP-Kennung, Quelle 1).
FIRMEN = {
    0x0059: "Nordic Semiconductor",
    0x000D: "Texas Instruments",
    0x0030: "ST Microelectronics",
    0x004C: "Apple",
    0x006B: "Polar Electro",
    0x0087: "Garmin",
    0x00E0: "Google",
    0x0171: "Wahoo Fitness",
    0x0499: "Ruuvi",
    0x038F: "Xiaomi",
    0x0157: "Huami (Anhui Huami)",
    0x02E5: "Dialog Semiconductor",
    0x0702: "Telink Semiconductor",
    0x0D53: "Realtek",
}


def kurz(uuid: str) -> str:
    """Standard-UUIDs auf die 16-bit-Form kürzen, herstellereigene ganz lassen."""
    u = uuid.lower()
    if u.endswith("-0000-1000-8000-00805f9b34fb") and u.startswith("0000"):
        return u[4:8]
    return u


def dienstname(uuid: str) -> str:
    k = kurz(uuid)
    if k in BEKANNTE_DIENSTE:
        return BEKANNTE_DIENSTE[k]
    return "herstellereigen — Kandidat für Rohdaten" if len(k) > 4 else "Standard (nicht gelistet)"


def _druckbar(b: bytes) -> str | None:
    try:
        s = b.decode("utf-8").strip("\x00")
    except UnicodeDecodeError:
        return None
    return s if s and all(32 <= ord(c) < 127 for c in s) else None


def pnp_dekodieren(b: bytes) -> str:
    if len(b) < 7:
        return f"unerwartete Länge {len(b)}"
    quelle = b[0]
    vid = int.from_bytes(b[1:3], "little")
    pid = int.from_bytes(b[3:5], "little")
    ver = int.from_bytes(b[5:7], "little")
    firma = FIRMEN.get(vid, "unbekannt") if quelle == 1 else "USB-Kennung"
    return f"Vendor 0x{vid:04X} ({firma}), Produkt 0x{pid:04X}, Version 0x{ver:04X}"


# ---------------------------------------------------------------------------
# HR-Strom auswerten
# ---------------------------------------------------------------------------


def hr_paket_zerlegen(data: bytes) -> dict:
    """Heart Rate Measurement (0x2A37): Flags, bpm, RR-Rohwerte (1/1024 s)."""
    flags = data[0]
    idx = 1
    if flags & 0x01:
        bpm = int.from_bytes(data[idx : idx + 2], "little")
        idx += 2
    else:
        bpm = data[idx]
        idx += 1
    if flags & 0x08:
        idx += 2  # Energy Expended
    rr_raw: list[int] = []
    if flags & 0x10:
        while idx + 1 < len(data):
            rr_raw.append(int.from_bytes(data[idx : idx + 2], "little"))
            idx += 2
    return {
        "flags": flags,
        "hr16": bool(flags & 0x01),
        "kontakt_unterstuetzt": bool(flags & 0x04),
        "kontakt": bool(flags & 0x02),
        "energie": bool(flags & 0x08),
        "rr_flag": bool(flags & 0x10),
        "bpm": bpm,
        "rr_raw": rr_raw,
        "rest_bytes": len(data) - idx,
    }


def hr_befund(pakete: list[tuple[float, bytes]]) -> dict:
    """Befund zum RR-Strom aus den rohen HR-Paketen."""
    if not pakete:
        return {"pakete": 0, "hinweis": "kein einziges HR-Paket — Gurt angelegt und angefeuchtet?"}
    zerlegt = [hr_paket_zerlegen(d) for _, d in pakete]
    t = [tt for tt, _ in pakete]
    dauer = t[-1] - t[0]
    abstaende = [b - a for a, b in itertools.pairwise(t)]
    rr_alle = [r for z in zerlegt for r in z["rr_raw"]]
    je_paket = Counter(len(z["rr_raw"]) for z in zerlegt)
    befund: dict = {
        "pakete": len(pakete),
        "dauer_s": round(dauer, 1),
        "paketabstand_s": {
            "median": round(sorted(abstaende)[len(abstaende) // 2], 3) if abstaende else None,
            "max": round(max(abstaende), 3) if abstaende else None,
        },
        "flags": {
            "rr_flag_anteil": round(sum(z["rr_flag"] for z in zerlegt) / len(zerlegt), 3),
            "kontakt_unterstuetzt": any(z["kontakt_unterstuetzt"] for z in zerlegt),
            "kontakt_anteil": round(sum(z["kontakt"] for z in zerlegt) / len(zerlegt), 3),
            "hr16": any(z["hr16"] for z in zerlegt),
            "energie": any(z["energie"] for z in zerlegt),
        },
        "rr_je_paket": dict(sorted(je_paket.items())),
        "rr_anzahl": len(rr_alle),
        "bpm_mittel": round(sum(z["bpm"] for z in zerlegt) / len(zerlegt), 1),
        "bpm_null_anteil": round(sum(z["bpm"] == 0 for z in zerlegt) / len(zerlegt), 3),
    }
    hinweise: list[str] = []
    if befund["flags"]["rr_flag_anteil"] == 0:
        hinweise.append(
            "RR-Flag nie gesetzt: der Gurt sendet keine RR-Intervalle, nur bpm. "
            "Damit ist keine HRV möglich."
        )
        befund["hinweise"] = hinweise
        return befund
    if not rr_alle:
        hinweise.append("RR-Flag gesetzt, aber keine RR-Werte im Paket.")
        befund["hinweise"] = hinweise
        return befund

    rr_ms = [r * 1000 / 1024 for r in rr_alle]
    # Auflösung: größter gemeinsamer Teiler der Abstände zum kleinsten Rohwert.
    # 1 heißt volle 1/1024-s-Auflösung; 8 etwa hieße Stufen von 7,8 ms.
    basis = min(rr_alle)
    schritt = 0
    for r in rr_alle:
        schritt = math.gcd(schritt, r - basis)
    befund["rr_aufloesung_schritt_1024stel"] = schritt
    # Aus der Herzfrequenz zurückgerechnet? Dann ist rr_raw ≈ 1024·60/bpm in fast jedem Paket.
    treffer = 0
    gesamt = 0
    for z in zerlegt:
        if z["bpm"] <= 0:
            continue
        soll = 1024 * 60 / z["bpm"]
        for r in z["rr_raw"]:
            gesamt += 1
            if abs(r - soll) <= 1.0:
                treffer += 1
    befund["rr_gleich_60000_durch_bpm_anteil"] = round(treffer / gesamt, 3) if gesamt else None
    # Zweite Variante derselben Abkürzung: der Rohwert ist 60000/bpm in Millisekunden, also
    # in der falschen Einheit (die Spezifikation verlangt 1/1024 s). Ein Empfänger, der
    # spezifikationsgemäß mit 1000/1024 skaliert, liest dann alle RR 2,3 % zu kurz.
    treffer_ms = 0
    for z in zerlegt:
        if z["bpm"] <= 0:
            continue
        soll_ms = 60000 / z["bpm"]
        treffer_ms += sum(abs(r - soll_ms) <= 1.0 for r in z["rr_raw"])
    befund["rr_gleich_60000_durch_bpm_in_ms_anteil"] = (
        round(treffer_ms / gesamt, 3) if gesamt else None
    )
    # Wiederholungen: identische aufeinanderfolgende RR sind beim echten Herzen selten.
    wdh = sum(a == b for a, b in itertools.pairwise(rr_alle))
    befund["rr_wiederholung_anteil"] = round(wdh / max(len(rr_alle) - 1, 1), 3)
    # Zeitbilanz: Summe der RR gegen die Dauer zwischen erstem und letztem RR-Paket.
    rr_pakete = [(tt, z) for tt, z in zip(t, zerlegt, strict=True) if z["rr_raw"]]
    if len(rr_pakete) > 1:
        summe = sum(r for _, z in rr_pakete[1:] for r in z["rr_raw"]) / 1024
        spanne = rr_pakete[-1][0] - rr_pakete[0][0]
        befund["zeitbilanz"] = {
            "summe_rr_s": round(summe, 2),
            "spanne_s": round(spanne, 2),
            "fehlend_s": round(spanne - summe, 2),
            "fehlende_schlaege_geschaetzt": round(
                (spanne - summe) / (sum(rr_ms) / len(rr_ms) / 1000), 1
            ),
        }
    mittel = sum(rr_ms) / len(rr_ms)
    diffs = [b - a for a, b in itertools.pairwise(rr_ms)]
    befund["rr_ms"] = {
        "mittel": round(mittel, 1),
        "min": round(min(rr_ms), 1),
        "max": round(max(rr_ms), 1),
        "rmssd_roh": round(math.sqrt(sum(d * d for d in diffs) / len(diffs)), 1) if diffs else None,
    }

    if schritt > 1:
        hinweise.append(
            f"RR-Auflösung ist {schritt}/1024 s ≈ {schritt * 1000 / 1024:.1f} ms statt "
            "1/1024 s — grober als der H10, RMSSD wird verzerrt."
        )
    if (
        befund["rr_gleich_60000_durch_bpm_anteil"]
        and befund["rr_gleich_60000_durch_bpm_anteil"] > 0.8
    ):
        hinweise.append(
            "RR entspricht fast immer 60000/bpm: die Intervalle sind aus der geglätteten "
            "Herzfrequenz zurückgerechnet, keine echten Schlag-zu-Schlag-Werte."
        )
    if (befund["rr_gleich_60000_durch_bpm_in_ms_anteil"] or 0) > 0.8:
        hinweise.append(
            "RR-Rohwert ist 60000/bpm in Millisekunden: keine Schlagmessung, dazu die falsche "
            "Einheit — spezifikationsgemäß gelesen (1/1024 s) sind alle RR 2,3 % zu kurz."
        )
    if befund["rr_wiederholung_anteil"] > 0.3:
        hinweise.append(
            "Viele identische aufeinanderfolgende RR: Glättung oder Wiederholung "
            "statt echter Schlagfolge."
        )
    zb = befund.get("zeitbilanz")
    if zb and abs(zb["fehlende_schlaege_geschaetzt"]) > 0.05 * len(rr_alle):
        hinweise.append(
            "Zeitbilanz geht nicht auf: Summe der RR weicht deutlich von der Aufnahmedauer "
            "ab — Schläge gehen verloren oder werden doppelt gesendet."
        )
    if befund["paketabstand_s"]["max"] and befund["paketabstand_s"]["max"] > 3:
        hinweise.append("Paketlücken über 3 s — Übertragungsaussetzer.")
    if not hinweise:
        hinweise.append(
            "RR-Strom unauffällig: volle Auflösung, echte Schlagfolge, Zeitbilanz stimmt."
        )
    befund["hinweise"] = hinweise
    return befund


# ---------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------


async def scannen(dauer: float) -> None:
    print(f"Suche {dauer:.0f} s …")
    gefunden = await BleakScanner.discover(timeout=dauer, return_adv=True)
    zeilen = []
    for adresse, (geraet, adv) in gefunden.items():
        dienste = [kurz(u) for u in adv.service_uuids]
        hr = "HR" if "180d" in dienste else "  "
        zeilen.append((hr, adv.rssi or -999, adresse, geraet.name or "?", dienste))
    for hr, rssi, adresse, name, dienste in sorted(zeilen, key=lambda z: (z[0] != "HR", -z[1])):
        print(f"  {hr} {rssi:5d} dBm  {adresse}  {name:<24} {' '.join(dienste)}")
    print("\nHR = bewirbt den Herzfrequenzdienst. Dann: ble_erkundung.py ADRESSE")


async def _verbinden(adresse: str) -> BleakClient:
    """Verbinden — auch mit einem Gerät, das BlueZ schon hält.

    Ein verbundenes Gerät sendet keine Advertisements; `BleakClient(<Adresse>)` scannt
    intern vergeblich. BlueZ führt es aber unter einem festen D-Bus-Pfad, und der reicht
    bleak zum Anhängen (derselbe Kniff wie in praxis_gui, `_bledevice_ohne_scan`).
    """
    client = BleakClient(adresse, timeout=30.0)
    try:
        await client.connect()
        return client
    except BleakDeviceNotFoundError:
        print("Im Scan nicht gefunden — vermutlich hält BlueZ es schon; hänge mich an.")
    from bleak.backends.device import BLEDevice

    adapter = "/org/bluez/hci0"
    try:
        from bleak.backends.bluezdbus.manager import get_global_bluez_manager

        adapter = (await get_global_bluez_manager()).get_default_adapter()
    except Exception:
        pass
    pfad = adapter + "/dev_" + adresse.upper().replace(":", "_")
    dev = BLEDevice(adresse, None, {"path": pfad, "props": {"Address": adresse}})
    client = BleakClient(dev, timeout=30.0)
    await client.connect()
    return client


async def erkunden(adresse: str, dauer: float, lauschen: bool, ordner: Path) -> None:
    start_utc = datetime.now(UTC)
    stempel = start_utc.strftime("%Y-%m-%d_%H%M%S")
    ordner.mkdir(parents=True, exist_ok=True)
    roh = (ordner / f"{stempel}_roh.jsonl").open("w", encoding="utf-8")
    befund: dict = {"schema": SCHEMA, "adresse": adresse, "start_utc": start_utc.isoformat()}

    def protokoll(eintrag: dict) -> None:
        roh.write(json.dumps(eintrag, ensure_ascii=False) + "\n")

    protokoll(
        {
            "art": "kopf",
            "schema": SCHEMA,
            "adresse": adresse,
            "start_utc": befund["start_utc"],
            "start_monotonic": time.monotonic(),
        }
    )

    print(f"Verbinde mit {adresse} …")
    client = await _verbinden(adresse)
    try:
        print("Verbunden.\n")
        befund["geraetename"] = None
        try:
            name_roh = await client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
            befund["geraetename"] = _druckbar(bytes(name_roh))
        except Exception as e:
            protokoll(
                {"art": "ereignis", "t": time.monotonic(), "text": f"Gerätename nicht lesbar: {e}"}
            )
        if befund["geraetename"]:
            print(f"Gerätename: {befund['geraetename']}")

        # --- Dienste und Charakteristiken ------------------------------------
        print("\nDienste:")
        dienste: list[dict] = []
        kandidaten: list = []
        hat_pmd = False
        for svc in client.services:
            sname = dienstname(svc.uuid)
            print(f"  {kurz(svc.uuid):<40} {sname}")
            chars = []
            for ch in svc.characteristics:
                props = ",".join(ch.properties)
                # Handle mit ausgeben: in einem HCI-Mitschnitt (Wireshark) stehen nur Handles,
                # keine UUIDs — die Tabelle hier ist der Schlüssel dazu.
                eintrag = {"uuid": kurz(ch.uuid), "handle": ch.handle, "props": props}
                print(f"      {kurz(ch.uuid):<36} 0x{ch.handle:04x}  {props}")
                if (
                    kurz(svc.uuid) == "180a"
                    and kurz(ch.uuid) in GERAETEINFO
                    and "read" in ch.properties
                ):
                    try:
                        wert = bytes(await client.read_gatt_char(ch))
                        text = pnp_dekodieren(wert) if kurz(ch.uuid) == "2a50" else _druckbar(wert)
                        eintrag["wert"] = text if text is not None else wert.hex()
                        print(f"          {GERAETEINFO[kurz(ch.uuid)]}: {eintrag['wert']}")
                    except Exception as e:
                        eintrag["fehler"] = str(e)
                if kurz(ch.uuid) == kurz(PMD_CONTROL) and "read" in ch.properties:
                    hat_pmd = True
                    try:
                        wert = bytes(await client.read_gatt_char(ch))
                        bits = wert[1] if len(wert) > 1 else 0
                        faeh = [n for b, n in PMD_FAEHIGKEITEN.items() if bits >> b & 1]
                        eintrag["wert"] = wert.hex()
                        befund["pmd_faehigkeiten"] = faeh
                        print(f"          PMD-Fähigkeiten: {', '.join(faeh) or 'keine gemeldet'}")
                    except Exception as e:
                        eintrag["fehler"] = str(e)
                if (
                    len(kurz(svc.uuid)) > 4
                    and kurz(svc.uuid) != kurz(PMD_SERVICE)
                    and ({"notify", "indicate"} & set(ch.properties))
                ):
                    kandidaten.append(ch)
                chars.append(eintrag)
            dienste.append({"uuid": kurz(svc.uuid), "name": sname, "charakteristiken": chars})
        befund["dienste"] = dienste
        befund["hat_pmd"] = hat_pmd
        befund["rohdaten_kandidaten"] = [kurz(c.uuid) for c in kandidaten]

        hr_char = client.services.get_characteristic(HR_MEASUREMENT)
        if hr_char is None:
            print(
                "\nKeine Heart-Rate-Measurement-Charakteristik — kein Herzfrequenzgerät "
                "nach Standard."
            )
            befund["hr_strom"] = {"pakete": 0, "hinweis": "0x2A37 fehlt"}
        else:
            # --- HR-Strom und ggf. herstellereigene Notifies mithören -------
            pakete: list[tuple[float, bytes]] = []
            fremd: Counter = Counter()

            def hr_cb(_sender, data: bytearray) -> None:
                t = time.monotonic()
                pakete.append((t, bytes(data)))
                protokoll({"art": "paket", "t": t, "q": "hr", "hex": bytes(data).hex()})
                z = hr_paket_zerlegen(bytes(data))
                rr = " ".join(f"{r * 1000 / 1024:.0f}" for r in z["rr_raw"])
                print(
                    f"\r  {len(pakete):4d} Pakete  {z['bpm']:3d} bpm  RR {rr:<28}",
                    end="",
                    flush=True,
                )

            def fremd_cb(uuid: str):
                def cb(_sender, data: bytearray) -> None:
                    fremd[uuid] += 1
                    protokoll(
                        {"art": "paket", "t": time.monotonic(), "q": uuid, "hex": bytes(data).hex()}
                    )

                return cb

            if lauschen:
                for ch in kandidaten:
                    try:
                        await client.start_notify(ch, fremd_cb(kurz(ch.uuid)))
                    except Exception as e:
                        protokoll(
                            {
                                "art": "ereignis",
                                "t": time.monotonic(),
                                "text": f"Notify {kurz(ch.uuid)} nicht möglich: {e}",
                            }
                        )
                print(
                    f"\nLausche zusätzlich auf {len(kandidaten)} herstellereigene "
                    "Charakteristik(en)."
                )

            print(f"\nHöre {dauer:.0f} s den HR-Strom ab — ruhig sitzen bleiben.")
            await client.start_notify(hr_char, hr_cb)
            await asyncio.sleep(dauer)
            await client.stop_notify(hr_char)
            print()
            befund["hr_strom"] = hr_befund(pakete)
            befund["fremde_notifies"] = dict(fremd)

    finally:
        await client.disconnect()
    roh.close()
    befund_pfad = ordner / f"{stempel}_befund.json"
    befund_pfad.write_text(json.dumps(befund, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Befund ---------------------------------------------------------------
    print("\nBefund")
    print("------")
    if hat_pmd:
        stroeme = ", ".join(befund.get("pmd_faehigkeiten", [])) or "?"
        print(f"Polar-PMD-Dienst vorhanden; gemeldete Ströme: {stroeme}")
    else:
        print("Kein Polar-PMD-Dienst: EKG wie beim H10 gibt es hier nicht.")
    if befund["rohdaten_kandidaten"]:
        print(
            f"Herstellereigene Notify-Charakteristiken: {', '.join(befund['rohdaten_kandidaten'])}"
        )
        if lauschen:
            if befund.get("fremde_notifies"):
                print(
                    "  Davon haben von sich aus gesendet: "
                    + ", ".join(f"{u} ({n} Pakete)" for u, n in befund["fremde_notifies"].items())
                )
            else:
                print("  Keine davon hat ohne Startkommando etwas gesendet.")
        else:
            print("  Ob dort etwas fließt: Lauf mit --lauschen.")
    else:
        print(
            "Keine herstellereigene Charakteristik mit Notify — nirgends Platz für ein Rohsignal."
        )
    hs = befund["hr_strom"]
    if hs.get("pakete"):
        print(
            f"HR-Strom: {hs['pakete']} Pakete in {hs['dauer_s']} s, {hs['rr_anzahl']} RR-Werte, "
            f"RR je Paket {hs['rr_je_paket']}"
        )
    for h in hs.get("hinweise", [hs.get("hinweis", "")]):
        print(f"  • {h}")
    print(f"\nRohpakete: {roh.name}\nBefund:    {befund_pfad}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "adresse", nargs="?", help="Bluetooth-Adresse; ohne: Geräte in der Nähe suchen"
    )
    parser.add_argument("--dauer", type=float, default=60.0, help="Sekunden HR-Strom mithören (60)")
    parser.add_argument(
        "--lauschen",
        action="store_true",
        help="herstellereigene Notify-Charakteristiken zusätzlich abonnieren",
    )
    parser.add_argument("--scan-dauer", type=float, default=8.0, help="Sekunden suchen (8)")
    parser.add_argument(
        "--ausgabe", type=Path, default=None, help="Zielordner (Vorgabe ausgaben/ble_erkundung/)"
    )
    args = parser.parse_args(argv)
    ordner = args.ausgabe or (REPO / "ausgaben" / "ble_erkundung")
    try:
        if args.adresse:
            asyncio.run(erkunden(args.adresse, args.dauer, args.lauschen, ordner))
        else:
            asyncio.run(scannen(args.scan_dauer))
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
