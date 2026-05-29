{{
    config(materialized='table')
}}

with profile as (
    select * from {{ ref('int_country_profile') }}
),

group_metrics as (
    select * from {{ ref('int_country_group_metrics') }}
),

independence as (
    select * from {{ ref('mart_country_independence') }}
),

resilience as (
    select
        p.country_code,
        p.country_name,
        p.year,
        p.renewable_share_pct,
        p.fossil_dependency_score,
        p.is_eu_member,
        p.eu_target_2030_pct,

        i.renewable_independence_days,
        i.pct_progress_toward_2030_target,
        i.gap_to_2030_target_pct,
        i.co2_avoided_tonnes,

        g.group_name,
        g.group_avg_renewable_pct,
        g.delta_from_group_avg,
        g.rank_within_group,
        g.rank_overall,

        -- Composite resilience score (0-100)
        -- Weighted: renewable share 50%, low fossil 30%, 2030 progress 20%
        round(
            (p.renewable_share_pct * 0.5)
            + ((100 - p.fossil_dependency_score) * 0.3)
            + (nullif(i.pct_progress_toward_2030_target, 0) * 0.2),
        2)                                          as resilience_score

    from profile p
    left join independence i
        on p.country_code = i.country_code
        and p.year = i.year
    left join group_metrics g
        on p.country_code = g.country_code
        and p.year = g.year
)

select * from resilience