# OpenSky Flight ETL Pipeline

A lightweight ETL pipeline that extracts monthly flight data from the [OpenSky COVID-19 Flight Dataset](https://zenodo.org/records/7923702), applies data quality transformations, and loads the result to Google Cloud Storage as Parquet.

## Architecture

```
Zenodo (CSV.gz) → Extract → Transform → Load → GCS (Parquet)
                                 ↓
                         Quality Report
```

**Extract** — Downloads monthly gzipped CSVs from Zenodo with local caching (re-runs don't re-download). Only the columns we need are read into memory, cutting footprint roughly in half on 200+ MB files.

**Transform** — Three passes:

1. _Validate_ — drop rows missing required fields (callsign, origin, destination, timestamps)
2. _Clean_ — strip/uppercase string columns, deduplicate on `(callsign, firstseen)`
3. _Enrich_ — derive `duration_minutes` and `date`, filter implausibly short flights (< 5 min, almost always ground movements or bad data)

**Load** — Serialises each month's data to Parquet (column-oriented, good compression, schema-preserving) and uploads to GCS under `flights/YYYY-MM/data.parquet`.

## Setup

### 1. Prerequisites

- Python 3.9+
- A Google Cloud project with a GCS bucket

### 2. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. GCS credentials

Create a service account with the **Storage Admin** role, download its JSON key, and set:

```bash
# .env
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-key.json
GCS_BUCKET=your-bucket-name
```

### 4. Configure months

Edit `config.yaml` to select which months to process:

```yaml
source:
  months:
    - "2020-01"
    - "2020-02"
```

### 5. Run

```bash
python main.py
# or with a custom config:
python main.py --config my-config.yaml
```

Raw files are cached in `data/raw/` — subsequent runs skip downloading.

## Tests

```bash
pytest
```

15 unit tests covering filename generation, validation, cleaning, enrichment, and the quality report.

## Output

Each month is uploaded to:

```
gs://<bucket>/flights/YYYY-MM/data.parquet
```

A JSON quality report is printed to stdout at the end of each run, showing row counts, unique flights, null counts, and date range.
