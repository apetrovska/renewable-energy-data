{{
    config(
        materialized='incremental',
        unique_key=['country_code', 'date', 'energy_category'],
        partition_by={'field': 'date', 'data_type': 'date'}
    )
}}

with source as (
    select * from {{ source('raw', 'entsoe_generation') }}

    {% if is_incremental() %}
        where DATE(datetime_utc) >= DATE_SUB(
            (select MAX(date) from {{ this }}),
            INTERVAL 3 DAY
        )
    {% endif %}
),

classified as (
    select
        country_code,
        DATE(datetime_utc)                          as date,
        datetime_utc,

        -- Energy category classification
        case
            when production_type in (
                'Wind Onshore', 'Wind Offshore',
                'Solar', 'Hydro Run-of-river and poundage',
                'Hydro Water Reservoir', 'Geothermal',
                'Marine', 'Other renewable'
            ) then 'renewable'
            when production_type in (
                'Fossil Gas', 'Fossil Hard coal', 'Fossil Brown coal/Lignite',
                'Fossil Oil', 'Fossil Coal-derived gas', 'Fossil Peat'
            ) then 'fossil'
            when production_type in ('Nuclear') then 'nuclear'
            else 'other'
        end                                         as energy_category,

        production_type,
        generation_mwh,
        load_mwh,

        -- Season - computed once here, reused downstream
        case
            when EXTRACT(MONTH from DATE(datetime_utc)) in (12, 1, 2)  then 'winter'
            when EXTRACT(MONTH from DATE(datetime_utc)) in (3, 4, 5)   then 'spring'
            when EXTRACT(MONTH from DATE(datetime_utc)) in (6, 7, 8)   then 'summer'
            when EXTRACT(MONTH from DATE(datetime_utc)) in (9, 10, 11) then 'autumn'
        end                                         as season

    from source

    {% if var('is_dev') %}
        where DATE(datetime_utc) >= DATE_SUB(CURRENT_DATE(), INTERVAL {{ var('dev_days') }} DAY)
    {% endif %}
),

aggregated as (
    select
        country_code,
        date,
        energy_category,
        season,
        sum(generation_mwh)                         as generation_mwh,
        avg(load_mwh)                               as load_mwh

    from classified
    group by country_code, date, energy_category, season
)

select * from aggregated