-- Severity: error
-- Catches silent empty API responses - schema tests pass on empty tables.
-- Expects at least 200 rows per country per day (hourly data * production types).
-- Returns country+date combinations with insufficient row count.

-- Aggregate row counts by country and date to detect incomplete data loads
select
    country_code,
    date,
    count(*)                                        as row_count

from {{ ref('int_generation_daily') }}

group by country_code, date

-- Flag combinations with fewer than 4 rows (incomplete energy category coverage)
having count(*) < 4
-- Note: after aggregation to daily level by energy_category,
-- minimum expected groups are: renewable, fossil, nuclear, other = 4