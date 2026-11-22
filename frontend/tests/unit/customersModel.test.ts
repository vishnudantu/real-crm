import test from "node:test";
import assert from "node:assert/strict";
import {
  groupOpportunitiesByStage,
  groupTimelineByDay,
  mergeSummaryCounts,
  OPPORTUNITY_STAGES,
} from "../../src/customers/customersModel.ts";
import type { Opportunity, TimelineItem } from "../../src/customers/customersModel.ts";

function timelineItem(occurredAt: string, type = "message"): TimelineItem {
  return { type, occurred_at: occurredAt, actor: null, summary: type, link_ids: {} };
}

function opportunity(id: string, stage: Opportunity["stage"], createdAt: string): Opportunity {
  return {
    id, contact_id: "contact", project_id: "project", lead_id: null, stage,
    owner_user_id: null, budget_min: null, budget_max: null,
    preferred_configuration: null, source: null, loss_reason: null,
    won_booking_id: null, value_paise: null, created_at: createdAt, updated_at: createdAt,
  };
}

test("groups timeline events by UTC day and sorts days and events newest first", () => {
  const original = [
    timelineItem("2026-01-02T09:00:00Z", "call"),
    timelineItem("2026-01-01T12:00:00Z", "lead"),
    timelineItem("2026-01-02T15:00:00Z", "message"),
  ];
  const groups = groupTimelineByDay(original);
  assert.deepEqual(groups.map((group) => group.dayKey), ["2026-01-02", "2026-01-01"]);
  assert.deepEqual(groups[0]?.items.map((item) => item.type), ["message", "call"]);
  assert.equal(groups[0]?.label, "Friday, January 2, 2026");
  assert.equal(original[0]?.type, "call");
  assert.notEqual(groups[0]?.items, original);
});

test("returns an empty timeline and handles invalid dates without throwing", () => {
  assert.deepEqual(groupTimelineByDay([]), []);
  const groups = groupTimelineByDay([timelineItem("not-a-date"), timelineItem("2026-01-01T00:00:00Z")]);
  assert.equal(groups.at(-1)?.dayKey, "unknown");
  assert.equal(groups.at(-1)?.label, "Date unavailable");
});

test("groups opportunities in pipeline order and sorts cards newest first", () => {
  const items = [
    opportunity("old", "NEW", "2026-01-01T00:00:00Z"),
    opportunity("new", "NEW", "2026-01-03T00:00:00Z"),
    opportunity("won", "WON", "2026-01-02T00:00:00Z"),
  ];
  const groups = groupOpportunitiesByStage(items);
  assert.equal(groups.length, OPPORTUNITY_STAGES.length);
  assert.deepEqual(groups.map((group) => group.stage), OPPORTUNITY_STAGES);
  assert.deepEqual(groups[0]?.items.map((item) => item.id), ["new", "old"]);
  assert.equal(items[0]?.id, "old");
});

test("uses an explicit final column for unknown stages and handles empty arrays", () => {
  assert.deepEqual(groupOpportunitiesByStage([]).every((group) => group.items.length === 0), true);
  const unknown = opportunity("future", "FUTURE_STAGE" as Opportunity["stage"], "2026-01-01T00:00:00Z");
  const groups = groupOpportunitiesByStage([unknown]);
  assert.equal(groups.at(-1)?.stage, "OTHER");
  assert.equal(groups.at(-1)?.label, "Other stages");
  assert.deepEqual(groups.at(-1)?.items, [unknown]);
});

test("counts merge evidence arrays without changing the evidence object", () => {
  const evidence = {
    moved_method_ids: ["m1", "m2"],
    skipped_method_ids: ["m3"],
    repointed_opportunity_ids: ["o1"],
  };
  assert.deepEqual(mergeSummaryCounts(evidence), {
    methodsMoved: 2,
    methodsSkipped: 1,
    opportunitiesRepointed: 1,
  });
  assert.deepEqual(evidence.moved_method_ids, ["m1", "m2"]);
});

test("merge evidence defaults to zero for empty or unexpected values", () => {
  assert.deepEqual(mergeSummaryCounts({}), { methodsMoved: 0, methodsSkipped: 0, opportunitiesRepointed: 0 });
  assert.deepEqual(mergeSummaryCounts({ moved_method_ids: null, repointed_opportunity_ids: "invalid" }), {
    methodsMoved: 0, methodsSkipped: 0, opportunitiesRepointed: 0,
  });
});
