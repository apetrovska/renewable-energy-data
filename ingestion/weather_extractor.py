"""Extract daily weather data for 11 European countries from Open-Meteo API.

This module fetches historical and current daily weather observations
(temperature, wind, precipitation, clouds, sunshine) from the Open-Meteo
archive API. Data is fetched by country coordinates and saved as raw records
for loading into BigQuery.
"""

import pandas as pd
import requests
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ────────────────────Configuration──────────────────────────
# Open-Meteo API endpoint for historical weather data
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Capital city coordinates - documented approximation.
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
    "wind_speed_10m_mean",   # km/h — mean wind speed at 10m height
    "sunshine_duration",     # seconds — converted to hours in staging
    "temperature_2m_mean",   # °C
    "precipitation_sum",     # mm
    "cloud_cover_mean",      # %
]
# ─────────────────────────────────────────────────────────


def fetch_country(country_code: str, lat: float, lon: float) -> pd.DataFrame:
    """Fetch daily weather data for one country from Open-Meteo archive API.

    Queries the Open-Meteo archive API for historical daily weather observations
    (wind speed, sunshine duration, temperature, precipitation, cloud cover) for
    a single country across the configured date range.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., "DE", "FR")
        lat: Latitude coordinate of the query location (typically country capital)
        lon: Longitude coordinate of the query location

    Returns:
        DataFrame with 7 columns:
        - country_code: ISO country code (string)
        - date: Date in YYYY-MM-DD format (string)
        - wind_speed_10m_mean: Mean wind speed at 10m height (km/h)
        - sunshine_duration: Duration of sunshine (seconds, converted to hours in staging)
        - temperature_2m_mean: Mean temperature (°C)
        - precipitation_sum: Total precipitation (mm)
        - cloud_cover_mean: Mean cloud cover (%)

        One row per day from START_DATE to END_DATE.

    Example:
        Input: fetch_country("DE", 52.52, 13.41)
        Output:
               country_code        date  wind_speed_10m_mean  sunshine_duration  \\
            0             DE  2023-01-01                  8.5               3600
            1             DE  2023-01-02                  7.2               1800

            temperature_2m_mean  precipitation_sum  cloud_cover_mean
        0                 2.3                2.1                 65
        1                 3.5                0.0                 45
    """
    logger.info(f"Fetching weather for {country_code} ({lat}, {lon})...")

    # Build API request parameters: location coordinates, date range, fields, timezone
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": DAILY_FIELDS,
        "timezone": "UTC"
    }

    # Query Open-Meteo archive API and parse JSON response
    response = requests.get(ARCHIVE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    # Convert API response (nested arrays) into DataFrame
    df = pd.DataFrame(data["daily"])

    # Add country code column for later grouping/filtering
    df["country_code"] = country_code

    # Rename 'time' column to 'date' for clarity
    df = df.rename(columns={'time': 'date'})

    # Reorder columns: country_code and date first, then weather fields
    df = df[["country_code", "date"] + DAILY_FIELDS]

    logger.info(f"{country_code}: {len(df)} rows ({START_DATE} to {END_DATE})")

    return df



def fetch_all_countries() -> pd.DataFrame:
    """Fetch weather data for all 11 configured countries and combine into single DataFrame.

    Iterates through each country in COUNTRIES dict, fetches daily weather via
    fetch_country(), handles errors gracefully, and concatenates results into
    one combined DataFrame. Includes rate limiting to respect API usage guidelines.

    Returns:
        Concatenated DataFrame containing weather records for all 11 countries.
        Columns: country_code, date, wind_speed_10m_mean, sunshine_duration,
                 temperature_2m_mean, precipitation_sum, cloud_cover_mean.
        Date range: START_DATE to END_DATE across all countries.
        Total rows: approximately 11 countries × 1095 days = 12,045 rows

    Example:
        Input: fetch_all_countries()
        Output:
               country_code        date  wind_speed_10m_mean  \\
            0             DE  2023-01-01                  8.5
            1             DE  2023-01-02                  7.2
            ...
            12044           LV  2025-12-31                  5.1

            Shape: (12045, 7)
            Countries: ['AT', 'DE', 'EE', 'ES', 'FR', 'HU', 'LT', 'LV', 'NO', 'PL', 'SK']
            Date range: 2023-01-01 to 2025-12-31
    """
    logger.info(f"Fetching all countries...")

    # Accumulator list for individual country DataFrames
    frames = []

    # Iterate through each country, fetch weather, handle errors
    for country_code, coords in COUNTRIES.items():
        try:
            # Fetch daily weather for this country
            df = fetch_country(country_code, coords['lat'], coords['lon'])
            frames.append(df)

            # Rate limiting: pause 3 seconds between requests (API best practices)
            time.sleep(3)

        except Exception as e:
            # Log error but continue processing other countries (resilient extraction)
            logger.error(f"Failed to fetch weather for {country_code}: {e}")
            continue

    # Concatenate all country DataFrames into one wide DataFrame
    df_all = pd.concat(frames, ignore_index=True)

    # Log summary statistics for quality assurance
    logger.info(
        f"Total: {len(df_all):,} rows — "
        f"{df_all['country_code'].nunique()} countries, "
        f"dates {df_all['date'].min()} → {df_all['date'].max()}"
    )

    return df_all



def main() -> pd.DataFrame:
    """Extract and save daily weather data for all 11 countries.

    Orchestrates the complete weather extraction pipeline:
    1. Fetch weather data from Open-Meteo for all countries
    2. Save a local CSV sample for inspection
    3. Print data preview and metadata to console
    4. Return combined DataFrame for programmatic use

    The returned DataFrame contains raw data from Open-Meteo with:
    - No transformations (renaming, unit conversion) applied
    - Original source column names preserved
    - All transformations deferred to dbt staging layer (stg_weather_daily.sql)

    Returns:
        DataFrame containing weather records for all 11 countries.
        Columns: country_code, date, wind_speed_10m_mean, sunshine_duration,
                 temperature_2m_mean, precipitation_sum, cloud_cover_mean.

    Side effects:
        - Saves CSV sample to ingestion/weather_sample.csv
        - Prints data preview (first 10 rows) and metadata to stdout
        - Creates .cache directory for HTTP caching (if using openmeteo_requests)

    Example:
        Input: main()
        Output (printed):
            ── Raw preview (no transformations applied) ──
               country_code        date  wind_speed_10m_mean  ...
            0             AT  2023-01-01                  8.5  ...
            1             AT  2023-01-02                  7.2  ...
            ...
            Shape: (12045, 7)
            Countries: ['AT', 'DE', 'EE', 'ES', 'FR', 'HU', 'LT', 'LV', 'NO', 'PL', 'SK']

            Returns: DataFrame with shape (12045, 7)
    """
    # Fetch combined weather data from all countries
    df_all = fetch_all_countries()

    # Save local CSV sample for inspection before BigQuery load
    output_path = "ingestion/weather_sample.csv"
    df_all.to_csv(output_path, index=False)
    logger.info(f"Saved raw sample to {output_path}")

    # Print human-readable preview and metadata
    print("── Raw preview (no transformations applied) ──")
    print(df_all.head(10).to_string())
    print(f"Shape: {df_all.shape}")
    print(f"Countries: {sorted(df_all['country_code'].unique())}")

    # Document that column names/units are from source (transformations in dbt)
    print(f"Column names are source originals — "
          f"renaming and unit conversions happen in stg_weather_daily.sql")
    print(f"Note: sunshine_duration is in seconds. "
          f"Divide by 3600 in staging to get hours.")

    return df_all



if __name__ == "__main__":
    main()