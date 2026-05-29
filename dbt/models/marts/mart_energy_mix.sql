{{
    config(materialized='table')
}}

with generation as (
    select * from {{ ref('int_generation_daily') }}
),

monthly as (
    select
        country_code,
        DATE_TRUNC(date, MONTH)                     as month,
        EXTRACT(YEAR from date)                     as year,
        EXTRACT(MONTH from date)                    as month_num,
        energy_category,
        season,

        sum(generation_mwh)                         as generation_mwh,
        sum(load_mwh)                               as load_mwh,

        -- Renewable share per country per month
        round(
            sum(case when energy_category = 'renewable'
                then generation_mwh else 0 end)
            / nullif(sum(generation_mwh), 0) * 100, 2
        )                                           as renewable_share_pct

    from generation
    group by country_code, month, year, month_num, energy_category, season
),

with_yoy as (
    select
        *,

        -- Year-over-year renewable growth
        round(
            (renewable_share_pct - LAG(renewable_share_pct) OVER (
                PARTITION BY country_code, month_num, energy_category
                ORDER BY year
            )) /
            nullif(LAG(renewable_share_pct) OVER (
                PARTITION BY country_code, month_num, energy_category
                ORDER BY year
            ), 0) * 100, 2
        )                                           as yoy_renewable_growth_pct

    from monthly
)

select * from with_yoy