import { ChevronRight } from "lucide-react";
import type { SaleBookingItem } from "./salesBookingModel";
import { saleStatusBadgeClass, saleStatusLabel } from "./salesBookingModel";
import { formatInrCompact, formatShortDate, saleCardClasses } from "./salesBookingUi";

interface SalesBookingCardListProps {
  bookings: SaleBookingItem[];
  projectNameById: Record<string, string>;
  leadNameById: Record<string, string>;
  onOpen: (booking: SaleBookingItem) => void;
}

export function SalesBookingCardList({
  bookings,
  projectNameById,
  leadNameById,
  onOpen,
}: SalesBookingCardListProps) {
  return (
    <ul className="flex flex-col gap-3">
      {bookings.map((booking) => (
        <li key={booking.id} className={`${saleCardClasses} p-4`}>
          <button
            type="button"
            onClick={() => onOpen(booking)}
            className="flex w-full items-start justify-between gap-3 text-left"
            aria-label={`Open ledger for unit ${booking.unit_number}`}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="truncate text-sm font-semibold text-charcoal">
                  Unit {booking.unit_number}
                </h3>
                <span
                  className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${saleStatusBadgeClass(booking.status)}`}
                >
                  {saleStatusLabel(booking.status)}
                </span>
              </div>
              {booking.configuration && (
                <p className="mt-0.5 text-[11px] text-charcoal/55">
                  {booking.configuration}
                </p>
              )}
              <dl className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <dt className="text-charcoal/55">Buyer</dt>
                  <dd className="mt-0.5 truncate font-medium text-charcoal">
                    {leadNameById[booking.lead_id] ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-charcoal/55">Project</dt>
                  <dd className="mt-0.5 truncate font-medium text-charcoal">
                    {projectNameById[booking.project_id] ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-charcoal/55">Booked on</dt>
                  <dd className="mt-0.5 font-medium text-charcoal">
                    {formatShortDate(booking.booked_on)}
                  </dd>
                </div>
                <div>
                  <dt className="text-charcoal/55">Consideration</dt>
                  <dd className="mt-0.5 font-semibold text-charcoal">
                    {formatInrCompact(booking.consideration_paise)}
                  </dd>
                </div>
              </dl>
            </div>
            <ChevronRight
              aria-hidden="true"
              className="mt-1 size-4 shrink-0 text-charcoal/40"
            />
          </button>
        </li>
      ))}
    </ul>
  );
}
