import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  BookCheck,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  Plus,
  RefreshCw,
} from "lucide-react";
import type { SalesLead } from "../../sales/api";
import { fetchLeads } from "../../sales/api";
import { fetchProjects } from "../api";
import { fetchSaleBookings } from "./salesBookingApi";
import type { SaleBookingItem, SaleStatus } from "./salesBookingModel";
import { CreateSaleBookingModal } from "./CreateSaleBookingModal";
import { BookingLedgerDrawer } from "./BookingLedgerDrawer";
import { SalesBookingFilters } from "./SalesBookingFilters";
import { SalesBookingTable } from "./SalesBookingTable";
import { SalesBookingCardList } from "./SalesBookingCardList";
import { salePrimaryButton, saleSecondaryButton } from "./salesBookingUi";

const PAGE_SIZE = 10;

export function SaleBookingsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<SaleStatus | "ALL">("ALL");
  const [projectId, setProjectId] = useState<string>("ALL");
  const [page, setPage] = useState(1);

  const [createOpen, setCreateOpen] = useState(false);
  const [openBooking, setOpenBooking] = useState<SaleBookingItem | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const showSuccess = (message: string) => {
    setSuccessMessage(message);
    window.setTimeout(() => {
      setSuccessMessage((prev) => (prev === message ? null : prev));
    }, 4500);
  };

  const { data: projectsData } = useQuery({
    queryKey: ["admin", "projects", "lookup"],
    queryFn: () => fetchProjects({ pageSize: 100 }),
  });
  const projects = projectsData?.items ?? [];
  const projectNameById = Object.fromEntries(
    projects.map((project) => [project.id, project.name]),
  );

  const { data: convertedLeadsData, isLoading: leadsLoading } = useQuery({
    queryKey: ["admin", "leads", "converted"],
    queryFn: async () => {
      const first = await fetchLeads({ page: 1, pageSize: 100, status: "CONVERTED" });
      const leads = [...first.items];
      const totalPages = Math.min(first.pages, 10);
      if (totalPages > 1) {
        const remaining = await Promise.all(
          Array.from({ length: totalPages - 1 }, (_, idx) =>
            fetchLeads({ page: idx + 2, pageSize: 100, status: "CONVERTED" }),
          ),
        );
        for (const chunk of remaining) leads.push(...chunk.items);
      }
      return leads;
    },
  });
  const convertedLeads: SalesLead[] = convertedLeadsData ?? [];
  const leadNameById = Object.fromEntries(
    convertedLeads.map((lead) => [lead.id, lead.full_name]),
  );

  const {
    data: bookingsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      "admin",
      "sale-bookings",
      { page, pageSize: PAGE_SIZE, search, status, projectId },
    ],
    queryFn: () =>
      fetchSaleBookings({
        page,
        pageSize: PAGE_SIZE,
        search,
        status,
        projectId,
      }),
  });

  const bookings = bookingsData?.items ?? [];
  const total = bookingsData?.total ?? 0;
  const totalPages = bookingsData?.pages ?? 1;
  const startIdx = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const endIdx = Math.min(page * PAGE_SIZE, total);

  const handleResetFilters = () => {
    setSearch("");
    setStatus("ALL");
    setProjectId("ALL");
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-sans text-3xl font-semibold tracking-tight text-charcoal sm:text-4xl">
            Sales Bookings
          </h1>
          <p className="mt-1 text-sm text-charcoal/65">
            Track post-sale payment plans, receipts, demand letters, and broker payouts.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className={salePrimaryButton}
          aria-label="Create a new sale booking"
        >
          <Plus aria-hidden="true" className="size-4" />
          <span>New booking</span>
        </button>
      </div>

      {successMessage && (
        <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 shadow-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 aria-hidden="true" className="size-4 shrink-0 text-emerald-600" />
            <span>{successMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-700/70 hover:text-emerald-900"
            aria-label="Dismiss notification"
          >
            Dismiss
          </button>
        </div>
      )}

      <SalesBookingFilters
        search={search}
        onSearchChange={(value) => {
          setSearch(value);
          setPage(1);
        }}
        status={status}
        onStatusChange={(value) => {
          setStatus(value);
          setPage(1);
        }}
        projectId={projectId}
        onProjectChange={(value) => {
          setProjectId(value);
          setPage(1);
        }}
        projects={projects}
        onReset={handleResetFilters}
      />

      {isError && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-xs">
          <AlertCircle aria-hidden="true" className="size-8 text-rose-500" />
          <h3 className="text-base font-semibold text-charcoal">
            Failed to load bookings
          </h3>
          <p className="text-xs text-charcoal/60">
            {(error as Error)?.message ?? "A network or server error occurred."}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className={saleSecondaryButton}
          >
            <RefreshCw aria-hidden="true" className="size-3.5" />
            <span>Try again</span>
          </button>
        </div>
      )}

      {isLoading && !isError && (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-charcoal/10 bg-white p-10 text-xs text-charcoal/65 shadow-xs">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          <span>Loading bookings…</span>
        </div>
      )}

      {!isLoading && !isError && bookings.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-charcoal/10 bg-white p-12 text-center shadow-xs">
          <div className="flex size-12 items-center justify-center rounded-full bg-charcoal/5 text-charcoal/60">
            <BookCheck aria-hidden="true" className="size-6" />
          </div>
          <h3 className="mt-3 text-base font-semibold text-charcoal">
            No sale bookings found
          </h3>
          <p className="mt-1 max-w-sm text-xs text-charcoal/60">
            {search || status !== "ALL" || projectId !== "ALL"
              ? "No bookings match the selected filters. Try widening your search."
              : "Create your first sale booking from a converted lead to start tracking the payment ledger."}
          </p>
          {(search || status !== "ALL" || projectId !== "ALL") && (
            <button
              type="button"
              onClick={handleResetFilters}
              className={`${saleSecondaryButton} mt-4`}
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {!isLoading && !isError && bookings.length > 0 && (
        <>
          <div className="hidden md:block">
            <SalesBookingTable
              bookings={bookings}
              projectNameById={projectNameById}
              leadNameById={leadNameById}
              onOpen={setOpenBooking}
            />
          </div>
          <div className="md:hidden">
            <SalesBookingCardList
              bookings={bookings}
              projectNameById={projectNameById}
              leadNameById={leadNameById}
              onOpen={setOpenBooking}
            />
          </div>

          {total > 0 && (
            <div className="flex flex-col items-center justify-between gap-3 rounded-2xl border border-charcoal/10 bg-white px-5 py-3.5 text-xs text-charcoal/70 shadow-xs sm:flex-row">
              <div>
                Showing <span className="font-semibold text-charcoal">{startIdx}</span> to{" "}
                <span className="font-semibold text-charcoal">{endIdx}</span> of{" "}
                <span className="font-semibold text-charcoal">{total}</span> bookings
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className={`${saleSecondaryButton} disabled:opacity-40`}
                  aria-label="Previous page"
                >
                  <ChevronLeft aria-hidden="true" className="size-3.5" />
                  <span>Previous</span>
                </button>
                <div className="px-2 text-xs font-semibold text-charcoal">
                  Page {page} of {Math.max(1, totalPages)}
                </div>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className={`${saleSecondaryButton} disabled:opacity-40`}
                  aria-label="Next page"
                >
                  <span>Next</span>
                  <ChevronRight aria-hidden="true" className="size-3.5" />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {createOpen && (
        <CreateSaleBookingModal
          convertedLeads={convertedLeads}
          onClose={() => setCreateOpen(false)}
          onCreated={async () => {
            setCreateOpen(false);
            await queryClient.invalidateQueries({
              queryKey: ["admin", "sale-bookings"],
            });
            showSuccess("Sale booking created.");
          }}
        />
      )}

      {openBooking && (
        <BookingLedgerDrawer
          booking={openBooking}
          leadName={leadNameById[openBooking.lead_id] ?? "Converted buyer"}
          projectName={projectNameById[openBooking.project_id] ?? "Project"}
          onClose={() => setOpenBooking(null)}
          onChanged={async (message) => {
            await queryClient.invalidateQueries({
              queryKey: ["admin", "sale-bookings"],
            });
            showSuccess(message);
          }}
        />
      )}

      {leadsLoading && convertedLeads.length === 0 && (
        <p className="sr-only" role="status">
          Loading converted leads…
        </p>
      )}
    </div>
  );
}
