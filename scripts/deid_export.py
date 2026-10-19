"""De-identifizierte Kopie von Messdateien in einen Personenordner legen.

Nur Ben führt das lokal aus — das Skript liest Originale aus den
Patientenordnern und schreibt ausschließlich die Kopie:

    python scripts/deid_export.py <messdatei…> --ziel $HRV_TESTDATA/p001 [--mit-beiwerk]

Weißliste je Feld (`hrv_core.deid.REGELN`): Personenfelder werden ``null``,
der Gerätename verliert seine Seriennummer, unbekannte Felder und der
Backup-Block fallen weg, Freitext wird gemeldet — das Protokoll nennt nur
Feldpfade, nie Inhalte. **Bewusst erhalten** bleiben ``start_utc``, ``datum``,
``wall_time`` und der Dateiname mit der UTC-Startsekunde (Ben, 19.10.2026:
Tagesdatum und Tageszeit sind für HRV-Aussagen wichtig); darum gehören die
Kopien nur in den Testdatenordner des privaten Repos hrv-research, nie in
hrv-core. Danach ``python scripts/pruefe_daten.py`` laufen lassen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_core.deid import deidentifizieren


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("messdateien", nargs="+", type=Path)
    parser.add_argument(
        "--ziel",
        required=True,
        type=Path,
        help="Personenordner in hrv-research, z. B. $HRV_TESTDATA/p001",
    )
    parser.add_argument(
        "--mit-beiwerk", action="store_true", help="_analyzed/_ecg/_ppg/_truth/__cNN mitnehmen"
    )
    parser.add_argument("--ueberschreiben", action="store_true")
    args = parser.parse_args(argv)
    for quelle in args.messdateien:
        protokoll: list[tuple[Path, str]] = []
        ziele = deidentifizieren(
            quelle,
            args.ziel,
            mit_beiwerk=args.mit_beiwerk,
            ueberschreiben=args.ueberschreiben,
            protokoll=protokoll,
        )
        for ziel in ziele:
            print(f"geschrieben: {ziel}")
            for pfad, meldung in protokoll:
                if pfad == ziel:
                    print(f"    {meldung}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
