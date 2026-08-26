"""
Extract AI-ready features from network flows.

Produces a 39-feature vector matching ``config.FEATURE_COLUMNS``
for direct use by the trained models.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_PROTOCOL_MAP: dict[int, int] = {
    6: 0,    # TCP
    17: 1,   # UDP
    1: 2,    # ICMP
}


def _safe_div(numerator: float, denominator: float) -> float:
    """Divide, returning 0.0 when the denominator is zero."""
    return numerator / denominator if denominator else 0.0


def _count_flag(packets: list[dict[str, Any]], flag_char: str) -> int:
    """Count packets whose ``tcp_flags`` string contains *flag_char*."""
    return sum(1 for p in packets if flag_char in p.get("tcp_flags", ""))


def extract_features(flow: dict[str, Any]) -> dict[str, float]:
    """Derive the full 39-feature vector from a single flow dict."""
    packets: list[dict[str, Any]] = flow.get("packets", [])
    timestamps: list[float] = sorted(flow.get("timestamps", []))
    pkt_count = len(packets)
    total_bytes = flow.get("byte_count", 0)
    duration = flow.get("duration", 0.0)
    src_ip = flow.get("source_ip", "")
    dst_ip = flow.get("destination_ip", "")

    lengths = np.array([p["length"] for p in packets], dtype=np.float64) if packets else np.zeros(1)
    min_len = float(np.min(lengths))
    max_len = float(np.max(lengths))
    mean_len = float(np.mean(lengths))
    std_len = float(np.std(lengths))

    if len(timestamps) > 1:
        iats = np.diff(timestamps)
        inter_arrival = float(np.mean(iats))
    else:
        iats = np.zeros(1)
        inter_arrival = 0.0

    # Gaps < 1s count as active; ≥ 1s as idle (CICFlowMeter-style heuristic)
    idle_threshold = 1.0
    active_intervals: list[float] = []
    idle_intervals: list[float] = []
    if len(timestamps) > 1:
        for gap in np.diff(timestamps):
            (idle_intervals if gap > idle_threshold else active_intervals).append(float(gap))
    active_time = float(np.sum(active_intervals)) if active_intervals else 0.0
    idle_time = float(np.sum(idle_intervals)) if idle_intervals else 0.0

    # Forward = direction of first packet; backward = reverse
    if packets:
        fwd_ip = packets[0].get("src_ip", "")
        fwd_pkts = [p for p in packets if p.get("src_ip") == fwd_ip]
        bwd_pkts = [p for p in packets if p.get("src_ip") != fwd_ip]
    else:
        fwd_pkts, bwd_pkts = [], []

    fwd_packets = len(fwd_pkts)
    bwd_packets = len(bwd_pkts)
    fwd_bytes = sum(p["length"] for p in fwd_pkts)
    bwd_bytes = sum(p["length"] for p in bwd_pkts)

    syn_count = _count_flag(packets, "S")
    ack_count = _count_flag(packets, "A")
    fin_count = _count_flag(packets, "F")
    rst_count = _count_flag(packets, "R")
    psh_count = _count_flag(packets, "P")
    urg_count = _count_flag(packets, "U")

    serror_rate = _safe_div(syn_count, pkt_count)
    rerror_rate = _safe_div(rst_count, pkt_count)

    # KDD-style host/service rates: single-flow defaults (shape must stay 39)
    same_srv_rate = 1.0
    diff_srv_rate = 0.0
    dst_host_count = 1
    dst_host_srv_count = 1
    dst_host_same_srv_rate = 1.0
    dst_host_diff_srv_rate = 0.0
    dst_host_serror_rate = serror_rate
    dst_host_rerror_rate = rerror_rate

    return {
        "duration": round(duration, 6),
        "protocol_type": _PROTOCOL_MAP.get(flow.get("protocol", 0), 3),
        "src_bytes": fwd_bytes,
        "dst_bytes": bwd_bytes,
        "count": pkt_count,
        "srv_count": pkt_count,
        "serror_rate": round(serror_rate, 6),
        "rerror_rate": round(rerror_rate, 6),
        "same_srv_rate": same_srv_rate,
        "diff_srv_rate": diff_srv_rate,
        "dst_host_count": dst_host_count,
        "dst_host_srv_count": dst_host_srv_count,
        "dst_host_same_srv_rate": dst_host_same_srv_rate,
        "dst_host_diff_srv_rate": dst_host_diff_srv_rate,
        "dst_host_serror_rate": round(dst_host_serror_rate, 6),
        "dst_host_rerror_rate": round(dst_host_rerror_rate, 6),
        "packet_count": pkt_count,
        "byte_count": total_bytes,
        "packet_rate": round(_safe_div(pkt_count, duration), 4),
        "flow_rate": round(_safe_div(total_bytes, duration), 4),
        "avg_packet_size": round(_safe_div(total_bytes, pkt_count), 4),
        "syn_count": syn_count,
        "ack_count": ack_count,
        "fin_count": fin_count,
        "rst_count": rst_count,
        "psh_count": psh_count,
        "urg_count": urg_count,
        "flow_duration": round(duration, 6),
        "fwd_packets": fwd_packets,
        "bwd_packets": bwd_packets,
        "fwd_bytes": fwd_bytes,
        "bwd_bytes": bwd_bytes,
        "min_packet_length": min_len,
        "max_packet_length": max_len,
        "mean_packet_length": round(mean_len, 4),
        "std_packet_length": round(std_len, 4),
        "inter_arrival_time": round(inter_arrival, 6),
        "active_time": round(active_time, 6),
        "idle_time": round(idle_time, 6),
    }


def extract_features_batch(flows: list[dict[str, Any]]) -> pd.DataFrame:
    """Extract features for every flow and return a DataFrame."""
    rows = [extract_features(f) for f in flows]

    if not rows:
        return pd.DataFrame(columns=list(rows[0].keys()) if rows else [])

    return pd.DataFrame(rows)
