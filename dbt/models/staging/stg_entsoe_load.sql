with source as (
    select * from {{ source('raw', 'entsoe_load')}}
),

renamed as (
    select
        -- Keys
        cast(country_code as string)            as country_code,
        cast(datetime_utc as timestamp)         as datetime_utc,

        -- Load
        cast(load_mwh as float64)               as load_mwh

    from source
    where country_code is not null
        and datetime_utc is not null
)

select * from renamed