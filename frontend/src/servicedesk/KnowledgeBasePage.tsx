import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  BookOpen,
  Globe,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import {
  formatDateTime,
  saleCardClasses,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { ApprovalPagination } from "../approvals/ApprovalsUi";
import { errorMessage } from "../shared/apiRequest";
import { createKbArticle, fetchKbArticles, kbKeys, publishKbArticle } from "./serviceDeskApi";
import type { KbArticleFormErrors, KbArticleFormState, KbArticleStatus } from "./serviceDeskModel";
import {
  MAX_KB_BODY_LENGTH,
  MAX_KB_CATEGORY_LENGTH,
  MAX_KB_TITLE_LENGTH,
  emptyKbArticleForm,
  kbArticleStatusLabel,
  kbArticleStatusTone,
  slugifyArticleTitle,
  validateKbArticleForm,
} from "./serviceDeskModel";

const PAGE_SIZE = 25;

/** /admin/service-desk/knowledge — staff KB manager: draft, publish, search. */
export function KnowledgeBasePage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<KbArticleStatus | "ALL">("ALL");
  const [search, setSearch] = useState("");
  const [pendingSearch, setPendingSearch] = useState("");
  const [form, setForm] = useState<KbArticleFormState>(emptyKbArticleForm);
  const [errors, setErrors] = useState<KbArticleFormErrors>({});
  const [notice, setNotice] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: kbKeys.list(page, PAGE_SIZE, status, pendingSearch),
    queryFn: () => fetchKbArticles({ page, pageSize: PAGE_SIZE, status, search: pendingSearch }),
  });

  const createMutation = useMutation({
    mutationFn: (state: KbArticleFormState) =>
      createKbArticle({
        title: state.title.trim(),
        slug: state.slug.trim() || null,
        category: state.category.trim(),
        body_markdown: state.body_markdown.trim(),
      }),
    onSuccess: async (article) => {
      setForm(emptyKbArticleForm());
      setErrors({});
      await queryClient.invalidateQueries({ queryKey: kbKeys.all });
      setNotice(`Draft “${article.title}” created.`);
    },
    onError: (error: unknown) => {
      setNotice(`Could not create the article — ${errorMessage(error, "please try again.")}`);
    },
  });

  const publishMutation = useMutation({
    mutationFn: (articleId: string) => publishKbArticle(articleId),
    onSuccess: async (article) => {
      await queryClient.invalidateQueries({ queryKey: kbKeys.all });
      setNotice(`“${article.title}” is now published.`);
    },
    onError: (error: unknown) => {
      setNotice(`Could not publish — ${errorMessage(error, "please try again.")}`);
    },
  });

  const setField = <Key extends keyof KbArticleFormState>(key: Key, value: KbArticleFormState[Key]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationErrors = validateKbArticleForm(form);
    setErrors(validationErrors);
    if (Object.values(validationErrors).some((message) => Boolean(message))) return;
    createMutation.mutate(form);
  };

  const articles = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-sans text-3xl font-semibold tracking-tight text-charcoal sm:text-4xl">
          Knowledge base
        </h1>
        <p className="mt-1 text-sm text-charcoal/65">
          Publish self-help articles for the buyer help center. Drafts stay staff-only.
        </p>
      </div>

      {notice && (
        <div
          role="status"
          className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 shadow-xs"
        >
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="text-emerald-700/70 hover:text-emerald-900">
            Dismiss
          </button>
        </div>
      )}

      <form
        noValidate
        onSubmit={handleCreate}
        className={`${saleCardClasses} flex flex-col gap-4 p-5`}
        aria-label="Create knowledge base article"
      >
        <h2 className="text-sm font-semibold text-charcoal">New article</h2>
        {createMutation.isError && (
          <p role="alert" className="text-xs text-rose-700">
            {errorMessage(createMutation.error, "The article could not be created.")}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label htmlFor="kb-title" className={saleLabelClasses}>
              Title <span className="text-rose-500">*</span>
            </label>
            <input
              id="kb-title"
              type="text"
              maxLength={MAX_KB_TITLE_LENGTH}
              value={form.title}
              onChange={(event) => setField("title", event.target.value)}
              placeholder="How do I check my loan status?"
              className={`${saleInputClasses} mt-1`}
            />
            {errors.title && <p role="alert" className="mt-1 text-[11px] text-rose-700">{errors.title}</p>}
          </div>
          <div>
            <label htmlFor="kb-category" className={saleLabelClasses}>
              Category <span className="text-rose-500">*</span>
            </label>
            <input
              id="kb-category"
              type="text"
              list="kb-category-options"
              maxLength={MAX_KB_CATEGORY_LENGTH}
              value={form.category}
              onChange={(event) => setField("category", event.target.value)}
              placeholder="Payments, Loans, Documents…"
              className={`${saleInputClasses} mt-1`}
            />
            <datalist id="kb-category-options">
              {["Payments", "Loans", "Documents", "Possession", "Site visits", "General"].map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>
            {errors.category && <p role="alert" className="mt-1 text-[11px] text-rose-700">{errors.category}</p>}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="kb-slug" className={saleLabelClasses}>
              Slug <span className="text-charcoal/45">(optional)</span>
            </label>
            <input
              id="kb-slug"
              type="text"
              value={form.slug}
              onChange={(event) => setField("slug", event.target.value)}
              placeholder={form.title.trim() ? slugifyArticleTitle(form.title) : "derived-from-title"}
              className={`${saleInputClasses} mt-1`}
            />
            {errors.slug && <p role="alert" className="mt-1 text-[11px] text-rose-700">{errors.slug}</p>}
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="kb-body" className={saleLabelClasses}>
              Body (markdown) <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="kb-body"
              rows={6}
              maxLength={MAX_KB_BODY_LENGTH}
              value={form.body_markdown}
              onChange={(event) => setField("body_markdown", event.target.value)}
              placeholder={"## Steps\n\n1. Open the portal…"}
              className={`${saleInputClasses} mt-1 resize-y font-mono text-xs`}
            />
            {errors.body_markdown && (
              <p role="alert" className="mt-1 text-[11px] text-rose-700">{errors.body_markdown}</p>
            )}
          </div>
        </div>
        <div className="flex justify-end">
          <button type="submit" disabled={createMutation.isPending} className={salePrimaryButton}>
            {createMutation.isPending ? (
              <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
            ) : (
              <Plus aria-hidden="true" className="size-3.5" />
            )}
            <span>{createMutation.isPending ? "Saving…" : "Save as draft"}</span>
          </button>
        </div>
      </form>

      <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs">
        <div>
          <label htmlFor="kb-status-filter" className={saleLabelClasses}>
            Status
          </label>
          <select
            id="kb-status-filter"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as KbArticleStatus | "ALL");
              setPage(1);
            }}
            className={`${saleInputClasses} mt-1 min-w-32`}
          >
            <option value="ALL">All statuses</option>
            <option value="DRAFT">Drafts</option>
            <option value="PUBLISHED">Published</option>
          </select>
        </div>
        <form
          className="flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setPendingSearch(search);
            setPage(1);
          }}
          aria-label="Search articles"
        >
          <div>
            <label htmlFor="kb-search" className={saleLabelClasses}>
              Search
            </label>
            <input
              id="kb-search"
              type="search"
              maxLength={200}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="title or body text"
              className={`${saleInputClasses} mt-1 min-w-48`}
            />
          </div>
          <button type="submit" className={`${saleSecondaryButton} mb-0.5`}>
            <Search aria-hidden="true" className="size-3.5" />
            <span>Search</span>
          </button>
        </form>
      </div>

      {query.isError && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-xs">
          <AlertCircle aria-hidden="true" className="size-8 text-rose-500" />
          <h3 className="text-base font-semibold text-charcoal">Failed to load articles</h3>
          <p className="text-xs text-charcoal/60">
            {errorMessage(query.error, "A network or server error occurred.")}
          </p>
          <button type="button" onClick={() => void query.refetch()} className={saleSecondaryButton}>
            <RefreshCw aria-hidden="true" className="size-3.5" />
            <span>Try again</span>
          </button>
        </div>
      )}

      {query.isLoading && !query.isError && (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-charcoal/10 bg-white p-10 text-xs text-charcoal/65 shadow-xs">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          <span>Loading articles…</span>
        </div>
      )}

      {!query.isLoading && !query.isError && articles.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-charcoal/10 bg-white p-12 text-center shadow-xs">
          <div className="flex size-12 items-center justify-center rounded-full bg-charcoal/5 text-charcoal/60">
            <BookOpen aria-hidden="true" className="size-6" />
          </div>
          <h3 className="mt-3 text-base font-semibold text-charcoal">No articles yet</h3>
          <p className="mt-1 max-w-sm text-xs text-charcoal/60">
            Draft a how-to above, then publish it so buyers can find it in the help center.
          </p>
        </div>
      )}

      {!query.isLoading && !query.isError && articles.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-charcoal/10 bg-white shadow-xs">
            <table className="min-w-full text-left text-xs">
              <thead className="border-b border-charcoal/10 bg-[#FAFAF7] text-[10px] uppercase tracking-wider text-charcoal/55">
                <tr>
                  <th scope="col" className="px-4 py-3">Article</th>
                  <th scope="col" className="px-4 py-3">Category</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3">Updated</th>
                  <th scope="col" className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal/5">
                {articles.map((article) => (
                  <tr key={article.id} className="align-middle">
                    <td className="max-w-96 px-4 py-3">
                      <p className="font-semibold truncate text-charcoal" title={article.title}>
                        {article.title}
                      </p>
                      <p className="mt-0.5 truncate text-[10.5px] text-charcoal/50">/{article.slug}</p>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-charcoal/75">{article.category}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap ${kbArticleStatusTone(article.status)}`}
                      >
                        {article.status === "PUBLISHED" && <Globe aria-hidden="true" className="size-3" />}
                        {kbArticleStatusLabel(article.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-charcoal/70">
                      {formatDateTime(article.updated_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {article.status === "DRAFT" && (
                        <button
                          type="button"
                          onClick={() => publishMutation.mutate(article.id)}
                          disabled={publishMutation.isPending}
                          className={saleSecondaryButton}
                          aria-label={`Publish ${article.title}`}
                        >
                          <Globe aria-hidden="true" className="size-3.5" />
                          <span>Publish</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ApprovalPagination
            page={page}
            pageCount={pageCount}
            total={total}
            pageSize={PAGE_SIZE}
            itemName="articles"
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
