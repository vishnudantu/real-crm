import { Eye } from "lucide-react";
import type { SaleBookingItem } from "./salesBookingModel";
import { saleStatusBadgeClass, saleStatusLabel } from "./salesBookingModel";
import { formatInrCompact, formatShortDate, saleSecondaryButton } from "./salesBookingUi";

interface SalesBookingTableProps {
  bookings: SaleBookingItem[];
  projectNameById: Record<string, string>;
  leadNameById: Record<string, string>;
  onOpen: (booking: SaleBookingItem) => void;
}

export function SalesBookingTable({
  bookings,
  projectNameById,
  leadNameById,
  onOpen,
}: SalesBookingTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white shadow-xs">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead className="border-b border-charcoal/10 bg-[#FAFAF7] text-[11px] uppercase tracking-wider text-charcoal/55">
            <tr>
              <th scope="col" className="px-4 py-3 font-semibold">Unit</th>
              <th scope="col" className="px-4 py-3 font-semibold">Buyer</th>
              <th scope="col" className="px-4 py-3 font-semibold">Project</th>
              <th scope="col" className="px-4 py-3 font-semibold">Booked On</th>
              <th scope="col" className="px-4 py-3 font-semibold">Consideration</th>
              <th scope="col" className="px-4 py-3 font-semibold">Status</th>
              <th scope="col" className="px-4 py-3 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-charcoal/5">
            {bookings.map((booking) => (
              <tr key={booking.id} className="hover:bg-charcoal/[0.02]">
                <td className="px-4 py-3">
                  <div className="font-semibold text-charcoal">
                    {booking.unit_number}
                  </div>
                  {booking.configuration && (
                    <div className="text-[11px] text-charcoal/55">
                      {booking.configuration}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-charcoal/75">
                  {leadNameById[booking.lead_id] ?? "—"}
                </td>
                <td className="px-4 py-3 text-charcoal/75">
                  {projectNameById[booking.project_id] ?? "—"}
                </td>
                <td className="px-4 py-3 text-charcoal/75">
                  {formatShortDate(booking.booked_on)}
                </td>
                <td className="px-4 py-3 font-semibold text-charcoal">
                  {formatInrCompact(booking.consideration_paise)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10.5px] font-semibold ${saleStatusBadgeClass(booking.status)}`}
                  >
                    {saleStatusLabel(booking.status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onOpen(booking)}
                    className={saleSecondaryButton}
                    aria-label={`Open ledger for unit ${booking.unit_number}`}
                  >
                    <Eye aria-hidden="true" className="size-3.5" />
                    <span>Ledger</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
