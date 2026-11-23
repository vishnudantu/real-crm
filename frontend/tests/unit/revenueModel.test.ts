import test from "node:test";
import assert from "node:assert/strict";
import {
  formatRevenuePaise,
  meterLabel,
  renewalUrgency,
  revenueMonthLabel,
  toInvoicedSeries,
} from "../../src/operator/revenueModel.ts";

test("formatRevenuePaise uses compact Indian INR", () => {
  assert.equal(formatRevenuePaise(0), "₹0");
  assert.equal(formatRevenuePaise(49_900), "₹499");
  // 149000 paise × 12 = 1,788,000 paise = ₹17,880 (< 1 Lakh, grouped rupees).
  assert.equal(formatRevenuePaise(149000 * 12), "₹17,880");
  // 1e7 paise = 1 Lakh.
  assert.equal(formatRevenuePaise(10_000_000), "₹1.00 L");
  // 1.788e8 paise = ₹17,88,000 = 17.88 Lakh.
  assert.equal(formatRevenuePaise(178_800_000), "₹17.88 L");
  // 1e9 paise = 1 Crore.
  assert.equal(formatRevenuePaise(1_000_000_000), "₹1.00 Cr");
});

test("revenueMonthLabel renders short month/year", () => {
  assert.equal(revenueMonthLabel("2026-11-01"), "Nov '26");
  assert.equal(revenueMonthLabel("bad"), "bad");
});

test("toInvoicedSeries maps API points to chart rows", () => {
  const series = toInvoicedSeries([
    { month: "2026-10-01", invoiced_paise: 1_000, invoice_count: 1 },
    { month: "2026-11-01", invoiced_paise: 2_000, invoice_count: 2 },
  ]);
  assert.deepEqual(series[1], {
    month: "2026-11-01",
    label: "Nov '26",
    invoicedPaise: 2_000,
    invoices: 2,
  });
});

test("meterLabel and renewalUrgency helpers", () => {
  assert.equal(meterLabel("leads"), "Monthly leads");
  assert.equal(meterLabel("whatsapp_sent"), "WhatsApp messages");
  assert.equal(meterLabel("users"), "Active users");
  assert.equal(meterLabel("custom"), "custom");
  assert.equal(renewalUrgency(0), "overdue");
  assert.equal(renewalUrgency(5), "soon");
  assert.equal(renewalUrgency(20), "later");
});
