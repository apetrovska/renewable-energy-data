{{
    config(materialized='table')
}}

with profile as (
    select * from {{ ref('int_country_profile') }}
),

owid as (
    select * from {{ ref('stg_owid_energy') }}
),

daily as (
    select * from {{ ref('int_generation_daily') }}
),

-- -- Renewable share per day
daily_renewable as (
    select
        country_code,
        date,
        EXTRACT(YEAR from date)                     as year,
        round(
            sum(case when energy_category = 'renewable'
                then generation_mwh else 0 end)
            / nullif(sum(generation_mwh), 0) * 100, 2
        )                                           as daily_renewable_pct

    from daily
    group by country_code, date
),

-- Count days where renewable share > 80%
independence_days as (
    select
        country_code,
        year,
        countif(daily_renewable_pct > 80)           as renewable_independence_days

    from daily_renewable
    group by country_code, year
),

joined as (
    select
        p.country_code,
        p.country_name,
        p.year,
        p.renewable_share_pct,
        p.fossil_dependency_score,
        p.total_generation_mwh,
        p.total_load_mwh,
        p.is_eu_member,
        p.eu_target_2030_pct,
        p.latitude,
        p.longitude,

        i.renewable_independence_days,

        -- Progress toward 2030 target
        round(
            p.renewable_share_pct
            / nullif(p.eu_target_2030_pct, 0) * 100, 2
        )                                           as pct_progress_toward_2030_target,

        -- Gap to 2030 target
        round(
            p.eu_target_2030_pct - p.renewable_share_pct, 2
        )                                           as gap_to_2030_target_pct,

        -- CO2 avoided (baseline = EU avg intensity ~300 gCO2/kWh)
        round(
            (300 - o.co2_intensity_gco2_kwh)
            * p.total_generation_mwh / 1000000, 2
        )                                           as co2_avoided_tonnes

    from profile p
    left join independence_days i
        on p.country_code = i.country_code
        and p.year = i.year
    left join owid o
        on p.country_code = o.country_code_iso3
        and p.year = o.year
)

select * from joined