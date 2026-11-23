import test from "node:test";
import assert from "node:assert/strict";
import { dailyDelta, funnelRatio, groupByUrgency } from "../../src/salesFloor/model.ts";

const item = (id, urgency) => ({ id, urgency, title: id, reason: "Recorded activity" });

test("groups checklist by urgency without changing the API priority within a group", () => {
  const groups = groupByUrgency([
    item("aging-new", "AGING_SILENCE"),
    item("overdue", "OVERDUE"),
    item("approval", "PENDING_APPROVAL"),
    item("aging-old", "AGING_SILENCE"),
  ]);
  assert.deepEqual(groups.map((group) => group.urgency), ["OVERDUE", "AGING_SILENCE", "PENDING_APPROVAL"]);
  assert.deepEqual(groups[1].items.map((entry) => entry.id), ["aging-new", "aging-old"]);
  assert.equal(groups.some((group) => group.urgency === "DUE_TODAY"), false);
});

test("daily delta handles a zero baseline without infinity or fabricated volume", () => {
  assert.equal(dailyDelta(0, 0), 0);
  assert.equal(dailyDelta(1, 0), 100);
  assert.equal(dailyDelta(3, 2), 50);
  assert.equal(dailyDelta(1, 2), -50);
});

test("funnel ratio is zero when there are no enquiries", () => {
  assert.equal(funnelRatio({ enquiries: 0, visits: 1, bookings: 1 }), 0);
  assert.equal(funnelRatio({ enquiries: 4, visits: 2, bookings: 1 }), 25);
});
