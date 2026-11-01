"""Small, dependency-free GTFS intake layer.

The transport router must not receive arbitrary ZIP files. This module checks the
minimum static GTFS contract, records immutable source provenance and exposes a
stable feed-qualified identifier convention for subsequent normalization.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from zipfile import BadZipFile, ZipFile

REQUIRED_FILES: dict[str, set[str]] = {
    "agency.txt": {"agency_name", "agency_url", "agency_timezone"},
    "stops.txt": {"stop_id", "stop_name", "stop_lat", "stop_lon"},
    "routes.txt": {"route_id", "route_type"},
    "trips.txt": {"route_id", "service_id", "trip_id"},
    "stop_times.txt": {"trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"},
}


class GTFSValidationError(ValueError):
    """A feed cannot safely enter the processing pipeline."""


@dataclass(frozen=True)
class FeedReport:
    feed_id: str
    source_file: str
    sha256: str
    imported_at: str
    rows: dict[str, int]
    service_start: str | None
    service_end: str | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def scope_id(feed_id: str, source_id: str) -> str:
    """Avoid collisions when an operator reuses GTFS identifiers."""
    if not feed_id.strip() or not source_id.strip():
        raise ValueError("feed_id and source_id must not be blank")
    return f"{feed_id.strip()}:{source_id.strip()}"


def inspect_feed(archive: Path, feed_id: str, imported_at: datetime | None = None) -> FeedReport:
    """Validate one GTFS ZIP and return a reproducible source report.

    No transit data is persisted here: validation is deliberately a separate,
    idempotent step before normalization and Parquet generation.
    """
    if not archive.is_file():
        raise GTFSValidationError(f"GTFS archive not found: {archive}")

    try:
        with ZipFile(archive) as zip_file:
            members = _members_by_filename(zip_file.namelist())
            _validate_file_set(members)
            rows = {name.removesuffix(".txt"): _row_count(zip_file, member) for name, member in members.items() if name in REQUIRED_FILES}
            service_start, service_end = _service_range(zip_file, members)
    except BadZipFile as error:
        raise GTFSValidationError(f"Invalid GTFS ZIP: {archive.name}") from error

    timestamp = imported_at or datetime.now(UTC)
    return FeedReport(
        feed_id=feed_id,
        source_file=archive.name,
        sha256=_sha256(archive),
        imported_at=timestamp.astimezone(UTC).isoformat(),
        rows=rows,
        service_start=service_start,
        service_end=service_end,
    )


def write_report(report: FeedReport, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{report.feed_id}-{report.sha256[:12]}.json"
    target.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _members_by_filename(names: Iterable[str]) -> dict[str, str]:
    members: dict[str, str] = {}
    for name in names:
        if name.endswith("/"):
            continue
        filename = Path(name).name.lower()
        if filename in REQUIRED_FILES or filename in {"calendar.txt", "calendar_dates.txt"}:
            if filename in members:
                raise GTFSValidationError(f"Duplicate GTFS file: {filename}")
            members[filename] = name
    return members


def _validate_file_set(members: dict[str, str]) -> None:
    missing = sorted(set(REQUIRED_FILES) - set(members))
    if missing:
        raise GTFSValidationError(f"Missing required GTFS files: {', '.join(missing)}")
    if "calendar.txt" not in members and "calendar_dates.txt" not in members:
        raise GTFSValidationError("GTFS requires calendar.txt or calendar_dates.txt")


def _reader(zip_file: ZipFile, member: str) -> csv.DictReader:
    text = zip_file.read(member).decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise GTFSValidationError(f"Empty GTFS table: {Path(member).name}")
    filename = Path(member).name.lower()
    required_columns = REQUIRED_FILES.get(filename, set())
    missing = sorted(required_columns - set(reader.fieldnames))
    if missing:
        raise GTFSValidationError(f"{filename} missing columns: {', '.join(missing)}")
    return reader


def _row_count(zip_file: ZipFile, member: str) -> int:
    return sum(1 for _ in _reader(zip_file, member))


def _service_range(zip_file: ZipFile, members: dict[str, str]) -> tuple[str | None, str | None]:
    dates: list[str] = []
    calendar = members.get("calendar.txt")
    if calendar:
        rows = _reader(zip_file, calendar)
        if not {"start_date", "end_date"}.issubset(rows.fieldnames or set()):
            raise GTFSValidationError("calendar.txt missing columns: start_date, end_date")
        for row in rows:
            dates.extend(value for value in (row["start_date"], row["end_date"]) if value)
    exceptions = members.get("calendar_dates.txt")
    if exceptions:
        rows = _reader(zip_file, exceptions)
        if "date" not in (rows.fieldnames or []):
            raise GTFSValidationError("calendar_dates.txt missing columns: date")
        dates.extend(row["date"] for row in rows if row["date"])
    return (min(dates), max(dates)) if dates else (None, None)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
