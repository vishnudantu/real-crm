import test from "node:test";
import assert from "node:assert/strict";
import {
  documentDownloadFilename,
  documentKindChipClass,
  documentKindLabel,
  documentStatusTone,
  extractProofFields,
  formatPayloadSnapshot,
  isVoided,
  sanitizeDocumentFilename,
  shortReference,
} from "../../src/documents/documentsModel.ts";

test("documentStatusTone: ISSUED is green, VOIDED muted, DRAFT amber", () => {
  assert.match(documentStatusTone("ISSUED"), /emerald/);
  assert.match(documentStatusTone("VOIDED"), /charcoal/);
  assert.doesNotMatch(documentStatusTone("VOIDED"), /emerald/);
  assert.match(documentStatusTone("DRAFT"), /amber/);
});

test("documentStatusTone: unknown statuses fall back to the neutral badge", () => {
  assert.equal(
    documentStatusTone("ARCHIVED"),
    "border-charcoal/15 bg-charcoal/5 text-charcoal/80",
  );
});

test("isVoided only matches the VOIDED status", () => {
  assert.equal(isVoided({ status: "VOIDED" }), true);
  assert.equal(isVoided({ status: "ISSUED" }), false);
  assert.equal(isVoided({ status: "DRAFT" }), false);
});

test("documentKindLabel formats known kinds and humanizes unknown ones", () => {
  assert.equal(documentKindLabel("DEMAND_LETTER"), "Demand letter");
  assert.equal(documentKindLabel("RECEIPT"), "Receipt");
  assert.equal(documentKindLabel("SOMETHING_ELSE"), "Something Else");
});

test("documentKindChipClass distinguishes demand letters from receipts", () => {
  assert.match(documentKindChipClass("DEMAND_LETTER"), /amber/);
  assert.match(documentKindChipClass("RECEIPT"), /teal/);
  assert.match(documentKindChipClass("STATEMENT"), /charcoal/);
});

test("shortReference truncates UUIDs but keeps short identifiers intact", () => {
  assert.equal(
    shortReference("0d1f2a3b-1111-2222-3333-444455556666"),
    "0d1f2a3b…",
  );
  assert.equal(shortReference("abc123"), "abc123");
  assert.equal(shortReference(""), "—");
});

test("sanitizeDocumentFilename strips path separators, traversal and odd characters", () => {
  assert.equal(sanitizeDocumentFilename("DOC-DEMAND-000042"), "DOC-DEMAND-000042");
  assert.equal(sanitizeDocumentFilename("../../etc/passwd"), "etc-passwd");
  assert.equal(sanitizeDocumentFilename("DOC/RECEIPT 12: final"), "DOC-RECEIPT-12-final");
  assert.equal(sanitizeDocumentFilename("   "), "document");
  assert.equal(sanitizeDocumentFilename("///"), "document");
  assert.equal(sanitizeDocumentFilename("DOC--DEMAND----0001"), "DOC-DEMAND-0001");
  assert.equal(sanitizeDocumentFilename("unicode-डिमांड"), "unicode");
  assert.ok(sanitizeDocumentFilename("a".repeat(500)).length > 0);
});

test("documentDownloadFilename always produces a safe .pdf name", () => {
  assert.equal(
    documentDownloadFilename("DOC-DEMAND-000042"),
    "DOC-DEMAND-000042.pdf",
  );
  assert.equal(documentDownloadFilename("../DOC 1"), "DOC-1.pdf");
});

test("extractProofFields surfaces key merge fields in display order", () => {
  const fields = extractProofFields({
    customer_name: "Asha Rao",
    unit_code: "T2-1403",
    project_name: "Riverbend Heights",
    rera_number: "P51900000000",
    milestone: "Plinth completion",
    amount: "₹4,50,000",
    due_date: "22 Nov 2026",
    outstanding: "₹1,00,000",
    bank_name: "HDFC Bank",
    bank_account_number: "XXXX1234",
  });
  assert.deepEqual(
    fields.map((field) => field.key),
    [
      "customer_name",
      "unit_code",
      "project_name",
      "rera_number",
      "milestone",
      "amount",
      "due_date",
      "outstanding",
      "bank_name",
      "bank_account_number",
    ],
  );
  assert.equal(fields[0]?.label, "Customer");
  assert.equal(fields[0]?.value, "Asha Rao");
});

test("extractProofFields handles null, undefined and non-object snapshots", () => {
  assert.deepEqual(extractProofFields(null), []);
  assert.deepEqual(extractProofFields(undefined), []);
  assert.deepEqual(extractProofFields("not-a-snapshot"), []);
  assert.deepEqual(extractProofFields(42), []);
  assert.deepEqual(extractProofFields([]), []);
  assert.deepEqual(extractProofFields({}), []);
});

test("extractProofFields skips empty values and stringifies numbers", () => {
  const fields = extractProofFields({
    customer_name: "   ",
    milestone: "",
    installment_number: 3,
    amount: 0,
  });
  assert.deepEqual(
    fields.map((field) => [field.key, field.value]),
    [
      ["installment_number", "3"],
      ["amount", "0"],
    ],
  );
});

test("extractProofFields ignores nested objects rather than leaking [object Object]", () => {
  const fields = extractProofFields({
    customer_name: "Asha Rao",
    amount: { paise: 45000000 },
  });
  assert.deepEqual(fields, [
    { key: "customer_name", label: "Customer", value: "Asha Rao" },
  ]);
});

test("formatPayloadSnapshot pretty-prints JSON and tolerates nullish input", () => {
  assert.equal(formatPayloadSnapshot(null), "{}");
  assert.equal(formatPayloadSnapshot(undefined), "{}");
  assert.equal(formatPayloadSnapshot({ a: 1 }), '{\n  "a": 1\n}');
});
