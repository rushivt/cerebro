"""
validation.py — Validate transaction records against rules.

Responsibilities:
    - Apply rules from validation_rules.json to the transactions DataFrame
    - Split rows into two groups: valid (passed all rules) and invalid (failed at least one rule)
    - For invalid rows, record a human-readable description of which rule(s) they failed

Approach:
    Validation is done with vectorized boolean masks. For each rule, we build a
    boolean Series the same length as the DataFrame, where True means "this row
    failed this rule." We OR these masks together across all rules to get a
    global failure mask. We also build a parallel string Series with the failure
    reasons, joined with "; " when a row fails multiple rules.

    This avoids row-by-row iteration over 284k rows, which would be ~100x slower.

Used by:
    - main.py (called after ingestion, before anomaly detection)
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def validate(df: pd.DataFrame, rules: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate a DataFrame against the supplied rules.

    Steps:
        1. Confirm the DataFrame has all required columns (else crash early).
        2. Initialize two trackers — a boolean failure_mask and a string reasons.
        3. For each column with rules, apply them and merge results into the trackers.
        4. Split the DataFrame into valid and invalid based on the final failure_mask.

    Args:
        df:    The raw transactions DataFrame produced by ingestion.read_transactions().
        rules: The parsed validation rules dictionary from ingestion.read_validation_rules().

    Returns:
        A tuple (valid_df, invalid_df).
        - valid_df:   rows that passed every rule. Same columns as input df.
        - invalid_df: rows that failed at least one rule. Has one extra column
                      'validation_errors' describing the failure(s).
    """
    logger.info(f"Validating {len(df):,} rows")

    # -------------------------------------------------------------------------
    # Step 1 — Structural check.
    # If required columns are missing, there's no point continuing. Crash early.
    # -------------------------------------------------------------------------
    _check_required_columns(df, rules['required_columns'])

    # -------------------------------------------------------------------------
    # Step 2 — Initialize trackers.
    # Two parallel Series, both the same length as df.
    #   failure_mask: starts all False. Will flip to True for rows that fail any rule.
    #   reasons:      starts all empty strings. Will hold the failure description.
    # Using index=df.index keeps these aligned with the DataFrame's row labels.
    # -------------------------------------------------------------------------
    failure_mask = pd.Series(False, index=df.index)
    reasons = pd.Series("", index=df.index)

    # -------------------------------------------------------------------------
    # Step 3 — Apply each column's rules.
    # rules['column_rules'] looks like:
    #     {
    #         "Time":   {"min": 0, "nullable": False, ...},
    #         "Amount": {"min": 0, "max": 25000, "nullable": False, ...},
    #         "Class":  {"allowed_values": [0, 1], "nullable": False, ...}
    #     }
    # For each column, _apply_column_rule() returns a (failure_mask, reasons)
    # pair just for that one column. We merge them into the global trackers.
    # -------------------------------------------------------------------------
    for column_name, column_rule in rules['column_rules'].items():
        col_mask, col_reasons = _apply_column_rule(df, column_name, column_rule)

        # OR the per-column mask into the global mask.
        # A row stays failed if it failed before OR fails now.
        failure_mask = failure_mask | col_mask

        # Merge the per-column reasons into the global reasons string.
        # Two cases handled separately:
        #   (a) Row's first failure         -> just set the reason text.
        #   (b) Row already had a failure   -> append new reason with "; " separator.
        new_failures = (col_reasons != "") & (reasons == "")
        also_failed = (col_reasons != "") & (reasons != "")

        reasons = reasons.mask(new_failures, col_reasons)
        reasons = reasons.mask(also_failed, reasons + "; " + col_reasons)

    # -------------------------------------------------------------------------
    # Step 4 — Split into valid and invalid.
    # ~failure_mask flips True<->False, so df[~failure_mask] keeps the passing rows.
    # df[failure_mask] keeps the failing rows.
    # .copy() prevents pandas SettingWithCopyWarning when we later add a column.
    # -------------------------------------------------------------------------
    valid_df = df[~failure_mask].copy()
    invalid_df = df[failure_mask].copy()

    # Attach the failure reason as a new column on invalid_df only.
    # reasons[failure_mask] keeps only the reason strings for failed rows,
    # matched to invalid_df by index.
    invalid_df['validation_errors'] = reasons[failure_mask]

    logger.info(
        f"Validation complete — "
        f"valid: {len(valid_df):,}, invalid: {len(invalid_df):,}"
    )
    return valid_df, invalid_df


# =============================================================================
# Helper functions (leading underscore = internal use only, not part of the
# module's public API).
# =============================================================================


def _check_required_columns(df: pd.DataFrame, required: list) -> None:
    """
    Raise an error if any required column is missing from the DataFrame.

    We use set arithmetic: (required_set - actual_set) gives us the missing names.
    If the result is non-empty (truthy in Python), we crash with a clear message.

    Args:
        df:       The DataFrame to check.
        required: List of column names that must be present.

    Raises:
        ValueError: If any required column is missing.
    """
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")


def _apply_column_rule(
    df: pd.DataFrame, column: str, rule: dict
) -> tuple[pd.Series, pd.Series]:
    """
    Apply all rules for one column and return (failure_mask, reasons) for that column.

    Four checks are run in order:
        1. Null check          — if rule says non-nullable, flag nulls
        2. Min check           — if rule has a min, flag values below it
        3. Max check           — if rule has a max, flag values above it
        4. Allowed values check — if rule has a whitelist, flag values not in it

    Each check uses vectorized pandas operations (no row loops).

    Args:
        df:     The full DataFrame (we extract just the column we care about).
        column: Name of the column to check, e.g. "Amount".
        rule:   The rule dict for this column, e.g. {"min": 0, "max": 25000, ...}.

    Returns:
        failure_mask: Boolean Series — True where this column failed for that row.
        reasons:      String Series  — failure description per row (empty if passed).
    """
    # Start with empty trackers, same length as the DataFrame.
    failure_mask = pd.Series(False, index=df.index)
    reasons = pd.Series("", index=df.index)

    # Pull out just the column we care about as a Series.
    series = df[column]

    # -------------------------------------------------------------------------
    # Check 1 — Null check.
    # rule.get('nullable', True) returns the 'nullable' value, defaulting to True
    # if the key is missing. We only run the check if nullable is False.
    # -------------------------------------------------------------------------
    if not rule.get('nullable', True):
        # .isna() is True where the value is NaN/None/missing.
        null_mask = series.isna()
        failure_mask = failure_mask | null_mask
        # .mask(cond, val) sets cells to val where cond is True, keeps others.
        reasons = reasons.mask(null_mask, f"{column} is null")

    # -------------------------------------------------------------------------
    # Check 2 — Min check.
    # `is not None` (not just `if rule.get('min'):`) because min could legitimately
    # be 0, which would be "falsy" in Python. We want to distinguish "missing key"
    # from "key with value 0".
    # -------------------------------------------------------------------------
    if rule.get('min') is not None:
        below_min = series < rule['min']
        failure_mask = failure_mask | below_min
        reasons = reasons.mask(below_min, f"{column} below min ({rule['min']})")

    # -------------------------------------------------------------------------
    # Check 3 — Max check. Same pattern as min, but with >.
    # -------------------------------------------------------------------------
    if rule.get('max') is not None:
        above_max = series > rule['max']
        failure_mask = failure_mask | above_max
        reasons = reasons.mask(above_max, f"{column} above max ({rule['max']})")

    # -------------------------------------------------------------------------
    # Check 4 — Allowed values check.
    # .isin([...]) returns True where the value IS in the list.
    # We use ~ to flip it: ~series.isin([...]) is True where value is NOT in the list.
    # Pandas has no built-in is_not_in() method, so this is the idiomatic pattern.
    # -------------------------------------------------------------------------
    if rule.get('allowed_values') is not None:
        not_allowed = ~series.isin(rule['allowed_values'])
        failure_mask = failure_mask | not_allowed
        reasons = reasons.mask(
            not_allowed,
            f"{column} not in allowed values {rule['allowed_values']}"
        )

    # Python automatically packages multiple comma-separated values into a tuple.
    return failure_mask, reasons