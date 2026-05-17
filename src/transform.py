"""Transform layer — validate, clean, and enrich raw flight data."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def validate(df: pd.DataFrame, required_fields: list[str]) -> pd.DataFrame:
    """Drop rows missing any required field and log a quality summary."""
    before = len(df)
    df = df.dropna(subset=required_fields)
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d rows with nulls in required fields.", dropped)
    logger.info("Validation: %d/%d rows passed.", len(df), before)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise string columns and remove duplicates."""
    for col in ("callsign", "origin", "destination", "typecode"):
        if col in df.columns:
            df[col] = df[col].str.strip().str.upper()

    before = len(df)
    df = df.drop_duplicates(subset=["callsign", "firstseen"])
    dropped = before - len(df)
    if dropped:
        logger.info("Removed %d duplicate flights.", dropped)

    return df


def enrich(df: pd.DataFrame, min_duration_minutes: int = 5) -> pd.DataFrame:
    """Add derived columns and filter implausible flights.

    Derived fields:
      - duration_minutes: flight time in minutes
      - date: calendar date of departure (for partitioning)

    Flights shorter than min_duration_minutes are almost always bad data
    (test squawks, ground movements) so we drop them here rather than
    carrying them downstream.
    """
    df["firstseen"] = pd.to_datetime(df["firstseen"], utc=True, errors="coerce")
    df["lastseen"] = pd.to_datetime(df["lastseen"], utc=True, errors="coerce")

    null_ts = df["firstseen"].isna().sum()
    if null_ts > 0:
        pct = null_ts / len(df) * 100
        logger.warning("%.1f%% of rows have unparseable firstseen timestamps (%d rows).", pct, null_ts)
        if pct > 50:
            raise ValueError(f"Too many unparseable timestamps ({pct:.1f}%) — check source data.")

    df["duration_minutes"] = (
        (df["lastseen"] - df["firstseen"]).dt.total_seconds() / 60
    ).round(1)

    df["date"] = df["firstseen"].dt.date

    before = len(df)
    df = df[df["duration_minutes"] >= min_duration_minutes]
    logger.info(
        "Filtered %d implausibly short flights (< %d min); %d remain.",
        before - len(df),
        min_duration_minutes,
        len(df),
    )

    return df


def quality_report(df: pd.DataFrame) -> dict:
    """Return a simple data quality summary dict."""
    return {
        "total_rows": len(df),
        "unique_flights": df["callsign"].nunique() if "callsign" in df.columns else None,
        "unique_origins": df["origin"].nunique() if "origin" in df.columns else None,
        "unique_destinations": df["destination"].nunique() if "destination" in df.columns else None,
        "null_counts": df.isnull().sum().to_dict(),
        "date_range": {
            "min": str(df["firstseen"].min()) if "firstseen" in df.columns else None,
            "max": str(df["firstseen"].max()) if "firstseen" in df.columns else None,
        },
    }


def transform(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """Run the full transform pipeline and return (cleaned_df, quality_report)."""
    required = config["transform"]["required_fields"]
    min_dur = config["transform"]["min_flight_duration_minutes"]

    df = validate(df, required)
    df = clean(df)
    df = enrich(df, min_duration_minutes=min_dur)

    report = quality_report(df)
    logger.info("Quality report: %s", report)

    return df, report
