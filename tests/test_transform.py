"""Tests for the transform layer."""

import pandas as pd
import pytest

from src.transform import clean, enrich, quality_report, validate


def _base_df():
    return pd.DataFrame(
        {
            "callsign": ["  DLH123 ", "BAW456", "BAW456", "RYR789"],
            "icao24": ["3c4b1c", "400f01", "400f01", "4ca868"],
            "typecode": ["a320", "B738", "B738", "B738"],
            "origin": ["EDDF", "EGLL", "EGLL", "EINN"],
            "destination": ["LEMD", "EDDM", "EDDM", "EGKK"],
            "firstseen": [
                "2020-01-15 08:00:00+00:00",
                "2020-01-15 10:00:00+00:00",
                "2020-01-15 10:00:00+00:00",
                "2020-01-15 12:00:00+00:00",
            ],
            "lastseen": [
                "2020-01-15 10:00:00+00:00",
                "2020-01-15 12:00:00+00:00",
                "2020-01-15 12:00:00+00:00",
                "2020-01-15 12:03:00+00:00",  # 3 min — below threshold
            ],
            "day": pd.to_datetime(["2020-01-15"] * 4),
        }
    )


class TestValidate:
    def test_drops_rows_with_null_required_fields(self):
        df = _base_df()
        df.loc[0, "callsign"] = None
        result = validate(df, required_fields=["callsign", "origin", "destination"])
        assert len(result) == 3
        assert "DLH123" not in result["callsign"].values

    def test_keeps_all_rows_when_no_nulls(self):
        df = _base_df()
        result = validate(df, required_fields=["callsign", "origin"])
        assert len(result) == len(df)


class TestClean:
    def test_strips_and_uppercases_callsign(self):
        df = _base_df()
        result = clean(df)
        assert result["callsign"].iloc[0] == "DLH123"

    def test_removes_duplicates_on_callsign_firstseen(self):
        df = _base_df()
        result = clean(df)
        assert len(result) == 3  # BAW456 duplicate removed

    def test_uppercases_typecode(self):
        df = _base_df()
        result = clean(df)
        assert result["typecode"].iloc[0] == "A320"


class TestEnrich:
    def test_duration_minutes_is_correct(self):
        df = _base_df()
        df = clean(df)
        result = enrich(df, min_duration_minutes=5)
        dlh_row = result[result["callsign"] == "DLH123"]
        assert dlh_row["duration_minutes"].iloc[0] == 120.0

    def test_filters_short_flights(self):
        df = _base_df()
        df = clean(df)
        result = enrich(df, min_duration_minutes=5)
        assert "RYR789" not in result["callsign"].values

    def test_date_column_added(self):
        df = _base_df()
        df = clean(df)
        result = enrich(df, min_duration_minutes=5)
        assert "date" in result.columns


class TestQualityReport:
    def test_report_contains_expected_keys(self):
        df = _base_df()
        df = clean(df)
        df = enrich(df, min_duration_minutes=5)
        report = quality_report(df)
        assert "total_rows" in report
        assert "unique_flights" in report
        assert "null_counts" in report
        assert "date_range" in report

    def test_total_rows_matches(self):
        df = _base_df()
        df = clean(df)
        df = enrich(df, min_duration_minutes=5)
        report = quality_report(df)
        assert report["total_rows"] == len(df)
