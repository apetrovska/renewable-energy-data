with source as (
    select * from {{ source('raw', 'owid_energy') }}
),

renamed as (
    select
        -- Keys
        iso_code                                    as country_code_iso3,
        country                                     as country_name,
        cast(year as int64)                         as year,

        -- Renewable shares
        cast(renewables_share_elec as float64)      as renewable_share_pct,
        cast(low_carbon_share_elec as float64)      as low_carbon_share_pct,
        cast(solar_share_elec as float64)           as solar_share_pct,
        cast(wind_share_elec as float64)            as wind_share_pct,
        cast(hydro_share_elec as float64)           as hydro_share_pct,
        cast(nuclear_share_elec as float64)         as nuclear_share_pct,
        cast(fossil_share_elec as float64)          as fossil_share_pct,

        -- Generation volumes (TWh)
        cast(solar_electricity as float64)          as solar_generation_twh,
        cast(wind_electricity as float64)           as wind_generation_twh,

        -- Carbon intensity
        cast(carbon_intensity_elec as float64)      as co2_intensity_gco2_kwh

    from source
    where iso_code is not null
      and year is not null
)

select * from renamed