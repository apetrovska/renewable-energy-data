import logging
from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = "renewable-energy-data-pipeline"
DATASET    = "raw"




def load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    write_disposition: str = "WRITE_TRUNCATE"
) -> None:
    """Load a DataFrame into BigQuery raw dataset."""

    client = bigquery.Client(project=PROJECT_ID)

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
    from ingestion.owid_extractor import main as extract_owid
    df = extract_owid()
    load_dataframe(df, "owid_energy", write_disposition="WRITE_TRUNCATE")


def load_weather() -> None:
    from ingestion.weather_extractor import main as extract_weather
    df = extract_weather()
    load_dataframe(df, "weather_daily", write_disposition="WRITE_TRUNCATE")


def load_entsoe(
    start: "pd.Timestamp | None" = None,
    end: "pd.Timestamp | None" = None,
    countries: "list[str] | None" = None,
) -> None:
    from ingestion.entsoe_extractor import main as extract_entsoe

    if start is None:
        start = pd.Timestamp("2023-01-01", tz="UTC")
    if end is None:
        end = pd.Timestamp("2026-01-01", tz="UTC")

    df_generation, df_load = extract_entsoe(
        start=start,
        end=end,
        countries=countries,
    )

    if not df_generation.empty:
        load_dataframe(
            df_generation,
            "entsoe_generation",
            write_disposition="WRITE_APPEND",
        )

    if not df_load.empty:
        load_dataframe(
            df_load,
            "entsoe_load",
            write_disposition="WRITE_APPEND",
        )


if __name__ == "__main__":
    import sys

    commands = {
        "owid":    load_owid,
        "weather": load_weather,
        "entsoe": load_entsoe,
        "all":     lambda: [load_owid(), load_weather(), load_entsoe()],
    }

    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg not in commands:
        print(f"Usage: python load_to_raw.py [owid|weather|all]")
        sys.exit(1)

    commands[arg]()