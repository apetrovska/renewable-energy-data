# Seed Files

Static reference data maintained as part of the dbt project.

## country_reference.csv

Factual metadata about the 11 countries in scope. All fields are
objective facts from public sources (Eurostat, UN, official EU records).

Fields: country_code, country_name, capital_city, coordinates,
population, is_eu_member, brell_member_pre2025, eu_target_2030_pct.

Note: Norway (NO) has NULL for eu_target_2030_pct — not an EU member,
not subject to the EU 2030 renewable energy directive.

## country_group_membership.csv

Analytical grouping of countries into three dimensions. These are
deliberate analytical decisions made for this project, not official
classifications.

**core:** Six EU countries selected to represent the full spectrum of
the EU energy transition — from Austria (near-complete renewables) to
Poland (coal-dominant). Chosen to maximize analytical contrast within
a single comparable group.

**geopolitical:** Three countries where energy decisions are shaped by
factors outside standard EU climate policy. Norway (EEA, not EU, major
gas exporter), Slovakia (RF gas dependency, proximity to Hungarian
policy drift), Lithuania (initiated Baltic grid independence project).

**baltic:** Estonia, Latvia, and Lithuania — isolated as a group to
analyze the February 2025 BRELL grid exit as a measurable before/after
event. Lithuania appears in both geopolitical and baltic groups because
it played both roles: initiator of the synchronization and participant
in the outcome.

Groups are not mutually exclusive by design. Lithuania's dual membership
reflects analytical reality, not a data error.
