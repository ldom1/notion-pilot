#!/usr/bin/env python
"""Dedup Companies — one-shot data-quality pass.

Runs crm_dedup.py --companies (prints suspected duplicates for review).
Enrichment is now handled by prosper's MCP `enrich_companies` tool, not a
subprocess step — call it from an MCP-aware client (e.g. Claude Code).

Usage:
    uv run python scripts/crm/crm_refresh_companies.py
"""

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent

_STEPS = [
    ("Dedup Companies", [sys.executable, str(_ROOT / "crm_dedup.py"), "--companies"]),
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
