"""Extract daily weather data for 11 European countries from Open-Meteo API.

This module fetches historical and current daily weather observations
(temperature, wind, precipitation, clouds, sunshine) from the Open-Meteo
archive API. Data is fetched by country coordinates and saved as raw records
for loading into BigQuery.
"""

import logging

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Open-Meteo API endpoint for historical weather data
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
    "wind_speed_10m_mean",   # km/h — mean wind speed at 10m height
    "sunshine_duration",     # seconds — converted to hours in staging
    "temperature_2m_mean",   # °C
    "precipitation_sum",     # mm
    "cloud_cover_mean",      # %
]
# ─────────────────────────────────────────────────────────


def get_client() -> openmeteo_requests.Client:
    """Create Open-Meteo API client with HTTP caching and retry logic.

    Returns:
        Configured openmeteo_requests.Client with:
        - HTTP response caching (cache never expires for archive data)
        - Automatic retry on transient failures (5 retries with exponential backoff)

    Example:
        >>> client = get_client()
        >>> type(client)
        <class 'openmeteo_requests.Client'>
    """
    # Setup HTTP caching session (archive data never changes, so cache indefinitely)
    cache_session = requests_cache.CachedSession(
        ".cache",
        expire_after=-1    # Cache never expires — archive data doesn't change
    )

    # Add retry logic with exponential backoff for transient failures
    retry_session = retry(
        cache_session,
        retries=5,
        backoff_factor=0.2  # 0.2s, 0.4s, 0.8s, 1.6s, 3.2s between retries
    )

    return openmeteo_requests.Client(session=retry_session)


def fetch_country(
    client: openmeteo_requests.Client,
    country_code: str,
    lat: float,
    lon: float,
) -> pd.DataFrame:
    """Fetch daily weather data for one country from Open-Meteo archive API.

    Args:
        client: Authenticated Open-Meteo API client with caching and retries
        country_code: ISO 3166-1 alpha-2 country code (e.g., "DE", "FR")
        lat: Latitude coordinate of the query location (typically country capital)
        lon: Longitude coordinate of the query location

    Returns:
        DataFrame with columns: country_code, date, wind_speed_10m_mean,
        sunshine_duration, temperature_2m_mean, precipitation_sum, cloud_cover_mean.
        Each row represents one daily record from START_DATE to END_DATE.

    Example:
        >>> client = get_client()
        >>> df = fetch_country(client, "DE", 52.52, 13.41)
        >>> df.shape
        (1095, 7)
        >>> df.head(1)
          country_code        date  wind_speed_10m_mean  sunshine_duration  \\
        0            DE  2023-01-01                  8.5               3600
          temperature_2m_mean  precipitation_sum  cloud_cover_mean
        0                 2.3                2.1                 65
    """
    logger.info(f"Fetching weather for {country_code} ({lat}, {lon})...")

    # Build request parameters for Open-Meteo API
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": START_DATE,
        "end_date":   END_DATE,
        "daily":      DAILY_FIELDS,
        "timezone":   "UTC",
    }

    # Query Open-Meteo API
    responses = client.weather_api(ARCHIVE_URL, params=params)
    response = responses[0]
    daily = response.Daily()

    # Extract daily data — variables are returned in same order as DAILY_FIELDS
    df = pd.DataFrame({
        "country_code":        country_code,
        "date":                pd.date_range(
            start=pd.to_datetime(daily.Time(),    unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(),   unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left",
        ).date,
        "wind_speed_10m_mean": daily.Variables(0).ValuesAsNumpy(),
        "sunshine_duration":   daily.Variables(1).ValuesAsNumpy(),
        "temperature_2m_mean": daily.Variables(2).ValuesAsNumpy(),
        "precipitation_sum":   daily.Variables(3).ValuesAsNumpy(),
        "cloud_cover_mean":    daily.Variables(4).ValuesAsNumpy(),
    })

    logger.info(f"{country_code}: {len(df)} rows ({START_DATE} → {END_DATE})")
    return df


def fetch_all_countries(client: openmeteo_requests.Client) -> pd.DataFrame:
    """Fetch weather data for all configured countries and combine into single DataFrame.

    Args:
        client: Authenticated Open-Meteo API client with caching and retries

    Returns:
        Concatenated DataFrame containing weather records for all 11 countries.
        Columns: country_code, date, wind_speed_10m_mean, sunshine_duration,
        temperature_2m_mean, precipitation_sum, cloud_cover_mean.
        Date range: START_DATE to END_DATE across all countries.

    Example:
        >>> client = get_client()
        >>> df = fetch_all_countries(client)
        >>> df.shape
        (12045, 7)
        >>> df['country_code'].nunique()
        11
        >>> df['country_code'].unique()
        ['DE', 'FR', 'ES', 'PL', 'AT', 'HU', 'NO', 'SK', 'LT', 'EE', 'LV']
    """
    # Accumulator for DataFrames from each country
    frames = []

    # Fetch data for each country (cached responses avoid redundant API calls)
    for country_code, coords in COUNTRIES.items():
        df = fetch_country(client, country_code, coords["lat"], coords["lon"])
        frames.append(df)

    # Combine all countries into single DataFrame
    df_all = pd.concat(frames, ignore_index=True)
    logger.info(
        f"Total: {len(df_all):,} rows — "
        f"{df_all['country_code'].nunique()} countries, "
        f"dates {df_all['date'].min()} → {df_all['date'].max()}"
    )
    return df_all


def main() -> pd.DataFrame:
    """Extract and save weather data for all countries.

    Returns:
        DataFrame containing weather records for all 11 countries with columns:
        country_code, date, wind_speed_10m_mean, sunshine_duration,
        temperature_2m_mean, precipitation_sum, cloud_cover_mean.

    Side effects:
        Saves a CSV sample to ingestion/weather_sample.csv for inspection.
        Prints data preview and column descriptions to stdout.

    Example:
        >>> df = main()
        Total: 12,045 rows — 11 countries, dates 2023-01-01 → 2025-12-31
        Saved raw sample to ingestion/weather_sample.csv
        >>> df.dtypes
        country_code              object
        date                      object
        wind_speed_10m_mean      float64
        sunshine_duration        float64
        temperature_2m_mean      float64
        precipitation_sum        float64
        cloud_cover_mean         float64
        dtype: object
    """
    # Initialize client with caching and retry logic
    client = get_client()

    # Fetch weather data for all countries
    df = fetch_all_countries(client)

    # Save locally for inspection before BigQuery load
    output_path = "ingestion/weather_sample.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Saved raw sample to {output_path}")

    # Print data preview and column information
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