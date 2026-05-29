import logging
import time
from datetime import date

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Capital city coordinates — documented approximation.
# Not actual generation sites; standard practice for country-level analysis.
# See README Known Limitations.
COUNTRIES = {
    "DE": {"lat": 52.52,  "lon": 13.41},   # Berlin
    "FR": {"lat": 48.85,  "lon":  2.35},   # Paris
    "ES": {"lat": 40.42,  "lon": -3.70},   # Madrid
    "PL": {"lat": 52.23,  "lon": 21.01},   # Warsaw
    "AT": {"lat": 48.21,  "lon": 16.37},   # Vienna
    "HU": {"lat": 47.50,  "lon": 19.05},   # Budapest
    "NO": {"lat": 59.91,  "lon": 10.75},   # Oslo
    "SK": {"lat": 48.15,  "lon": 17.11},   # Bratislava
    "LT": {"lat": 54.69,  "lon": 25.28},   # Vilnius
    "EE": {"lat": 59.44,  "lon": 24.75},   # Tallinn
    "LV": {"lat": 56.95,  "lon": 24.11},   # Riga
}

START_DATE = "2023-01-01"
END_DATE   = "2025-12-31"

# Original source field names are preserved.
# Unit conversions (sunshine seconds → hours) happen in stg_weather_daily.sql
DAILY_FIELDS = [
    "wind_speed_10m_max",    # km/h — max, not avg; documented in schema.yml
    "sunshine_duration",     # seconds — converted to hours in staging
    "temperature_2m_mean",   # °C
    "precipitation_sum",     # mm
    "cloud_cover_mean",      # %
]

REQUEST_DELAY_SECONDS = 1   # Open-Meteo has no rate limit but be polite
# ─────────────────────────────────────────────────────────


def fetch_country(country_code: str, lat: float, lon: float) -> pd.DataFrame:
    """Fetch daily weather for one country from Open-Meteo archive API."""
    logger.info(f"Fetching weather for {country_code} ({lat}, {lon})...")

    params = {
        "latitude":  lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date":   END_DATE,
        "daily":      ",".join(DAILY_FIELDS),
        "timezone":   "UTC",
    }

    response = requests.get(ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    # API returns parallel arrays — assemble into DataFrame row by row
    daily = data["daily"]
    df = pd.DataFrame({
        "country_code":       country_code,
        "date":               daily["time"],
        "wind_speed_10m_max": daily["wind_speed_10m_max"],
        "sunshine_duration":  daily["sunshine_duration"],
        "temperature_2m_mean":daily["temperature_2m_mean"],
        "precipitation_sum":  daily["precipitation_sum"],
        "cloud_cover_mean":   daily["cloud_cover_mean"],
    })

    logger.info(f"{country_code}: {len(df)} rows ({START_DATE} → {END_DATE})")
    return df


def fetch_all_countries() -> pd.DataFrame:
    """Fetch weather for all 11 countries and combine into one DataFrame."""
    frames = []

    for country_code, coords in COUNTRIES.items():
        df = fetch_country(country_code, coords["lat"], coords["lon"])
        frames.append(df)
        time.sleep(REQUEST_DELAY_SECONDS)

    df_all = pd.concat(frames, ignore_index=True)
    logger.info(
        f"Total: {len(df_all):,} rows — "
        f"{df_all['country_code'].nunique()} countries, "
        f"dates {df_all['date'].min()} → {df_all['date'].max()}"
    )
    return df_all


def main() -> pd.DataFrame:
    df = fetch_all_countries()

    # Save locally for inspection before BigQuery load
    output_path = "ingestion/weather_sample.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Saved raw sample to {output_path}")

    print("\n── Raw preview (no transformations applied) ──")
    print(df.head(10).to_string())
    print(f"\nShape: {df.shape}")
    print(f"\nCountries: {sorted(df['country_code'].unique())}")
    print(f"\nColumn names are source originals — "
          f"renaming and unit conversions happen in stg_weather_daily.sql")
    print(f"\nNote: sunshine_duration is in seconds. "
          f"Divide by 3600 in staging to get hours.")

    return df


if __name__ == "__main__":
    main()