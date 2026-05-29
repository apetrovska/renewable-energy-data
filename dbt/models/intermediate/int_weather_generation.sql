{{
    config(
        materialized='incremental',
        unique_key=['country_code', 'date'],
        partition_by={'field': 'date', 'data_type': 'date'}
    )
}}

with generation as (
    select * from {{ ref('int_generation_daily') }}

    {% if is_incremental() %}
        where date >= DATE_SUB(
            (select MAX(date) from {{ this }}),
            INTERVAL 3 DAY
        )
    {% endif %}
),

weather as (
    select * from {{ ref('stg_weather_daily') }}
),

daily_generation as (
    select
        country_code,
        date,
        season,
        sum(case when energy_category = 'renewable'
            then generation_mwh else 0 end)         as renewable_mwh,
        sum(case when production_type in ('Wind Onshore', 'Wind Offshore')
            then generation_mwh else 0 end)         as wind_generation_mwh,
        sum(case when production_type = 'Solar'
            then generation_mwh else 0 end)         as solar_generation_mwh,
        sum(generation_mwh)                         as total_generation_mwh

    from generation
    group by country_code, date, season
),

joined as (
    select
        g.country_code,
        g.date,
        g.season,
        g.renewable_mwh,
        g.wind_generation_mwh,
        g.solar_generation_mwh,
        g.total_generation_mwh,

        w.wind_speed_10m_max_kmh,
        w.sunshine_duration_hrs,
        w.temperature_avg_c,
        w.precipitation_mm,
        w.cloud_cover_pct

    from daily_generation g
    left join weather w
        on g.country_code = w.country_code
        and g.date = w.date
),

with_zscores as (
    select
        *,

        -- Wind z-score: 90-day rolling window
        round(
            (wind_generation_mwh - AVG(wind_generation_mwh) OVER (
                PARTITION BY country_code
                ORDER BY date
                ROWS BETWEEN 89 PRECEDING AND CURRENT ROW
            )) /
            NULLIF(STDDEV(wind_generation_mwh) OVER (
                PARTITION BY country_code
                ORDER BY date
                ROWS BETWEEN 89 PRECEDING AND CURRENT ROW
            ), 0),
        2)                                          as wind_generation_zscore,

        -- Solar z-score: 90-day rolling window
        round(
            (solar_generation_mwh - AVG(solar_generation_mwh) OVER (
                PARTITION BY country_code
                ORDER BY date
                ROWS BETWEEN 89 PRECEDING AND CURRENT ROW
            )) /
            NULLIF(STDDEV(solar_generation_mwh) OVER (
                PARTITION BY country_code
                ORDER BY date
                ROWS BETWEEN 89 PRECEDING AND CURRENT ROW
            ), 0),
        2)                                          as solar_generation_zscore

    from joined
),

with_anomalies as (
    select
        *,
        ABS(wind_generation_zscore) > 2.5           as is_wind_anomaly,
        ABS(solar_generation_zscore) > 2.5          as is_solar_anomaly

    from with_zscores
)

select * from with_anomalies