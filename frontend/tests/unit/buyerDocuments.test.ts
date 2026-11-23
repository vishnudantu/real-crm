import test from "node:test";
import assert from "node:assert/strict";
import {
  ACCEPTED_DOCUMENT_TYPES,
  MAX_DOCUMENT_BYTES,
  categoryLabel,
  documentStatusLabel,
  documentStatusTone,
  downloadFilename,
  extensionForContentType,
  formatBytes,
  isDownloadable,
  isOpenRequest,
  requestStatusTone,
  sanitizeFilename,
  shouldCompress,
  validateUploadFile,
} from "../../src/buyer/documents/buyerDocumentsModel.ts";
import { scaledDimensions } from "../../src/buyer/documents/imageCompress.ts";

/* ---------- categoryLabel ---------- */

test("categoryLabel maps known categories and humanizes unknown ones", () => {
  assert.equal(categoryLabel("IDENTITY"), "Identity proof");
  assert.equal(categoryLabel("BANK"), "Bank statement");
  assert.equal(categoryLabel("SOMETHING_NEW"), "Something New");
});

/* ---------- documentStatusTone / Label ---------- */

test("documentStatusTone: VERIFIED green, SUBMITTED/UNDER_REVIEW amber, REJECTED rose", () => {
  assert.match(documentStatusTone("VERIFIED"), /emerald/);
  assert.match(documentStatusTone("SUBMITTED"), /amber/);
  assert.match(documentStatusTone("UNDER_REVIEW"), /amber/);
  assert.match(documentStatusTone("REJECTED"), /rose/);
  assert.match(documentStatusTone("EXPIRED"), /charcoal/);
});

test("documentStatusTone falls back to neutral badge for unknown statuses", () => {
  assert.equal(
    documentStatusTone("ARCHIVED"),
    "border-charcoal/15 bg-charcoal/5 text-charcoal/80",
  );
});

test("documentStatusLabel humanizes known statuses and passes unknown through", () => {
  assert.equal(documentStatusLabel("SUBMITTED"), "Submitted");
  assert.equal(documentStatusLabel("UNDER_REVIEW"), "Under review");
  assert.equal(documentStatusLabel("VERIFIED"), "Verified");
  assert.equal(documentStatusLabel("CUSTOM"), "CUSTOM");
});

test("requestStatusTone: OPEN amber, FULFILLED green, CANCELLED muted", () => {
  assert.match(requestStatusTone("OPEN"), /amber/);
  assert.match(requestStatusTone("FULFILLED"), /emerald/);
  assert.match(requestStatusTone("CANCELLED"), /charcoal/);
});

/* ---------- formatBytes ---------- */

test("formatBytes renders B, KB and MB sensibly", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(2048), "2.0 KB");
  assert.equal(formatBytes(1536), "1.5 KB");
  assert.equal(formatBytes(50 * 1024), "50 KB");
  assert.equal(formatBytes(2.4 * 1024 * 1024), "2.4 MB");
  assert.equal(formatBytes(10 * 1024 * 1024), "10 MB");
});

test("formatBytes tolerates invalid input", () => {
  assert.equal(formatBytes(-5), "—");
  assert.equal(formatBytes(NaN), "—");
});

/* ---------- extensionForContentType ---------- */

test("extensionForContentType maps MIME types to file extensions", () => {
  assert.equal(extensionForContentType("application/pdf"), "pdf");
  assert.equal(extensionForContentType("image/jpeg"), "jpg");
  assert.equal(extensionForContentType("image/png"), "png");
  assert.equal(extensionForContentType("image/webp"), "webp");
  assert.equal(extensionForContentType("image/jpeg; charset=binary"), "jpg");
  assert.equal(extensionForContentType("image/tiff"), "tiff");
  assert.equal(extensionForContentType("application/octet-stream"), "bin");
});

/* ---------- sanitizeFilename / downloadFilename ---------- */

test("sanitizeFilename strips traversal and odd characters", () => {
  assert.equal(sanitizeFilename("Aadhaar Card"), "Aadhaar-Card");
  assert.equal(sanitizeFilename("../../etc/passwd"), "etc-passwd");
  assert.equal(sanitizeFilename("   "), "document");
  assert.equal(sanitizeFilename("ID--Proof----2024"), "ID-Proof-2024");
});

test("downloadFilename produces a safe name with the right extension", () => {
  assert.equal(
    downloadFilename({ title: "Bank Statement", content_type: "application/pdf" }),
    "Bank-Statement.pdf",
  );
  assert.equal(
    downloadFilename({ title: "../ID Proof", content_type: "image/jpeg" }),
    "ID-Proof.jpg",
  );
});

/* ---------- isDownloadable / isOpenRequest ---------- */

test("isDownloadable excludes only REJECTED documents", () => {
  assert.equal(isDownloadable({ status: "VERIFIED" }), true);
  assert.equal(isDownloadable({ status: "SUBMITTED" }), true);
  assert.equal(isDownloadable({ status: "REJECTED" }), false);
});

test("isOpenRequest matches only OPEN", () => {
  assert.equal(isOpenRequest({ status: "OPEN" }), true);
  assert.equal(isOpenRequest({ status: "FULFILLED" }), false);
  assert.equal(isOpenRequest({ status: "CANCELLED" }), false);
});

/* ---------- validateUploadFile ---------- */

test("validateUploadFile accepts PDF and images within the size limit", () => {
  assert.equal(validateUploadFile({ type: "application/pdf", size: 1000 }), null);
  assert.equal(validateUploadFile({ type: "image/jpeg", size: 1000 }), null);
  assert.equal(validateUploadFile({ type: "image/png", size: 1000 }), null);
  assert.equal(
    validateUploadFile({ type: "application/pdf", size: MAX_DOCUMENT_BYTES }),
    null,
  );
});

test("validateUploadFile rejects unsupported types", () => {
  const error = validateUploadFile({ type: "text/plain", size: 1000 });
  assert.ok(error);
  assert.match(error, /PDF or image/);
  assert.ok(validateUploadFile({ type: "video/mp4", size: 1000 }));
  assert.ok(validateUploadFile({ type: "application/zip", size: 1000 }));
});

test("validateUploadFile rejects empty files", () => {
  assert.match(
    validateUploadFile({ type: "application/pdf", size: 0 }) ?? "",
    /empty/,
  );
});

test("validateUploadFile rejects files over the limit", () => {
  const error = validateUploadFile({
    type: "image/png",
    size: MAX_DOCUMENT_BYTES + 1,
  });
  assert.ok(error);
  assert.match(error, /10 MB/);
});

/* ---------- shouldCompress ---------- */

test("shouldCompress targets images, not PDFs", () => {
  assert.equal(shouldCompress("image/jpeg"), true);
  assert.equal(shouldCompress("image/png"), true);
  assert.equal(shouldCompress("application/pdf"), false);
  assert.equal(shouldCompress("text/plain"), false);
});

/* ---------- accept types contract ---------- */

test("ACCEPTED_DOCUMENT_TYPES reflects the backend image/* + pdf rule", () => {
  assert.ok(ACCEPTED_DOCUMENT_TYPES.includes("application/pdf"));
  assert.ok(ACCEPTED_DOCUMENT_TYPES.includes("image/*"));
});

/* ---------- scaledDimensions (image compress) ---------- */

test("scaledDimensions never upscales small images", () => {
  assert.deepEqual(scaledDimensions(800, 600, 2560), { width: 800, height: 600 });
  assert.deepEqual(scaledDimensions(2560, 100, 2560), { width: 2560, height: 100 });
});

test("scaledDimensions fits the longest edge within maxEdge, preserving aspect", () => {
  // 4000x3000 -> longest edge 4000 scales to 2560
  assert.deepEqual(scaledDimensions(4000, 3000, 2560), {
    width: 2560,
    height: 1920,
  });
  // Portrait: 3000x4000 -> height is the longest edge
  const portrait = scaledDimensions(3000, 4000, 2560);
  assert.equal(portrait.height, 2560);
  assert.equal(portrait.width, 1920);
});

test("scaledDimensions respects a custom maxEdge", () => {
  assert.deepEqual(scaledDimensions(2000, 1000, 1000), {
    width: 1000,
    height: 500,
  });
});

test("scaledDimensions guards against degenerate input", () => {
  assert.deepEqual(scaledDimensions(0, 100), { width: 0, height: 0 });
  assert.deepEqual(scaledDimensions(-10, 100), { width: 0, height: 0 });
  assert.deepEqual(scaledDimensions(NaN, 100), { width: 0, height: 0 });
});

test("scaledDimensions keeps at least 1px on every edge", () => {
  const result = scaledDimensions(1, 100000, 100);
  assert.ok(result.width >= 1);
  assert.ok(result.height >= 1);
});
