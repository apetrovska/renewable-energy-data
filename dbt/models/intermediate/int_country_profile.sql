{{
    config(materialized='table')
}}

with generation as (
    select * from {{ ref('int_generation_daily') }}
),

country_ref as (
    select * from {{ ref('stg_country_reference') }}
),

aggregated as (
    select
        country_code,
        EXTRACT(YEAR from date)                     as year,

        -- Renewable share
        round(
            sum(case when energy_category = 'renewable'
                then generation_mwh else 0 end)
            / nullif(sum(generation_mwh), 0) * 100, 2
        )                                           as renewable_share_pct,

        -- Fossil dependency score
        round(
            sum(case when energy_category = 'fossil'
                then generation_mwh else 0 end)
            / nullif(sum(generation_mwh), 0) * 100, 2
        )                                           as fossil_dependency_score,

        sum(generation_mwh)                         as total_generation_mwh,
        sum(load_mwh)                               as total_load_mwh

    from generation
    group by country_code, year
),

joined as (
    select
        a.country_code,
        a.year,
        a.renewable_share_pct,
        a.fossil_dependency_score,
        a.total_generation_mwh,
        a.total_load_mwh,

        r.country_name,
        r.capital_city,
        r.latitude,
        r.longitude,
        r.population,
        r.is_eu_member,
        r.brell_member_pre2025,
        r.eu_target_2030_pct

    from aggregated a
    left join country_ref r
        on a.country_code = r.country_code
)

select * from joined