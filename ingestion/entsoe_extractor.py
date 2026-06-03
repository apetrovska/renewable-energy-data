"""Extract electricity generation and load data from ENTSO-E API.

This module queries the ENTSO-E (European Network of Transmission System
Operators for Electricity) API for hourly generation by production type
(solar, wind, hydro, nuclear, fossil, etc.) and total electricity load
across 11 European countries.

Requires ENTSOE_API_KEY environment variable for authentication.
"""

import logging
import os

import pandas as pd
from entsoe import EntsoePandasClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configured countries for data extraction
COUNTRIES = ["DE", "FR", "ES", "PL", "AT", "HU", "NO", "SK", "LT", "EE", "LV"]

START_DATE = pd.Timestamp("2023-01-01", tz="UTC")
END_DATE   = pd.Timestamp("2026-01-01", tz="UTC")

# Production types to keep -- "Actual Aggregated" sub-column only.
# Keys are ENTSO-E source names, values are our standardized names.
PRODUCTION_TYPES = {
    "Biomass":                          "biomass",
    "Fossil Brown coal/Lignite":        "fossil_brown_coal",
    "Fossil Coal-derived gas":          "fossil_coal_gas",
    "Fossil Gas":                       "fossil_gas",
    "Fossil Hard coal":                 "fossil_hard_coal",
    "Fossil Oil":                       "fossil_oil",
    "Geothermal":                       "geothermal",
    "Hydro Pumped Storage":             "hydro_pumped_storage",
    "Hydro Run-of-river and poundage":  "hydro_run_of_river",
    "Hydro Water Reservoir":            "hydro_reservoir",
    "Nuclear":                          "nuclear",
    "Other":                            "other",
    "Other renewable":                  "other_renewable",
    "Solar":                            "solar",
    "Waste":                            "waste",
    "Wind Offshore":                    "wind_offshore",
    "Wind Onshore":                     "wind_onshore",
}
# ----------------------------------------------------------------------


def get_client() -> EntsoePandasClient:
    """Create ENTSO-E API client from environment variable.

    Returns:
        Initialized EntsoePandasClient ready for API queries.

    Raises:
        ValueError: If ENTSOE_API_KEY environment variable is not set.
    """
    api_key = os.environ.get("ENTSOE_API_KEY")
    if not api_key:
        raise ValueError("ENTSOE_API_KEY environment variable is not set")
    return EntsoePandasClient(api_key=api_key)


def fetch_generation(
    client: EntsoePandasClient,
    country: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Fetch generation data for one country from ENTSO-E API.

    Args:
        client: Authenticated ENTSO-E API client
        country: ISO 3166-1 alpha-2 country code (e.g., "DE", "FR")
        start: Start timestamp (must be timezone-aware, UTC)
        end: End timestamp (must be timezone-aware, UTC)

    Returns:
        Long-format DataFrame with columns:
        - country_code: ISO country code
        - datetime_utc: Hourly timestamp in UTC
        - production_type: Standardized production type name
        - generation_mwh: Generation in MWh

        Data is normalized: filters to 'Actual Aggregated' values only,
        resampled to hourly (if source provides 15-min intervals),
        and converted to UTC timezone.
    """
    logger.info(f"Fetching generation: {country} {start.date()} -> {end.date()}")

    # Query ENTSO-E API for generation data
    raw = client.query_generation(country, start=start, end=end)

    # Extract 'Actual Aggregated' sub-column for each production type (ENTSO-E returns MultiIndex columns)
    frames = []
    for col in raw.columns:
        prod_type, sub_type = col  # MultiIndex: (production_type, sub_type)
        if sub_type != "Actual Aggregated":
            continue
        if prod_type not in PRODUCTION_TYPES:
            continue

        series = raw[col].copy()
        series.name = PRODUCTION_TYPES[prod_type]
        frames.append(series)

    if not frames:
        logger.warning(f"No matching columns found for {country}")
        return pd.DataFrame()

    # Combine series into wide-format DataFrame
    df = pd.concat(frames, axis=1)

    # Resample to hourly granularity (ENTSO-E sometimes returns 15-min or 30-min intervals)
    df = df.resample("h").sum()

    # Normalize timezone to UTC
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    # Convert from wide format to long format for data warehouse
    df = df.reset_index().rename(columns={"index": "datetime_utc"})
    df = df.melt(
        id_vars="datetime_utc",
        var_name="production_type",
        value_name="generation_mwh",
    )
    df["country_code"] = country

    return df[["country_code", "datetime_utc", "production_type", "generation_mwh"]]


def fetch_load(
    client: EntsoePandasClient,
    country: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Fetch load (electricity demand) data for one country from ENTSO-E API.

    Args:
        client: Authenticated ENTSO-E API client
        country: ISO 3166-1 alpha-2 country code (e.g., "DE", "FR")
        start: Start timestamp (must be timezone-aware, UTC)
        end: End timestamp (must be timezone-aware, UTC)

    Returns:
        DataFrame with columns:
        - country_code: ISO country code
        - datetime_utc: Hourly timestamp in UTC
        - load_mwh: Total load/demand in MWh

        Data is normalized: resampled to hourly if necessary and converted to UTC.
    """
    logger.info(f"Fetching load: {country} {start.date()} -> {end.date()}")

    # Query ENTSO-E API for load data
    raw = client.query_load(country, start=start, end=end)

    # Normalize API response to Series (raw may be Series or single-column DataFrame)
    if isinstance(raw, pd.DataFrame):
        series = raw.iloc[:, 0]
    else:
        series = raw

    # Resample to hourly granularity if needed
    series = series.resample("h").sum()

    # Normalize timezone to UTC
    if series.index.tzinfo is None:
        series.index = series.index.tz_localize("UTC")
    else:
        series.index = series.index.tz_convert("UTC")

    # Convert to DataFrame with proper column names
    df = series.reset_index()
    df.columns = ["datetime_utc", "load_mwh"]
    df["country_code"] = country

    return df[["country_code", "datetime_utc", "load_mwh"]]


def main(
    start: pd.Timestamp = START_DATE,
    end: pd.Timestamp = END_DATE,
    countries: list[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract generation and load data from ENTSO-E API for multiple countries.

    Args:
        start: Start date (timezone-aware, UTC). Defaults to START_DATE.
        end: End date (timezone-aware, UTC). Defaults to END_DATE.
        countries: List of ISO country codes to fetch. Defaults to all 11 configured countries.

    Returns:
        Tuple of two DataFrames:
        - df_generation: Long-format with columns country_code, datetime_utc,
          production_type, generation_mwh. Contains data for all production types.
        - df_load: Long-format with columns country_code, datetime_utc, load_mwh.
          Contains total electricity demand.

        Both DataFrames are concatenated from individual country queries.
        Empty DataFrames are returned if no data is available for a dataset.
    """
    if countries is None:
        countries = COUNTRIES

    # Initialize ENTSO-E API client
    client = get_client()

    # Accumulators for generation and load data from each country
    gen_frames  = []
    load_frames = []

    # Query each country's generation and load data with error handling
    for country in countries:
        try:
            gen_data  = fetch_generation(client, country, start, end)
            load_data = fetch_load(client, country, start, end)

            if not gen_data.empty:
                gen_frames.append(gen_data)
            if not load_data.empty:
                load_frames.append(load_data)

        except Exception as e:
            logger.error(f"Failed to fetch data for {country}: {e}")
            continue

    # Concatenate all country data or return empty DataFrame if no data
    df_generation = pd.concat(gen_frames,  ignore_index=True) if gen_frames  else pd.DataFrame()
    df_load       = pd.concat(load_frames, ignore_index=True) if load_frames else pd.DataFrame()

    logger.info(f"Generation: {len(df_generation):,} rows")
    logger.info(f"Load:       {len(df_load):,} rows")

    return df_generation, df_load


if __name__ == "__main__":
    df_gen, df_load = main(
        start=pd.Timestamp("2023-01-01", tz="UTC"),
        end=pd.Timestamp("2023-01-08", tz="UTC"), # one week for quick testing
        countries=["DE"], # single country for quick testing
    )

    print("\n-- Generation preview --")
    print(df_gen.head(10).to_string())
    print(f"\nShape: {df_gen.shape}")
    print(f"Production types: {sorted(df_gen['production_type'].unique())}")

    print("\n-- Load preview --")
    print(df_load.head(5).to_string())
    print(f"\nShape: {df_load.shape}")