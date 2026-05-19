"""
anomaly.py — Detect anomalies in validated transactions using Isolation Forest.

Responsibilities:
    - Take the validated DataFrame from validation.py
    - Train Isolation Forest on the feature columns (V1-V28 + Amount)
    - Score every row and flag anomalies
    - Return the DataFrame with two new columns: anomaly_score and is_anomaly

The Class column is deliberately EXCLUDED from the features. The model must not
see the ground truth label — that would defeat the purpose of unsupervised
anomaly detection. Class is preserved in the DataFrame for later evaluation.

Used by:
    - main.py (called after validation, before persistence)
"""

import logging

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from cerebro import config

logger = logging.getLogger(__name__)

# Columns used as input features for the model.
# Class is excluded (it's the ground truth, not a feature).
# Time is excluded because it's seconds-since-start, not a meaningful pattern.
FEATURE_COLUMNS = [f"V{i}" for i in range(1, 29)] + ["Amount"]


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run Isolation Forest on the input DataFrame and add anomaly columns.

    Steps:
        1. Extract feature columns (V1-V28 + Amount).
        2. Scale features with StandardScaler (mean=0, std=1).
        3. Train Isolation Forest with the contamination from config.
        4. Predict anomaly flags and compute continuous anomaly scores.
        5. Add 'anomaly_score' (float) and 'is_anomaly' (bool) columns to df.

    Args:
        df: The validated DataFrame from validation.validate().

    Returns:
        The same DataFrame with two new columns appended.
    """
    logger.info(f"Running anomaly detection on {len(df):,} rows")

    # Step 1 — extract just the feature columns into a new DataFrame.
    # Original df is untouched; X is the input matrix for the model.
    X = df[FEATURE_COLUMNS]

    # Step 2 — scale features so no single column dominates by magnitude.
    # fit_transform = learn the mean/std from this data AND apply scaling.
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Step 3 — create and train the model.
    # contamination = expected fraction of anomalies (we set 0.002 in config).
    # random_state = seed for reproducibility (same input -> same output).
    model = IsolationForest(
        contamination=config.ANOMALY_CONTAMINATION,
        random_state=config.RANDOM_SEED,
        n_jobs=-1,  # use all CPU cores for faster training
    )
    model.fit(X_scaled)

    # Step 4 — get predictions and scores.
    # predict() returns 1 (normal) or -1 (anomaly).
    # score_samples() returns continuous scores; lower = more anomalous.
    predictions = model.predict(X_scaled)
    scores = model.score_samples(X_scaled)

    # Step 5 — attach results to a copy of the DataFrame.
    # .copy() avoids modifying the caller's DataFrame in place.
    result = df.copy()
    result['anomaly_score'] = scores
    result['is_anomaly'] = (predictions == -1)

    n_anomalies = result['is_anomaly'].sum()
    logger.info(
        f"Anomaly detection complete — "
        f"flagged {n_anomalies:,} anomalies "
        f"({n_anomalies / len(result) * 100:.3f}% of rows)"
    )
    return result