#!/usr/bin/env python
"""Golden-Master-Dateien neu schreiben — nur nach einer bewusst begründeten Algorithmusänderung.

    uv run python scripts/golden_erneuern.py [--fixtures DIR] [--ziel DIR]

Vorher: Begründung in docs/, Notebook unter notebooks/, ALGO_VERSION hochzählen.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "src"))

from hrv_core.referenz import ist_rohdatei, referenz  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixtures", type=Path, default=HIER.parent / "tests" / "fixtures")
    parser.add_argument("--ziel", type=Path, default=HIER.parent / "tests" / "golden" / "trainingsapp")
    args = parser.parse_args(argv)
    args.ziel.mkdir(parents=True, exist_ok=True)
    for p in sorted(x for x in args.fixtures.rglob("sensor_*.json") if ist_rohdatei(x)):
        name = f"{p.parent.name}__{p.stem}.json"
        with open(args.ziel / name, "w", encoding="utf-8") as fh:
            json.dump(referenz(p), fh, ensure_ascii=False, separators=(",", ":"))
        print("geschrieben:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
