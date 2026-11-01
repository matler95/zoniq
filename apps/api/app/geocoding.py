"""Small, policy-conscious adapter for user-triggered address search."""

from __future__ import annotations

import json
import os
import time
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_CACHE: dict[str, list[dict[str, object]]] = {}
_LOCK = Lock()
_LAST_REQUEST = 0.0
_MIN_INTERVAL_SECONDS = 1.0
_USER_AGENT = os.getenv("ZONIQ_GEOCODER_USER_AGENT", "zoniq-development/0.1 (local accessibility analysis)")


def search_address(query: str) -> list[dict[str, object]]:
    """Search Nominatim once per user action; callers must not autocomplete."""
    normalized = " ".join(query.strip().split())
    if len(normalized) < 3:
        return []
    key = normalized.casefold()
    if key in _CACHE:
        return _CACHE[key]
    global _LAST_REQUEST
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        delay = _MIN_INTERVAL_SECONDS - (time.monotonic() - _LAST_REQUEST)
        if delay > 0:
            time.sleep(delay)
        params = urlencode({"q": f"{normalized}, Warszawa", "format": "jsonv2", "limit": 5, "countrycodes": "pl", "addressdetails": 1})
        request = Request(f"https://nominatim.openstreetmap.org/search?{params}", headers={"User-Agent": _USER_AGENT, "Accept-Language": "pl"})
        with urlopen(request, timeout=6) as response:  # nosec B310: fixed HTTPS host
            payload = json.load(response)
        _LAST_REQUEST = time.monotonic()
        results = parse_results(payload)
        _CACHE[key] = results
        return results


def reverse_address(lat: float, lon: float) -> str | None:
    """Resolve a user-clicked map point to an address with the same rate limit."""
    key = f"reverse:{lat:.5f}:{lon:.5f}"
    if key in _CACHE:
        return str(_CACHE[key][0]["label"]) if _CACHE[key] else None
    global _LAST_REQUEST
    with _LOCK:
        if key in _CACHE:
            return str(_CACHE[key][0]["label"]) if _CACHE[key] else None
        delay = _MIN_INTERVAL_SECONDS - (time.monotonic() - _LAST_REQUEST)
        if delay > 0:
            time.sleep(delay)
        params = urlencode({"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 18})
        request = Request(f"https://nominatim.openstreetmap.org/reverse?{params}", headers={"User-Agent": _USER_AGENT, "Accept-Language": "pl"})
        with urlopen(request, timeout=6) as response:  # nosec B310: fixed HTTPS host
            payload = json.load(response)
        _LAST_REQUEST = time.monotonic()
        label = str(payload["display_name"]) if "display_name" in payload else None
        _CACHE[key] = [{"label": label}] if label else []
        return label


def parse_results(payload: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {"label": str(item["display_name"]), "lat": float(item["lat"]), "lon": float(item["lon"])}
        for item in payload
        if "display_name" in item and "lat" in item and "lon" in item
    ]
