"""
Compute aggregate traffic statistics from a collection of flows.

Produces dashboard-level summaries (totals, protocol mix, top talkers,
average duration) for the Streamlit UI — separate from per-flow ML features.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

_PROTOCOL_NAMES: dict[int, str] = {
    1: "ICMP",
    6: "TCP",
    17: "UDP",
}


def compute_stats(flows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return high-level traffic statistics derived from *flows*."""
    if not flows:
        return {
            "total_packets": 0,
            "total_bytes": 0,
            "total_flows": 0,
            "protocols": {},
            "top_sources": [],
            "top_destinations": [],
            "avg_duration": 0.0,
        }

    total_packets = sum(f.get("packet_count", 0) for f in flows)
    total_bytes = sum(f.get("byte_count", 0) for f in flows)
    total_flows = len(flows)

    proto_counter: Counter[str] = Counter()
    for f in flows:
        proto_num = f.get("protocol", 0)
        proto_name = _PROTOCOL_NAMES.get(proto_num, f"OTHER({proto_num})")
        proto_counter[proto_name] += f.get("packet_count", 0)
    protocols = dict(proto_counter.most_common())

    src_counter: Counter[str] = Counter()
    dst_counter: Counter[str] = Counter()
    for f in flows:
        src_counter[f.get("source_ip", "unknown")] += f.get("byte_count", 0)
        dst_counter[f.get("destination_ip", "unknown")] += f.get("byte_count", 0)

    top_sources = [
        {"ip": ip, "bytes": count} for ip, count in src_counter.most_common(10)
    ]
    top_destinations = [
        {"ip": ip, "bytes": count} for ip, count in dst_counter.most_common(10)
    ]

    durations = [f.get("duration", 0.0) for f in flows]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    return {
        "total_packets": total_packets,
        "total_bytes": total_bytes,
        "total_flows": total_flows,
        "protocols": protocols,
        "top_sources": top_sources,
        "top_destinations": top_destinations,
        "avg_duration": round(avg_duration, 6),
    }
