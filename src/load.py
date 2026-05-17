"""Load layer — write extracted DataFrames to Google Cloud Storage as Parquet.

Files are stored under the prefix:  flights/YYYY-MM/data.parquet
e.g.  gs://<bucket>/flights/2020-01/data.parquet
"""

import io
import logging
import os

import pandas as pd
from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

logger = logging.getLogger(__name__)


def _get_or_create_bucket(client: storage.Client, bucket_name: str) -> storage.Bucket:
    bucket = client.lookup_bucket(bucket_name)
    if bucket is None:
        project = client.project
        bucket = client.create_bucket(bucket_name, project=project)
        logger.info("Created GCS bucket: gs://%s", bucket_name)
    return bucket


def upload_month(df: pd.DataFrame, month_str: str) -> str:
    """Serialise df to Parquet and upload to GCS.

    Returns the full GCS URI of the uploaded object.
    """
    bucket_name = os.environ["GCS_BUCKET"]
    blob_path = f"flights/{month_str}/data.parquet"

    client = storage.Client()
    bucket = _get_or_create_bucket(client, bucket_name)

    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)

    blob = bucket.blob(blob_path)
    blob.upload_from_file(buffer, content_type="application/octet-stream")

    uri = f"gs://{bucket_name}/{blob_path}"
    logger.info("Uploaded %d rows → %s", len(df), uri)
    return uri
