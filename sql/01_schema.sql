-- =============================================================================
-- 01_schema.sql — Cerebro database schema
--
-- Two tables:
--   transactions     — valid rows processed by the pipeline
--   invalid_records  — rows that failed validation, with the reason
--
-- Both store all original columns from the CSV. transactions also stores
-- anomaly detection results (score + flag) and an ingestion timestamp.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- transactions: validated rows with anomaly detection results.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id              BIGSERIAL PRIMARY KEY,
    time_offset     DOUBLE PRECISION NOT NULL,
    amount          NUMERIC(12, 2) NOT NULL,
    class           SMALLINT NOT NULL,

    -- PCA-transformed features (V1 through V28)
    v1  DOUBLE PRECISION, v2  DOUBLE PRECISION, v3  DOUBLE PRECISION, v4  DOUBLE PRECISION,
    v5  DOUBLE PRECISION, v6  DOUBLE PRECISION, v7  DOUBLE PRECISION, v8  DOUBLE PRECISION,
    v9  DOUBLE PRECISION, v10 DOUBLE PRECISION, v11 DOUBLE PRECISION, v12 DOUBLE PRECISION,
    v13 DOUBLE PRECISION, v14 DOUBLE PRECISION, v15 DOUBLE PRECISION, v16 DOUBLE PRECISION,
    v17 DOUBLE PRECISION, v18 DOUBLE PRECISION, v19 DOUBLE PRECISION, v20 DOUBLE PRECISION,
    v21 DOUBLE PRECISION, v22 DOUBLE PRECISION, v23 DOUBLE PRECISION, v24 DOUBLE PRECISION,
    v25 DOUBLE PRECISION, v26 DOUBLE PRECISION, v27 DOUBLE PRECISION, v28 DOUBLE PRECISION,

    -- Anomaly detection results
    anomaly_score   DOUBLE PRECISION,
    is_anomaly      BOOLEAN NOT NULL DEFAULT FALSE,

    -- Metadata
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------------------
-- invalid_records: rows that failed validation.
-- Same columns as transactions but with validation_errors instead of anomaly fields.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invalid_records (
    id                 BIGSERIAL PRIMARY KEY,
    time_offset        DOUBLE PRECISION,
    amount             NUMERIC(12, 2),
    class              SMALLINT,

    v1  DOUBLE PRECISION, v2  DOUBLE PRECISION, v3  DOUBLE PRECISION, v4  DOUBLE PRECISION,
    v5  DOUBLE PRECISION, v6  DOUBLE PRECISION, v7  DOUBLE PRECISION, v8  DOUBLE PRECISION,
    v9  DOUBLE PRECISION, v10 DOUBLE PRECISION, v11 DOUBLE PRECISION, v12 DOUBLE PRECISION,
    v13 DOUBLE PRECISION, v14 DOUBLE PRECISION, v15 DOUBLE PRECISION, v16 DOUBLE PRECISION,
    v17 DOUBLE PRECISION, v18 DOUBLE PRECISION, v19 DOUBLE PRECISION, v20 DOUBLE PRECISION,
    v21 DOUBLE PRECISION, v22 DOUBLE PRECISION, v23 DOUBLE PRECISION, v24 DOUBLE PRECISION,
    v25 DOUBLE PRECISION, v26 DOUBLE PRECISION, v27 DOUBLE PRECISION, v28 DOUBLE PRECISION,

    validation_errors  TEXT NOT NULL,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------------------
-- Indexes on commonly queried columns.
-- The .NET API will frequently query anomalies and filter by amount/time.
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_transactions_is_anomaly
    ON transactions(is_anomaly)
    WHERE is_anomaly = TRUE;

CREATE INDEX IF NOT EXISTS idx_transactions_anomaly_score
    ON transactions(anomaly_score);

CREATE INDEX IF NOT EXISTS idx_transactions_amount
    ON transactions(amount);