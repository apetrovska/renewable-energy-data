import logging
from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = "renewable-energy-data-pipeline"
DATASET    = "raw"

client = bigquery.Client(project=PROJECT_ID)


def load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    write_disposition: str = "WRITE_TRUNCATE"
) -> None:
    """Load a DataFrame into BigQuery raw dataset."""

    # Add metadata column for freshness checks
    df["_loaded_at"] = datetime.now(timezone.utc)

    table_id = f"{PROJECT_ID}.{DATASET}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=write_disposition,
        autodetect=True,
    )

    logger.info(f"Loading {len(df):,} rows into {table_id}...")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    logger.info(f"Done — {table_id}")


def load_owid() -> None:
    from owid_extractor import main as extract_owid
    df = extract_owid()
    load_dataframe(df, "owid_energy", write_disposition="WRITE_TRUNCATE")


def load_weather() -> None:
    from weather_extractor import main as extract_weather
    df = extract_weather()
    load_dataframe(df, "weather_daily", write_disposition="WRITE_TRUNCATE")


if __name__ == "__main__":
    import sys

    commands = {
        "owid":    load_owid,
        "weather": load_weather,
        "all":     lambda: [load_owid(), load_weather()],
    }

    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg not in commands:
        print(f"Usage: python load_to_raw.py [owid|weather|all]")
        sys.exit(1)

    commands[arg]()