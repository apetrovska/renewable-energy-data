{{
    config(materialized='table')
}}

with daily as (
    select * from {{ ref('int_generation_daily') }}
),

owid as (
    select * from {{ ref('stg_owid_energy') }}
),

yearly_generation as (
    select
        country_code,
        EXTRACT(YEAR from date)                     as year,
        energy_category,

        sum(generation_mwh)                         as generation_mwh,
        sum(load_mwh)                               as load_mwh,

        -- Renewable share from generation data
        round(
            sum(case when energy_category = 'renewable'
                then generation_mwh else 0 end)
            / nullif(sum(generation_mwh), 0) * 100, 2
        )                                           as renewable_share_pct

    from daily
    group by country_code, year, energy_category
),

joined as (
    select
        g.country_code,
        g.year,
        g.energy_category,
        g.generation_mwh,
        g.load_mwh,
        g.renewable_share_pct,

        -- From OWID - capacity context
        o.solar_generation_twh,
        o.wind_generation_twh,
        o.co2_intensity_gco2_kwh,
        o.fossil_share_pct                          as owid_fossil_share_pct

    from yearly_generation g
    left join owid o
        on g.country_code = o.country_code_iso3  -- ISO2 vs ISO3 - resolved in intermediate
        and g.year = o.year
)

select * from joined