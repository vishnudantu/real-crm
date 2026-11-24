import test from "node:test";
import assert from "node:assert/strict";
import {
  bestConfidence,
  categoryLabel,
  connectivityBand,
  distanceLabel,
  orderedCategories,
  sortDemand,
  sortReports,
} from "../../src/cityIntel/cityIntelModel.ts";
import type { LocalityDemand, LocalityReport } from "../../src/cityIntel/cityIntelModel.ts";

function demand(leadCount: number, locality: string): LocalityDemand {
  return {
    project_id: locality,
    locality,
    project_name: locality,
    lead_count: leadCount,
    booking_count: 0,
    conversion_pct: 0,
    median_budget_paise: null,
    top_price_band: "UNKNOWN",
    top_property_type: "UNKNOWN",
  };
}

function report(confidence: string, asOf: string): LocalityReport {
  return {
    id: `${confidence}-${asOf}`,
    project_id: "p1",
    title: "t",
    body: "b",
    sources: [{ label: "s", confidence }],
    status: "DRAFT",
    as_of: asOf,
    created_at: asOf,
  };
}

test("bestConfidence picks the strongest source confidence", () => {
  assert.equal(bestConfidence([{ label: "a", confidence: "estimated" }, { label: "b", confidence: "verified" }]), "verified");
  assert.equal(bestConfidence([{ label: "a", confidence: "unverified" }]), "unverified");
  assert.equal(bestConfidence([]), "unverified");
});

test("sortReports orders verified first, then newest as_of", () => {
  const sorted = sortReports([
    report("unverified", "2026-11-01"),
    report("verified", "2026-10-01"),
    report("verified", "2026-11-15"),
  ]);
  assert.equal(sorted[0].as_of, "2026-11-15");
  assert.equal(sorted[0].sources[0].confidence, "verified");
  assert.equal(sorted[2].sources[0].confidence, "unverified");
});

test("sortDemand orders by lead count desc then locality asc", () => {
  const sorted = sortDemand([demand(2, "B"), demand(5, "A"), demand(5, "C")]);
  assert.deepEqual(sorted.map((d) => d.locality), ["A", "C", "B"]);
});

test("connectivityBand maps score to advisory band", () => {
  assert.equal(connectivityBand(90), "Excellent");
  assert.equal(connectivityBand(65), "Good");
  assert.equal(connectivityBand(45), "Moderate");
  assert.equal(connectivityBand(10), "Limited");
  assert.equal(connectivityBand(0), "No data");
});

test("categoryLabel and orderedCategories present categories in fixed order", () => {
  assert.equal(categoryLabel("transit"), "Transit");
  assert.equal(categoryLabel("employment"), "Employment hubs");
  const ordered = orderedCategories([
    { category: "amenity", count: 1, nearest_km: null, nearest_travel_minutes: null },
    { category: "school", count: 2, nearest_km: 1, nearest_travel_minutes: 5 },
  ]);
  assert.deepEqual(ordered.map((c) => c.category), ["school", "amenity"]);
});

test("distanceLabel formats sub-km as metres", () => {
  assert.equal(distanceLabel(0.5), "500 m");
  assert.equal(distanceLabel(1.2), "1.2 km");
});
