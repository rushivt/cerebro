"""
config.py — Central configuration for the Cerebro fraud detection pipeline.

This module loads configuration values from environment variables (via .env file)
and exposes them as Python constants. All other pipeline modules import their
settings from here, ensuring a single source of truth.

Secrets like database passwords are NEVER hardcoded — they live in .env (gitignored)
and are loaded at runtime.

Used by:
    - ingestion.py    (file paths)
    - validation.py   (rules file path)
    - anomaly.py      (model parameters)
    - persistence.py  (database connection)
    - main.py         (orchestration)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve the project root (cerebro/) so paths work regardless of where
# the script is run from. This file lives at: cerebro/python-pipeline/cerebro/config.py
# So project root is 3 levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env file from project root if present
load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

CSV_INPUT_PATH = DATA_RAW_DIR / "creditcard.csv"
VALIDATION_RULES_PATH = DATA_RAW_DIR / "validation_rules.json"


# ---------------------------------------------------------------------------
# Database connection (read from .env, fall back to local defaults)
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "cerebro")
DB_USER = os.getenv("DB_USER", "cerebro_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

# SQLAlchemy connection URL — used by persistence.py
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# ---------------------------------------------------------------------------
# Anomaly detection parameters
# ---------------------------------------------------------------------------
# Contamination = expected fraction of anomalies in the data.
# Dataset has 0.172% fraud, so we set slightly above at 0.2%.
ANOMALY_CONTAMINATION = float(os.getenv("ANOMALY_CONTAMINATION", "0.002"))

# Random seed for reproducibility — same input always gives same output
RANDOM_SEED = 42

# Batch size for database inserts (rows per chunk)
DB_BATCH_SIZE = 1000