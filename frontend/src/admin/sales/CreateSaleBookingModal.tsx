import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LoaderCircle, Plus, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { errorMessage } from "../../shared/apiRequest";
import type { SalesLead } from "../../sales/api";
import { createSaleBooking } from "./salesBookingApi";
import type { SaleBookingItem } from "./salesBookingModel";
import {
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
  rupeesInputToPaise,
} from "./salesBookingUi";

const todayStr = () => new Date().toISOString().split("T")[0];

const createBookingSchema = z.object({
  leadId: z.string().min(1, "Select a converted lead."),
  unitNumber: z.string().trim().min(1, "Unit number is required.").max(64),
  configuration: z.string().trim().max(100),
  carpetAreaSqft: z.string().trim(),
  considerationRupees: z
    .string()
    .trim()
    .min(1, "Consideration amount is required.")
    .refine(
      (value) => {
        const paise = rupeesInputToPaise(value);
        return Number.isFinite(paise) && paise > 0;
      },
      { message: "Enter a positive rupee amount, e.g. 7500000 or 75000.50." },
    ),
  bookedOn: z.string().trim(),
});

type CreateBookingFormValues = z.infer<typeof createBookingSchema>;

interface CreateSaleBookingModalProps {
  convertedLeads: SalesLead[];
  onClose: () => void;
  onCreated: (booking: SaleBookingItem) => Promise<void> | void;
}

export function CreateSaleBookingModal({
  convertedLeads,
  onClose,
  onCreated,
}: CreateSaleBookingModalProps) {
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateBookingFormValues>({
    resolver: zodResolver(createBookingSchema),
    defaultValues: {
      leadId: convertedLeads[0]?.id ?? "",
      unitNumber: "",
      configuration: "",
      carpetAreaSqft: "",
      considerationRupees: "",
      bookedOn: todayStr(),
    },
  });

  useEffect(() => {
    reset({
      leadId: convertedLeads[0]?.id ?? "",
      unitNumber: "",
      configuration: "",
      carpetAreaSqft: "",
      considerationRupees: "",
      bookedOn: todayStr(),
    });
  }, [convertedLeads, reset]);

  const mutation = useMutation({
    mutationFn: async (values: CreateBookingFormValues) => {
      const paise = rupeesInputToPaise(values.considerationRupees);
      const carpet = values.carpetAreaSqft.trim()
        ? Number(values.carpetAreaSqft)
        : null;
      return createSaleBooking({
        lead_id: values.leadId,
        unit_number: values.unitNumber.trim(),
        configuration: values.configuration.trim() || null,
        carpet_area_sqft:
          carpet && Number.isInteger(carpet) && carpet > 0 ? carpet : null,
        consideration_paise: paise,
        booked_on: values.bookedOn || null,
      });
    },
    onSuccess: async (created) => {
      await onCreated(created);
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to create sale booking."));
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Create sale booking"
        className="max-h-[90svh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              Create sale booking
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              Link a converted lead to a unit and record the consideration value.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close booking form"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <form
          noValidate
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="p-5"
        >
          {error && (
            <p
              role="alert"
              className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700"
            >
              {error}
            </p>
          )}

          {convertedLeads.length === 0 && (
            <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800">
              No converted leads are available. Convert a lead first to create a
              sale booking.
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label htmlFor="create-booking-lead" className={saleLabelClasses}>
                Converted lead <span className="text-rose-500">*</span>
              </label>
              <select
                id="create-booking-lead"
                className={saleInputClasses}
                {...register("leadId")}
              >
                <option value="">Select a converted lead…</option>
                {convertedLeads.map((lead) => (
                  <option key={lead.id} value={lead.id}>
                    {lead.full_name}
                    {lead.phone ? ` — ${lead.phone}` : ""}
                  </option>
                ))}
              </select>
              {errors.leadId && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.leadId.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="create-booking-unit" className={saleLabelClasses}>
                Unit number <span className="text-rose-500">*</span>
              </label>
              <input
                id="create-booking-unit"
                placeholder="A-1204"
                maxLength={64}
                className={saleInputClasses}
                {...register("unitNumber")}
              />
              {errors.unitNumber && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.unitNumber.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="create-booking-config"
                className={saleLabelClasses}
              >
                Configuration
              </label>
              <input
                id="create-booking-config"
                placeholder="3 BHK"
                maxLength={100}
                className={saleInputClasses}
                {...register("configuration")}
              />
              {errors.configuration && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.configuration.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="create-booking-carpet"
                className={saleLabelClasses}
              >
                Carpet area (sqft)
              </label>
              <input
                id="create-booking-carpet"
                inputMode="numeric"
                placeholder="1450"
                className={saleInputClasses}
                {...register("carpetAreaSqft")}
              />
              {errors.carpetAreaSqft && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.carpetAreaSqft.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="create-booking-consideration"
                className={saleLabelClasses}
              >
                Consideration (₹) <span className="text-rose-500">*</span>
              </label>
              <input
                id="create-booking-consideration"
                inputMode="decimal"
                placeholder="7500000"
                className={saleInputClasses}
                {...register("considerationRupees")}
              />
              {errors.considerationRupees && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.considerationRupees.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="create-booking-date"
                className={saleLabelClasses}
              >
                Booked on
              </label>
              <input
                id="create-booking-date"
                type="date"
                className={saleInputClasses}
                {...register("bookedOn")}
              />
              {errors.bookedOn && (
                <p className="mt-1 text-[11px] text-rose-600">
                  {errors.bookedOn.message}
                </p>
              )}
            </div>
          </div>

          <div className="mt-5 flex items-center justify-end gap-3 border-t border-charcoal/10 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting || mutation.isPending}
              className={saleSecondaryButton}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                isSubmitting ||
                mutation.isPending ||
                convertedLeads.length === 0
              }
              className={salePrimaryButton}
            >
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : (
                <Plus aria-hidden="true" className="size-3.5" />
              )}
              <span>{mutation.isPending ? "Creating…" : "Create booking"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
