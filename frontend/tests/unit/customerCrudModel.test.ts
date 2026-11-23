import test from "node:test";
import assert from "node:assert/strict";
import {
  validateContactCreateForm,
  buildContactCreatePayload,
} from "../../src/customers/customersModel.ts";
import {
  validateVisitCapture,
  buildVisitLeadPayload,
  validateVisitCustomerEdit,
  leadLabel,
} from "../../src/admin/visits/scheduleVisitModel.ts";

const validContact = {
  displayName: "Asha Rao",
  email: "asha@example.com",
  phone: "+91 98765 43210",
  primaryLanguage: "en",
  notes: "",
};

test("contact create form rejects missing identity and short name", () => {
  const errors = validateContactCreateForm({
    displayName: "A",
    email: "",
    phone: "",
    primaryLanguage: "en",
    notes: "",
  });
  assert.ok(errors.displayName);
  assert.ok(errors.email);
  assert.ok(errors.phone);
});

test("contact create accepts a valid phone-only identity and normalizes language", () => {
  const payload = buildContactCreatePayload({
    ...validContact,
    email: "",
    primaryLanguage: " EN ",
  });
  assert.equal(payload.email, null);
  assert.equal(payload.phone, "+91 98765 43210");
  assert.equal(payload.primary_language, "en");
  assert.deepEqual(
    validateContactCreateForm({ ...validContact, email: "" }),
    {},
  );
});

test("contact create validates email and phone formats", () => {
  assert.ok(validateContactCreateForm({ ...validContact, email: "bad" }).email);
  assert.ok(validateContactCreateForm({ ...validContact, phone: "12" }).phone);
});

test("visit capture existing mode requires a lead", () => {
  const errors = validateVisitCapture({
    mode: "existing",
    leadId: "",
    fullName: "",
    email: "",
    phone: "",
    source: "OTHER",
    consentToContact: true,
  });
  assert.ok(errors.leadId);
  assert.deepEqual(Object.keys(errors), ["leadId"]);
});

test("visit capture new mode enforces name, contact method, and consent", () => {
  const errors = validateVisitCapture({
    mode: "new",
    leadId: "",
    fullName: "Asha Rao",
    email: "",
    phone: "",
    source: "REFERRAL",
    consentToContact: false,
  });
  assert.ok(errors.contact);
  assert.ok(errors.consent);
});

test("buildVisitLeadPayload trims and nulls empty contact methods", () => {
  const payload = buildVisitLeadPayload(
    {
      mode: "new",
      leadId: "",
      fullName: "  Asha Rao  ",
      email: "",
      phone: "+91 98765 43210",
      source: "REFERRAL",
      consentToContact: true,
    },
    "project-1",
  );
  assert.equal(payload.full_name, "Asha Rao");
  assert.equal(payload.project_id, "project-1");
  assert.equal(payload.email, null);
  assert.equal(payload.phone, "+91 98765 43210");
  assert.equal(payload.source, "REFERRAL");
  assert.equal(payload.consent_to_contact, true);
});

test("visit customer edit allows email-only but never clears both methods", () => {
  assert.deepEqual(
    validateVisitCustomerEdit({ fullName: "Asha", email: "a@b.co", phone: "" }),
    {},
  );
  assert.ok(
    validateVisitCustomerEdit({ fullName: "Asha", email: "", phone: "" }).contact,
  );
});

test("leadLabel shows contact and opted-out marker", () => {
  assert.equal(
    leadLabel(
      {
        id: "1",
        full_name: "Asha",
        email: null,
        phone: "+91999",
        project_id: "p1",
        opted_out: true,
      },
      "Riverbend",
    ),
    "Asha (+91999 · opted out) — Riverbend",
  );
});
