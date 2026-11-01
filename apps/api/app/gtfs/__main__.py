"""Run GTFS validation without starting the API."""

from __future__ import annotations

import argparse
from pathlib import Path

from .ingestion import inspect_feed, write_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a GTFS ZIP and write immutable intake metadata.")
    parser.add_argument("archive", type=Path, help="Path to the downloaded GTFS ZIP")
    parser.add_argument("--feed-id", required=True, help="Stable source namespace, e.g. ztm")
    parser.add_argument("--report-dir", type=Path, default=Path("data/processed/metadata"))
    args = parser.parse_args()

    report = inspect_feed(args.archive, args.feed_id)
    destination = write_report(report, args.report_dir)
    print(destination)


if __name__ == "__main__":
    main()
