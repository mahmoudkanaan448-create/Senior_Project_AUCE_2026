"""Cloud telemetry ingestion (AWS VPC Flow / Azure NSG / GCP VPC) – CSV/JSON."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List


def parse_aws_vpc_flow(text: str) -> List[Dict[str, Any]]:
    """Parse space-separated AWS VPC Flow Logs version 2+."""
    rows = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("version"):
            continue
        parts = line.split()
        if len(parts) < 14:
            continue
        try:
            rows.append({
                "source_ip": parts[3],
                "destination_ip": parts[4],
                "source_port": int(parts[5]) if parts[5].isdigit() else 0,
                "destination_port": int(parts[6]) if parts[6].isdigit() else 0,
                "protocol": _ip_proto(parts[7]),
                "packets": int(parts[8]) if parts[8].isdigit() else 0,
                "bytes_total": int(parts[9]) if parts[9].isdigit() else 0,
                "cloud": "aws",
            })
        except Exception:
            continue
    return rows


def parse_generic_csv(text: str) -> List[Dict[str, Any]]:
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        rows.append({
            "source_ip": raw.get("src_ip") or raw.get("source_ip") or raw.get("srcaddr") or "0.0.0.0",
            "destination_ip": raw.get("dst_ip") or raw.get("destination_ip") or raw.get("dstaddr") or "0.0.0.0",
            "source_port": int(raw.get("src_port") or raw.get("source_port") or 0),
            "destination_port": int(raw.get("dst_port") or raw.get("destination_port") or 0),
            "protocol": raw.get("protocol") or "TCP",
            "packets": int(raw.get("packets") or raw.get("packet_count") or 0),
            "bytes_total": int(raw.get("bytes") or raw.get("byte_count") or 0),
            "cloud": raw.get("cloud") or "generic",
        })
    return rows


def parse_payload(filename: str, text: str) -> List[Dict[str, Any]]:
    name = (filename or "").lower()
    if name.endswith(".json"):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("records") or data.get("flows") or [data]
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            out.append({
                "source_ip": str(item.get("src_ip") or item.get("source_ip") or "0.0.0.0"),
                "destination_ip": str(item.get("dst_ip") or item.get("destination_ip") or "0.0.0.0"),
                "source_port": int(item.get("src_port") or item.get("source_port") or 0),
                "destination_port": int(item.get("dst_port") or item.get("destination_port") or 0),
                "protocol": str(item.get("protocol") or "TCP"),
                "packets": int(item.get("packets") or 0),
                "bytes_total": int(item.get("bytes") or item.get("bytes_total") or 0),
                "cloud": str(item.get("cloud") or "json"),
            })
        return out
    if "vpcflow" in name or "aws" in name:
        return parse_aws_vpc_flow(text)
    return parse_generic_csv(text)


def ingest_rows(rows: List[Dict[str, Any]]) -> int:
    from database.database import SessionLocal
    from database.queries import insert_flow
    from assets.inventory import upsert_from_flow
    db = SessionLocal()
    n = 0
    try:
        for r in rows:
            insert_flow(
                db,
                source_ip=r.get("source_ip"),
                destination_ip=r.get("destination_ip"),
                source_port=int(r.get("source_port") or 0),
                destination_port=int(r.get("destination_port") or 0),
                protocol=str(r.get("protocol") or "TCP"),
                packets=int(r.get("packets") or 0),
                bytes_total=int(r.get("bytes_total") or 0),
            )
            upsert_from_flow(str(r.get("source_ip") or ""), str(r.get("destination_ip") or ""), int(r.get("destination_port") or 0))
            n += 1
        return n
    finally:
        db.close()


def _ip_proto(code: str) -> str:
    return {"6": "TCP", "17": "UDP", "1": "ICMP"}.get(str(code), str(code))
