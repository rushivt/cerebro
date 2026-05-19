"""
main.py — Cerebro pipeline orchestrator.

Runs the full data pipeline end-to-end:
    1. Ingest CSV transactions and JSON validation rules
    2. Validate records (split into valid / invalid)
    3. Run Isolation Forest anomaly detection on valid records
    4. Save processed data to PostgreSQL

Usage:
    cd python-pipeline
    python main.py

The pipeline is idempotent — re-running truncates and reloads target tables.
"""

import logging
import sys
import time

from cerebro import ingestion, validation, anomaly, persistence


def configure_logging() -> None:
    """Set up basic logging to stdout with timestamps."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def run_pipeline() -> dict:
    """
    Execute the full pipeline end-to-end.

    Returns:
        A dict summarizing the run: row counts, anomaly count, duration.
    """
    logger = logging.getLogger("cerebro.main")
    start = time.time()

    logger.info("=" * 60)
    logger.info("Cerebro pipeline starting")
    logger.info("=" * 60)

    # Step 1 — ingest
    df = ingestion.read_transactions()
    rules = ingestion.read_validation_rules()

    # Step 2 — validate
    valid_df, invalid_df = validation.validate(df, rules)

    # Step 3 — anomaly detection on valid rows
    result_df = anomaly.detect_anomalies(valid_df)

    # Step 4 — persist
    n_transactions = persistence.save_transactions(result_df)
    n_invalid = persistence.save_invalid_records(invalid_df)

    duration = time.time() - start

    summary = {
        "rows_read": len(df),
        "valid": n_transactions,
        "invalid": n_invalid,
        "anomalies_flagged": int(result_df["is_anomaly"].sum()),
        "duration_seconds": round(duration, 2),
    }

    logger.info("=" * 60)
    logger.info(f"Pipeline complete in {summary['duration_seconds']}s")
    logger.info(f"  Rows read:           {summary['rows_read']:,}")
    logger.info(f"  Valid → DB:          {summary['valid']:,}")
    logger.info(f"  Invalid → DB:        {summary['invalid']:,}")
    logger.info(f"  Anomalies flagged:   {summary['anomalies_flagged']:,}")
    logger.info("=" * 60)

    return summary


if __name__ == "__main__":
    configure_logging()
    run_pipeline()