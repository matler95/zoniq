from datetime import date
from pathlib import Path
from zipfile import ZipFile

from app.gtfs import find_direct_journeys, find_one_transfer_journeys, find_reachable_stops, prepare_store


def make_direct_feed(path: Path) -> None:
    rows = {
        "agency.txt": "agency_name,agency_url,agency_timezone\nZTM,https://ztm.waw.pl,Europe/Warsaw\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Start,52.200,21.000\nB,End,52.210,21.010\n",
        "routes.txt": "route_id,route_short_name,route_type\nM1,M1,1\n",
        "trips.txt": "route_id,service_id,trip_id\nM1,weekday,trip-1\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\ntrip-1,08:00:00,08:00:00,A,1\ntrip-1,08:10:00,08:10:00,B,2\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nweekday,1,1,1,1,1,0,0,20261101,20261231\n",
    }
    with ZipFile(path, "w") as zip_file:
        for filename, contents in rows.items():
            zip_file.writestr(filename, contents)


def test_prepared_store_returns_direct_scheduled_journey(tmp_path: Path) -> None:
    archive = tmp_path / "feed.zip"
    database = tmp_path / "gtfs.sqlite"
    make_direct_feed(archive)
    prepare_store(archive, database, "ztm")

    journeys = find_direct_journeys(database, (52.200, 21.000), (52.210, 21.010), date(2026, 11, 2), 7 * 3600 + 50 * 60)

    assert len(journeys) == 1
    assert journeys[0]["route"] == "M1"
    assert journeys[0]["duration_minutes"] == 20.0

    reachable = find_reachable_stops(database, (52.200, 21.000), date(2026, 11, 2), 7 * 3600 + 50 * 60, 30, (1,))
    assert reachable[0]["stop_id"] == "ztm:B"
    assert reachable[0]["travel_minutes"] == 20.0


def test_prepared_store_finds_one_transfer_from_calendar_dates(tmp_path: Path) -> None:
    archive = tmp_path / "transfer.zip"
    database = tmp_path / "gtfs.sqlite"
    rows = {
        "agency.txt": "agency_name,agency_url,agency_timezone\nZTM,https://ztm.waw.pl,Europe/Warsaw\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Start,52.200,21.000\nX,Change,52.212,21.012\nB,End,52.222,21.022\n",
        "routes.txt": "route_id,route_short_name,route_type\nR1,1,3\nR2,2,3\n",
        "trips.txt": "route_id,service_id,trip_id\nR1,special,first\nR2,special,second\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nfirst,08:00:00,08:00:00,A,1\nfirst,08:08:00,08:08:00,X,2\nsecond,08:12:00,08:12:00,X,1\nsecond,08:22:00,08:22:00,B,2\n",
        "calendar_dates.txt": "service_id,date,exception_type\nspecial,20261102,1\n",
    }
    with ZipFile(archive, "w") as zip_file:
        for filename, contents in rows.items():
            zip_file.writestr(filename, contents)
    prepare_store(archive, database, "ztm")

    journeys = find_one_transfer_journeys(database, (52.200, 21.000), (52.222, 21.022), date(2026, 11, 2), 7 * 3600 + 50 * 60)

    assert journeys[0]["route"] == "1 → 2"
    assert journeys[0]["transfers"] == 1

    reachable = find_reachable_stops(database, (52.200, 21.000), date(2026, 11, 2), 7 * 3600 + 50 * 60, 40, (3,), max_transfers=1)
    assert any(stop["stop_id"] == "ztm:B" and stop["transfers"] == 1 for stop in reachable)


def test_reachable_stops_allows_walking_transfer_between_platforms(tmp_path: Path) -> None:
    archive = tmp_path / "platform-transfer.zip"
    database = tmp_path / "gtfs.sqlite"
    rows = {
        "agency.txt": "agency_name,agency_url,agency_timezone\nZTM,https://ztm.waw.pl,Europe/Warsaw\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Start,52.200,21.000\nX,Platform A,52.212,21.012\nY,Platform B,52.2124,21.012\nB,End,52.222,21.022\n",
        "routes.txt": "route_id,route_short_name,route_type\nR1,1,3\nR2,2,3\n",
        "trips.txt": "route_id,service_id,trip_id\nR1,special,first\nR2,special,second\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nfirst,08:00:00,08:00:00,A,1\nfirst,08:08:00,08:08:00,X,2\nsecond,08:12:00,08:12:00,Y,1\nsecond,08:22:00,08:22:00,B,2\n",
        "calendar_dates.txt": "service_id,date,exception_type\nspecial,20261102,1\n",
    }
    with ZipFile(archive, "w") as zip_file:
        for filename, contents in rows.items():
            zip_file.writestr(filename, contents)
    prepare_store(archive, database, "ztm")

    reachable = find_reachable_stops(database, (52.200, 21.000), date(2026, 11, 2), 7 * 3600 + 50 * 60, 40, (3,), max_transfers=1)

    assert any(stop["stop_id"] == "ztm:B" and stop["transfers"] == 1 for stop in reachable)
