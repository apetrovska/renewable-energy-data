-- Severity: error
-- Physically impossible - generation cannot be negative.
-- Returns rows that violate the assertion (test fails if any rows returned).

-- Identify any generation values below zero, indicating data errors or calculation bugs
select
    country_code,
    date,
    energy_category,
    generation_mwh

from {{ ref('int_generation_daily') }}

-- Filter to negative generation (physically impossible)
where generation_mwh < 0