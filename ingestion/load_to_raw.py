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

    Example:
        >>> df = pd.DataFrame({
        ...     'country_code': ['DE', 'FR'],
        ...     'date': ['2023-01-01', '2023-01-01'],
        ...     'value': [10.5, 11.2]
        ... })
        >>> load_dataframe(df, "test_table", write_disposition="WRITE_TRUNCATE")
        Loading 2 rows into renewable-energy-data-pipeline.raw.test_table...
        Done — renewable-energy-data-pipeline.raw.test_table
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

    Example:
        >>> load_owid()
        Downloading OWID energy dataset...
        Downloaded 21,870 rows, 137 columns
        After scope filter: 66 rows (11 countries, years 2020–2025)
        Saved raw sample to ingestion/owid_sample.csv
        Loading 66 rows into renewable-energy-data-pipeline.raw.owid_energy...
        Done — renewable-energy-data-pipeline.raw.owid_energy
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

    Example:
        >>> load_weather()
        Fetching weather for DE (52.52, 13.41)...
        DE: 1095 rows (2023-01-01 → 2025-12-31)
        ...
        Total: 12,045 rows — 11 countries, dates 2023-01-01 → 2025-12-31
        Saved raw sample to ingestion/weather_sample.csv
        Loading 12,045 rows into renewable-energy-data-pipeline.raw.weather_daily...
        Done — renewable-energy-data-pipeline.raw.weather_daily
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

    Example:
        >>> start = pd.Timestamp("2023-01-01", tz="UTC")
        >>> end = pd.Timestamp("2023-01-08", tz="UTC")
        >>> load_entsoe(start=start, end=end, countries=["DE", "FR"])
        Fetching generation: DE 2023-01-01 -> 2023-01-08
        ...
        Fetching load: DE 2023-01-01 -> 2023-01-08
        ...
        Generation: 4,320 rows
        Load: 384 rows
        Loading 4,320 rows into renewable-energy-data-pipeline.raw.entsoe_generation...
        Done — renewable-energy-data-pipeline.raw.entsoe_generation
        Loading 384 rows into renewable-energy-data-pipeline.raw.entsoe_load...
        Done — renewable-energy-data-pipeline.raw.entsoe_load
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