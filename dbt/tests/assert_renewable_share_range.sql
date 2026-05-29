-- Severity: error
-- Renewable share must be between 0 and 100.
-- Values outside this range indicate a calculation error.

-- Identify invalid renewable share percentages (impossible values outside 0-100 range)
select
    country_code,
    year,
    renewable_share_pct

from {{ ref('int_country_profile') }}

-- Filter to rows with percentages outside valid range (indicates calculation or data issues)
where renewable_share_pct < 0
   or renewable_share_pct > 100