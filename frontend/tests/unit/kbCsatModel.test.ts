import test from "node:test";
import assert from "node:assert/strict";
import {
  CSAT_PERIODS,
  csatAverageLabel,
  csatResponseRateLabel,
  csatStars,
  emptyKbArticleForm,
  kbArticleStatusLabel,
  slugifyArticleTitle,
  validateKbArticleForm,
} from "../../src/servicedesk/serviceDeskModel.ts";
import {
  isRatingEligible,
  kbMarkdownBlocks,
  normalizeHelpQuery,
  validateCsatSubmission,
} from "../../src/buyer/help/helpCenterModel.ts";

test("kb form validation mirrors the backend constraints", () => {
  assert.deepEqual(validateKbArticleForm(emptyKbArticleForm()), {
    title: "A title is required.",
    category: "Pick or type a category.",
    body_markdown: "Write the article body in markdown.",
  });

  const valid = validateKbArticleForm({
    title: "How to pay",
    slug: "",
    category: "Payments",
    body_markdown: "# Steps",
  });
  assert.deepEqual(valid, {});

  const longTitle = validateKbArticleForm({
    title: "x".repeat(256),
    slug: "",
    category: "P",
    body_markdown: "body",
  });
  assert.equal(longTitle.title, "At most 255 characters.");
});

test("kb slug validation accepts only lowercase kebab case", () => {
  assert.equal(
    validateKbArticleForm({ title: "T", slug: "Good Slug", category: "c", body_markdown: "b" })
      .slug,
    "Lowercase letters, digits and single hyphens only.",
  );
  assert.equal(
    validateKbArticleForm({ title: "T", slug: "good-slug-2", category: "c", body_markdown: "b" })
      .slug,
    undefined,
  );
});

test("slugifyArticleTitle matches the backend slug derivation", () => {
  assert.equal(slugifyArticleTitle("How to track your loan status"), "how-to-track-your-loan-status");
  assert.equal(slugifyArticleTitle("  Reg-no: 1234!! "), "reg-no-1234");
  assert.equal(slugifyArticleTitle("???"), "article");
  assert.ok(slugifyArticleTitle("a".repeat(200)).length <= 60);
});

test("csat display helpers", () => {
  assert.equal(csatStars(3), "★★★☆☆");
  assert.equal(csatStars(null), "—");
  assert.equal(csatStars(6), "—");
  assert.equal(csatAverageLabel(4.166), "4.2 / 5");
  assert.equal(csatAverageLabel(null), "No ratings yet");
  assert.equal(csatResponseRateLabel(0.6669), "67%");
  assert.equal(csatResponseRateLabel(null), "—");
  assert.deepEqual(
    CSAT_PERIODS.map((period) => period.value),
    ["30d", "90d", "365d"],
  );
});

test("normalizeHelpQuery trims, caps and empties", () => {
  assert.equal(normalizeHelpQuery("  loan status  "), "loan status");
  assert.equal(normalizeHelpQuery("   "), "");
  assert.equal(normalizeHelpQuery("x".repeat(300)).length, 200);
});

test("validateCsatSubmission requires an integer 1..5 rating", () => {
  assert.equal(validateCsatSubmission(null, ""), "Pick a rating from 1 to 5 stars.");
  assert.ok(validateCsatSubmission(0, ""));
  assert.ok(validateCsatSubmission(6, ""));
  assert.ok(validateCsatSubmission(3.5, ""));
  assert.equal(validateCsatSubmission(4, "great"), null);
  assert.ok(validateCsatSubmission(4, "y".repeat(2001)));
});

test("only closed tickets are rating eligible", () => {
  assert.ok(isRatingEligible({ status: "CLOSED" }));
  assert.ok(!isRatingEligible({ status: "RESOLVED" }));
  assert.ok(!isRatingEligible({ status: "OPEN" }));
});

test("kbMarkdownBlocks parses headings lists and paragraphs", () => {
  assert.deepEqual(
    kbMarkdownBlocks("## Steps\n\n1. do it\n- a bullet\n* another\ntext\n\n\n## More"),
    [
      { type: "h2", text: "Steps" },
      { type: "p", text: "1. do it" },
      { type: "li", text: "a bullet" },
      { type: "li", text: "another" },
      { type: "p", text: "text" },
      { type: "h2", text: "More" },
    ],
  );
});
