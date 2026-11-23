import test from "node:test";
import assert from "node:assert/strict";
import {
  ALLOWED_TICKET_TRANSITIONS,
  allowedNextStatuses,
  emptyTicketCreateForm,
  isSlaBreached,
  offsetForPage,
  slaCountdownLabel,
  ticketStatusLabel,
  totalPages,
  validateCommentBody,
  validateTicketCreateForm,
} from "../../src/servicedesk/serviceDeskModel.ts";
import type { TicketItem } from "../../src/servicedesk/serviceDeskModel.ts";

function ticket(overrides: Partial<TicketItem> = {}): TicketItem {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    ticket_number: "TCK-000001",
    subject: "Leak in bathroom",
    description: "Customer reports a leak.",
    category: "DEFECT",
    priority: "HIGH",
    status: "OPEN",
    contact_id: null,
    booking_id: null,
    assigned_to_id: null,
    created_by_id: null,
    sla_due_at: "2026-01-01T00:00:00Z",
    first_response_at: null,
    resolved_at: null,
    resolution_note: null,
    created_at: "2025-12-31T00:00:00Z",
    updated_at: "2025-12-31T00:00:00Z",
    ...overrides,
  };
}

test("allowed transitions mirror the backend status machine", () => {
  assert.deepEqual(allowedNextStatuses("OPEN"), [
    "IN_PROGRESS",
    "WAITING_ON_CUSTOMER",
    "RESOLVED",
    "CLOSED",
  ]);
  assert.deepEqual(allowedNextStatuses("IN_PROGRESS"), ["WAITING_ON_CUSTOMER", "RESOLVED"]);
  assert.deepEqual(allowedNextStatuses("WAITING_ON_CUSTOMER"), ["IN_PROGRESS", "RESOLVED"]);
  assert.deepEqual(allowedNextStatuses("RESOLVED"), ["CLOSED"]);
  assert.deepEqual(allowedNextStatuses("CLOSED"), []);
  assert.equal(ALLOWED_TICKET_TRANSITIONS.CLOSED.length, 0);
});

test("isSlaBreached only flags OPEN/IN_PROGRESS tickets past their deadline", () => {
  const now = Date.parse("2026-01-02T00:00:00Z");
  assert.equal(isSlaBreached(ticket(), now), true, "OPEN and past due");
  assert.equal(isSlaBreached(ticket({ status: "IN_PROGRESS" }), now), true);
  assert.equal(isSlaBreached(ticket({ status: "WAITING_ON_CUSTOMER" }), now), false);
  assert.equal(isSlaBreached(ticket({ status: "RESOLVED" }), now), false);
  assert.equal(isSlaBreached(ticket({ sla_due_at: "2026-01-03T00:00:00Z" }), now), false);
  assert.equal(isSlaBreached(ticket({ sla_due_at: "not-a-date" }), now), false);
});

test("slaCountdownLabel reports due-in and overdue durations", () => {
  const now = Date.parse("2026-01-01T12:00:00Z");
  assert.equal(slaCountdownLabel("2026-01-01T15:00:00Z", now), "Due in 3h 0m");
  assert.equal(slaCountdownLabel("2026-01-01T09:30:00Z", now), "Overdue by 2h 30m");
  assert.equal(slaCountdownLabel("2026-01-04T12:00:00Z", now), "Due in 3d 0h");
  assert.equal(slaCountdownLabel("2026-01-01T12:20:00Z", now), "Due in 20m");
  assert.equal(slaCountdownLabel("bad", now), "SLA unavailable");
});

test("validateTicketCreateForm requires trimmed subject and description", () => {
  const errors = validateTicketCreateForm({
    ...emptyTicketCreateForm(),
    subject: "   ",
    description: "   ",
  });
  assert.ok(errors.subject);
  assert.ok(errors.description);
  const tooLong = validateTicketCreateForm({
    ...emptyTicketCreateForm(),
    subject: "s".repeat(256),
    description: "d".repeat(20001),
  });
  assert.ok(tooLong.subject);
  assert.ok(tooLong.description);
});

test("validateTicketCreateForm passes for a valid ticket", () => {
  assert.deepEqual(
    validateTicketCreateForm({
      ...emptyTicketCreateForm(),
      subject: "  Broken lift  ",
      description: "  Lift stuck on floor 3.  ",
    }),
    {},
  );
});

test("validateCommentBody enforces the 1..4000 trimmed contract", () => {
  assert.ok(validateCommentBody(""));
  assert.ok(validateCommentBody("   "));
  assert.ok(validateCommentBody("x".repeat(4001)));
  assert.equal(validateCommentBody("  Looks good.  "), null);
  assert.equal(validateCommentBody("x".repeat(4000)), null);
});

test("status label falls back to the raw value for unknown statuses", () => {
  assert.equal(ticketStatusLabel("WAITING_ON_CUSTOMER"), "Waiting on customer");
  assert.equal(ticketStatusLabel("SOME_FUTURE"), "SOME_FUTURE");
});

test("offset/page math matches the backend limit+offset contract", () => {
  assert.equal(offsetForPage(2, 25), 25);
  assert.equal(offsetForPage(-1, 25), 0);
  assert.equal(totalPages(51, 25), 3);
  assert.equal(totalPages(0, 25), 1);
});
