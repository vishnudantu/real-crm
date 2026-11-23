import test from "node:test";
import assert from "node:assert/strict";
import { parseBankRows } from "../../src/reconciliation/model.ts";
import { providerLabel, validateProviderInput } from "../../src/tenantai/model.ts";
import { formatMilliseconds, structuredText, transcriptSegments } from "../../src/voiceintel/model.ts";

test("parseBankRows maps CSV rows to exact integer-paise API payloads", () => {
  assert.deepEqual(parseBankRows("UTR1, 1250.50, 2026-11-22, Asha, A-1204\nUTR2,10,2026-11-23"), [
    { utr: "UTR1", amount_paise: 125050, txn_date: "2026-11-22", payer_name: "Asha", payer_detail: "A-1204" },
    { utr: "UTR2", amount_paise: 1000, txn_date: "2026-11-23", payer_name: null, payer_detail: null },
  ]);
});

test("parseBankRows rejects malformed, zero, and impossible rows with row numbers", () => {
  assert.throws(() => parseBankRows("UTR1, 0, 2026-11-22"), /Row 1/);
  assert.throws(() => parseBankRows("UTR1, 1.00, 2026-02-30"), /YYYY-MM-DD/);
  assert.throws(() => parseBankRows("UTR1, 1.00"), /Row 1/);
  assert.deepEqual(parseBankRows("\n"), []);
});

test("provider validation enforces model, secret length, and compatible base URL", () => {
  assert.equal(providerLabel("groq"), "Groq");
  assert.equal(validateProviderInput({ provider: "groq", apiKey: "12345678", model: "llama", baseUrl: "" }), null);
  assert.match(validateProviderInput({ provider: "groq", apiKey: "short", model: "llama", baseUrl: "" }) ?? "", /8 characters/);
  assert.match(validateProviderInput({ provider: "openai-compatible", apiKey: "12345678", model: "gpt", baseUrl: "not a url" }) ?? "", /base URL/);
  assert.equal(validateProviderInput({ provider: "openai-compatible", apiKey: "12345678", model: "gpt", baseUrl: "https://example.com/v1" }), null);
});

test("transcriptSegments safely narrows unknown external JSON", () => {
  assert.deepEqual(transcriptSegments(null), []);
  assert.deepEqual(transcriptSegments([{ start_ms: 1000, end_ms: 2500, speaker: "Agent", text: "Hello" }, "bad"]), [
    { startMs: 1000, endMs: 2500, speaker: "Agent", text: "Hello" },
  ]);
  assert.equal(formatMilliseconds(65000), "1:05");
  assert.equal(structuredText({ budget: "2 Cr" }), '{"budget":"2 Cr"}');
});
