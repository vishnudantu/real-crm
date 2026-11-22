import test from "node:test";
import assert from "node:assert/strict";
import {
  bulkCsvParse,
  groupUnitsByFloorTower,
  holdCountdown,
  isUuid,
  paiseToRupeesFormat,
  rupeesToPaise,
  statusLabel,
  statusVisual,
  UNASSIGNED_FLOOR,
  UNASSIGNED_TOWER,
} from "../../src/inventory/inventoryModel.ts";
import type { Unit } from "../../src/inventory/inventoryModel.ts";

function unit(overrides: Partial<Unit>): Unit {
  return {
    id: overrides.id ?? "00000000-0000-0000-0000-000000000000",
    project_id: "p1",
    internal_code: "A-101",
    configuration: "2 BHK",
    floor: "1",
    position: null,
    tower: "A",
    carpet_area_sqft: 1200,
    built_up_area_sqft: null,
    plot_number: null,
    facing: "East",
    views: null,
    saleable: true,
    status: "AVAILABLE",
    status_reason: null,
    rera_disclosure_json: {},
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

test("groupUnitsByFloorTower returns empty for no units", () => {
  assert.deepEqual(groupUnitsByFloorTower([]), []);
});

test("groupUnitsByFloorTower groups by tower then floor, floors descending numeric", () => {
  const units = [
    unit({ id: "1", tower: "B", floor: "2", internal_code: "B-201" }),
    unit({ id: "2", tower: "A", floor: "10", internal_code: "A-1001" }),
    unit({ id: "3", tower: "A", floor: "9", internal_code: "A-901" }),
    unit({ id: "4", tower: "A", floor: "10", internal_code: "A-1002" }),
  ];
  const groups = groupUnitsByFloorTower(units);
  assert.deepEqual(groups.map((g) => g.tower), ["A", "B"]);
  assert.deepEqual(groups[0].floors.map((f) => f.floor), ["10", "9"]);
  assert.deepEqual(
    groups[0].floors[0].units.map((u) => u.internal_code),
    ["A-1001", "A-1002"],
  );
});

test("groupUnitsByFloorTower buckets missing tower/floor into unassigned groups", () => {
  const groups = groupUnitsByFloorTower([
    unit({ id: "1", tower: null, floor: null, internal_code: "X-1" }),
  ]);
  assert.equal(groups[0].tower, UNASSIGNED_TOWER);
  assert.equal(groups[0].floors[0].floor, UNASSIGNED_FLOOR);
});

test("statusVisual falls back gracefully for unknown status", () => {
  const visual = statusVisual("TELEPORTED");
  assert.equal(visual.icon, "circle-alert");
  assert.equal(visual.tone, "stone");
  assert.equal(statusVisual("AVAILABLE").icon, "circle-check");
  assert.equal(statusVisual("ON_HOLD").tone, "amber");
});

test("statusLabel prettifies known and unknown statuses", () => {
  assert.equal(statusLabel("UNDER_DISPUTE"), "Under dispute");
  assert.equal(statusLabel("SOME_NEW_STATE"), "Some new state");
});

test("rupeesToPaise converts whole and decimal rupees", () => {
  assert.equal(rupeesToPaise("7500000"), 750000000);
  assert.equal(rupeesToPaise("75000.50"), 7500050);
  assert.equal(rupeesToPaise("1,25,000"), 12500000);
  assert.equal(rupeesToPaise("0"), 0);
});

test("rupeesToPaise rounds to integer paise (12.345 -> 1235)", () => {
  assert.equal(rupeesToPaise("12.345"), 1235);
  assert.equal(rupeesToPaise("0.001"), 0);
  assert.equal(rupeesToPaise("0.005"), 1);
});

test("rupeesToPaise rejects invalid input", () => {
  assert.ok(Number.isNaN(rupeesToPaise("")));
  assert.ok(Number.isNaN(rupeesToPaise("abc")));
  assert.ok(Number.isNaN(rupeesToPaise("-5")));
  assert.ok(Number.isNaN(rupeesToPaise("12.34.56")));
});

test("paiseToRupeesFormat renders Indian-grouped rupees", () => {
  assert.equal(paiseToRupeesFormat(750000000), "₹75,00,000.00");
  assert.equal(paiseToRupeesFormat(1235), "₹12.35");
  assert.equal(paiseToRupeesFormat(Number.NaN), "—");
});

test("bulkCsvParse returns empty for empty input", () => {
  assert.deepEqual(bulkCsvParse("", "p1"), { rows: [], errors: [] });
  assert.deepEqual(bulkCsvParse("   \n \n", "p1"), { rows: [], errors: [] });
});

test("bulkCsvParse parses the documented four-column header", () => {
  const { rows, errors } = bulkCsvParse(
    "code,configuration,facing,carpet_area\nA-101,2 BHK,East,1200\nA-102,3 BHK,West,\n",
    "p1",
  );
  assert.equal(errors.length, 0);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].internal_code, "A-101");
  assert.equal(rows[0].carpet_area_sqft, 1200);
  assert.equal(rows[0].project_id, "p1");
  assert.equal(rows[0].status, "AVAILABLE");
  assert.equal(rows[0].saleable, true);
  assert.equal(rows[1].carpet_area_sqft, null);
});

test("bulkCsvParse parses optional tower/floor columns and quoted fields", () => {
  const { rows, errors } = bulkCsvParse(
    'code,configuration,facing,carpet_area,tower,floor\n"A-101","3 BHK, corner",East,1450,A,10\n',
    "p1",
  );
  assert.equal(errors.length, 0);
  assert.equal(rows[0].configuration, "3 BHK, corner");
  assert.equal(rows[0].tower, "A");
  assert.equal(rows[0].floor, "10");
});

test("bulkCsvParse reports per-row errors and keeps valid rows", () => {
  const csv = [
    "code,configuration,facing,carpet_area",
    "A-101,2 BHK,East,1200",
    ",2 BHK,East,1200",
    "A-103,2 BHK,East,-5",
    "A-104,2 BHK,East,abc",
    "A-101,2 BHK,East,1300",
    'A-105,"unclosed,East,1200',
  ].join("\n");
  const { rows, errors } = bulkCsvParse(csv, "p1");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].internal_code, "A-101");
  assert.equal(errors.length, 5);
  assert.deepEqual(errors.map((e) => e.row), [3, 4, 5, 6, 7]);
  assert.match(errors[4].message, /unclosed/i);
});

test("bulkCsvParse requires a code header and validates status values", () => {
  const noCode = bulkCsvParse("configuration,facing\n2 BHK,East\n", "p1");
  assert.equal(noCode.rows.length, 0);
  assert.match(noCode.errors[0].message, /code column/i);

  const badStatus = bulkCsvParse("code,status\nA-101,SOLD\n", "p1");
  assert.equal(badStatus.rows.length, 0);
  assert.match(badStatus.errors[0].message, /DRAFT, APPROVED, or AVAILABLE/);
});

test("isUuid accepts canonical UUIDs and rejects near-misses", () => {
  assert.equal(isUuid("3fa85f64-5717-4562-b3fc-2c963f66afa6"), true);
  assert.equal(isUuid("3FA85F64-5717-4562-B3FC-2C963F66AFA6"), true);
  assert.equal(isUuid("00000000-0000-0000-0000-00000000000-"), false);
  assert.equal(isUuid("3fa85f6457174562b3fc2c963f66afa6"), false);
  assert.equal(isUuid("not-a-uuid"), false);
  assert.equal(isUuid(undefined), false);
});

test("holdCountdown formats hours, minutes, and expired states", () => {
  const expiry = "2026-01-02T00:00:00Z";
  const now = new Date("2026-01-01T00:00:00Z").getTime();
  assert.equal(holdCountdown(expiry, now), "24h 00m");
  assert.equal(holdCountdown(expiry, now + 23 * 3600 * 1000), "1h 00m");
  assert.equal(holdCountdown(expiry, now + 23 * 3600 * 1000 + 59 * 60 * 1000 + 5000), "0m 55s");
  assert.equal(holdCountdown(expiry, now + 24 * 3600 * 1000), "Expired");
  assert.equal(holdCountdown(expiry, now + 25 * 3600 * 1000), "Expired");
});
