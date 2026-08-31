"""
Messy Data Cleaner: CSV/JSON -> Structured Records
====================================================

Common FDE coding-round pattern: "A client gives you a CSV with N columns,
many with inconsistent naming (snake_case, camelCase, spaces). Clean it
into a structured schema."

This script handles the realistic mess you actually get from clients:
  - Inconsistent column naming (snake_case, camelCase, Title Case, spaces)
  - Missing values in different forms ("", "NULL", "N/A", "null", None)
  - Duplicate rows
  - Type coercion failures (a numeric column containing "unknown")
  - Extra/unexpected whitespace

Design principle: never silently drop bad rows. Log what was skipped
and why, so the caller can decide whether that's acceptable. Client
data cleaning that fails silently is a common source of production bugs.

Usage:
    python messy_data_cleaner.py sample_input.csv
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Column name normalization
# ---------------------------------------------------------------------------

def normalize_column_name(raw_name: str) -> str:
    """Converts snake_case, camelCase, Title Case, or 'spaced names'
    into a single consistent snake_case format.

    Examples:
        "Customer ID"     -> "customer_id"
        "customerID"      -> "customer_id"
        "customer_id"     -> "customer_id"
        "  Customer Name" -> "customer_name"
    """
    name = raw_name.strip()
    # Insert underscore before capital letters that follow a lowercase
    # letter or digit (handles camelCase -> camel_Case)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    # Replace whitespace/hyphens with underscores
    name = re.sub(r"[\s\-]+", "_", name)
    return name.lower()


# ---------------------------------------------------------------------------
# Missing-value handling
# ---------------------------------------------------------------------------

MISSING_VALUE_TOKENS = {"", "null", "n/a", "na", "none", "nil", "-"}


def is_missing(value: str) -> bool:
    return value is None or value.strip().lower() in MISSING_VALUE_TOKENS


def clean_value(value: str) -> str | None:
    if is_missing(value):
        return None
    return value.strip()


# ---------------------------------------------------------------------------
# Row-level cleaning with explicit skip tracking
# ---------------------------------------------------------------------------

@dataclass
class CleaningReport:
    total_rows: int = 0
    cleaned_rows: int = 0
    skipped_duplicate: int = 0
    skipped_missing_required: int = 0
    skipped_type_error: int = 0


def clean_rows(
    raw_rows: list[dict],
    required_fields: list[str],
    numeric_fields: list[str],
) -> tuple[list[dict], CleaningReport]:
    report = CleaningReport(total_rows=len(raw_rows))
    seen_rows = set()
    cleaned = []

    for raw_row in raw_rows:
        # Normalize keys
        row = {normalize_column_name(k): clean_value(v) for k, v in raw_row.items()}

        # Duplicate detection (based on full-row content after cleaning)
        row_signature = tuple(sorted(row.items()))
        if row_signature in seen_rows:
            report.skipped_duplicate += 1
            continue
        seen_rows.add(row_signature)

        # Required field check
        if any(row.get(field) is None for field in required_fields):
            report.skipped_missing_required += 1
            continue

        # Type coercion for numeric fields
        type_error = False
        for field in numeric_fields:
            if row.get(field) is not None:
                try:
                    row[field] = float(row[field])
                except ValueError:
                    type_error = True
                    break
        if type_error:
            report.skipped_type_error += 1
            continue

        cleaned.append(row)
        report.cleaned_rows += 1

    return cleaned, report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", help="Path to the messy input CSV")
    parser.add_argument(
        "--required", nargs="*", default=["customer_id"],
        help="Normalized field names that must be present (non-null)",
    )
    parser.add_argument(
        "--numeric", nargs="*", default=["amount"],
        help="Normalized field names expected to be numeric",
    )
    args = parser.parse_args()

    with open(args.input_csv, newline="") as f:
        raw_rows = list(csv.DictReader(f))

    cleaned, report = clean_rows(raw_rows, args.required, args.numeric)

    print(f"Total rows read:            {report.total_rows}")
    print(f"Cleaned rows:               {report.cleaned_rows}")
    print(f"Skipped (duplicate):        {report.skipped_duplicate}")
    print(f"Skipped (missing required): {report.skipped_missing_required}")
    print(f"Skipped (type error):       {report.skipped_type_error}")

    if cleaned:
        print("\nSample cleaned row:")
        print(cleaned[0])


if __name__ == "__main__":
    main()
