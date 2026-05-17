"""
ingestion.py — Read raw inputs from disk into memory.

Responsibilities:
    - Read the credit card transactions CSV into a pandas DataFrame
    - Read the validation rules JSON into a Python dictionary

This module does NOT validate, transform, or clean data. It only reads.
Downstream modules (validation.py, anomaly.py) consume what this returns.

Used by:
    - main.py (orchestrator calls these functions first)
"""

import json
import logging
from pathlib import Path

import pandas as pd

from cerebro import config

logger = logging.getLogger(__name__)


def read_transactions(csv_path: Path = config.CSV_INPUT_PATH) -> pd.DataFrame:
    """
    Read the credit card transactions CSV into a DataFrame.

    Args:
        csv_path: Path to the CSV file. Defaults to the location in config.

    Returns:
        A pandas DataFrame with all rows and columns from the CSV.

    Raises:
        FileNotFoundError: If the CSV doesn't exist at the given path.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found at {csv_path}. "
            f"Download creditcard.csv from Kaggle and place it in data/raw/."
        )

    logger.info(f"Reading transactions from {csv_path}")
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def read_validation_rules(rules_path: Path = config.VALIDATION_RULES_PATH) -> dict:
    """
    Read the validation rules JSON into a dictionary.

    Args:
        rules_path: Path to the JSON file. Defaults to the location in config.

    Returns:
        A dictionary with validation rules (column constraints, expected values).

    Raises:
        FileNotFoundError: If the rules file doesn't exist.
    """
    if not rules_path.exists():
        raise FileNotFoundError(
            f"Validation rules not found at {rules_path}. "
            f"Create validation_rules.json in data/raw/."
        )

    logger.info(f"Reading validation rules from {rules_path}")
    with open(rules_path, "r") as f:
        rules = json.load(f)
    logger.info(f"Loaded validation rules with {len(rules)} top-level entries")
    return rules