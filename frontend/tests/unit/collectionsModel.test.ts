import test from "node:test";
import assert from "node:assert/strict";
import {
  currentMonth,
  flattenCalendar,
  monthLabel,
  orderedAgingBuckets,
  orderedSeverityGroups,
  overdueRows,
  severityRank,
  shiftMonth,
  sortEscalationRows,
} from "../../src/collections/collectionsModel.ts";
import type { CalendarDay, CalendarRow, EscalationRow } from "../../src/collections/collectionsModel.ts";

function calRow(overdue: number, outstanding = 1000): CalendarRow {
  return {
    installment_id: `i-${overdue}`,
    booking_id: "b1",
    plan_id: "p1",
    project_id: "pr1",
    customer_name: "Test",
    unit_number: "A-101",
    milestone: "Slab",
    due_on: "2026-11-01",
    amount_paise: outstanding + 100,
    paid_paise: 100,
    outstanding_paise: outstanding,
    status: "OVERDUE",
    days_overdue: overdue,
    demand_letter_status: "NONE",
    demand_letter_sent_at: null,
    last_reminder_at: null,
    has_overdue_promise: false,
  };
}

function escRow(daysOverdue: number, outstanding: number): EscalationRow {
  return {
    booking_id: `b-${daysOverdue}`,
    project_id: "pr1",
    customer_name: "X",
    unit_number: "A-1",
    severity: "HIGH",
    oldest_due_on: "2026-01-01",
    days_overdue: daysOverdue,
    outstanding_paise: outstanding,
    overdue_installments: 2,
    last_actions: {},
    suggested_action: "Call",
  };
}

test("severityRank orders CRITICAL first, unknown last", () => {
  assert.ok(severityRank("CRITICAL") < severityRank("HIGH"));
  assert.ok(severityRank("HIGH") < severityRank("MEDIUM"));
  assert.equal(severityRank("whatever"), 4);
});

test("orderedSeverityGroups sorts groups by severity", () => {
  const groups = orderedSeverityGroups({ LOW: [escRow(5, 100)], CRITICAL: [escRow(90, 999)] });
  assert.deepEqual(groups.map((g) => g.severity), ["CRITICAL", "LOW"]);
});

test("sortEscalationRows orders by days overdue then outstanding", () => {
  const sorted = sortEscalationRows([escRow(5, 100), escRow(40, 50), escRow(40, 900)]);
  assert.equal(sorted[0].outstanding_paise, 900);
  assert.equal(sorted[1].outstanding_paise, 50);
  assert.equal(sorted[2].days_overdue, 5);
});

test("flattenCalendar orders days soonest first and flattens rows", () => {
  const days: CalendarDay[] = [
    { date: "2026-11-05", due_paise: 1, rows: [calRow(4)] },
    { date: "2026-11-01", due_paise: 1, rows: [calRow(8), calRow(0)] },
  ];
  const flat = flattenCalendar(days);
  assert.equal(flat.length, 3);
  assert.equal(flat[0].days_overdue, 8);
});

test("overdueRows keeps only days_overdue > 0", () => {
  const days: CalendarDay[] = [
    { date: "2026-11-01", due_paise: 1, rows: [calRow(0), calRow(3)] },
  ];
  const rows = overdueRows(days);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].days_overdue, 3);
});

test("monthLabel formats YYYY-MM to a friendly label", () => {
  assert.equal(monthLabel("2026-11"), "Nov 2026");
  assert.equal(monthLabel("bad"), "bad");
});

test("shiftMonth steps across year boundaries", () => {
  assert.equal(shiftMonth("2026-11", 1), "2026-12");
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2027-01", -1), "2026-12");
  assert.equal(shiftMonth("2026-01", -1), "2025-12");
});

test("currentMonth returns zero-padded YYYY-MM", () => {
  assert.equal(currentMonth(new Date("2026-03-09T00:00:00Z")), "2026-03");
});

test("orderedAgingBuckets orders known buckets, unknown last", () => {
  const order = orderedAgingBuckets({ "90+": 1, "1-30": 2, custom: 3 });
  assert.deepEqual(order, ["1-30", "90+", "custom"]);
});
