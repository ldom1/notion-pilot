"""Summarize data/email-import-review.csv — senders and counts.

Usage:
    uv run python scripts/inbox/analyze_email_review.py
    uv run python scripts/inbox/analyze_email_review.py --csv path/to/file.csv
"""

import sys
from pathlib import Path

import pandas as pd

_DEFAULT_CSV = Path("data/inbox/email-import-review.csv")


def _arg(name: str) -> str | None:
    for a in sys.argv:
        if a.startswith(f"{name}="):
            return a.split("=", 1)[1]
    return None


def main(csv_path: Path) -> None:
    if not csv_path.is_file():
        print(f"Missing file: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path, sep=None, engine="python", encoding="utf-8-sig", dtype=str).fillna(
        ""
    )
    by_sender = df["sender"].str.strip().value_counts()

    print(f"File: {csv_path}")
    print(f"Total rows: {len(df)}")
    print(f"Unique senders: {len(by_sender)}\n")
    print(f"{'count':>6}  sender")
    print("-" * 60)
    for sender, count in by_sender.items():
        print(f"{count:>6}  {sender}")


if __name__ == "__main__":
    main(Path(_arg("--csv") or _DEFAULT_CSV))
