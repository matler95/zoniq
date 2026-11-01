from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

from app.gtfs import GTFSValidationError, inspect_feed, scope_id, write_report


def make_feed(path: Path, include_stops: bool = True) -> None:
    files = {
        "agency.txt": "agency_name,agency_url,agency_timezone\nZTM,https://ztm.waw.pl,Europe/Warsaw\n",
        "routes.txt": "route_id,route_type\nM1,1\n",
        "trips.txt": "route_id,service_id,trip_id\nM1,weekday,trip-1\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\ntrip-1,08:00:00,08:00:00,A,1\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nweekday,1,1,1,1,1,0,0,20261101,20261231\n",
    }
    if include_stops:
        files["stops.txt"] = "stop_id,stop_name,stop_lat,stop_lon\nA,Metro,52.2,21.0\n"
    with ZipFile(path, "w") as zip_file:
        for name, content in files.items():
            zip_file.writestr(name, content)


def test_inspect_feed_captures_provenance_and_service_range(tmp_path: Path) -> None:
    archive = tmp_path / "ztm.zip"
    make_feed(archive)

    report = inspect_feed(archive, "ztm", datetime(2026, 11, 1, tzinfo=UTC))

    assert report.rows == {"agency": 1, "stops": 1, "routes": 1, "trips": 1, "stop_times": 1}
    assert report.service_start == "20261101"
    assert report.service_end == "20261231"
    assert report.sha256
    report_path = write_report(report, tmp_path / "metadata")
    assert '"feed_id": "ztm"' in report_path.read_text(encoding="utf-8")


def test_inspect_feed_rejects_incomplete_archives(tmp_path: Path) -> None:
    archive = tmp_path / "broken.zip"
    make_feed(archive, include_stops=False)

    with pytest.raises(GTFSValidationError, match="stops.txt"):
        inspect_feed(archive, "ztm")


def test_scope_id_keeps_feed_namespace() -> None:
    assert scope_id("ztm", "123") == "ztm:123"
