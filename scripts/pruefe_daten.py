"""Testdatenordner prüfen — vor jeder Sitzung, in der Claude Code Testdaten liest.

    python scripts/pruefe_daten.py            # $HRV_TESTDATA (Ordner in hrv-research)
    python scripts/pruefe_daten.py tests/fixtures --ohne-ordnerregel

Abgelehnt werden gefüllte Personenfelder (auch verschachtelt: ``teilnehmer[]``,
``_wiederherstellung.subject_id``), Seriennummern im Gerätenamen, unbekannte
Felder oder Dateiformate und Ordner, deren Name nicht ``p###`` oder ``selbst``
ist (Exit-Code 1). Freitext (``titel``, ``notiz``, Ereignistexte, ``marke.name``,
Abschnittsnamen) wird nur aufgezählt — den liest Ben selbst.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_core.deid import pruefen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    vorgabe = os.environ.get("HRV_TESTDATA")
    parser.add_argument("wurzel", nargs="?", default=vorgabe, type=Path)
    parser.add_argument(
        "--ohne-ordnerregel",
        action="store_true",
        help="Ordnernamen nicht prüfen (für tests/fixtures)",
    )
    args = parser.parse_args(argv)
    if args.wurzel is None:
        print(
            "Kein Testdatenordner: $HRV_TESTDATA setzen (Ordner in hrv-research) oder Pfad angeben."
        )
        return 2
    bericht = pruefen(args.wurzel, ordnerregel=not args.ohne_ordnerregel)
    for pfad, grund in bericht.ablehnungen:
        print(f"ABGELEHNT  {pfad}: {grund}")
    for pfad, grund in bericht.hinweise:
        print(f"Hinweis    {pfad}: {grund}")
    print(
        f"{bericht.geprueft} Dateien geprüft, {len(bericht.ablehnungen)} abgelehnt, "
        f"{len(bericht.hinweise)} Hinweise"
    )
    return 0 if bericht.ok else 1


if __name__ == "__main__":
    sys.exit(main())
