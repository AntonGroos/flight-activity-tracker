"""ETL pipeline entrypoint.

Usage:
    python main.py                    # uses config.yaml
    python main.py --config my.yaml   # custom config file
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

from src.extract import ZenodoExtractor
from src.load import upload_month
from src.transform import transform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as exc:
        logger.error("Invalid YAML in config file %s: %s", path, exc)
        sys.exit(1)
    except OSError as exc:
        logger.error("Could not read config file %s: %s", path, exc)
        sys.exit(1)


def run(config: dict) -> None:
    logger.info("=== Extract ===")
    extractor = ZenodoExtractor(config)
    raw = extractor.extract()

    if raw.empty:
        logger.error("No data extracted — aborting.")
        sys.exit(1)

    logger.info("=== Transform ===")
    try:
        cleaned, report = transform(raw, config)
    except Exception as exc:
        logger.error("Transform failed: %s", exc, exc_info=True)
        sys.exit(1)

    if cleaned.empty:
        logger.error("Transform produced no rows — aborting.")
        sys.exit(1)

    logger.info("Quality report:\n%s", json.dumps(report, indent=2, default=str))

    logger.info("=== Load ===")
    months = config["source"]["months"]
    uploaded, failed = [], []

    for month_str in months:
        year, month = map(int, month_str.split("-"))
        month_df = cleaned[
            (cleaned["firstseen"].dt.year == year) & (cleaned["firstseen"].dt.month == month)
        ]
        if month_df.empty:
            logger.warning("No data for %s after transform — skipping upload.", month_str)
            continue
        try:
            uri = upload_month(month_df, month_str)
            logger.info("Uploaded %s → %s", month_str, uri)
            uploaded.append(month_str)
        except Exception as exc:
            logger.error("Failed to upload %s: %s — skipping.", month_str, exc)
            failed.append(month_str)

    logger.info("=== Pipeline complete: %d uploaded, %d failed ===", len(uploaded), len(failed))
    if failed:
        logger.warning("Failed months: %s", ", ".join(failed))
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSky ETL pipeline")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    config = load_config(str(config_path))
    try:
        run(config)
    except Exception as exc:
        logger.critical("Unexpected pipeline failure: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
