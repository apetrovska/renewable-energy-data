{{
    config(materialized='table')
}}

with daily as (
    select * from {{ ref('int_generation_daily') }}
),

weather_gen as (
    select * from {{ ref('int_weather_generation') }}
),

core_baseline as (
    select
        date,
        EXTRACT(YEAR from date)                     as year,
        season,

        avg(case when energy_category = 'renewable'
            then generation_mwh end)                as core_avg_renewable_mwh,

        round(
            sum(case when energy_category = 'renewable'
                then generation_mwh else 0 end)
            / nullif(sum(generation_mwh), 0) * 100, 2
        )                                           as core_avg_renewable_pct

    from daily
    where country_code in ('DE', 'FR', 'ES', 'PL', 'AT', 'HU')
    group by date, year, season
),

baltic as (
    select
        d.country_code,
        d.date,
        d.season,
        EXTRACT(YEAR from d.date)                   as year,

        -- BRELL exit marker
        case
            when d.date < '2025-02-01' then 'pre_brell'
            else 'post_brell'
        end                                         as brell_period,

        sum(case when d.energy_category = 'renewable'
            then d.generation_mwh else 0 end)       as renewable_mwh,

        sum(d.generation_mwh)                       as total_generation_mwh,

        round(
            sum(case when d.energy_category = 'renewable'
                then d.generation_mwh else 0 end)
            / nullif(sum(d.generation_mwh), 0) * 100, 2
        )                                           as renewable_share_pct,

        w.wind_speed_10m_max_kmh,
        w.sunshine_duration_hrs

    from daily d
    left join weather_gen w
        on d.country_code = w.country_code
        and d.date = w.date
    where d.country_code in ('EE', 'LV', 'LT')
    group by
        d.country_code, d.date, d.season,
        year, brell_period,
        w.wind_speed_10m_max_kmh, w.sunshine_duration_hrs
),

joined as (
    select
        b.*,
        c.core_avg_renewable_pct,
        round(
            b.renewable_share_pct - c.core_avg_renewable_pct, 2
        )                                           as delta_from_core_baseline

    from baltic b
    left join core_baseline c
        on b.date = c.date
)

select * from joined