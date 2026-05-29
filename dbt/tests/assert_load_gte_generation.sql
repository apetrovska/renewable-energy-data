-- Severity: warn
-- Generation significantly exceeding load may indicate data issues.
-- Net exporters (NO, AT, FR) regularly have generation > load - expected.
-- Flags extreme or unexpected divergences for manual review.
-- Threshold: generation > load * 1.5 (50% excess)

-- Detect cases where generation exceeds load by more than 50% for investigation
select
    country_code,
    date,
    energy_category,
    generation_mwh,
    load_mwh,
    -- Calculate ratio to show magnitude of excess generation
    round(generation_mwh / nullif(load_mwh, 0), 2)     as generation_to_load_ratio

from {{ ref('int_generation_daily') }}

-- Flag only extreme divergences: >50% excess generation with non-zero load
where generation_mwh > load_mwh * 1.5
  and load_mwh > 0