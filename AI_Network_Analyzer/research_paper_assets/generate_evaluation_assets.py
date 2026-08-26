"""Evaluate trained models on datasets/dataset.csv and produce paper figures."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import label_binarize

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
DATA = ROOT / "datasets" / "dataset.csv"
MODELS = ROOT / "models"
OUT = ROOT / "research_paper_assets" / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)

from config import FEATURE_COLUMNS


def font(size=16):
    for n in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            pass
    return ImageFont.load_default()


def save_bar_chart(metrics: dict, path: Path):
    names = list(metrics.keys())
    acc = [metrics[n]["accuracy"] * 100 for n in names]
    f1 = [metrics[n]["f1"] * 100 for n in names]
    w, h = 1100, 620
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 20), "Experimental Model Performance (Holdout Test Split)", fill=(15, 23, 42), font=font(22))
    ox, oy, maxh = 80, 540, 400
    d.line((ox, oy, w - 40, oy), fill=(71, 85, 105), width=2)
    d.line((ox, oy, ox, oy - maxh), fill=(71, 85, 105), width=2)
    bw = 70
    gap = 40
    for i, name in enumerate(names):
        x = ox + 40 + i * (bw * 2 + gap)
        ha = int(acc[i] / 100 * maxh)
        hf = int(f1[i] / 100 * maxh)
        d.rectangle((x, oy - ha, x + bw - 4, oy), fill=(29, 78, 216))
        d.rectangle((x + bw, oy - hf, x + 2 * bw - 4, oy), fill=(180, 140, 30))
        d.text((x, oy + 10), name[:12], fill=(15, 23, 42), font=font(12))
        d.text((x, oy - ha - 22), f"{acc[i]:.1f}%", fill=(29, 78, 216), font=font(12))
        d.text((x + bw, oy - hf - 22), f"{f1[i]:.1f}%", fill=(180, 140, 30), font=font(12))
    d.text((ox + 40, 70), "Blue = Accuracy   Gold = Weighted F1", fill=(71, 85, 105), font=font(14))
    img.save(path)


def save_confusion(cm, labels, path: Path):
    n = len(labels)
    cell = 70
    pad = 120
    w = pad + n * cell + 40
    h = pad + n * cell + 80
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 20), "Confusion Matrix — Random Forest (Holdout Test Set)", fill=(15, 23, 42), font=font(18))
    mx = cm.max() if cm.max() else 1
    for i, lab in enumerate(labels):
        d.text((20, pad + i * cell + 25), str(lab)[:10], fill=(15, 23, 42), font=font(11))
        d.text((pad + i * cell + 8, pad - 25), str(lab)[:10], fill=(15, 23, 42), font=font(11))
    for i in range(n):
        for j in range(n):
            v = int(cm[i, j])
            intensity = int(220 - 120 * (v / mx))
            color = (intensity, intensity + 20, 255)
            x1 = pad + j * cell
            y1 = pad + i * cell
            d.rectangle((x1, y1, x1 + cell - 4, y1 + cell - 4), fill=color, outline=(30, 41, 59))
            d.text((x1 + 22, y1 + 22), str(v), fill=(15, 23, 42), font=font(14))
    img.save(path)


def save_dataset_stats(df: pd.DataFrame, path: Path):
    counts = df["label"].value_counts()
    w, h = 1000, 560
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 20), "Dataset Class Distribution (Evaluation Set)", fill=(15, 23, 42), font=font(20))
    d.text((40, 55), f"Total samples: {len(df)} | Features: {len(FEATURE_COLUMNS)} | Classes: {df['label'].nunique()}",
           fill=(71, 85, 105), font=font(14))
    labels = list(counts.index)
    vals = list(counts.values)
    mx = max(vals)
    ox, oy, maxh, bw = 80, 480, 350, 90
    for i, (lab, v) in enumerate(zip(labels, vals)):
        x = ox + i * (bw + 30)
        hh = int(v / mx * maxh)
        d.rectangle((x, oy - hh, x + bw, oy), fill=(34, 120, 80), outline=(30, 41, 59))
        d.text((x + 10, oy + 10), str(lab), fill=(15, 23, 42), font=font(12))
        d.text((x + 25, oy - hh - 24), str(v), fill=(20, 83, 45), font=font(14))
    img.save(path)


def save_ui_mock(path: Path, title: str, lines: list[str]):
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), (7, 17, 31))
    d = ImageDraw.Draw(img)
    # sidebar
    d.rectangle((0, 0, 280, h), fill=(5, 13, 24))
    d.text((30, 30), "AI Network Analyzer", fill=(212, 175, 55), font=font(18))
    d.text((30, 60), "NDR Platform v1.0.0", fill=(203, 213, 225), font=font(12))
    nav = ["Home", "Live Monitoring", "AI Detection", "Threat Simulation", "Alerts", "SOC Ops", "Settings"]
    for i, n in enumerate(nav):
        y = 120 + i * 40
        if n == title.split("–")[0].strip() or title.startswith(n):
            d.rectangle((10, y - 6, 270, y + 26), fill=(18, 35, 61), outline=(212, 175, 55))
        d.text((30, y), n, fill=(241, 245, 249), font=font(14))
    d.text((320, 30), title, fill=(255, 255, 255), font=font(24))
    y = 100
    for line in lines:
        d.text((320, y), line, fill=(226, 232, 240), font=font(16))
        y += 36
    # metric cards
    cards = [("Flows", "480"), ("Attacks", "400"), ("Alerts", "Active"), ("Models", "5 Ready")]
    for i, (k, v) in enumerate(cards):
        x = 320 + i * 220
        d.rounded_rectangle((x, 520, x + 200, 620), radius=12, fill=(18, 35, 61), outline=(30, 58, 95))
        d.text((x + 20, 540), k, fill=(203, 213, 225), font=font(14))
        d.text((x + 20, 570), v, fill=(212, 175, 55), font=font(22))
    img.save(path)


def main():
    df = pd.read_csv(DATA)
    save_dataset_stats(df, OUT / "fig_dataset_distribution.png")

    # features
    cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    X = df[cols].astype(float).values
    y_raw = df["label"].astype(str).values

    scaler = joblib.load(MODELS / "scaler.pkl")
    le = joblib.load(MODELS / "label_encoder.pkl")
    # align labels with encoder classes
    # If encoder was trained on broader set, transform carefully
    classes = list(getattr(le, "classes_", []))
    mask = np.isin(y_raw, classes) if classes else np.ones(len(y_raw), dtype=bool)
    X, y_raw = X[mask], y_raw[mask]
    y = le.transform(y_raw)
    Xs = scaler.transform(X)

    Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.25, random_state=42, stratify=y)

    metrics = {}
    rf = joblib.load(MODELS / "random_forest.pkl")
    xgb = joblib.load(MODELS / "xgboost_model.pkl")

    for name, model in [("RandomForest", rf), ("XGBoost", xgb)]:
        pred = model.predict(Xte)
        # handle string vs int preds
        if getattr(pred, "dtype", None) is not None and pred.dtype.kind in ("U", "O", "S"):
            pred = le.transform(pred)
        metrics[name] = {
            "accuracy": float(accuracy_score(yte, pred)),
            "precision": float(precision_score(yte, pred, average="weighted", zero_division=0)),
            "recall": float(recall_score(yte, pred, average="weighted", zero_division=0)),
            "f1": float(f1_score(yte, pred, average="weighted", zero_division=0)),
        }
        if name == "RandomForest":
            cm = confusion_matrix(yte, pred)
            labels = [str(le.inverse_transform([i])[0]) for i in sorted(set(yte))]
            # confusion_matrix labels order
            present = sorted(set(yte))
            labels = [str(le.inverse_transform([i])[0]) for i in present]
            save_confusion(cm, labels, OUT / "fig_confusion_rf.png")

    # Isolation Forest – anomaly vs normal (binary-ish evaluation)
    try:
        iso = joblib.load(MODELS / "isolation_forest.pkl")
        # IF returns -1 anomaly, 1 normal
        raw = iso.predict(Xte)
        # map: treat non-Normal as anomaly for rough check
        y_bin = np.array([0 if le.inverse_transform([i])[0] == "Normal" else 1 for i in yte])
        pred_bin = np.array([1 if v == -1 else 0 for v in raw])
        metrics["IsolationForest"] = {
            "accuracy": float(accuracy_score(y_bin, pred_bin)),
            "precision": float(precision_score(y_bin, pred_bin, zero_division=0)),
            "recall": float(recall_score(y_bin, pred_bin, zero_division=0)),
            "f1": float(f1_score(y_bin, pred_bin, zero_division=0)),
            "note": "Binary Normal vs Attack proxy evaluation",
        }
    except Exception as e:
        metrics["IsolationForest"] = {"error": str(e)}

    save_bar_chart({k: v for k, v in metrics.items() if "accuracy" in v}, OUT / "fig_model_performance.png")

    # UI screenshots (faithful mocks of implemented pages)
    save_ui_mock(OUT / "shot_home.png", "Home – SOC Dashboard", [
        "Overview metrics from live SQLite database",
        "Quick Actions: Threat Simulation | Live Monitoring | AI Detection | SOC Ops",
        "Recent alerts include MITRE technique IDs and severity",
        "Hybrid AI status: Random Forest, XGBoost, Isolation Forest, Autoencoder, LSTM",
    ])
    save_ui_mock(OUT / "shot_threat_sim.png", "Threat Simulation", [
        "Campaign: Mixed | Incidents: 5 | Telegram notify: ON",
        "Pipeline: Generate flows -> Hybrid AI -> Alerts -> Telegram + Local sound",
        "Results: attacks detected, alerts created, telegram_sent, blocked IPs",
        "Lab IPs only (203.0.113.x) for safe academic simulation",
    ])
    save_ui_mock(OUT / "shot_soc_ops.png", "SOC Ops", [
        "Tabs: MITRE ATT&CK | SOAR Playbooks | Online Learning | Server Health",
        "MITRE mapping example: Ransomware -> Impact / T1486",
        "Online buffer samples and SGD incremental model status",
        "Server readiness: database OK, models OK, auto-heal available",
    ])
    save_ui_mock(OUT / "shot_ai_models.png", "AI Models", [
        "Registered model metrics and comparison charts",
        "Train-all from CSV upload (batch offline training)",
        "Online / incremental learning panel (does not overwrite core models)",
        f"Latest experimental RF accuracy: {metrics.get('RandomForest',{}).get('accuracy',0)*100:.1f}%",
    ])

    (OUT / "metrics.json").write_text(json.dumps({
        "dataset": {
            "path": str(DATA),
            "rows": int(len(df)),
            "features": len(cols),
            "classes": df["label"].value_counts().to_dict(),
            "test_size": 0.25,
            "random_state": 42,
        },
        "metrics": metrics,
    }, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
