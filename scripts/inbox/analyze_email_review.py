"""Summarize data/email-import-review.csv — senders and counts.

Usage:
    uv run python scripts/inbox/analyze_email_review.py
    uv run python scripts/inbox/analyze_email_review.py --csv path/to/file.csv
"""

import csv
import sys
from collections import Counter
from pathlib import Path

_DEFAULT_CSV = Path("data/email-import-review.csv")


def _arg(name: str) -> str | None:
    for a in sys.argv:
        if a.startswith(f"{name}="):
            return a.split("=", 1)[1]
    return None


def main(csv_path: Path) -> None:
    if not csv_path.is_file():
        print(f"Missing file: {csv_path}")
        sys.exit(1)

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    by_sender = Counter(r["sender"].strip() for r in rows if r.get("sender"))

    print(f"File: {csv_path}")
    print(f"Total rows: {len(rows)}")
    print(f"Unique senders: {len(by_sender)}\n")
    print(f"{'count':>6}  sender")
    print("-" * 60)
    for sender, count in by_sender.most_common():
        print(f"{count:>6}  {sender}")


if __name__ == "__main__":
    main(Path(_arg("--csv") or _DEFAULT_CSV))
