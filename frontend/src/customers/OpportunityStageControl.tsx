import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { updateOpportunity } from "./customersApi";
import { OPPORTUNITY_STAGES, OPPORTUNITY_STAGE_LABELS } from "./customersModel";
import type { Opportunity, OpportunityStage } from "./customersModel";
import { CustomerErrorBanner, customerInputClass } from "./CustomerUi";

export function OpportunityStageControl({ opportunity, compact = false, onUpdated }: {
  opportunity: Opportunity;
  compact?: boolean;
  onUpdated?: () => void;
}) {
  const queryClient = useQueryClient();
  const [selectedStage, setSelectedStage] = useState<OpportunityStage>(opportunity.stage);
  const [lossReason, setLossReason] = useState(opportunity.loss_reason ?? "");
  const [lossReasonError, setLossReasonError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: ({ stage, reason }: { stage: OpportunityStage; reason?: string }) => updateOpportunity(opportunity.id, {
      stage,
      ...(reason !== undefined ? { loss_reason: reason } : {}),
    }),
    onSuccess: (updated) => {
      setSelectedStage(updated.stage);
      setLossReasonError(null);
      void queryClient.invalidateQueries({ queryKey: ["admin", "opportunities"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "customers", "detail", opportunity.contact_id] });
      onUpdated?.();
    },
  });

  const saveStage = (stage: OpportunityStage, reason?: string) => {
    if (stage === opportunity.stage) return;
    if (stage === "LOST" && !reason?.trim()) {
      setLossReasonError("Enter a loss reason before moving this opportunity to Lost.");
      return;
    }
    setLossReasonError(null);
    mutation.mutate({ stage, ...(stage === "LOST" ? { reason: reason?.trim() } : {}) });
  };

  const submitLoss = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    saveStage("LOST", lossReason);
  };

  const isLost = opportunity.stage === "LOST";
  return (
    <div className="min-w-0 space-y-2" onClick={(event) => event.stopPropagation()}>
      <label className={`block text-xs font-semibold text-charcoal/65 ${compact ? "sr-only" : ""}`}>
        Opportunity stage
        <select
          aria-label={`Stage for opportunity ${opportunity.id}`}
          value={selectedStage}
          disabled={mutation.isPending}
          onChange={(event) => {
            const next = event.target.value as OpportunityStage;
            setSelectedStage(next);
            if (next === "LOST") return;
            saveStage(next);
          }}
          className={`${customerInputClass} mt-1.5 min-w-0 cursor-pointer py-2 text-xs font-medium`}
        >
          {OPPORTUNITY_STAGES.map((stage) => <option key={stage} value={stage}>{OPPORTUNITY_STAGE_LABELS[stage]}</option>)}
        </select>
      </label>
      {mutation.isPending && <p role="status" className="flex items-center gap-1.5 text-xs text-charcoal/55"><LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />Saving stage…</p>}
      {selectedStage === "LOST" && !isLost && (
        <form onSubmit={submitLoss} className="space-y-2 rounded-xl border border-amber-200 bg-amber-50/70 p-3">
          <label className="block text-xs font-semibold text-charcoal/70">Reason for loss
            <textarea required maxLength={500} rows={2} value={lossReason} onChange={(event) => setLossReason(event.target.value)} placeholder="Budget, timing, another property…" className={`${customerInputClass} mt-1.5 resize-none bg-white`} />
          </label>
          <button type="submit" disabled={mutation.isPending} className="rounded-lg bg-charcoal px-3 py-2 text-xs font-semibold text-ivory disabled:opacity-50">Confirm move to Lost</button>
        </form>
      )}
      {lossReasonError && <p role="alert" className="text-xs leading-5 text-rose-700">{lossReasonError}</p>}
      {mutation.isError && <CustomerErrorBanner error={mutation.error} fallback="The opportunity stage could not be changed. It may not be an allowed transition." />}
      {opportunity.loss_reason && <p className="text-xs leading-5 text-charcoal/55"><span className="font-semibold">Loss reason:</span> {opportunity.loss_reason}</p>}
    </div>
  );
}
