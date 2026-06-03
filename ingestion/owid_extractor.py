"""Extract energy statistics from Our World in Data (OWID) dataset.

This module downloads the OWID energy dataset from GitHub, applies scope
filtering (11 European countries, years 2020-2025), and prepares it for
loading into BigQuery. Semantic transformations happen in dbt staging.
"""

import io
import logging

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GitHub URL for OWID energy dataset
OWID_URL = (
    "https://raw.githubusercontent.com/owid/energy-data/master/"
    "owid-energy-data.csv"
)

# Scope filter — technical decision: which countries and years
# we will ever need. Avoids loading 200+ countries and 50+ years.
COUNTRIES_ISO3 = ["DEU", "FRA", "ESP", "POL", "AUT", "HUN",
                  "NOR", "SVK", "LTU", "EST", "LVA"]

START_YEAR = 2020
END_YEAR   = 2025

# Columns to retain — technical decision: avoids loading 100+
# irrelevant OWID columns into BigQuery raw layer.
# Column names are preserved exactly as they appear in the source.
RAW_COLUMNS = [
    "iso_code",
    "country",
    "year",
    "renewables_share_elec",
    "low_carbon_share_elec",
    "solar_share_elec",
    "wind_share_elec",
    "hydro_share_elec",
    "nuclear_share_elec",
    "fossil_share_elec",
    "solar_electricity",
    "wind_electricity",
    "carbon_intensity_elec",
]
# ─────────────────────────────────────────────────────────


def download_owid() -> pd.DataFrame:
    """Download the full OWID energy dataset from GitHub repository.

    Returns:
        Raw DataFrame with all rows and columns from OWID energy-data.csv.
        No filtering or transformation is applied at this stage.

    Raises:
        requests.HTTPError: If the HTTP request fails (network error, 404, etc.)

    Example:
        >>> df = download_owid()
        >>> df.shape
        (21870, 137)
        >>> df.columns.tolist()[:5]
        ['iso_code', 'country', 'year', 'renewables_share_elec', ...]
        >>> df['iso_code'].nunique()
        250
    """
    logger.info("Downloading OWID energy dataset...")
    response = requests.get(OWID_URL, timeout=60)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text), low_memory=False)
    logger.info(f"Downloaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def scope_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply technical scope filter: load optimization by countries and
    time range only, not business logic.

    Avoids loading 200+ countries and 50+ years into BigQuery raw layer.
    Filter criteria are constant (11 countries, 2020-2025) and documented
    in README Known Limitations as an explicit modeling decision.

    All semantic transformation (renaming, unit conversion, aggregation) happens
    in dbt staging layer, not here.

    Args:
        df: Raw OWID DataFrame with all columns and rows.

    Returns:
        Filtered DataFrame containing only:
        - Columns in RAW_COLUMNS list
        - Countries in COUNTRIES_ISO3 list (ISO3 codes)
        - Years from START_YEAR to END_YEAR inclusive

        Column names and values are preserved from source.

    Example:
        >>> df_raw = download_owid()
        >>> df = scope_filter(df_raw)
        >>> df.shape
        (66, 13)
        >>> df['iso_code'].unique()
        ['DEU', 'FRA', 'ESP', 'POL', 'AUT', 'HUN', 'NOR', 'SVK', 'LTU', 'EST', 'LVA']
        >>> sorted(df['year'].unique())
        [2020, 2021, 2022, 2023, 2024, 2025]
    """
    # Select columns that exist in the source, warn about missing ones
    available = [c for c in RAW_COLUMNS if c in df.columns]
    missing   = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        logger.warning(f"Columns not found in OWID source: {missing}")

    df = df[available].copy()

    # Keep only configured countries (ISO3 code format matches source)
    df = df[df["iso_code"].isin(COUNTRIES_ISO3)]

    # Keep only configured year range
    df = df[df["year"].between(START_YEAR, END_YEAR)]

    logger.info(
        f"After scope filter: {len(df)} rows "
        f"({df['iso_code'].nunique()} countries, "
        f"years {int(df['year'].min())}–{int(df['year'].max())})"
    )

    return df


def main() -> pd.DataFrame:
    """Extract OWID energy data with country and time scope filtering.

    Returns:
        Filtered DataFrame with columns in RAW_COLUMNS, countries in COUNTRIES_ISO3,
        and years from START_YEAR to END_YEAR.

        Column names are preserved from source; transformation happens in dbt staging.

    Side effects:
        Downloads full OWID dataset from GitHub.
        Saves filtered sample to ingestion/owid_sample.csv for inspection.
        Prints data preview and metadata to stdout.

    Example:
        >>> df = main()
        >>> df.shape
        (66, 13)
        >>> df.columns.tolist()
        ['iso_code', 'country', 'year', 'renewables_share_elec', ...]
        >>> df.groupby('iso_code').size()
        iso_code
        DEU    6
        FRA    6
        ...
    """
    # Download full dataset from GitHub
    df_raw = download_owid()

    # Apply country and year scope filtering
    df_filtered = scope_filter(df_raw)

    # Save locally for inspection before BigQuery load
    output_path = "ingestion/owid_sample.csv"
    df_filtered.to_csv(output_path, index=False)
    logger.info(f"Saved raw sample to {output_path}")

    # Print data preview and column information
    print("\n── Raw preview (no transformations applied) ──")
    print(df_filtered.head(5).to_string())
    print(f"\nShape: {df_filtered.shape}")
    print(f"\nCountries (ISO3): {sorted(df_filtered['iso_code'].unique())}")
    print(f"Years: {sorted(df_filtered['year'].unique())}")
    print(f"\nColumn names are source originals — "
          f"renaming happens in stg_owid_energy.sql")

    return df_filtered


if __name__ == "__main__":
    main()