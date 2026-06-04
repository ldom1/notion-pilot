#!/usr/bin/env python
"""Dedup then enrich Companies — one-shot data-quality pass.

Runs crm_dedup.py --companies first (prints suspected duplicates for review),
then crm_enrich.py --companies to fill in missing data via Apollo / Brave Search.

Usage:
    uv run python scripts/crm/crm_refresh_companies.py
"""

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent

_STEPS = [
    ("Dedup Companies", [sys.executable, str(_ROOT / "crm_dedup.py"), "--companies"]),
    ("Enrich Companies", [sys.executable, str(_ROOT / "crm_enrich.py"), "--companies"]),
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
