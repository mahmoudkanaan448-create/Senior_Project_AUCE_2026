"""
Build a larger CICIDS-style training/eval set with class imbalance and noise.

This is NOT the official CICIDS2017 dump. It uses the same 39 flow features
and attack signatures as the live detector, with CICIDS-like class mix.
If a real CICIDS/UNSW CSV is present in datasets/, prefer importing it.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config import DATASETS_DIR, FEATURE_COLUMNS
from detection.attack_simulator import _apply_attack_profile, _base_features
from training.cicids_adapter import find_public_csv, import_public_csv

# CICIDS2017-like mix (benign majority, flood classes next, rare web/bot)
CLASS_COUNTS = {
    "Normal": 6000,
    "DoS": 1800,
    "DDoS": 1800,
    "PortScan": 1100,
    "BruteForce": 800,
    "SQLInjection": 500,
}


def _apply_normal_profile(features: dict, rng: np.random.Generator) -> dict:
    f = dict(features)
    f.update({
        "protocol_type": float(rng.choice([0.0, 1.0, 2.0], p=[0.08, 0.82, 0.10])),
        "packet_rate": float(rng.uniform(0.4, 28.0)),
        "flow_rate": float(rng.uniform(80.0, 1.2e4)),
        "syn_count": float(rng.integers(0, 5)),
        "ack_count": float(rng.integers(1, 40)),
        "fin_count": float(rng.integers(0, 4)),
        "rst_count": float(rng.integers(0, 3)),
        "psh_count": float(rng.integers(0, 12)),
        "serror_rate": float(rng.uniform(0.0, 0.08)),
        "rerror_rate": float(rng.uniform(0.0, 0.06)),
        "dst_host_serror_rate": float(rng.uniform(0.0, 0.08)),
        "same_srv_rate": float(rng.uniform(0.55, 1.0)),
        "diff_srv_rate": float(rng.uniform(0.0, 0.25)),
        "packet_count": float(rng.integers(4, 180)),
        "byte_count": float(rng.integers(200, 4.0e4)),
        "duration": float(rng.uniform(0.05, 12.0)),
        "count": float(rng.integers(1, 25)),
        "srv_count": float(rng.integers(1, 20)),
        "dst_host_count": float(rng.integers(1, 40)),
        "idle_time": float(rng.uniform(0.0, 4.0)),
        "inter_arrival_time": float(rng.uniform(0.01, 1.5)),
    })
    dur = max(float(f["duration"]), 0.001)
    pkts = float(f["packet_count"])
    byts = float(f["byte_count"])
    f["flow_duration"] = dur
    f["avg_packet_size"] = byts / max(pkts, 1.0)
    f["src_bytes"] = byts * 0.55
    f["dst_bytes"] = byts * 0.45
    f["fwd_packets"] = max(1.0, pkts * 0.58)
    f["bwd_packets"] = max(0.0, pkts * 0.42)
    f["fwd_bytes"] = f["src_bytes"]
    f["bwd_bytes"] = f["dst_bytes"]
    return f


def _jitter(features: dict, rng: np.random.Generator, scale: float = 0.12) -> dict:
    out = dict(features)
    for key, val in list(out.items()):
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        noise = float(rng.normal(0.0, abs(num) * scale + 1e-6))
        out[key] = max(0.0, num + noise)
    return out


def generate_synthetic(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for class_name, n in CLASS_COUNTS.items():
        for _ in range(n):
            feat = _base_features(rng)
            if class_name == "Normal":
                feat = _apply_normal_profile(feat, rng)
                # Flash-crowd / busy benign traffic
                if rng.random() < 0.10:
                    feat["packet_rate"] = float(rng.uniform(40, 160))
                    feat["packet_count"] = float(rng.integers(80, 600))
                    feat["syn_count"] = float(rng.integers(2, 18))
            else:
                feat = _apply_attack_profile(class_name, feat, rng)
                roll = rng.random()
                if roll < 0.22:
                    # Mild / early-stage attack closer to benign
                    feat = _jitter(feat, rng, scale=0.40)
                    for k in ("packet_rate", "serror_rate", "syn_count", "flow_rate"):
                        feat[k] = float(feat.get(k, 0)) * float(rng.uniform(0.18, 0.55))
                elif class_name in ("DoS", "DDoS") and roll < 0.38:
                    # DoS/DDoS overlap
                    other = "DDoS" if class_name == "DoS" else "DoS"
                    mix = _apply_attack_profile(other, _base_features(rng), rng)
                    for k in FEATURE_COLUMNS:
                        feat[k] = 0.55 * float(feat.get(k, 0)) + 0.45 * float(mix.get(k, 0))
            feat = _jitter(feat, rng, scale=0.14)
            out_label = class_name
            if rng.random() < 0.02:
                out_label = str(rng.choice(list(CLASS_COUNTS)))
            row = {col: float(feat.get(col, 0.0) or 0.0) for col in FEATURE_COLUMNS}
            row["label"] = out_label
            rows.append(row)
    df = pd.DataFrame(rows)
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def build_dataset(
    *,
    dest: Path | None = None,
    also_copy_default: bool = True,
    seed: int = 42,
) -> Path:
    dest = dest or (DATASETS_DIR / "cicids_style_dataset.csv")
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    public = find_public_csv()
    if public is not None:
        mapped = import_public_csv(public, dest)
        source = f"public:{public.name}"
        df = pd.read_csv(mapped)
    else:
        df = generate_synthetic(seed=seed)
        df.to_csv(dest, index=False)
        source = "synthetic_cicids_style"

    if also_copy_default:
        df.to_csv(DATASETS_DIR / "dataset.csv", index=False)

    meta = DATASETS_DIR / "dataset_build_note.txt"
    meta.write_text(
        f"source={source}\nrows={len(df)}\nfeatures={len(FEATURE_COLUMNS)}\n"
        f"classes={df['label'].value_counts().to_dict()}\n"
        "disclaimer=Not a CICIDS2017 leaderboard dump unless a public CSV was imported.\n",
        encoding="utf-8",
    )
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate / import CICIDS-style dataset")
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()
    path = build_dataset(dest=Path(args.out) if args.out else None)
    print(f"Wrote {path}")
