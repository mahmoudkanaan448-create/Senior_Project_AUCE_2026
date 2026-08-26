"""Generate a small synthetic CIC-style dataset for local demo / training."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ATTACK_LABELS, DATASETS_DIR, FEATURE_COLUMNS

rng = np.random.default_rng(42)
n_per_class = 80
rows = []

for label in ATTACK_LABELS[:6]:  # Normal + 5 attack types
    for _ in range(n_per_class):
        row = {col: float(rng.random()) for col in FEATURE_COLUMNS}
        # Make Normal traffic look different from attacks
        if label == "Normal":
            row["packet_rate"] = float(rng.uniform(1, 20))
            row["syn_count"] = float(rng.integers(0, 3))
            row["serror_rate"] = float(rng.uniform(0, 0.1))
        else:
            row["packet_rate"] = float(rng.uniform(50, 500))
            row["syn_count"] = float(rng.integers(10, 80))
            row["serror_rate"] = float(rng.uniform(0.4, 1.0))
        row["label"] = label
        rows.append(row)

df = pd.DataFrame(rows)
DATASETS_DIR.mkdir(parents=True, exist_ok=True)
out = DATASETS_DIR / "dataset.csv"
df.to_csv(out, index=False)
print(f"Wrote {len(df)} rows to {out}")
