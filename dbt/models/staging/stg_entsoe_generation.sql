with source as (
    select * from  {{ source ('raw', 'entsoe_generation')}}
),

renamed as (
    select
        -- Keys
       cast(country_code as string)         as country_code,
       cast(datetime_utc as timestamp)      as datetime_utc,
       cast(production_type as string)      as production_type,

       -- Generation
       cast(generation_mwh as float64)      as generation_mwh

       from source
       where country_code is not null
        and datetime_utc is not null
        and production_type is not null
)

select * from renamed