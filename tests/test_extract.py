"""Tests for the extract layer."""

from src.extract import _month_to_filename


class TestMonthToFilename:
    """Verify the month string → Zenodo filename conversion."""

    def test_january(self):
        assert _month_to_filename("2019-01") == "flightlist_20190101_20190131.csv.gz"

    def test_february_non_leap(self):
        assert _month_to_filename("2019-02") == "flightlist_20190201_20190228.csv.gz"

    def test_february_leap(self):
        assert _month_to_filename("2020-02") == "flightlist_20200201_20200229.csv.gz"

    def test_december(self):
        assert _month_to_filename("2022-12") == "flightlist_20221201_20221231.csv.gz"

    def test_september_30_days(self):
        assert _month_to_filename("2019-09") == "flightlist_20190901_20190930.csv.gz"
