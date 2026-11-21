import test from "node:test";
import assert from "node:assert/strict";
import {
  featureRecordToRows,
  featureRowsToRecord,
  formatInrFromPaise,
  paiseToRupeesInput,
  rupeesInputToPaise,
} from "../../src/operator/format.ts";

test("converts INR rupee inputs to integer paise without floating-point drift", () => {
  assert.equal(rupeesInputToPaise("1499"), 149900);
  assert.equal(rupeesInputToPaise(" 1499.25 "), 149925);
  assert.equal(rupeesInputToPaise("0.01"), 1);
  assert.equal(rupeesInputToPaise("999.999"), Number.NaN);
  assert.equal(rupeesInputToPaise("-10"), Number.NaN);
  assert.equal(rupeesInputToPaise(""), Number.NaN);
  assert.equal(rupeesInputToPaise("1,499"), Number.NaN);
  assert.equal(paiseToRupeesInput(149900), "1499");
  assert.equal(paiseToRupeesInput(149925), "1499.25");
  assert.equal(formatInrFromPaise(149900), "₹1,499");
});

test("maps editable plan feature rows to the backend object and back", () => {
  const features = featureRowsToRecord([
    { key: "ai_assistant", value: "true" },
    { key: "custom_domain", value: "" },
    { key: "", value: "ignored" },
  ]);
  assert.deepEqual(features, {
    ai_assistant: "true",
    custom_domain: true,
  });
  assert.deepEqual(featureRecordToRows(features), [
    { key: "ai_assistant", value: "true" },
    { key: "custom_domain", value: "" },
  ]);
});
