import test from "node:test";
import assert from "node:assert/strict";
import {
  buildApprovalCreatePayload,
  canUserCancel,
  canUserDecide,
  emptyApprovalCreateForm,
  isPending,
  isUuid,
  offsetForPage,
  rupeesInputToPaise,
  shortId,
  totalPages,
  validateApprovalCreateForm,
} from "../../src/approvals/approvalsModel.ts";
import type { ApprovalRequestItem } from "../../src/approvals/approvalsModel.ts";

const UUID_A = "11111111-1111-4111-8111-111111111111";
const UUID_B = "22222222-2222-4222-8222-222222222222";

function request(overrides: Partial<ApprovalRequestItem> = {}): ApprovalRequestItem {
  return {
    id: UUID_A,
    request_type: "DISCOUNT",
    reference_type: "unit",
    reference_id: UUID_B,
    requested_by_id: UUID_A,
    approver_id: null,
    status: "PENDING",
    amount_paise: 500000,
    reason: "Buyer negotiation",
    decision_note: null,
    decided_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function validForm() {
  return {
    ...emptyApprovalCreateForm(),
    requestType: "DISCOUNT",
    referenceType: "unit",
    referenceId: UUID_B,
    reason: "  Buyer asked for 5% off.  ",
    amountRupees: "5000",
    approverId: UUID_A,
  };
}

test("isUuid accepts canonical UUIDs and rejects malformed ids", () => {
  assert.equal(isUuid(UUID_A), true);
  assert.equal(isUuid(UUID_A.toUpperCase()), true);
  assert.equal(isUuid(`  ${UUID_A}  `), true);
  assert.equal(isUuid("not-a-uuid"), false);
  assert.equal(isUuid(UUID_A.slice(1)), false);
  assert.equal(isUuid(""), false);
});

test("canUserDecide requires pending and a different requester", () => {
  assert.equal(canUserDecide(request(), UUID_B), true);
  assert.equal(canUserDecide(request(), UUID_A), false, "self-approval must be blocked");
  assert.equal(canUserDecide(request({ status: "APPROVED" }), UUID_B), false);
  assert.equal(canUserDecide(request({ status: "CANCELLED" }), UUID_B), false);
});

test("canUserCancel allows requester or admin, only while pending", () => {
  assert.equal(canUserCancel(request(), UUID_A, false), true, "requester can withdraw");
  assert.equal(canUserCancel(request(), UUID_B, true), true, "admin can cancel any");
  assert.equal(canUserCancel(request(), UUID_B, false), false, "other staff cannot");
  assert.equal(canUserCancel(request({ status: "REJECTED" }), UUID_A, true), false);
});

test("isPending and shortId helpers", () => {
  assert.equal(isPending(request()), true);
  assert.equal(isPending(request({ status: "APPROVED" })), false);
  assert.equal(shortId(null), "—");
  assert.equal(shortId("abc"), "abc");
  assert.equal(shortId(UUID_A), "11111111…");
});

test("validateApprovalCreateForm flags each required field", () => {
  const errors = validateApprovalCreateForm(emptyApprovalCreateForm());
  assert.ok(errors.requestType);
  assert.ok(errors.referenceId);
  assert.ok(errors.reason);
  assert.equal(Object.values(errors).filter(Boolean).length, 3);
});

test("validateApprovalCreateForm rejects bad reference id and amount formats", () => {
  const errors = validateApprovalCreateForm({
    ...validForm(),
    referenceId: "not-a-uuid",
    amountRupees: "-500",
  });
  assert.ok(errors.referenceId);
  assert.ok(errors.amountRupees);
  const noAmount = validateApprovalCreateForm({ ...validForm(), amountRupees: "" });
  assert.equal(noAmount.amountRupees, undefined, "amount is optional");
});

test("validateApprovalCreateForm rejects over-long reason and bad approver id", () => {
  const errors = validateApprovalCreateForm({
    ...validForm(),
    reason: "x".repeat(2001),
    approverId: "abc",
  });
  assert.ok(errors.reason);
  assert.ok(errors.approverId);
});

test("buildApprovalCreatePayload trims strings and converts rupees to paise", () => {
  const payload = buildApprovalCreatePayload(validForm());
  assert.equal(payload.request_type, "DISCOUNT");
  assert.equal(payload.reference_id, UUID_B);
  assert.equal(payload.reason, "Buyer asked for 5% off.");
  assert.equal(payload.amount_paise, 500000);
  assert.equal(payload.approver_id, UUID_A);
});

test("buildApprovalCreatePayload omits optional amount and approver when blank", () => {
  const payload = buildApprovalCreatePayload({ ...validForm(), amountRupees: "", approverId: "" });
  assert.equal("amount_paise" in payload, false);
  assert.equal("approver_id" in payload, false);
  assert.equal("amount" in payload, false);
});

test("rupeesInputToPaise handles decimals, zero and invalid input", () => {
  assert.equal(rupeesInputToPaise("100.50"), 10050);
  assert.equal(rupeesInputToPaise("0"), 0);
  assert.equal(rupeesInputToPaise(""), null);
  assert.equal(rupeesInputToPaise("12.345"), null);
  assert.equal(rupeesInputToPaise("abc"), null);
});

test("offset/page math matches the backend limit+offset contract", () => {
  assert.equal(offsetForPage(1, 25), 0);
  assert.equal(offsetForPage(3, 25), 50);
  assert.equal(offsetForPage(0, 25), 0, "never negative");
  assert.equal(totalPages(0, 25), 1);
  assert.equal(totalPages(26, 25), 2);
  assert.equal(totalPages(50, 25), 2);
});
