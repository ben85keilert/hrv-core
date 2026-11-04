"""Rohmitschnitt ``mitschnitt-v1`` — jedes Bluetooth-Paket mit Zeit, dazu Marken und Kontext.

Ein Format für alle Rohmitschnitte (Plan Diagnosemodus der trainingsapp, 4.11.2026, P116):
die trainingsapp im Diagnosemodus, die Brustgurt-Diagnose in hrv-research (vorher
``roh.jsonl``, eine Teilmenge), später praxis_gui (``devices/rohlog.py``). JSON Lines, nur
angehängt; jede Zeile ein Objekt mit ``art`` und ``t`` (monotone Uhr der App in ns, dieselbe
wie die Ankunftszeit der Messwerte). Die Arten:

============  ===============================================================================
``kopf``      erste Zeile: ``format``, ``app``, ``version``, ``start_utc``, ``wall_ns``,
              ``geraet`` (``name``, ``id`` = Adresse maskiert, ``profil``, ``art``), ``stroeme``
              (gewählte Ströme und Einstellungen), ``dienste`` (Abbild der Dienste),
              ``messdatei``
``n``         Benachrichtigung: ``c`` Merkmal (Kürzel oder UUID), ``x`` Hex; vom Transport, wenn
              er sie kennt: ``s`` Folgenummer, ``tm`` monotone Uhr der Dart-Seite (µs), ``tw``
              Wanduhr der Dart-Seite (µs)
``w``         Schreiben (Kommando): ``c``, ``x``, ``a`` (mit Antwort)
``r``         Lesen: ``c``, ``x`` — oder ``fehler``
``v``         Verbindung und Protokoll: ``text``, ``q`` (Quelle, etwa ``polar``); wahlweise
              ``zustand`` (``verbunden``, ``getrennt``, ``neu``, ``watchdog``), ``grund``, ``code``
``uhr``       alle `UHR_ABSTAND_S` ein Paar: ``utc`` (ISO) und ``wall_ns`` zur Zeit ``t``
``probe``     Zustand alle paar Sekunden: ``akku`` (Gerät), ``akku_handy``, ``laedt``,
              ``verzug_ms``, ``verzug_spitze_ms`` (Ereignisschleife der App), ``bildschirm``
``marke``     Diagnosemarke: ``id`` (laufend), ``typ`` (`MARKEN_TYPEN`), ``quelle`` (``handy``,
              ``uhr``), ``nr`` (Nummer im Satz), ``tm`` (Zeit der Dart-Seite, µs, bei der Uhr),
              ``kontext`` (``uebung``, ``uebung_id``, ``satz``, ``phase``)
``marke_weg`` nimmt eine Marke zurück: ``id`` — gelöscht wird nie, die Zeile bleibt
``kontext``   ``was`` (`KONTEXT_WAS`) mit ``uebung``, ``uebung_id``, ``satz``, ``feld``, ``wert``,
              ``abschnitt``, ``dauer_s``
============  ===============================================================================

Unbekannte Arten und Felder liest `lesen` mit; `hrv_core.deid` entfernt sie (Weißliste
``MITSCHNITT_REGELN``). Schreiben: `Schreiber` — jede Zeile sofort geschrieben und geflusht,
``fsync`` höchstens alle `FSYNC_ABSTAND_S`; endet die Datei beim Öffnen mitten in einer Zeile
(Absturz), beginnt der Anhang mit einem Zeilenumbruch. Lesen: `lesen` übergeht eine halbe
oder kaputte Zeile. Ein Absturz kostet so höchstens Sekunden, nie die Datei.

Ablage (Vertrag ``trainingsapp/docs/kompatibilitaet.md`` §2): neben der Messdatei
``sensor_<ts>_mitschnitt.jsonl`` (`mitschnitt_pfad`), während der Aufnahme neben dem
Crash-Backup ``.backup_<ts>_mitschnitt.jsonl`` (`journal_pfad`); ohne Messung (unbekanntes
Gerät) ``Diagnose/<ts>_<gerät>/mitschnitt.jsonl``. `stroeme` entschlüsselt EKG und
Beschleunigung aus den ``pmd_data``-Zeilen (`hrv_core.geraete.pmd`), mit Probenzeiten nach
Gerätezeit und Lücken.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import numpy as np

from .geraete import pmd

FORMAT: str = "mitschnitt-v1"
#: Endung neben der Messdatei: ``sensor_<ts>_mitschnitt.jsonl``
ENDUNG: str = "_mitschnitt.jsonl"
#: Name im eigenen Ordner (Rohmitschnitt ohne Messung)
DATEINAME: str = "mitschnitt.jsonl"
#: Abstand zwischen zwei ``fsync`` (s)
FSYNC_ABSTAND_S: float = 5.0
#: Abstand der Uhrzeilen (s)
UHR_ABSTAND_S: float = 10.0

# Arten
KOPF = "kopf"
N = "n"
W = "w"
R = "r"
V = "v"
UHR = "uhr"
PROBE = "probe"
MARKE = "marke"
MARKE_WEG = "marke_weg"
KONTEXT = "kontext"
ARTEN = (KOPF, N, W, R, V, UHR, PROBE, MARKE, MARKE_WEG, KONTEXT)

# Marken
MARKE_WDH = "wdh"
MARKE_ATEM = "atem"
MARKE_STOERUNG = "stoerung"
MARKE_FREI = "marke"
MARKEN_TYPEN = (MARKE_WDH, MARKE_ATEM, MARKE_STOERUNG, MARKE_FREI)
QUELLE_HANDY = "handy"
QUELLE_UHR = "uhr"

#: Was eine ``kontext``-Zeile meldet
KONTEXT_WAS = (
    "uebung_start",
    "uebung_ende",
    "timer_start",
    "timer_pause",
    "timer_weiter",
    "timer_abschnitt",
    "timer_ende",
    "satz",
    "pause",
    "diagnose_start",
    "diagnose_ende",
)

_BT = "-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37" + _BT
BATTERY_LEVEL_UUID = "00002a19" + _BT
#: Gerätename (GAP), Systemkennung, Seriennummer — tragen eine Kennung des einzelnen Geräts.
#: Die Apps lesen 0x2A25 und 0x2A23 nie; `hrv_core.deid` entfernt Zeilen aller drei.
KENNUNGS_MERKMALE: frozenset[str] = frozenset(
    {"00002a00" + _BT, "00002a23" + _BT, "00002a25" + _BT}
)
NIE_LESEN: frozenset[str] = frozenset({"00002a23" + _BT, "00002a25" + _BT})
#: Geräteinformation, die gelesen werden darf (ohne Seriennummer und Systemkennung)
GERAETEINFO: dict[str, str] = {
    "hersteller": "00002a29" + _BT,
    "modell": "00002a24" + _BT,
    "firmware": "00002a26" + _BT,
    "hardware": "00002a27" + _BT,
    "software": "00002a28" + _BT,
}
#: Kürzel der bekannten Merkmale; andere stehen als volle UUID (klein geschrieben)
KUERZEL: dict[str, str] = {
    HR_MEASUREMENT_UUID: "hr",
    pmd.PMD_CONTROL_UUID: "pmd_ctrl",
    pmd.PMD_DATA_UUID: "pmd_data",
    BATTERY_LEVEL_UUID: "akku",
} | {uuid: f"info_{name}" for name, uuid in GERAETEINFO.items()}
_KUERZEL_ZU_UUID = {k: u for u, k in KUERZEL.items()}


def kuerzel(uuid: str) -> str:
    """Kürzel eines Merkmals — unbekannte bleiben als volle UUID stehen.

    >>> kuerzel(HR_MEASUREMENT_UUID), kuerzel("00002A00-0000-1000-8000-00805F9B34FB")
    ('hr', '00002a00-0000-1000-8000-00805f9b34fb')
    """
    return KUERZEL.get(uuid.lower(), uuid.lower())


def uuid_von(c: str) -> str:
    """Volle UUID zu einem Kürzel (oder die UUID selbst).

    >>> uuid_von("hr") == HR_MEASUREMENT_UUID, uuid_von("00002a00" + _BT)[:8]
    (True, '00002a00')
    """
    return _KUERZEL_ZU_UUID.get(c, c.lower())


def mitschnitt_pfad(messdatei: Path | str) -> Path:
    """Der Mitschnitt neben einer Messdatei (``sensor_<ts>_mitschnitt.jsonl``).

    >>> mitschnitt_pfad("Messungen/PolarH10/sensor_2026-11-04_061500.json").name
    'sensor_2026-11-04_061500_mitschnitt.jsonl'
    """
    p = Path(messdatei)
    return p.with_name(p.stem + ENDUNG)


def journal_pfad(backup: Path | str) -> Path:
    """Der Mitschnitt einer laufenden Aufnahme neben ihrem Crash-Backup ``.backup_<ts>.json``.

    >>> journal_pfad("Messungen/PolarH10/.backup_2026-11-04_061500.json").name
    '.backup_2026-11-04_061500_mitschnitt.jsonl'
    """
    p = Path(backup)
    return p.with_name(p.stem + ENDUNG)


def ist_mitschnitt(pfad: Path | str) -> bool:
    """Ob ein Dateiname ein Mitschnitt ist (neben einer Messung, einem Backup oder im Ordner).

    >>> ist_mitschnitt("sensor_2026-11-04_061500_mitschnitt.jsonl"), ist_mitschnitt("x.jsonl")
    (True, False)
    """
    name = Path(pfad).name
    return name.endswith(ENDUNG) or name == DATEINAME


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------


def _jetzt_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Schreiber:
    """Ein Mitschnitt, in den nur angehängt wird (siehe Modultext).

    Thread-sicher: Die App schreibt aus der Ereignisschleife, gespeichert wird in einem Thread
    (`umbenennen`, `schliessen`). Ein Fehler beim Schreiben (Speicher voll) geht nie an den
    Aufrufer: Er wird gezählt (``fehler``), die Messung läuft weiter. Nach `schliessen` passiert
    nichts mehr.

    >>> import tempfile
    >>> pfad = Path(tempfile.mkdtemp()) / "sensor_x_mitschnitt.jsonl"
    >>> s = Schreiber(pfad, {"app": "test"}, uhr_ns=lambda: 7, wanduhr_ns=lambda: 9)
    >>> s.zeile("n", c="hr", x="0040")["t"]
    7
    >>> s.schliessen()
    >>> [(z["art"], z.get("format")) for z in lesen(pfad)]
    [('kopf', 'mitschnitt-v1'), ('n', None)]
    """

    def __init__(
        self,
        pfad: Path | str,
        kopf: dict[str, Any] | None = None,
        *,
        uhr_ns: Callable[[], int] = time.monotonic_ns,
        wanduhr_ns: Callable[[], int] = time.time_ns,
        fsync_abstand_s: float = FSYNC_ABSTAND_S,
        uhr_abstand_s: float = UHR_ABSTAND_S,
    ) -> None:
        self.pfad = Path(pfad)
        self._uhr_ns = uhr_ns
        self._wanduhr_ns = wanduhr_ns
        self._fsync_abstand_ns = int(fsync_abstand_s * 1e9)
        self._uhr_abstand_ns = int(uhr_abstand_s * 1e9)
        self._sperre = threading.RLock()
        self.zeilen = 0
        self.bytes = 0
        self.fehler = 0
        self.letzter_fehler: str | None = None
        self._naechste_marke = 1
        self._datei: TextIO | None = None
        neu = not self.pfad.exists() or self.pfad.stat().st_size == 0
        self._oeffnen()
        self._letzter_fsync = self._uhr_ns()
        self._letzte_uhr: int | None = None
        if neu:
            jetzt = self._uhr_ns()
            self._letzte_uhr = jetzt  # der Kopf trägt selbst ein Uhrpaar
            self.zeile(
                KOPF,
                t=jetzt,
                format=FORMAT,
                start_utc=_jetzt_utc(),
                wall_ns=self._wanduhr_ns(),
                **(kopf or {}),
            )
        else:
            self._naechste_marke = _hoechste_marke(self.pfad) + 1

    def _oeffnen(self) -> None:
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        halb = False
        if self.pfad.exists() and self.pfad.stat().st_size:
            with open(self.pfad, "rb") as f:
                f.seek(-1, os.SEEK_END)
                halb = f.read(1) != b"\n"
        self._datei = open(self.pfad, "a", encoding="utf-8")  # noqa: SIM115 — bleibt offen
        if halb:
            self._datei.write("\n")
        self.bytes = self.pfad.stat().st_size

    @property
    def offen(self) -> bool:
        return self._datei is not None

    def jetzt_ns(self) -> int:
        return self._uhr_ns()

    def zeile(self, art: str, *, t: int | None = None, **felder: Any) -> dict[str, Any]:
        """Eine Zeile ``{"art": …, "t": …, **felder}`` anhängen und zurückgeben.

        Felder mit ``None`` fallen weg; alle `UHR_ABSTAND_S` folgt von selbst eine ``uhr``-Zeile.
        """
        eintrag: dict[str, Any] = {"art": art, "t": self._uhr_ns() if t is None else int(t)}
        eintrag.update({k: v for k, v in felder.items() if v is not None})
        with self._sperre:
            self._anhaengen(eintrag)
            if art != UHR and (
                self._letzte_uhr is None or eintrag["t"] - self._letzte_uhr >= self._uhr_abstand_ns
            ):
                self.uhr(t=eintrag["t"])
        return eintrag

    def _anhaengen(self, eintrag: dict[str, Any]) -> None:
        if self._datei is None:
            return
        text = json.dumps(eintrag, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            self._datei.write(text)
            self._datei.flush()
        except (OSError, ValueError) as fehler:
            self.fehler += 1
            self.letzter_fehler = repr(fehler)
            return
        self.zeilen += 1
        self.bytes += len(text.encode("utf-8"))
        if eintrag["t"] - self._letzter_fsync >= self._fsync_abstand_ns:
            self._sichern(eintrag["t"])

    def uhr(self, *, t: int | None = None) -> None:
        """Ein Uhrpaar: monotone Uhr ``t`` ↔ UTC und Wanduhr (ns)."""
        jetzt = self._uhr_ns() if t is None else int(t)
        with self._sperre:
            self._letzte_uhr = jetzt
            self._anhaengen(
                {"art": UHR, "t": jetzt, "utc": _jetzt_utc(), "wall_ns": self._wanduhr_ns()}
            )

    # -- Bequeme Zeilen ------------------------------------------------------

    def benachrichtigung(
        self,
        c: str,
        daten: bytes,
        *,
        t: int | None = None,
        s: int | None = None,
        tm: int | None = None,
        tw: int | None = None,
    ) -> dict[str, Any]:
        return self.zeile(N, t=t, c=c, x=bytes(daten).hex(), s=s, tm=tm, tw=tw)

    def geschrieben(self, c: str, daten: bytes, *, mit_antwort: bool = True) -> dict[str, Any]:
        return self.zeile(W, c=c, x=bytes(daten).hex(), a=bool(mit_antwort))

    def gelesen(
        self, c: str, daten: bytes | None = None, *, fehler: str | None = None
    ) -> dict[str, Any]:
        return self.zeile(R, c=c, x=None if daten is None else bytes(daten).hex(), fehler=fehler)

    def protokoll(self, text: str, *, q: str = "app", **felder: Any) -> dict[str, Any]:
        return self.zeile(V, text=str(text), q=q, **felder)

    def marke(
        self,
        typ: str,
        *,
        quelle: str = QUELLE_HANDY,
        nr: int | None = None,
        kontext: dict[str, Any] | None = None,
        t: int | None = None,
        tm: int | None = None,
    ) -> dict[str, Any]:
        """Eine Diagnosemarke; die ``id`` zählt je Datei hoch (auch nach einem Neustart)."""
        if typ not in MARKEN_TYPEN:
            raise ValueError(f"unbekannte Marke: {typ}")
        with self._sperre:
            nummer = self._naechste_marke
            self._naechste_marke += 1
            return self.zeile(
                MARKE, t=t, id=nummer, typ=typ, quelle=quelle, nr=nr, tm=tm, kontext=kontext or None
            )

    def marke_weg(self, marke_id: int, *, quelle: str = QUELLE_HANDY) -> dict[str, Any]:
        return self.zeile(MARKE_WEG, id=int(marke_id), quelle=quelle)

    def kontext(self, was: str, **felder: Any) -> dict[str, Any]:
        return self.zeile(KONTEXT, was=was, **felder)

    # -- Datei ---------------------------------------------------------------

    def _sichern(self, jetzt: int | None = None) -> None:
        if self._datei is None:
            return
        self._letzter_fsync = self._uhr_ns() if jetzt is None else jetzt
        with contextlib.suppress(OSError):
            os.fsync(self._datei.fileno())

    def sichern(self) -> None:
        """Auf den Datenträger zwingen (``fsync``) — still, wo es nicht geht."""
        with self._sperre:
            self._sichern()

    def umbenennen(self, ziel: Path | str) -> Path:
        """Die Datei unter neuem Namen weiterführen (Backup → Messdatei); gibt ``ziel`` zurück.

        Liegt am Ziel schon etwas, bleibt das Original (``FileExistsError``) — nichts wird ersetzt.
        """
        ziel = Path(ziel)
        with self._sperre:
            if ziel.exists():
                raise FileExistsError(ziel)
            offen = self._datei is not None
            if offen:
                self._sichern()
                assert self._datei is not None
                self._datei.close()
                self._datei = None
            try:
                os.replace(self.pfad, ziel)
                self.pfad = ziel
            finally:
                if offen:  # auch nach einem Fehler weiter schreiben — dann unter dem alten Namen
                    self._oeffnen()
        return ziel

    def schliessen(self) -> None:
        with self._sperre:
            if self._datei is None:
                return
            self._sichern()
            with contextlib.suppress(OSError):
                self._datei.close()
            self._datei = None


def _hoechste_marke(pfad: Path) -> int:
    hoechste = 0
    for z in lesen(pfad):
        if z.get("art") == MARKE and isinstance(z.get("id"), int):
            hoechste = max(hoechste, int(z["id"]))
    return hoechste


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


def lesen(pfad: Path | str) -> Iterator[dict[str, Any]]:
    """Alle Zeilen als Objekte; eine kaputte (meist die letzte, halbe) wird übergangen.

    >>> import tempfile
    >>> pfad = Path(tempfile.mkdtemp()) / "y.jsonl"
    >>> _ = pfad.write_text('{"art":"n","t":1}\\n{"art":"n","t"\\n{"art":"v","t":3}', "utf-8")
    >>> [z["t"] for z in lesen(pfad)]
    [1, 3]
    """
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                obj = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("art"), str):
                yield obj


@dataclass
class Mitschnitt:
    """Ein gelesener Mitschnitt: der Kopf und alle Zeilen (mit dem Kopf) in Dateireihenfolge."""

    kopf: dict[str, Any]
    zeilen: list[dict[str, Any]]

    def art(self, *arten: str) -> list[dict[str, Any]]:
        return [z for z in self.zeilen if z.get("art") in arten]

    def benachrichtigungen(self, c: str | None = None) -> list[dict[str, Any]]:
        """``n``-Zeilen, wahlweise nur eines Merkmals (Kürzel oder UUID)."""
        if c is None:
            return self.art(N)
        ziel = kuerzel(uuid_von(c))
        return [z for z in self.zeilen if z.get("art") == N and z.get("c") == ziel]

    def marken(self) -> list[dict[str, Any]]:
        """Die gültigen Marken (zurückgenommene fallen weg), nach Zeit sortiert."""
        weg = {z.get("id") for z in self.zeilen if z.get("art") == MARKE_WEG}
        return sorted(
            (z for z in self.zeilen if z.get("art") == MARKE and z.get("id") not in weg),
            key=lambda z: int(z.get("t") or 0),
        )

    def uhrpaare(self) -> list[tuple[int, int]]:
        """``(t, wall_ns)`` je Uhrzeile (und aus dem Kopf)."""
        return [
            (int(z["t"]), int(z["wall_ns"]))
            for z in self.zeilen
            if z.get("art") in (UHR, KOPF)
            and isinstance(z.get("t"), int)
            and isinstance(z.get("wall_ns"), int)
        ]

    @property
    def t0_ns(self) -> int:
        """Zeit der ersten Zeile — Nullpunkt für Sekundenangaben."""
        for z in self.zeilen:
            if isinstance(z.get("t"), int):
                return int(z["t"])
        return 0


def laden(pfad: Path | str) -> Mitschnitt:
    """Einen Mitschnitt lesen. Ohne Kopf (abgeschnittener Anfang) ist ``kopf`` leer."""
    zeilen = list(lesen(pfad))
    kopf = next((z for z in zeilen if z.get("art") == KOPF), {})
    return Mitschnitt(kopf=kopf, zeilen=zeilen)


# ---------------------------------------------------------------------------
# Entschlüsseln: EKG und Beschleunigung aus den PMD-Zeilen
# ---------------------------------------------------------------------------

#: Nennrate je Strom (Hz), wenn der Kopf nichts sagt
NENNRATE: dict[str, float] = {"ecg": 130.0, "acc": float(pmd.ACC_RATE_HZ)}
#: Eine Lücke zwischen zwei Rahmen zählt ab so vielen fehlenden Proben
LUECKE_AB_PROBEN: float = 1.5


@dataclass
class PmdStrom:
    """Ein PMD-Strom (EKG oder ACC) mit Rahmen, Proben und Lücken nach Gerätezeit.

    Je Rahmen: Ankunft (``t`` der Zeile, ns), Gerätezeit der letzten Probe (ns), Probenzahl,
    Folgenummer. Proben hintereinander (EKG ``n``, ACC ``n × 3`` in mG) und je Probe die
    Gerätezeit, zurückgerechnet von der letzten Probe des Rahmens mit der Rate aus der
    Gerätezeit (Median über Rahmen ohne Lücke, nahe der Nennrate).
    """

    name: str
    nennrate_hz: float
    rate_hz: float
    ankunft_ns: np.ndarray
    geraet_ns: np.ndarray
    n_proben: np.ndarray
    seq: list[int | None]
    werte: np.ndarray
    proben_geraet_ns: np.ndarray
    frame_typen: Counter[int] = field(default_factory=Counter)
    #: komprimierte oder unbekannte Rahmen — gezählt, nie als Werte gelesen
    ungelesen: int = 0
    #: ``{"nach_rahmen", "geraet_ns", "dauer_s", "fehlend"}`` je Lücke
    luecken: list[dict[str, Any]] = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(self.proben_geraet_ns.size)

    @property
    def rahmen(self) -> int:
        return int(self.ankunft_ns.size)


def _strom(
    name: str,
    rahmen: list[tuple[int, int, int, np.ndarray, int | None]],
    nennrate: float,
    frame_typen: Counter[int],
    ungelesen: int,
) -> PmdStrom:
    rahmen = sorted(rahmen, key=lambda r: r[1])
    ankunft = np.array([r[0] for r in rahmen], dtype=np.int64)
    geraet = np.array([r[1] for r in rahmen], dtype=np.int64)
    n = np.array([r[2] for r in rahmen], dtype=np.int64)
    if rahmen:
        werte = np.concatenate([r[3] for r in rahmen])
    else:
        werte = np.empty((0, 3), dtype=np.int64) if name == "acc" else np.empty(0, dtype=np.int64)
    rate = float(nennrate)
    if geraet.size >= 3:
        dt = np.diff(geraet) / 1e9
        with np.errstate(divide="ignore", invalid="ignore"):
            je = n[1:] / np.where(dt > 0, dt, np.nan)
        nah = np.isfinite(je) & (np.abs(je - nennrate) < 0.2 * nennrate)
        if nah.any():
            rate = float(np.median(je[nah]))
    luecken: list[dict[str, Any]] = []
    for k in range(1, geraet.size):
        verzug = (geraet[k] - geraet[k - 1]) / 1e9 * rate - n[k]
        if verzug > LUECKE_AB_PROBEN:
            luecken.append(
                {
                    "nach_rahmen": k - 1,
                    "geraet_ns": int(geraet[k - 1]),
                    "dauer_s": round(float(verzug) / rate, 4),
                    "fehlend": round(float(verzug)),
                }
            )
    teile = [
        geraet[k] - np.round((n[k] - 1 - np.arange(n[k])) / rate * 1e9).astype(np.int64)
        for k in range(geraet.size)
    ]
    proben = np.concatenate(teile) if teile else np.empty(0, dtype=np.int64)
    return PmdStrom(
        name=name,
        nennrate_hz=float(nennrate),
        rate_hz=rate,
        ankunft_ns=ankunft,
        geraet_ns=geraet,
        n_proben=n,
        seq=[r[4] for r in rahmen],
        werte=werte,
        proben_geraet_ns=proben,
        frame_typen=frame_typen,
        ungelesen=ungelesen,
        luecken=luecken,
    )


def _nennraten(kopf: dict[str, Any]) -> dict[str, float]:
    raten = dict(NENNRATE)
    stroeme_ = kopf.get("stroeme")
    if isinstance(stroeme_, dict):
        for name in raten:
            eintrag = stroeme_.get(name)
            if isinstance(eintrag, dict) and isinstance(eintrag.get("rate_hz"), int | float):
                raten[name] = float(eintrag["rate_hz"])
    return raten


def stroeme(m: Mitschnitt | Iterable[dict[str, Any]]) -> dict[str, PmdStrom]:
    """EKG (``ecg``, µV) und Beschleunigung (``acc``, mG) aus den ``pmd_data``-Zeilen.

    >>> from hrv_core.geraete.pmd import MEAS_ACC, acc_kodieren, rahmen_bauen
    >>> zeilen = [{"art": "n", "t": 10 + k, "c": "pmd_data", "x": rahmen_bauen(
    ...     MEAS_ACC, (k + 1) * 50_000_000, acc_kodieren([(k, 0, 1000)] * 10), 1).hex()}
    ...     for k in range(4)]
    >>> acc = stroeme(Mitschnitt(kopf={}, zeilen=zeilen))["acc"]
    >>> acc.rahmen, acc.n, acc.rate_hz, acc.werte.shape, acc.luecken
    (4, 40, 200.0, (40, 3), [])
    """
    zeilen = m.zeilen if isinstance(m, Mitschnitt) else list(m)
    kopf = m.kopf if isinstance(m, Mitschnitt) else {}
    rahmen: dict[str, list[tuple[int, int, int, np.ndarray, int | None]]] = {"ecg": [], "acc": []}
    typen: dict[str, Counter[int]] = {"ecg": Counter(), "acc": Counter()}
    ungelesen: Counter[str] = Counter()
    for z in zeilen:
        if z.get("art") != N or z.get("c") != "pmd_data":
            continue
        try:
            daten = bytes.fromhex(str(z.get("x") or ""))
        except ValueError:
            continue
        if len(daten) < pmd.HEADER_SIZE:
            continue
        name = pmd.TYP_NAME.get(daten[0])
        if name not in rahmen:
            continue
        typen[name][daten[9]] += 1
        r = pmd.parse_pmd_rahmen(daten)
        if r is None:
            ungelesen[name] += 1
            continue
        if name == "ecg":
            if r.frame_typ != 0x00:
                ungelesen[name] += 1
                continue
            werte = np.asarray(pmd.parse_ekg_proben(r.nutzdaten), dtype=np.int64)
        else:
            acc = pmd.acc_proben(r)
            if acc is None:
                ungelesen[name] += 1
                continue
            werte = np.asarray(acc, dtype=np.int64).reshape(-1, 3)
        if not werte.shape[0]:
            continue
        seq = z.get("s")
        rahmen[name].append(
            (int(z.get("t") or 0), r.zeitstempel_ns, int(werte.shape[0]), werte, seq)
        )
    nenn = _nennraten(kopf)
    return {
        name: _strom(name, rahmen[name], nenn[name], typen[name], ungelesen[name])
        for name in ("ecg", "acc")
    }


# ---------------------------------------------------------------------------
# Zusammenfassen
# ---------------------------------------------------------------------------


def seq_luecken(zeilen: Iterable[dict[str, Any]]) -> int:
    """Fehlende Folgenummern der Dart-Seite (``s``) — Pakete, die Python nie erreichten.

    Ein Rücksprung (neue Verbindung, Neustart der Erweiterung) beginnt neu.

    >>> seq_luecken([{"art": "n", "s": s} for s in (1, 2, 5, 6, 1, 2)])
    2
    """
    luecken = 0
    letzte: int | None = None
    for z in zeilen:
        if z.get("art") != N or not isinstance(z.get("s"), int):
            continue
        s = int(z["s"])
        if letzte is not None and s > letzte + 1:
            luecken += s - letzte - 1
        letzte = s
    return luecken


def zusammenfassen(m: Mitschnitt) -> dict[str, Any]:
    """Was im Mitschnitt steht: Dauer, Zeilen je Art, Pakete je Merkmal, Marken je Typ, Ströme.

    >>> z = zusammenfassen(Mitschnitt(kopf={"art": "kopf"}, zeilen=[
    ...     {"art": "kopf", "t": 0}, {"art": "n", "t": 2_000_000_000, "c": "hr", "x": "0040"},
    ...     {"art": "marke", "t": 1, "id": 1, "typ": "wdh"},
    ...     {"art": "marke", "t": 2, "id": 2, "typ": "wdh"},
    ...     {"art": "marke_weg", "t": 3, "id": 2}]))
    >>> z["dauer_s"], z["pakete"], z["marken"], z["bytes_nutzdaten"]
    (2.0, {'hr': 1}, {'wdh': 1}, 2)
    """
    zeiten = [int(z["t"]) for z in m.zeilen if isinstance(z.get("t"), int)]
    arten = Counter(str(z.get("art")) for z in m.zeilen)
    pakete = Counter(str(z.get("c")) for z in m.zeilen if z.get("art") == N)
    nutz = sum(len(str(z.get("x") or "")) // 2 for z in m.zeilen if z.get("art") == N)
    marken = Counter(str(z.get("typ")) for z in m.marken())
    quellen = Counter(str(z.get("quelle") or QUELLE_HANDY) for z in m.marken())
    getrennt = sum(1 for z in m.zeilen if z.get("art") == V and z.get("zustand") == "getrennt")
    stroeme_ = stroeme(m)
    return {
        "format": m.kopf.get("format"),
        "dauer_s": round((max(zeiten) - min(zeiten)) / 1e9, 1) if zeiten else 0.0,
        "zeilen": dict(sorted(arten.items())),
        "pakete": dict(sorted(pakete.items())),
        "bytes_nutzdaten": nutz,
        "seq_luecken": seq_luecken(m.zeilen),
        "trennungen": getrennt,
        "marken": dict(sorted(marken.items())),
        "marken_quelle": dict(sorted(quellen.items())),
        "stroeme": {
            name: {
                "rahmen": s.rahmen,
                "proben": s.n,
                "rate_hz": round(s.rate_hz, 2),
                "luecken": len(s.luecken),
                "ungelesen": s.ungelesen,
            }
            for name, s in stroeme_.items()
            if s.rahmen or s.ungelesen
        },
    }


__all__ = [
    "ARTEN",
    "BATTERY_LEVEL_UUID",
    "DATEINAME",
    "ENDUNG",
    "FORMAT",
    "FSYNC_ABSTAND_S",
    "GERAETEINFO",
    "HR_MEASUREMENT_UUID",
    "KENNUNGS_MERKMALE",
    "KONTEXT",
    "KONTEXT_WAS",
    "KOPF",
    "KUERZEL",
    "MARKE",
    "MARKEN_TYPEN",
    "MARKE_ATEM",
    "MARKE_FREI",
    "MARKE_STOERUNG",
    "MARKE_WDH",
    "MARKE_WEG",
    "NIE_LESEN",
    "PROBE",
    "QUELLE_HANDY",
    "QUELLE_UHR",
    "UHR",
    "UHR_ABSTAND_S",
    "Mitschnitt",
    "PmdStrom",
    "Schreiber",
    "ist_mitschnitt",
    "journal_pfad",
    "kuerzel",
    "laden",
    "lesen",
    "mitschnitt_pfad",
    "seq_luecken",
    "stroeme",
    "uuid_von",
    "zusammenfassen",
]
