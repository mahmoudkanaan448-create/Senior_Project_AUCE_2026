"""
Group captured packets into unidirectional network flows by 5-tuple.

A flow is a sequence of packets sharing the same
(src_ip, dst_ip, src_port, dst_port, protocol). Forward/backward
split is handled later in feature_extraction.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

FlowKey = tuple[str, str, int, int, int]


def _make_key(packet: dict[str, Any]) -> FlowKey:
    """Build the unidirectional 5-tuple key for a packet."""
    return (
        packet["src_ip"],
        packet["dst_ip"],
        packet["src_port"],
        packet["dst_port"],
        packet["protocol"],
    )


def _summarise_flow(key: FlowKey, packets: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate statistics for a single flow."""
    timestamps = sorted(p["timestamp"] for p in packets)
    total_bytes = sum(p["length"] for p in packets)
    duration = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0.0
    packet_count = len(packets)

    packet_rate = packet_count / duration if duration > 0 else 0.0
    flow_rate = total_bytes / duration if duration > 0 else 0.0

    flow = {
        "source_ip": key[0],
        "destination_ip": key[1],
        "source_port": key[2],
        "destination_port": key[3],
        "protocol": key[4],
        "duration": round(duration, 6),
        "packet_count": packet_count,
        "byte_count": total_bytes,
        "packet_rate": round(packet_rate, 4),
        "flow_rate": round(flow_rate, 4),
        "timestamps": timestamps,
        "packets": packets,
    }
    try:
        from monitoring.dpi import summarize_flow_dpi, protocol_from_ports
        flow.update(summarize_flow_dpi(packets))
        flow["app_protocol"] = flow.get("app_protocol") or protocol_from_ports(key[2], key[3], key[4])
    except Exception:
        pass
    return flow


def build_flows(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group *packets* into flows keyed by 5-tuple."""
    buckets: dict[FlowKey, list[dict[str, Any]]] = defaultdict(list)
    for pkt in packets:
        buckets[_make_key(pkt)].append(pkt)

    return [_summarise_flow(key, pkts) for key, pkts in buckets.items()]
