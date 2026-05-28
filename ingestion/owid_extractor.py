import io
import logging

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────
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
    """Download the full OWID energy dataset from GitHub."""
    logger.info("Downloading OWID energy dataset...")
    response = requests.get(OWID_URL, timeout=60)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text), low_memory=False)
    logger.info(f"Downloaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def scope_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply technical scope filter only.
    All transformation happens in dbt staging.
    """
    # Keep only columns that exist in the source
    available = [c for c in RAW_COLUMNS if c in df.columns]
    missing   = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        logger.warning(f"Columns not found in OWID source: {missing}")

    df = df[available].copy()

    # Filter to our 11 countries (ISO3 codes — as in source)
    df = df[df["iso_code"].isin(COUNTRIES_ISO3)]

    # Filter to our time window
    df = df[df["year"].between(START_YEAR, END_YEAR)]

    logger.info(
        f"After scope filter: {len(df)} rows "
        f"({df['iso_code'].nunique()} countries, "
        f"years {int(df['year'].min())}–{int(df['year'].max())})"
    )

    return df


def main() -> pd.DataFrame:
    df_raw      = download_owid()
    df_filtered = scope_filter(df_raw)

    # Save locally for inspection before BigQuery load
    output_path = "ingestion/owid_sample.csv"
    df_filtered.to_csv(output_path, index=False)
    logger.info(f"Saved raw sample to {output_path}")

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