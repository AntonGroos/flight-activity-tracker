"""Extract layer — download and read monthly flight CSVs from Zenodo.

Data source: OpenSky COVID-19 Flight Dataset
  https://zenodo.org/records/7923702

Each file is a gzipped CSV covering one calendar month with columns:
  callsign, number, icao24, registration, typecode,
  origin, destination, firstseen, lastseen, day,
  latitude_1, longitude_1, altitude_1,
  latitude_2, longitude_2, altitude_2

The file naming convention is: flightlist_YYYYMMDD_YYYYMMDD.csv.gz
where the dates are the first and last day of the month.
"""

import calendar
import logging
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Columns we actually need — dropping lat/lon/alt to save memory.
# The Zenodo CSVs can be 200+ MB uncompressed; selecting only the columns
# we use cuts memory consumption roughly in half.
USECOLS = [
    "callsign",
    "icao24",
    "typecode",
    "origin",
    "destination",
    "firstseen",
    "lastseen",
    "day",
]


def _month_to_filename(month_str: str) -> str:
    """Convert '2019-01' to 'flightlist_20190101_20190131.csv.gz'.

    The Zenodo dataset uses the first and last calendar day of each month
    in the filename. calendar.monthrange gives us the last day.
    """
    year, month = map(int, month_str.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return f"flightlist_{year}{month:02d}01_{year}{month:02d}{last_day:02d}.csv.gz"


class ZenodoExtractor:
    """Downloads and reads monthly flight data CSVs from Zenodo.

    The download-then-read pattern (instead of streaming directly into pandas)
    is deliberate: it gives us a local cache so re-runs don't hit the network,
    and it makes debugging easier because you can inspect the raw files.
    """

    def __init__(self, config: dict):
        self.base_url = config["source"]["zenodo_base_url"]
        self.months = config["source"]["months"]
        self.raw_dir = Path(config["source"]["raw_dir"])
        self.timeout = config["source"]["download_timeout_seconds"]

    def _download_file(self, filename: str) -> Path:
        """Download a single CSV.gz from Zenodo if not already cached locally."""
        local_path = self.raw_dir / filename
        if local_path.exists():
            logger.info("Using cached file: %s", local_path)
            return local_path

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/{filename}"
        logger.info("Downloading %s", url)

        resp = requests.get(url, timeout=self.timeout, stream=True)
        resp.raise_for_status()

        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info("Downloaded %.1f MB → %s", size_mb, local_path)
        return local_path

    def _read_csv(self, path: Path) -> pd.DataFrame:
        """Read a gzipped CSV into a DataFrame, selecting only needed columns.

        pandas can read .csv.gz natively — it detects the gzip compression
        from the file extension. We specify dtypes to avoid mixed-type warnings
        and reduce memory usage.
        """
        df = pd.read_csv(
            path,
            usecols=USECOLS,
            dtype={
                "callsign": "str",
                "icao24": "str",
                "typecode": "str",
                "origin": "str",
                "destination": "str",
            },
            parse_dates=["day"],
        )
        logger.info("Read %d flights from %s", len(df), path.name)
        return df

    def extract(self) -> pd.DataFrame:
        """Download and concatenate all configured months into one DataFrame.

        Returns the combined raw data. If a download fails for one month,
        it logs a warning and continues with the remaining months — this is
        intentional so the pipeline produces partial results rather than
        failing completely.
        """
        frames = []
        for month_str in self.months:
            filename = _month_to_filename(month_str)
            try:
                path = self._download_file(filename)
                df = self._read_csv(path)
                frames.append(df)
            except requests.RequestException as exc:
                logger.warning("Failed to download %s: %s — skipping.", filename, exc)
            except Exception as exc:
                logger.warning("Failed to read %s: %s — skipping.", filename, exc)

        if not frames:
            logger.error("No data extracted from any month.")
            return pd.DataFrame(columns=USECOLS)

        combined = pd.concat(frames, ignore_index=True)
        logger.info(
            "Extraction complete: %d total flights from %d month(s).",
            len(combined),
            len(frames),
        )
        return combined
