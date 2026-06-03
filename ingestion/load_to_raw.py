"""Load extracted data from all sources into BigQuery raw dataset.

This module orchestrates the extraction and loading of data from three sources:
- OWID: Energy statistics (renewable/fossil share, generation)
- Open-Meteo: Daily weather observations (temperature, wind, precipitation)
- ENTSO-E: Hourly electricity generation and demand

Raw data is loaded with minimal transformation; all business logic
transformations happen in dbt staging layer.
"""

import logging
from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BigQuery project and dataset for raw data
PROJECT_ID = "renewable-energy-data-pipeline"
DATASET    = "raw"




def load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    write_disposition: str = "WRITE_TRUNCATE"
) -> None:
    """Load a DataFrame into BigQuery raw dataset.

    Args:
        df: DataFrame to load (columns and dtypes are auto-detected)
        table_name: Name of table in raw dataset (e.g., "weather_daily")
        write_disposition: How to handle existing data:
            - "WRITE_TRUNCATE": Replace entire table (default)
            - "WRITE_APPEND": Append to existing table

    Side effects:
        Adds "_loaded_at" timestamp column with current UTC time.
        Creates or modifies table in BigQuery raw dataset.
    """
    # Initialize BigQuery client
    client = bigquery.Client(project=PROJECT_ID)

    # Add metadata column for data freshness tracking
    df["_loaded_at"] = datetime.now(timezone.utc)

    table_id = f"{PROJECT_ID}.{DATASET}.{table_name}"

    # Configure BigQuery load job with auto-schema detection
    job_config = bigquery.LoadJobConfig(
        write_disposition=write_disposition,
        autodetect=True,
    )

    logger.info(f"Loading {len(df):,} rows into {table_id}...")
    # Execute load job and wait for completion
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    logger.info(f"Done — {table_id}")


def load_owid() -> None:
    """Extract OWID energy data and load to BigQuery raw.owid_energy table.

    Returns:
        None. Side effect: loads data to BigQuery.
    """
    # Extract filtered OWID energy data
    from ingestion.owid_extractor import main as extract_owid
    df = extract_owid()

    # Load to BigQuery (truncate existing table)
    load_dataframe(df, "owid_energy", write_disposition="WRITE_TRUNCATE")


def load_weather() -> None:
    """Extract daily weather data and load to BigQuery raw.weather_daily table.

    Returns:
        None. Side effect: loads data to BigQuery.
    """
    # Extract daily weather data for all countries
    from ingestion.weather_extractor import main as extract_weather
    df = extract_weather()

    # Load to BigQuery (truncate existing table)
    load_dataframe(df, "weather_daily", write_disposition="WRITE_TRUNCATE")


def load_entsoe(
    start: "pd.Timestamp | None" = None,
    end: "pd.Timestamp | None" = None,
    countries: "list[str] | None" = None,
) -> None:
    """Extract ENTSO-E generation and load data and load to BigQuery raw.

    Args:
        start: Start date (timezone-aware UTC). Defaults to 2023-01-01.
        end: End date (timezone-aware UTC). Defaults to 2026-01-01.
        countries: List of ISO country codes. Defaults to all 11 configured countries.

    Returns:
        None. Side effect: appends data to BigQuery tables.

    Note:
        Uses WRITE_APPEND disposition to accumulate data from multiple date ranges.
        Only loads non-empty DataFrames.
    """
    # Extract generation and load data from ENTSO-E API
    from ingestion.entsoe_extractor import main as extract_entsoe

    # Apply defaults for date range if not provided
    if start is None:
        start = pd.Timestamp("2023-01-01", tz="UTC")
    if end is None:
        end = pd.Timestamp("2026-01-01", tz="UTC")

    df_generation, df_load = extract_entsoe(
        start=start,
        end=end,
        countries=countries,
    )

    # Load generation data if available (append to existing table)
    if not df_generation.empty:
        load_dataframe(
            df_generation,
            "entsoe_generation",
            write_disposition="WRITE_APPEND",
        )

    # Load demand data if available (append to existing table)
    if not df_load.empty:
        load_dataframe(
            df_load,
            "entsoe_load",
            write_disposition="WRITE_APPEND",
        )


if __name__ == "__main__":
    import sys

    # Map CLI arguments to load functions
    commands = {
        "owid":    load_owid,
        "weather": load_weather,
        "entsoe":  load_entsoe,
        "all":     lambda: [load_owid(), load_weather(), load_entsoe()],
    }

    # Get command from CLI argument, default to "all"
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Validate and execute command
    if arg not in commands:
        print(f"Usage: python load_to_raw.py [owid|weather|entsoe|all]")
        sys.exit(1)

    commands[arg]()