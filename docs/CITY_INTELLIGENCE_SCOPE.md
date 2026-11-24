# Module 22 — City Intelligence Engine: Scope & Phasing

**Status:** SCOPING (no build started). This document defines what Module 22 can
responsibly ship, on what data, in what order. It follows the PROPFLOW 2046
catalogue section "22. City Intelligence Engine" and the anti-placeholder rule
in `docs/CAPABILITY_MAP.md`: nothing is marked done until it has endpoints +
real data + tests.

## The 8 sub-features (from the spec)

| # | Sub-feature | Data it needs | Feasible on existing data? |
|---|-------------|---------------|----------------------------|
| 1 | Future Infrastructure Map | Verified infrastructure proposals with geolocation + status | ❌ needs external/curated feed |
| 2 | Location Intelligence (travel, schools, hospitals, employment, amenities) | Points of interest + distances per project | ⚠️ partial — manual/curated POI table |
| 3 | Infrastructure Timeline (proposed → approved → under-construction → completed) | Dated infrastructure records with lifecycle status | ⚠️ partial — manual/curated records |
| 4 | Neighborhood Development Tracker | Documented nearby developments + expected effects | ⚠️ partial — manual/curated records |
| 5 | Catchment Demand Intelligence (demand by locality, price, property type) | Leads/bookings aggregated by locality | ✅ buildable now |
| 6 | City Growth Scenario Simulator | Hypothetical infra changes → demand/market model | ⚠️ heuristic on #5 + #3 |
| 7 | Location Risk Intelligence (flood, environmental, planning, accessibility) | Hazard/environmental datasets | ❌ needs external/curated feed |
| 8 | Source-Verified Locality Reports | Authored research with dates, evidence, stated uncertainty | ✅ buildable now (authored + cited) |

**Legend:** ✅ buildable on existing schema/data · ⚠️ needs a small curated
data table (no external API required) · ❌ needs an external data source or a
curated import that does not exist yet.

## Existing data I can build on

- `Project.location` (free text) + `Project.latitude` / `Project.longitude`
  (added for solar). Every project has a site; many have coordinates.
- `Lead` (locality via project, `source`, `status`, `budget_min/max`,
  `preferred_configuration`, `created_at`) — the raw signal for catchment demand.
- `SaleBooking` (consideration_paise, booked_on) — realized demand per project.
- `TowerOrientation`, `PropertyUnit` (facing, configuration, area) — property-type
  breakdowns for demand analysis.

No GIS, hazard, or infrastructure-proposal dataset exists in the codebase today.
Sub-features 1 and 7 therefore **cannot be honestly built** without a curated
import or an external provider, and are explicitly out of the first phase.

## Recommended phasing

### Phase 1 — Demand & locality intelligence (buildable now, no external feeds)
Build a new module `city_intel` with deterministic, tenant-scoped analytics:

1. **Catchment Demand Intelligence (#5).** Aggregate leads + bookings by
   locality (project), price band (from budget_min/max and consideration), and
   property type (from preferred_configuration / unit.configuration). Output:
   per-locality demand counts, conversion rate (leads→bookings), median budget
   band, and dominant property type. Pure aggregation + explainable thresholds.
2. **Source-Verified Locality Reports (#8).** An authored-report model:
   `locality_reports` (id, tenant_id, project_id FK, title, body, sources JSON
   `[{label, url_or_ref, observed_on, confidence}]`, status DRAFT/APPROVED
   reusing the existing fact-approval pattern). Reports carry explicit
   `confidence` per source (`verified` / `estimated` / `unverified`) and an
   `as_of` date so uncertainty is stated, never faked. These feed the grounded
   AI assistant as DRAFT-then-approved ProjectFacts, exactly like solar facts.
3. **Location Intelligence — curated POI (#2, curated).** A small curated
   `project_amenities` table (project_id, category[school/hospital/transit/
   employment/amenity], name, distance_km, travel_minutes, source_ref). No
   geocoding API — the data is authored by an admin and clearly marked as
   curated. A read endpoint returns the POI set for a project; a service
   computes a simple "connectivity score" from counts per category.

Phase 1 ships: 3 endpoints groups + a curated-data admin write path, DRAFT fact
generation, and a City Intelligence dashboard tab. It needs **no external API**
and every number is traceable to existing rows or curated, cited input.

### Phase 2 — Infrastructure timeline & scenario (needs curated records)
4. **Infrastructure Timeline (#3) + Neighborhood Development Tracker (#4).**
   A curated `infrastructure_projects` table (locality/project link, name,
   category, status[proposed/approved/under_construction/completed], announced_on,
   expected_on, source_ref, notes). Read endpoints expose the timeline per
   locality; the tracker surfaces expected effects as authored notes.
5. **City Growth Scenario Simulator (#6).** A deterministic heuristic: given a
   hypothetical new infrastructure record (status + category), estimate a
   demand-lift band on the Phase-1 catchment metrics using documented, capped
   coefficients per category (e.g. "new metro → +X%..+Y% demand, advisory").
   Clearly advisory/approximate, like the solar pricing hint.

### Phase 3 — External feeds (requires a real provider or curated import)
6. **Future Infrastructure Map (#1).** Only with a verified proposal feed.
7. **Location Risk Intelligence (#7).** Only with flood/environmental data
   (e.g. a government hazard dataset or a licensed provider). The solar module's
   pluggable-provider pattern is the integration seam.

## What this phase deliberately does NOT do
- No geocoding, GIS tiles, or map rendering without a real provider.
- No flood/environmental "risk scores" invented from thin air.
- No auto-generated locality "facts" without a source and a confidence level.
- Phase 1 will not call itself a "Future Infrastructure Map" or "Location Risk
  Intelligence" — those are Phase 3 and require data we do not have.

## Open questions for the founder (affects phasing, not blocking Phase 1)
- Is there a preferred infrastructure/hazard data provider for Phase 3, or do we
  start with admin-curated imports? (Default: curated imports, pluggable later.)
- Should locality reports be auto-drafted into the AI fact sheet by default, or
  only on explicit admin action? (Default: on action, DRAFT status.)

## Effort shape (matches the proven pattern)
- Phase 1: 1 module + models + service + router + DRAFT facts + dashboard tab.
  Parallel agents for the pure analytics cores (demand aggregation, connectivity
  score) + orchestrated integration, exactly like Module 20. ~50–70 tests.
- Phase 2: curated infra table + timeline read + scenario heuristic.
- Phase 3: provider integration behind the solar-style provider protocol.
