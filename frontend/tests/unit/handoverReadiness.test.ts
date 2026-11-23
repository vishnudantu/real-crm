import assert from "node:assert/strict";
import test from "node:test";
import { canManageHandover, moneyDisplay, nextSnagAction, readinessDisplay } from "../../src/handover/model.ts";
import type { HandoverChecklist } from "../../src/handover/model.ts";
import { buildAdminMobileNav, buildAdminNav } from "../../src/admin/adminNavigation.ts";

const ready: HandoverChecklist = {
  case_id: "case-1", score: 100, required_count: 5, met_count: 5,
  conditions: [], blockers: [], snag_count: 0, unresolved_snag_count: 0,
  financials: { planned_paise: 100000, collected_paise: 100000, outstanding_paise: 0, live_receipt_count: 1 },
  checked_at: "2026-11-23T12:00:00Z",
};

test("readiness is ready only when score and blockers agree", () => {
  assert.deepEqual(readinessDisplay(ready), { score: 100, summary: "All conditions met · ready for possession", tone: "ready" });
  assert.equal(readinessDisplay({ ...ready, blockers: [{ code: "SNAGS", label: "Snags", detail: "One open", met: false }] }).tone, "blocked");
  assert.equal(readinessDisplay({ ...ready, score: 80, met_count: 4, blockers: [{ code: "FINANCIALS", label: "Money", detail: "Outstanding", met: false }] }).summary, "4/5 conditions met · 1 blocker");
});

test("readiness display handles missing data and clamps unsafe scores", () => {
  assert.equal(readinessDisplay(null).summary, "Checklist not loaded");
  assert.equal(readinessDisplay({ ...ready, score: 120 }).score, 100);
  assert.equal(readinessDisplay({ ...ready, score: -20 }).score, 0);
});

test("snag verification is never offered to the fixer", () => {
  assert.deepEqual(nextSnagAction("OPEN", "staff-1", null), { action: "fix", label: "Mark fixed" });
  assert.equal(nextSnagAction("FIXED", "staff-1", "staff-1"), null);
  assert.deepEqual(nextSnagAction("FIXED", "staff-2", "staff-1"), { action: "verify", label: "Verify repair" });
  assert.deepEqual(nextSnagAction("VERIFIED", "staff-1", "staff-1"), { action: "close", label: "Close snag" });
  assert.equal(nextSnagAction("CLOSED", "staff-2", "staff-1"), null);
});

test("only administrator and manager may manage handover", () => {
  assert.equal(canManageHandover("ADMIN"), true);
  assert.equal(canManageHandover("MANAGER"), true);
  assert.equal(canManageHandover("SALES_EXECUTIVE"), false);
  assert.equal(canManageHandover("BUYER"), false);
  assert.equal(canManageHandover(undefined), false);
});

test("money is shown in rupees without hiding a missing ledger", () => {
  assert.equal(moneyDisplay(0), "₹0.00");
  assert.equal(moneyDisplay(123456), "₹1,234.56");
  assert.equal(moneyDisplay(null), "No linked ledger");
});

test("manager staff session only sees the handover workspace", () => {
  const navigation = buildAdminNav({}, "MANAGER", true);
  assert.deepEqual(navigation.flatMap((group) => group.items).map((item) => item.to), ["/admin/handover"]);
  assert.deepEqual(buildAdminMobileNav({}, "MANAGER", true).map((item) => item.to), ["/admin/handover"]);
  assert.equal(buildAdminNav({}, "SALES_EXECUTIVE").flatMap((group) => group.items).some((item) => item.to === "/admin/handover"), false);
});
