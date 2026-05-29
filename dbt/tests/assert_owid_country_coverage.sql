-- Severity: error
-- All 11 countries must be present in OWID per year.
-- Missing country-year combinations indicate data gaps.

-- Collect country-year combinations that actually exist in the data
with expected as (
    select country_code_iso3, year
    from {{ ref('stg_owid_energy') }}
),

-- Define the 11 required countries for this analysis
required_countries as (
    select code from unnest([
        'DEU', 'FRA', 'ESP', 'POL', 'AUT', 'HUN',
        'NOR', 'SVK', 'LTU', 'EST', 'LVA'
    ]) as code
),

-- Extract distinct years available in OWID data
years as (
    select distinct year from {{ ref('stg_owid_energy') }}
),

-- Create cartesian product of all required countries × all available years
all_combinations as (
    select r.code as country_code_iso3, y.year
    from required_countries r
    cross join years y
)

-- Find missing country-year combinations (in expected combinations but not in actual data)
select
    a.country_code_iso3,
    a.year

from all_combinations a
left join expected e
    on a.country_code_iso3 = e.country_code_iso3
    and a.year = e.year

where e.country_code_iso3 is null