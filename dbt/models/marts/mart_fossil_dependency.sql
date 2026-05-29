{{
    config(materialized='table')
}}

with daily as (
    select * from {{ ref('int_generation_daily') }}
),

group_metrics as (
    select * from {{ ref('int_country_group_metrics') }}
),

monthly_fossil as (
    select
        country_code,
        DATE_TRUNC(date, MONTH)                     as month,
        EXTRACT(YEAR from date)                     as year,
        EXTRACT(MONTH from date)                    as month_num,
        season,

        sum(generation_mwh)                         as total_generation_mwh,

        sum(case when energy_category = 'fossil'
            then generation_mwh else 0 end)         as fossil_generation_mwh,

        round(
            sum(case when energy_category = 'fossil'
                then generation_mwh else 0 end)
            / nullif(sum(generation_mwh), 0) * 100, 2
        )                                           as fossil_dependency_score

    from daily
    group by country_code, month, year, month_num, season
),

with_group_context as (
    select
        m.*,
        g.group_name,
        g.group_avg_renewable_pct,
        g.delta_from_group_avg,
        g.rank_within_group,
        g.rank_overall

    from monthly_fossil m
    left join group_metrics g
        on m.country_code = g.country_code
        and m.year = g.year
)

select * from with_group_context