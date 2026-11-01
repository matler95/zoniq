from app.geocoding import parse_results


def test_parse_results_uses_coordinates_and_label() -> None:
    results = parse_results([{"display_name": "Kabaty, Warszawa", "lat": "52.131", "lon": "21.065"}])
    assert results == [{"label": "Kabaty, Warszawa", "lat": 52.131, "lon": 21.065}]
