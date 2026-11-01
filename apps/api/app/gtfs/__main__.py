"""Run GTFS validation without starting the API."""

from __future__ import annotations

import argparse
from pathlib import Path

from .ingestion import inspect_feed, write_report
from .store import prepare_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and prepare GTFS data.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "prepare"):
        command = subparsers.add_parser(name)
        command.add_argument("archive", type=Path, help="Path to the downloaded GTFS ZIP")
        command.add_argument("--feed-id", required=True, help="Stable source namespace, e.g. ztm")
        command.add_argument("--report-dir", type=Path, default=Path("data/processed/metadata"))
        if name == "prepare":
            command.add_argument("--database", type=Path, default=Path("data/processed/ztm.sqlite"))
    args = parser.parse_args()

    report = prepare_store(args.archive, args.database, args.feed_id) if args.command == "prepare" else inspect_feed(args.archive, args.feed_id)
    destination = write_report(report, args.report_dir)
    print(destination)


if __name__ == "__main__":
    main()
