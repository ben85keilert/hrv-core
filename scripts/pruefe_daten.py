#!/usr/bin/env python
"""Testdatenordner prüfen — vor jeder Sitzung, in der Claude Code Testdaten liest.

    python scripts/pruefe_daten.py            # daten/ bzw. $HRV_TESTDATA
    python scripts/pruefe_daten.py tests/fixtures --ohne-ordnerregel

Abgelehnt werden Dateien mit gefülltem ``patient_id``/``behandlung_id`` und
Ordner, deren Name nicht ``p###`` oder ``selbst`` ist (Exit-Code 1). Freitext
(``titel``, ``notiz``, Ereignistexte) wird nur aufgezählt — den liest Ben selbst.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_core.deid import pruefen  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    vorgabe = os.environ.get("HRV_TESTDATA") or str(Path(__file__).resolve().parents[1] / "daten")
    parser.add_argument("wurzel", nargs="?", default=vorgabe, type=Path)
    parser.add_argument("--ohne-ordnerregel", action="store_true", help="Ordnernamen nicht prüfen (für tests/fixtures)")
    args = parser.parse_args(argv)
    bericht = pruefen(args.wurzel, ordnerregel=not args.ohne_ordnerregel)
    for pfad, grund in bericht.ablehnungen:
        print(f"ABGELEHNT  {pfad}: {grund}")
    for pfad, grund in bericht.hinweise:
        print(f"Hinweis    {pfad}: {grund}")
    print(f"{bericht.geprueft} Dateien geprüft, {len(bericht.ablehnungen)} abgelehnt, {len(bericht.hinweise)} Hinweise")
    return 0 if bericht.ok else 1


if __name__ == "__main__":
    sys.exit(main())
