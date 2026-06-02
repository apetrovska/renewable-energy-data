{{
    config(materialized='table')
}}

with generation as (
    select * from {{ ref('int_generation_daily') }}
),

load_daily as (
    select
        country_code,
        DATE(datetime_utc)                          as date,
        sum(load_mwh)                               as load_mwh
    from {{ ref('stg_entsoe_load') }}
    group by country_code, date
),

country_ref as (
    select * from {{ ref('stg_country_reference') }}
),

aggregated as (
    select
        g.country_code,
        EXTRACT(YEAR from g.date)                     as year,

        -- Renewable share
        round(
            sum(case when g.energy_category = 'renewable'
                then g.generation_mwh else 0 end)
            / nullif(sum(g.generation_mwh), 0) * 100, 2
        )                                           as renewable_share_pct,

        -- Fossil dependency score
        round(
            sum(case when g.energy_category = 'fossil'
                then g.generation_mwh else 0 end)
            / nullif(sum(g.generation_mwh), 0) * 100, 2
        )                                           as fossil_dependency_score,

        sum(g.generation_mwh)                         as total_generation_mwh,
        sum(l.load_mwh)                               as total_load_mwh

    from generation g
    left join load_daily l
        on g.country_code = l.country_code
        and g.date = l.date
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