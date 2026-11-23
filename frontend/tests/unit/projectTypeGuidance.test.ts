import test from "node:test";
import assert from "node:assert/strict";
import {
  bulkCsvParse,
  plotNumberColumnRequired,
  splitUnitValidationMessage,
  unitAuthoringGuidance,
} from "../../src/inventory/inventoryModel.ts";
import {
  PROJECT_TYPE_LABELS,
  PROJECT_TYPES,
  projectTypeLabel,
} from "../../src/admin/projectModel.ts";

test("apartment guidance requires tower+floor and forbids plot number", () => {
  const g = unitAuthoringGuidance("APARTMENT");
  assert.equal(g.requiresTower, true);
  assert.equal(g.requiresFloor, true);
  assert.equal(g.requiresPlotNumber, false);
  assert.equal(g.disallowsPlotNumber, true);
  assert.equal(g.disallowsTower, false);
  assert.match(g.summary, /tower and floor/);
});

test("commercial guidance requires tower+floor but tolerates plot number", () => {
  const g = unitAuthoringGuidance("COMMERCIAL");
  assert.equal(g.requiresTower, true);
  assert.equal(g.requiresFloor, true);
  assert.equal(g.disallowsPlotNumber, false);
});

test("villa and plot guidance requires plot_number and forbids tower", () => {
  for (const type of ["VILLA", "PLOT"] as const) {
    const g = unitAuthoringGuidance(type);
    assert.equal(g.requiresPlotNumber, true, type);
    assert.equal(g.disallowsTower, true, type);
    assert.equal(g.requiresTower, false, type);
    assert.equal(g.requiresFloor, false, type);
    assert.match(g.floorHint ?? "", /G/);
    assert.match(g.summary, /plot number/);
  }
});

test("mixed and untyped projects carry no restrictions", () => {
  for (const type of ["MIXED", null, undefined] as const) {
    const g = unitAuthoringGuidance(type);
    assert.equal(g.requiresTower, false);
    assert.equal(g.requiresFloor, false);
    assert.equal(g.requiresPlotNumber, false);
    assert.equal(g.disallowsTower, false);
    assert.equal(g.disallowsPlotNumber, false);
    assert.equal(g.floorHint, null);
  }
});

test("plotNumberColumnRequired mirrors the villa/plot rule", () => {
  assert.equal(plotNumberColumnRequired("VILLA"), true);
  assert.equal(plotNumberColumnRequired("PLOT"), true);
  assert.equal(plotNumberColumnRequired("APARTMENT"), false);
  assert.equal(plotNumberColumnRequired("COMMERCIAL"), false);
  assert.equal(plotNumberColumnRequired("MIXED"), false);
  assert.equal(plotNumberColumnRequired(null), false);
});

test("splitUnitValidationMessage splits joined server sentences without losing text", () => {
  const joined = "Tower is required for apartment units. Floor is required for apartment units.";
  assert.deepEqual(splitUnitValidationMessage(joined), [
    "Tower is required for apartment units.",
    "Floor is required for apartment units.",
  ]);
  assert.deepEqual(splitUnitValidationMessage("Single message."), ["Single message."]);
});

test("projectTypeLabel handles known types, null and unknown strings", () => {
  assert.equal(projectTypeLabel("APARTMENT"), "Apartment");
  assert.equal(projectTypeLabel("VILLA"), "Villa");
  assert.equal(projectTypeLabel("MIXED"), "Mixed development");
  assert.equal(projectTypeLabel(null), "Unspecified");
  assert.equal(projectTypeLabel(undefined), "Unspecified");
  assert.equal(projectTypeLabel("UNKNOWN_TYPE"), "UNKNOWN TYPE");
  for (const type of PROJECT_TYPES) {
    assert.ok(PROJECT_TYPE_LABELS[type].length > 0);
  }
});

test("bulkCsvParse keeps plot_number when supplied", () => {
  const csv = "code,tower,floor,plot_number\nA-101,A,12,\nV-1,,,PLOT-9\n";
  const result = bulkCsvParse(csv, "project-1");
  assert.deepEqual(result.errors, []);
  assert.equal(result.rows.length, 2);
  assert.equal(result.rows[0]?.plot_number, null);
  assert.equal(result.rows[1]?.plot_number, "PLOT-9");
});

test("bulkCsvParse accepts plot and plot_no aliases and trims whitespace", () => {
  const csv = "code,plot\nV-1,  PLOT-7  \n";
  const result = bulkCsvParse(csv, "project-1");
  assert.deepEqual(result.errors, []);
  assert.equal(result.rows[0]?.plot_number, "PLOT-7");

  const csv2 = "code,plot_no\nV-2,22-A\n";
  const result2 = bulkCsvParse(csv2, "project-1");
  assert.equal(result2.rows[0]?.plot_number, "22-A");
});
