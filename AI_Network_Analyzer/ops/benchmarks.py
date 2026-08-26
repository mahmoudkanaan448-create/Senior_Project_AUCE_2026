"""Detection latency / load / FP benchmarks (lab-safe)."""

from __future__ import annotations

import time
from typing import Any, Dict, List


def detection_latency(n: int = 25) -> Dict[str, Any]:
    from detection.attack_detector import load_models, predict_single
    from detection.decision_engine import fuse_decisions
    from config import MODELS_DIR, FEATURE_COLUMNS

    models = load_models(str(MODELS_DIR))
    feats = {c: 0.0 for c in FEATURE_COLUMNS}
    feats.update({"packet_rate": 12.0, "byte_count": 800, "packet_count": 10, "syn_count": 2})
    times: List[float] = []
    for _ in range(max(3, n)):
        t0 = time.perf_counter()
        raw = predict_single(feats, models)
        fuse_decisions(raw)
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return {
        "samples": len(times),
        "avg_ms": round(sum(times) / len(times), 2),
        "p95_ms": round(times[int(0.95 * (len(times) - 1))], 2),
        "min_ms": round(times[0], 2),
        "max_ms": round(times[-1], 2),
    }


def load_flows_per_sec(seconds: float = 1.0) -> Dict[str, Any]:
    from monitoring.flow_builder import build_flows
    packets = []
    now = time.time()
    for i in range(400):
        packets.append({
            "src_ip": "10.0.0.8",
            "dst_ip": f"10.0.0.{(i % 40) + 1}",
            "src_port": 40000 + i,
            "dst_port": 80,
            "protocol": 6,
            "length": 64,
            "timestamp": now + (i * 0.001),
        })
    t0 = time.perf_counter()
    flows = build_flows(packets)
    elapsed = max(0.001, time.perf_counter() - t0)
    return {
        "packets": len(packets),
        "flows": len(flows),
        "elapsed_ms": round(elapsed * 1000, 2),
        "packets_per_sec": round(len(packets) / elapsed, 1),
        "flows_per_sec": round(len(flows) / elapsed, 1),
    }


def false_positive_benchmark() -> Dict[str, Any]:
    from soc.feedback import fp_rate
    return fp_rate()
