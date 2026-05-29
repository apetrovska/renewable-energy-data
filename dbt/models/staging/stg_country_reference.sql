with source as (
    select * from {{ ref('country_reference') }}
),

renamed as (
    select
        -- Keys
        cast(country_code as string)            as country_code,
        cast(country_name as string)            as country_name,
        cast(capital_city as string)            as capital_city,

        -- Coordinates
        cast(latitude as float64)               as latitude,
        cast(longitude as float64)              as longitude,

        -- Metadata
        cast(population as int64)               as population,
        cast(is_eu_member as bool)              as is_eu_member,
        cast(brell_member_pre2025 as bool)      as brell_member_pre2025,

        -- 2030 target — NULL for Norway (not EU member)
        cast(eu_target_2030_pct as float64)     as eu_target_2030_pct

    from source
)

select * from renamed