-- Severity: warn
-- Weather data should exist for every generation date per country.
-- Missing weather rows reduce correlation analysis quality.

-- Identify generation dates missing corresponding weather data
select
    g.country_code,
    g.date

from {{ ref('int_generation_daily') }} g
-- Left join to detect missing weather records (null in weather table)
left join {{ ref('stg_weather_daily') }} w
    on g.country_code = w.country_code
    and g.date = w.date

-- Return dates with no matching weather record (data quality issues for analysis)
where w.date is null
group by g.country_code, g.date