"""
persistence.py — Save processed DataFrames into PostgreSQL.

Responsibilities:
    - Truncate target tables (idempotent batch reload)
    - Map DataFrame column names to PostgreSQL conventions
    - Bulk-insert rows via pandas' to_sql()

Why truncate-before-insert:
    This is a batch pipeline. Re-running it should produce the same end state,
    not duplicate every row. For a streaming/incremental system, we'd use
    upserts or append-with-dedup instead.

Used by:
    - main.py (called after anomaly detection)
"""

import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from cerebro import config

logger = logging.getLogger(__name__)


def get_engine() -> Engine:
    """Create a SQLAlchemy Engine connected to PostgreSQL."""
    return create_engine(config.DATABASE_URL)


def save_transactions(df: pd.DataFrame) -> int:
    """
    Save validated + scored transactions to the `transactions` table.

    The DataFrame is expected to have columns: Time, V1..V28, Amount, Class,
    anomaly_score, is_anomaly. We rename them to match the Postgres schema
    (lowercase, time_offset instead of Time) before inserting.

    Args:
        df: The result DataFrame from anomaly.detect_anomalies().

    Returns:
        The number of rows inserted.
    """
    if df.empty:
        logger.warning("No transactions to save")
        return 0

    logger.info(f"Saving {len(df):,} transactions to PostgreSQL")

    engine = get_engine()

    # Rename DataFrame columns to match Postgres schema (snake_case, lowercase).
    df_to_save = df.rename(columns={
        "Time": "time_offset",
        "Amount": "amount",
        "Class": "class",
        **{f"V{i}": f"v{i}" for i in range(1, 29)},
    })

    # Truncate the table first for idempotent batch behavior.
    # RESTART IDENTITY resets the auto-increment id counter.
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE transactions RESTART IDENTITY"))

    # Bulk insert. chunksize uses multi-row INSERTs internally for speed.
    df_to_save.to_sql(
        name="transactions",
        con=engine,
        if_exists="append",
        index=False,
        chunksize=config.DB_BATCH_SIZE,
        method="multi",
    )

    logger.info(f"Inserted {len(df_to_save):,} rows into transactions")
    return len(df_to_save)


def save_invalid_records(df: pd.DataFrame) -> int:
    """
    Save invalid rows to the `invalid_records` table.

    Args:
        df: The invalid_df from validation.validate(), which has a
            'validation_errors' column.

    Returns:
        The number of rows inserted.
    """
    if df.empty:
        logger.info("No invalid records to save")
        return 0

    logger.info(f"Saving {len(df):,} invalid records to PostgreSQL")

    engine = get_engine()

    df_to_save = df.rename(columns={
        "Time": "time_offset",
        "Amount": "amount",
        "Class": "class",
        **{f"V{i}": f"v{i}" for i in range(1, 29)},
    })

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE invalid_records RESTART IDENTITY"))

    df_to_save.to_sql(
        name="invalid_records",
        con=engine,
        if_exists="append",
        index=False,
        chunksize=config.DB_BATCH_SIZE,
        method="multi",
    )

    logger.info(f"Inserted {len(df_to_save):,} rows into invalid_records")
    return len(df_to_save)