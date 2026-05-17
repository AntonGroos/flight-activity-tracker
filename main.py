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
    with open(path) as f:
        return yaml.safe_load(f)


def run(config: dict) -> None:
    logger.info("=== Extract ===")
    extractor = ZenodoExtractor(config)
    raw = extractor.extract()

    if raw.empty:
        logger.error("No data extracted — aborting.")
        sys.exit(1)

    logger.info("=== Transform ===")
    clean, report = transform(raw, config)

    logger.info("Quality report:\n%s", json.dumps(report, indent=2, default=str))

    logger.info("=== Load ===")
    months = config["source"]["months"]

    for month_str in months:
        year, month = map(int, month_str.split("-"))
        month_df = clean[
            (clean["firstseen"].dt.year == year) & (clean["firstseen"].dt.month == month)
        ]
        if month_df.empty:
            logger.warning("No data for %s after transform — skipping upload.", month_str)
            continue
        uri = upload_month(month_df, month_str)
        logger.info("Uploaded %s → %s", month_str, uri)

    logger.info("=== Pipeline complete ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSky ETL pipeline")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    config = load_config(str(config_path))
    run(config)


if __name__ == "__main__":
    main()
