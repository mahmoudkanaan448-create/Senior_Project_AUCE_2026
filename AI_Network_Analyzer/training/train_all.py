"""
Orchestrator that trains every model in the pipeline and reports a summary.

Runs Random Forest, XGBoost, Isolation Forest, Autoencoder, and LSTM
in sequence, then prints a side-by-side metrics comparison.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATASETS_DIR, MODELS_DIR

from training import (
    train_autoencoder,
    train_isolation_forest,
    train_lstm,
    train_random_forest,
    train_xgboost,
)

TRAINERS = [
    ("RandomForest", train_random_forest),
    ("XGBoost", train_xgboost),
    ("IsolationForest", train_isolation_forest),
    ("Autoencoder", train_autoencoder),
    ("LSTM", train_lstm),
]


def train_all_models(dataset_path: str, models_dir: str | None = None) -> dict:
    """Run every training script and collect metrics keyed by model name."""
    models_dir = str(models_dir) if models_dir else str(MODELS_DIR)
    all_metrics: dict = {}

    for name, module in TRAINERS:
        print(f"\n{'=' * 60}")
        print(f"  Training: {name}")
        print(f"{'=' * 60}")
        try:
            metrics = module.train(dataset_path, models_dir)
            all_metrics[name] = metrics
        except Exception as exc:
            print(f"  [ERROR] {name} training failed: {exc}")
            all_metrics[name] = {"model": name, "error": str(exc)}

    _print_summary(all_metrics)
    return all_metrics


def _print_summary(all_metrics: dict) -> None:
    """Print a formatted comparison table of all models."""
    print(f"\n{'=' * 80}")
    print("  MODEL TRAINING SUMMARY")
    print(f"{'=' * 80}")

    header = f"{'Model':<20} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'ROC-AUC':>10}"
    print(header)
    print("-" * 80)

    for name, m in all_metrics.items():
        if "error" in m:
            print(f"{name:<20} {'FAILED':>10}")
            continue

        acc = f"{m.get('accuracy', 0):.4f}"
        prec = f"{m.get('precision', 0):.4f}"
        rec = f"{m.get('recall', 0):.4f}"
        f1 = f"{m.get('f1', 0):.4f}"
        auc = f"{m.get('roc_auc', 0):.4f}" if m.get("roc_auc") is not None else "N/A"
        print(f"{name:<20} {acc:>10} {prec:>10} {rec:>10} {f1:>10} {auc:>10}")

    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train all AI models")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(DATASETS_DIR / "dataset.csv"),
        help="Path to the training CSV dataset",
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default=str(MODELS_DIR),
        help="Directory to save trained models",
    )
    args = parser.parse_args()
    train_all_models(args.dataset, args.models_dir)
