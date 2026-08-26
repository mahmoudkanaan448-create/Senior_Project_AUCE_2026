"""
IP reputation lookup via AbuseIPDB (keyed) and ip-api.com (free fallback).

Enriches a source IP with reputation, geo/ISP metadata, threat_score,
and blacklist status for risk scoring and the dashboard.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict

import requests

from config import ABUSEIPDB_API_KEY

_ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"
_IPAPI_URL = "http://ip-api.com/json"
_REQUEST_TIMEOUT = 10


def _query_abuseipdb(ip_address: str) -> Dict[str, Any]:
    """Query the AbuseIPDB v2 API for reputation data."""
    headers = {
        "Accept": "application/json",
        "Key": ABUSEIPDB_API_KEY,
    }
    params = {"ipAddress": ip_address, "maxAgeInDays": 90, "verbose": ""}

    resp = requests.get(_ABUSEIPDB_URL, headers=headers, params=params, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json().get("data", {})

    return {
        "reputation": "malicious" if data.get("abuseConfidenceScore", 0) > 50 else "clean",
        "country": data.get("countryCode", "Unknown"),
        "city": "N/A",
        "isp": data.get("isp", "Unknown"),
        "asn": str(data.get("asn", "Unknown")),
        "threat_score": min(data.get("abuseConfidenceScore", 0) / 10.0, 10.0),
        "reports": data.get("totalReports", 0),
        "blacklisted": data.get("abuseConfidenceScore", 0) > 75,
    }


def _query_ipapi(ip_address: str) -> Dict[str, Any]:
    """Fallback geo-location query via ip-api.com."""
    resp = requests.get(f"{_IPAPI_URL}/{ip_address}", timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "success":
        raise ValueError(data.get("message", "ip-api query failed"))

    return {
        "reputation": "unknown",
        "country": data.get("country", "Unknown"),
        "city": data.get("city", "Unknown"),
        "isp": data.get("isp", "Unknown"),
        "asn": data.get("as", "Unknown"),
        "threat_score": 0.0,
        "reports": 0,
        "blacklisted": False,
    }


def lookup_ip(ip_address: str) -> Dict[str, Any]:
    """Look up reputation and geo-data; prefer AbuseIPDB, else ip-api.com."""
    result: Dict[str, Any] = {
        "ip": ip_address,
        "reputation": "unknown",
        "country": "Unknown",
        "city": "Unknown",
        "isp": "Unknown",
        "asn": "Unknown",
        "threat_score": 0.0,
        "reports": 0,
        "blacklisted": False,
        "source": "none",
    }

    if ABUSEIPDB_API_KEY:
        try:
            abuse_data = _query_abuseipdb(ip_address)
            result.update(abuse_data)
            result["source"] = "abuseipdb"
        except Exception as exc:
            print(f"[IPLookup] AbuseIPDB failed for {ip_address}: {exc}")

    if result["source"] != "abuseipdb" or result["city"] == "N/A":
        try:
            geo = _query_ipapi(ip_address)
            if result["source"] != "abuseipdb":
                result.update(geo)
                result["source"] = "ip-api"
            else:
                result["city"] = geo.get("city", "Unknown")
                result["country"] = geo.get("country", result["country"])
        except Exception as exc:
            print(f"[IPLookup] ip-api fallback failed for {ip_address}: {exc}")

    return result
