import test from "node:test";
import assert from "node:assert/strict";
import {
  axisTicks,
  collectionsTrailingSum,
  formatDayLabel,
  formatMonthLabel,
  formatPaise,
  niceAxis,
  toCollectionsSeries,
  toVelocitySeries,
  trailingSum,
} from "../../src/admin/executive/executiveModel.ts";
import type {
  CollectionsMonthPoint,
  ExecutiveMonthPoint,
} from "../../src/admin/executive/executiveModel.ts";

test("formatPaise renders compact Indian INR without floating point drift", () => {
  assert.equal(formatPaise(0), "₹0");
  assert.equal(formatPaise(99_99), "₹100"); // 9999 paise = ₹99.99 rounds to ₹100
  // 1e7 paise = ₹1,00,000 = 1 Lakh.
  assert.equal(formatPaise(10_000_000), "₹1.00 L");
  // 1.5e8 paise = ₹15,00,000 = 15 Lakh.
  assert.equal(formatPaise(150_000_000), "₹15.00 L");
  // 1e9 paise = ₹1,00,00,000 = 1 Crore.
  assert.equal(formatPaise(1_000_000_000), "₹1.00 Cr");
  assert.equal(formatPaise(-1_000_000_000), "-₹1.00 Cr");
  // 123456 paise = ₹1234.56; sub-lakh amounts round to whole grouped rupees.
  assert.equal(formatPaise(123456), "₹1,235");
});

test("month and day labels format from ISO first-of-month dates", () => {
  assert.equal(formatMonthLabel("2026-11-01"), "Nov '26");
  assert.equal(formatMonthLabel("2026-01-01"), "Jan '26");
  assert.equal(formatMonthLabel("not-a-date"), "not-a-date");
  assert.equal(formatDayLabel("2026-11-01"), "1 Nov");
});

const month = (m: string, enquiries: number, visits: number, bookings: number, value: number): ExecutiveMonthPoint => ({
  month: m,
  enquiries,
  visits_completed: visits,
  bookings,
  booking_value_paise: value,
});

test("toVelocitySeries normalizes API points into chart-ready rows", () => {
  const series = toVelocitySeries([
    month("2026-10-01", 4, 2, 1, 1_00_00_00_00),
    month("2026-11-01", 6, 3, 2, 2_00_00_00_00),
  ]);
  assert.equal(series.length, 2);
  assert.deepEqual(series[0], {
    month: "2026-10-01",
    label: "Oct '26",
    enquiries: 4,
    visits: 2,
    bookings: 1,
    valuePaise: 1_00_00_00_00,
  });
});

test("trailingSum sums only the trailing N months", () => {
  const series = toVelocitySeries([
    month("2026-08-01", 1, 0, 0, 0),
    month("2026-09-01", 2, 0, 0, 0),
    month("2026-10-01", 4, 0, 0, 0),
    month("2026-11-01", 8, 0, 0, 0),
  ]);
  assert.equal(trailingSum(series, "enquiries"), 14); // trailing 3: 2+4+8
  assert.equal(trailingSum(series, "enquiries", 2), 12);
  assert.equal(trailingSum(series, "enquiries", 1), 8);
  assert.equal(trailingSum(series, "enquiries", 4), 15); // all four months
  assert.equal(trailingSum([], "enquiries"), 0);
});

test("collections series + trailing sum", () => {
  const points: CollectionsMonthPoint[] = [
    { month: "2026-10-01", collected_paise: 10_00_00_00, receipt_count: 3 },
    { month: "2026-11-01", collected_paise: 20_00_00_00, receipt_count: 5 },
  ];
  const series = toCollectionsSeries(points);
  assert.equal(series[1].label, "Nov '26");
  assert.equal(series[1].receipts, 5);
  assert.equal(collectionsTrailingSum(series), 30_00_00_00);
  assert.equal(collectionsTrailingSum(series, 1), 20_00_00_00);
});

test("niceAxis produces a clean maximum and step", () => {
  assert.deepEqual(niceAxis(0), { max: 4, step: 1 });
  assert.deepEqual(niceAxis(3), { max: 4, step: 1 });
  const axis = niceAxis(37);
  assert.ok(axis.max >= 37);
  assert.ok(axis.step > 0);
  const { max, ticks } = axisTicks(9);
  assert.ok(ticks[0] === 0);
  assert.ok(ticks.at(-1) === max);
  assert.ok(ticks.every((t, i) => i === 0 || t > ticks[i - 1]));
});
