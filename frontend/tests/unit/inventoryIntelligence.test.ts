import test from "node:test";
import assert from "node:assert/strict";
import {
  conflictLabel,
  hoursRemainingLabel,
  orderedStatuses,
  realizationPercent,
  sortByUrgency,
  sortUnsoldByRisk,
  statusLabel,
  statusTiles,
  towerAging,
} from "../../src/inventoryIntelligence/intelligenceModel.ts";
import type { RevenueRow } from "../../src/inventoryIntelligence/intelligenceModel.ts";

test("realizationPercent counts BOOKED+SOLD over total, zero-safe", () => {
  assert.equal(realizationPercent({ BOOKED: 2, SOLD: 1, AVAILABLE: 7 }, 10), 30);
  assert.equal(realizationPercent({}, 0), 0);
  assert.equal(realizationPercent({ AVAILABLE: 5 }, 5), 0);
});

test("orderedStatuses puts actionable states first, unknown last", () => {
  const order = orderedStatuses({ SOLD: 1, AVAILABLE: 2, CUSTOM: 1, ON_HOLD: 3 });
  assert.deepEqual(order, ["AVAILABLE", "ON_HOLD", "SOLD", "CUSTOM"]);
});

test("statusLabel and statusTiles map codes to labels", () => {
  assert.equal(statusLabel("ON_HOLD"), "On hold");
  assert.equal(statusLabel("UNDER_DISPUTE"), "Under dispute");
  const tiles = statusTiles({ AVAILABLE: 2, SOLD: 1 });
  assert.deepEqual(tiles.map((t) => t.status), ["AVAILABLE", "SOLD"]);
  assert.equal(tiles[0].count, 2);
  assert.equal(tiles[0].label, "Available");
});

function row(code: string, booked: number | null, age: number): RevenueRow {
  return { unit_id: code, internal_code: code, status: "AVAILABLE", booked_value_paise: booked, age_days: age };
}

test("towerAging groups by tower prefix with booked sum and oldest age", () => {
  const aging = towerAging([
    row("A-101", 100, 50),
    row("A-102", 200, 80),
    row("B-201", null, 30),
  ]);
  const a = aging.find((t) => t.tower === "A");
  const b = aging.find((t) => t.tower === "B");
  assert.equal(a?.units, 2);
  assert.equal(a?.bookedValuePaise, 300);
  assert.equal(a?.oldestAgeDays, 80);
  assert.equal(b?.bookedValuePaise, 0);
  assert.equal(b?.oldestAgeDays, 30);
});

test("sortByUrgency orders HIGH then MEDIUM then LOW, soonest first", () => {
  const sorted = sortByUrgency([
    { risk: "LOW", hours_remaining: 100 },
    { risk: "HIGH", hours_remaining: 2 },
    { risk: "MEDIUM", hours_remaining: 12 },
    { risk: "HIGH", hours_remaining: 0.5 },
  ]);
  assert.deepEqual(sorted.map((i) => i.risk), ["HIGH", "HIGH", "MEDIUM", "LOW"]);
  assert.equal(sorted[0].hours_remaining, 0.5);
});

test("sortUnsoldByRisk orders by risk then most days on market", () => {
  const sorted = sortUnsoldByRisk([
    { risk: "LOW", days_available: 10 },
    { risk: "HIGH", days_available: 200 },
    { risk: "HIGH", days_available: 150 },
  ]);
  assert.deepEqual(sorted.map((i) => i.days_available), [200, 150, 10]);
});

test("conflictLabel humanizes known kinds and falls back", () => {
  assert.equal(conflictLabel("MULTIPLE_ACTIVE_HOLDS"), "Multiple active holds");
  assert.equal(conflictLabel("SOLD_WITH_ACTIVE_HOLD"), "Sold with active hold");
  assert.equal(conflictLabel("BOOKED_WITH_ACTIVE_HOLD"), "Booked with active hold");
  assert.equal(conflictLabel("HOLD_WITHOUT_UNIT"), "Hold without unit");
});

test("hoursRemainingLabel formats expiry windows", () => {
  assert.equal(hoursRemainingLabel(0), "Expired");
  assert.equal(hoursRemainingLabel(-3), "Expired");
  assert.equal(hoursRemainingLabel(0.5), "30m left");
  assert.equal(hoursRemainingLabel(5), "5h left");
  assert.equal(hoursRemainingLabel(72), "3d left");
});
