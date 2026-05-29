{{
    config(materialized='table')
}}

with weather_gen as (
    select * from {{ ref('int_weather_generation') }}
),

correlations as (
    select
        country_code,
        season,
        EXTRACT(YEAR from date)                     as year,

        -- Wind correlation
        round(
            CORR(wind_speed_10m_max_kmh, wind_generation_mwh), 4
        )                                           as wind_generation_correlation,

        -- Solar correlation
        round(
            CORR(sunshine_duration_hrs, solar_generation_mwh), 4
        )                                           as solar_generation_correlation,

        count(*)                                    as observation_count

    from weather_gen
    group by country_code, season, year
),

daily_detail as (
    select
        country_code,
        date,
        season,
        EXTRACT(YEAR from date)                     as year,
        EXTRACT(MONTH from date)                    as month_num,

        wind_speed_10m_max_kmh,
        sunshine_duration_hrs,
        temperature_avg_c,
        precipitation_mm,
        cloud_cover_pct,

        wind_generation_mwh,
        solar_generation_mwh,
        renewable_mwh,
        total_generation_mwh,

        wind_generation_zscore,
        solar_generation_zscore,
        is_wind_anomaly,
        is_solar_anomaly

    from weather_gen
),

joined as (
    select
        d.*,
        c.wind_generation_correlation,
        c.solar_generation_correlation,
        c.observation_count

    from daily_detail d
    left join correlations c
        on d.country_code = c.country_code
        and d.season = c.season
        and d.year = c.year
)

select * from joined