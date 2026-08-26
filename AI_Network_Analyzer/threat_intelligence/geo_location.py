"""
Geo-location lookup via the free ip-api.com service.

Resolves an IP to country, city, coordinates, ISP, ASN, and timezone
for map plots and alert context. Returns safe defaults on failure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict

import requests

_IPAPI_URL = "http://ip-api.com/json"
_REQUEST_TIMEOUT = 10


def get_location(ip_address: str) -> Dict[str, Any]:
    """Resolve an IP address to geographic and network metadata."""
    default: Dict[str, Any] = {
        "country": "Unknown",
        "city": "Unknown",
        "region": "Unknown",
        "lat": 0.0,
        "lon": 0.0,
        "isp": "Unknown",
        "org": "Unknown",
        "asn": "Unknown",
        "timezone": "Unknown",
    }

    try:
        resp = requests.get(
            f"{_IPAPI_URL}/{ip_address}",
            params={"fields": "status,message,country,city,regionName,lat,lon,isp,org,as,timezone"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            print(f"[GeoLocation] Query failed for {ip_address}: {data.get('message')}")
            return default

        return {
            "country": data.get("country", "Unknown"),
            "city": data.get("city", "Unknown"),
            "region": data.get("regionName", "Unknown"),
            "lat": float(data.get("lat", 0.0)),
            "lon": float(data.get("lon", 0.0)),
            "isp": data.get("isp", "Unknown"),
            "org": data.get("org", "Unknown"),
            "asn": data.get("as", "Unknown"),
            "timezone": data.get("timezone", "Unknown"),
        }

    except requests.RequestException as exc:
        print(f"[GeoLocation] Request error for {ip_address}: {exc}")
        return default
