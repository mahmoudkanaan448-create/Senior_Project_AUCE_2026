"""
Data preprocessing utilities for the AI Network Traffic Analyzer.

Handles loading, cleaning, label encoding, feature scaling, LSTM
sequence windows, and persistence of fitted scalers/encoders.
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import FEATURE_COLUMNS, MODELS_DIR


def load_dataset(filepath: str) -> pd.DataFrame:
    """Load a CSV dataset into a DataFrame."""
    df = pd.read_csv(filepath)
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates, replace infinities, and fill missing values."""
    df = df.drop_duplicates()
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.fillna(0, inplace=True)
    return df


def encode_labels(
    df: pd.DataFrame, label_col: str = "label"
) -> tuple[pd.DataFrame, LabelEncoder]:
    """Encode the label column as integers and return the fitted encoder."""
    le = LabelEncoder()
    df[label_col] = le.fit_transform(df[label_col].astype(str))
    return df, le


def scale_features(
    X_train: np.ndarray, X_test: np.ndarray
) -> tuple[np.ndarray, np.ndarray, StandardScaler]:
    """Fit a StandardScaler on the training set and transform both splits."""
    # Fit on train only to avoid leaking test-set statistics
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    return X_train_scaled, X_test_scaled, scaler


def prepare_sequences(
    X: np.ndarray, y: np.ndarray, window_size: int = 10
) -> tuple[np.ndarray, np.ndarray]:
    """Slide a window over rows to create (seq, label) pairs for LSTM input."""
    sequences, labels = [], []
    for i in range(len(X) - window_size):
        sequences.append(X[i : i + window_size])
        labels.append(y[i + window_size])
    return np.array(sequences), np.array(labels)


def save_scaler(scaler: StandardScaler, path: str | Path | None = None) -> Path:
    """Persist a fitted StandardScaler with joblib."""
    path = Path(path) if path else MODELS_DIR / "scaler.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, path)
    return path


def load_scaler(path: str | Path | None = None) -> StandardScaler:
    """Load a previously saved StandardScaler."""
    path = Path(path) if path else MODELS_DIR / "scaler.pkl"
    return joblib.load(path)


def save_encoder(encoder: LabelEncoder, path: str | Path | None = None) -> Path:
    """Persist a fitted LabelEncoder with joblib."""
    path = Path(path) if path else MODELS_DIR / "label_encoder.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(encoder, path)
    return path


def load_encoder(path: str | Path | None = None) -> LabelEncoder:
    """Load a previously saved LabelEncoder."""
    path = Path(path) if path else MODELS_DIR / "label_encoder.pkl"
    return joblib.load(path)
