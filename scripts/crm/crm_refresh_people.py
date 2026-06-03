#!/usr/bin/env python
"""Dedup then enrich People — one-shot data-quality pass.

Runs crm_dedup.py --people first (prints suspected duplicates for review),
then crm_enrich.py --people to fill in missing data via Apollo / Brave Search.

Usage:
    uv run python scripts/crm/crm_refresh_people.py
"""

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent

_STEPS = [
    ("Dedup People", [sys.executable, str(_ROOT / "crm_dedup.py"), "--people"]),
    ("Enrich People", [sys.executable, str(_ROOT / "crm_enrich.py"), "--people"]),
]


def main() -> None:
    for label, cmd in _STEPS:
        print(f"\n── {label} {'─' * (50 - len(label))}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"\n✗ {label} failed (exit {result.returncode}), stopping.")
            sys.exit(result.returncode)
    print("\n✓ Refresh complete.")


if __name__ == "__main__":
    main()
