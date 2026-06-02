{{
    config(materialized='table')
}}

with profile as (
    select * from {{ ref('int_country_profile') }}
),

country_groups as (
    select * from {{ ref('country_group_membership') }}
),

joined as (
    select
        p.country_code,
        p.country_name,
        p.year,
        p.renewable_share_pct,
        p.fossil_dependency_score,
        p.total_generation_mwh,
        p.is_eu_member,
        p.eu_target_2030_pct,

        cg.group_name,
        cg.group_description

    from profile p
    inner join country_groups cg
        on p.country_code = cg.country_code
),

with_window_functions as (
    select
        *,

        -- Group average renewable share
        round(
            AVG(renewable_share_pct) OVER (
                PARTITION BY group_name, year
            ), 2
        )                                           as group_avg_renewable_pct,

        -- Delta from group average
        round(
            renewable_share_pct - AVG(renewable_share_pct) OVER (
                PARTITION BY group_name, year
            ), 2
        )                                           as delta_from_group_avg,

        -- Rank within group (best renewable share = rank 1)
        RANK() OVER (
            PARTITION BY group_name, year
            ORDER BY renewable_share_pct DESC
        )                                           as rank_within_group,

        -- Rank overall across all 11 countries
        RANK() OVER (
            PARTITION BY year
            ORDER BY renewable_share_pct DESC
        )                                           as rank_overall

    from joined
)

select * from with_window_functions