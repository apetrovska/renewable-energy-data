-- Severity: warn
-- No gaps in daily dates between MIN and MAX per country.
-- Returns country + missing date combinations.

-- Generate a complete date range (spine) from min to max date for each country
with date_spine as (
    select
        country_code,
        date_add(min_date, interval day_offset day)     as expected_date

    from (
        -- Calculate min/max dates and total day count per country
        select
            country_code,
            min(date)                                   as min_date,
            max(date)                                   as max_date,
            date_diff(max(date), min(date), day)        as total_days

        from {{ ref('int_generation_daily') }}
        group by country_code
    )
    -- Expand into one row per day using array generation
    cross join unnest(
        generate_array(0, total_days)
    ) as day_offset
),

-- Extract unique dates actually present in the data
actual_dates as (
    select distinct country_code, date
    from {{ ref('int_generation_daily') }}
)

-- Identify missing dates by anti-joining expected spine against actual dates
select
    d.country_code,
    d.expected_date                                     as missing_date

from date_spine d
left join actual_dates a
    on d.country_code = a.country_code
    and d.expected_date = a.date

where a.date is null