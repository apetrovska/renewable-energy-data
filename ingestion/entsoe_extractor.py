import logging
import os
from datetime import timezone

import pandas as pd
from entsoe import EntsoePandasClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -- Configuration -----------------------------------------------------
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
    """Create ENTSO-E client from environment variable."""
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
    """Fetch generation data for one country and return normalized DataFrame.

    - Keeps only 'Actual Aggregated' sub-column for each production type.
    - Resamples to hourly (ENTSO-E may return 15-min intervals).
    - Converts index to UTC.
    - Returns long-format DataFrame with columns:
      datetime_utc, country_code, production_type, generation_mwh
    """
    logger.info(f"Fetching generation: {country} {start.date()} -> {end.date()}")

    raw = client.query_generation(country, start=start, end=end)

    # -- Extract 'Actual Aggregated' sub-column for each production type --
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

    df = pd.concat(frames, axis=1)

    # -- Resample to hourly if needed --
    df = df.resample("h").sum()

    # -- Convert index to UTC --
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    # -- Convert to long format --
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
    """Fetch load data for one country and return normalized DataFrame.

    Returns long-format DataFrame with columns:
    datetime_utc, country_code, load_mwh
    """
    logger.info(f"Fetching load: {country} {start.date()} -> {end.date()}")

    raw = client.query_load(country, start=start, end=end)

    # raw is a Series or single-column DataFrame
    if isinstance(raw, pd.DataFrame):
        series = raw.iloc[:, 0]
    else:
        series = raw

    # -- Resample to hourly --
    series = series.resample("h").sum()

    # -- Convert index to UTC --
    if series.index.tzinfo is None:
        series.index = series.index.tz_localize("UTC")
    else:
        series.index = series.index.tz_convert("UTC")

    df = series.reset_index()
    df.columns = ["datetime_utc", "load_mwh"]
    df["country_code"] = country

    return df[["country_code", "datetime_utc", "load_mwh"]]


def main(
    start: pd.Timestamp = START_DATE,
    end: pd.Timestamp = END_DATE,
    countries: list[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract generation and load data for all countries.

    Returns:
        df_generation: long-format generation DataFrame
        df_load: load DataFrame
    """
    if countries is None:
        countries = COUNTRIES

    client = get_client()

    gen_frames  = []
    load_frames = []

    for country in countries:
        try:
            df_gen  = fetch_generation(client, country, start, end)
            df_load = fetch_load(client, country, start, end)

            if not df_gen.empty:
                gen_frames.append(df_gen)
            if not df_load.empty:
                load_frames.append(df_load)

        except Exception as e:
            logger.error(f"Failed to fetch data for {country}: {e}")
            continue

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