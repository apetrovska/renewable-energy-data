with source as (
    select * from {{ source('raw', 'weather_daily') }}
),

renamed as (
    select
        -- Keys
        cast(country_code as string)                as country_code,
        cast(date as date)                          as date,

        -- Wind - source field is max, not avg; documented in schema.yml
        cast(wind_speed_10m_max as float64)         as wind_speed_10m_max_kmh,

        -- Sunshine: source is seconds → convert to hours here
        round(
            cast(sunshine_duration as float64) / 3600, 2
        )                                           as sunshine_duration_hrs,

        -- Temperature
        cast(temperature_2m_mean as float64)        as temperature_avg_c,

        -- Precipitation
        cast(precipitation_sum as float64)          as precipitation_mm,

        -- Cloud cover
        cast(cloud_cover_mean as float64)           as cloud_cover_pct

    from source
    where country_code is not null
      and date is not null
)

select * from renamed