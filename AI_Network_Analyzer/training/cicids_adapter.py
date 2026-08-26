"""
Map public IDS CSVs (CICIDS2017 / UNSW-NB15 style) onto FEATURE_COLUMNS.

If a real CICIDS MachineLearningCSV file is dropped into datasets/,
call import_public_csv() to produce a trainer-ready CSV. Column names
are matched after stripping spaces and lowercasing.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from config import DATASETS_DIR, FEATURE_COLUMNS

# CICIDS2017 MachineLearningCSV → internal feature names
_CICIDS_MAP: Dict[str, str] = {
    "flow duration": "duration",
    "protocol": "protocol_type",
    "total length of fwd packets": "src_bytes",
    "total length of bwd packets": "dst_bytes",
    "total fwd packets": "fwd_packets",
    "total backward packets": "bwd_packets",
    "fwd packet length min": "min_packet_length",
    "fwd packet length max": "max_packet_length",
    "fwd packet length mean": "mean_packet_length",
    "fwd packet length std": "std_packet_length",
    "flow bytes/s": "flow_rate",
    "flow packets/s": "packet_rate",
    "flow iat mean": "inter_arrival_time",
    "syn flag count": "syn_count",
    "ack flag count": "ack_count",
    "fin flag count": "fin_count",
    "rst flag count": "rst_count",
    "psh flag count": "psh_count",
    "urg flag count": "urg_count",
    "active mean": "active_time",
    "idle mean": "idle_time",
    "subflow fwd bytes": "fwd_bytes",
    "subflow bwd bytes": "bwd_bytes",
    "average packet size": "avg_packet_size",
    "total length of fwd packets": "byte_count",
}

# UNSW-NB15 (common Kaggle / ARGUS export names)
_UNSW_MAP: Dict[str, str] = {
    "dur": "duration",
    "proto": "protocol_type",
    "spkts": "fwd_packets",
    "dpkts": "bwd_packets",
    "sbytes": "src_bytes",
    "dbytes": "dst_bytes",
    "rate": "packet_rate",
    "sload": "flow_rate",
    "sinpkt": "inter_arrival_time",
    "smean": "mean_packet_length",
    "dmean": "avg_packet_size",
    "synack": "syn_count",
    "ackdat": "ack_count",
    "ct_srv_src": "srv_count",
    "ct_dst_src_ltm": "count",
    "ct_dst_ltm": "dst_host_count",
    "ct_src_ltm": "dst_host_srv_count",
    "sjit": "active_time",
    "djit": "idle_time",
}

_LABEL_MAP: Dict[str, str] = {
    "benign": "Normal",
    "normal": "Normal",
    "dos": "DoS",
    "ddos": "DDoS",
    "dos hulk": "DoS",
    "dos goldeneye": "DoS",
    "dos slowloris": "DoS",
    "dos slowhttptest": "DoS",
    "heartbleed": "DoS",
    "portscan": "PortScan",
    "ftp-patator": "BruteForce",
    "ssh-patator": "BruteForce",
    "brute force": "BruteForce",
    "web attack – brute force": "BruteForce",
    "web attack – xss": "WebAttack",
    "web attack – sql injection": "SQLInjection",
    "web attack xss": "WebAttack",
    "web attack sql injection": "SQLInjection",
    "sqlinjection": "SQLInjection",
    "infiltration": "Infiltration",
    "bot": "Botnet",
    "botnet": "Botnet",
    "generic": "Malware",
    "exploits": "Malware",
    "fuzzers": "WebAttack",
    "reconnaissance": "PortScan",
    "shellcode": "Malware",
    "worms": "Malware",
    "analysis": "Infiltration",
    "backdoor": "Malware",
}


def _norm(name: str) -> str:
    s = str(name or "").strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_label(raw: str) -> str:
    key = _norm(raw)
    if key in _LABEL_MAP:
        return _LABEL_MAP[key]
    if "sql" in key:
        return "SQLInjection"
    if "xss" in key or "web" in key:
        return "WebAttack"
    if "ddos" in key:
        return "DDoS"
    if "dos" in key:
        return "DoS"
    if "scan" in key:
        return "PortScan"
    if "brute" in key or "patator" in key:
        return "BruteForce"
    if key in ("benign", "normal"):
        return "Normal"
    return str(raw).strip() or "Unknown"


def import_public_csv(
    src: str | Path,
    dest: Optional[str | Path] = None,
    *,
    max_rows: Optional[int] = 80000,
) -> Path:
    """Convert a CICIDS/UNSW CSV into FEATURE_COLUMNS + label."""
    src_path = Path(src)
    if not src_path.exists():
        raise FileNotFoundError(src_path)
    dest_path = Path(dest) if dest else DATASETS_DIR / "public_mapped_dataset.csv"

    df = pd.read_csv(src_path, low_memory=False)
    if max_rows and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=42)

    rename: Dict[str, str] = {}
    combined = {**_UNSW_MAP, **_CICIDS_MAP}
    for col in df.columns:
        n = _norm(col)
        if n in ("label", "attack_cat", "class"):
            rename[col] = "label"
        elif n in combined:
            rename[col] = combined[n]
        elif n.replace(" ", "_") in FEATURE_COLUMNS:
            rename[col] = n.replace(" ", "_")
    mapped = df.rename(columns=rename)

    if "label" not in mapped.columns:
        raise ValueError("No label/attack_cat column found in public CSV")

    out = pd.DataFrame()
    for col in FEATURE_COLUMNS:
        if col in mapped.columns:
            out[col] = pd.to_numeric(mapped[col], errors="coerce").fillna(0.0)
        else:
            out[col] = 0.0

    # Derived fills when CICIDS provided packet/byte totals
    if "packet_count" not in mapped.columns:
        out["packet_count"] = out["fwd_packets"] + out["bwd_packets"]
    else:
        out["packet_count"] = pd.to_numeric(mapped["packet_count"], errors="coerce").fillna(0.0)
    if out["byte_count"].sum() == 0:
        out["byte_count"] = out["src_bytes"] + out["dst_bytes"]
    if out["flow_duration"].sum() == 0:
        out["flow_duration"] = out["duration"]
    if out["avg_packet_size"].sum() == 0:
        pk = out["packet_count"].clip(lower=1)
        out["avg_packet_size"] = out["byte_count"] / pk

    out["label"] = mapped["label"].astype(str).map(normalize_label)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest_path, index=False)
    return dest_path


def find_public_csv(folder: Optional[Path] = None) -> Optional[Path]:
    """Return the first CSV that looks like CICIDS/UNSW (has Label or attack_cat)."""
    root = Path(folder) if folder else DATASETS_DIR
    if not root.exists():
        return None
    skip = {
        "dataset.csv",
        "implementation_eval_dataset.csv",
        "cicids_style_dataset.csv",
        "public_mapped_dataset.csv",
    }
    for path in sorted(root.glob("*.csv")):
        if path.name.lower() in skip:
            continue
        try:
            head = pd.read_csv(path, nrows=2)
        except Exception:
            continue
        names = {_norm(c) for c in head.columns}
        if names & {"label", "attack cat", "attack_cat", "class"}:
            return path
    return None
