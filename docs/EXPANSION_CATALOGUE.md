# PropFlow Expansion Catalogue (canonical requirement register)

Status: requirement backlog, captured from product direction. Not a commitment
that any item is implemented. Each section lists the capability areas and the
current backend reality so workstreams can be scoped against what exists.

This register consolidates two sources the product owner supplied:
1. "PROPFLOW 2046 — Enterprise feature expansion catalogue" (75 numbered groups).
2. "PropFlow Connect / Voice Intelligence / BuyerVault / Architecture Studio /
   SunPath / WindLab / Vista / Building Intelligence / Environmental Intelligence /
   Immersive / Spatial AI / Property Data Factory / Unified Operational Controls /
   Enterprise Sidebar Additions" (14 modules).

Grounding rule for every item below: claims about what exists were verified by a
read-only pass over `backend/app/modules/*/router.py` and the relevant models.
Do not present a catalogue capability as shipped unless a route + tests back it.

---

## A. Already present in the backend today (verified)

- Operator console: tenants list/create/status/config/usage/health/impersonate,
  plans, feature flags, deployments, audit-logs, tenant onboarding.
- Leads CRM: create/list/get/patch/status/assign/opt-out, duplicate check.
- Bookings: visit-slot CRUD, schedule-custom, cancel/reschedule/status.
- Conversations, handoffs, follow-ups, notifications (full lifecycle).
- Projects + versioned facts with approve/reject and fact versions.
- Inventory: canonical units, holds lifecycle, availability map.
- Post-sales: sale bookings, payment plans, installments, append-only receipts,
  broker commissions, ledger.
- Documents: versioned templates, deterministic demand-letter + receipt PDFs,
  evidence proof, void-with-reason (commit 0e15689).
- Messaging: template + trigger-rule CRUD, transactional outbox,
  consent-at-dispatch, send-test.
- Omnichannel: WhatsApp/Instagram/Messenger inbox, channel credentials,
  browser calling via LiveKit (`CallRecord` room, join/end, recordings list).
- Call recordings: `CallRecording` model + list endpoint (LiveKit Egress or
  simulated provider), status + size, tied to a `CallRecord`.
- Settings, users, auth (refresh/revoke/reset), tenancy, billing summary +
  subscriptions + Razorpay webhook, central AI assistant chat.

## B. Partial — foundation exists, needs build-out

- Collections/demand: milestone demands + versioned demand docs exist; no
  scheduled trigger engine, no approval gate, no delivery callbacks.
- Receipts: append-only; no single-receipt GET, no void/reversal, no
  installment-update route (schema exists, unused).
- Customers/contacts: search/list/merge/opportunities; NO create/update endpoint.
- Calling: LiveKit browser room + recordings list exist; no inbound dialer/IVR/
  queues/transfer/hold/conference/disposition/DNC/wallboard/campaigns; no SIP or
  telephony-provider integration beyond LiveKit; no transcription.
- Inventory: flat units; no tower/floor/villa/commercial authoring, no unit
  field edit/delete.
- Site visits: status PATCH; no staff evidence/photo upload, no approval flow.
- AI: central provider settings; no per-tenant provider config, no insights
  layer, no agent registry/governance.
- Team chat: customer conversations exist; no internal team-chat module.

## C. Absent — net-new modules (nothing exists)

### Platform / operator
- Revenue command centre; predictive incident detection; infrastructure control;
  AI workforce control tower (agent registry, deployment studio, sandbox,
  authority matrix, kill switch, evaluation lab, cost-per-outcome).
- Enterprise SaaS revenue engine (usage-based pricing, contracts, revenue
  recovery, partner billing, forecasting, profitability, entitlement marketplace).
- Security & trust centre (SSO/SCIM/MFA, PAM, cryptographic audit evidence,
  retention engine, DR simulator, customer trust portal).

### Admin / organization
- Org & workforce OS (org designer, custom role studio, dynamic approval
  hierarchy, workload/skill assignment, capacity forecasting, org memory).
- Business process composer (visual builder, custom object/form/pipeline studio,
  policy compiler, versioned publishing, simulation, industry templates).
- Enterprise automation studio (universal event engine, long-running automation,
  replay, business calendar, human approval stations, outcome analytics).
- Enterprise collaboration hub (workspaces, decision threads, work orders,
  knowledge graph, secure external collaboration, commitment tracker).

### Sales
- Invisible CRM (auto activity capture, voice CRM, AI summaries, auto follow-ups,
  offline field mode, sales copilot).
- Buyer intent intelligence (intent twin, preference evolution, readiness,
  objection intelligence, affordability scenarios, compatibility engine).
- Autonomous sales recovery; intelligent sales floor; autonomous deal room.

### Marketing
- Marketing command centre (attribution, profitability, saturation, budget
  recommendations, launch simulator); autonomous marketing studio; growth lab.

### Property / inventory
- Living digital twin explorer; advanced inventory intelligence (revenue map,
  release strategy, pricing governance, conflict detection, scenario simulator).
- Land & title intelligence; city intelligence; climate & resilience.

### Construction
- Development feasibility studio; construction intelligence command centre;
  contractor & vendor OS; project quality & safety OS.

### Finance
- Banking & reconciliation (ingestion, matching, unidentified-payment cases,
  multi-account, refunds, gateway reconciliation, daily close, immutable audit).
- Financial pulse (cash-flow forecast, receivables aging, revenue recognition,
  unit profitability, what-if); loan & mortgage intelligence; enterprise
  financial control (budget-vs-actual, cost centres, maker-checker, tax engine,
  financial close, ERP/accounting hub).

### Legal / compliance
- Legal intelligence studio (agreement lifecycle, clause intelligence,
  obligations, litigation register); RERA compliance studio; registration
  mission control.

### Channel
- Broker network intelligence (360, relationship graph, lead protection,
  inventory portal, commission simulator); autonomous partner growth.

### Service / customer experience
- Omnichannel service desk + SLA + field dispatch; handover & possession OS;
  permanent property passport; resident & community OS; autonomous property care.

### Frontier AI
- AI agent organization; AI workforce builder; universal intent workspace;
  business time machine; business consequence engine; adversarial AI boardroom;
  reality & promise intelligence (promise ledger); simulation universe;
  self-improving business OS; market intelligence network; open property protocol.

### Role workspaces & experiences
- Dedicated workspaces (sales exec/manager, finance, inventory/pricing,
  marketing, construction, legal, CX, buyer/owner, broker, board/investor).
- Omnipresent field companion; intelligent customer decision room; immersive 3D/AR;
  knowledge & training OS; no-code app studio; integration marketplace;
  data-intelligence platform; fraud & anomaly intelligence; business continuity;
  website & credibility studio.

### PropFlow Connect (web calling & contact centre)
Beyond the existing LiveKit room: one-click/incoming dialer, real phone-number +
SIP integration, virtual numbers, caller ID + screen pop, dial pad, transfer,
conference, hold/resume, call queues, IVR builder, skill-based routing, missed-
call recovery, scheduled callbacks, campaigns, dispositions, DNC management,
call quality monitoring, continuity routing, live wallboard, supervisor
monitor/coach/escalate, agent availability, cost dashboard, provider failover.

### PropFlow Voice Intelligence (recording/transcription/AI analysis)
Recording controls (pause/resume), secure encrypted vault + retention, in-record
playback, audio timeline, recording search/export/access-audit/integrity hashes,
automatic + multilingual transcription, speaker identification, AI summary,
requirement/objection/commitment extraction, follow-up suggestions, call-to-
opportunity linking, call-quality review, real-time sales copilot, coaching
library, conversation-vs-approved-facts comparison, risk-statement alerts,
voice analytics, outcome verification, transcript corrections, consent evidence.

### PropFlow BuyerVault (buyer documents & identity)
Per-buyer document vault, configurable categories, identity (PAN) management,
joint-buyer docs, document request centre + checklists, buyer upload portal,
mobile camera upload, bulk upload, OCR extraction, verification status workflow,
rejection/resubmission, expiry reminders, version history, duplicate detection,
redaction, granular permissions, secure expiring share links, access history,
booking/agreement/loan/payment/registration/possession packs, document compare,
e-signature integration, completeness score, bank/legal limited access, tamper
alerts, retention, document Q&A assistant.

### PropFlow Architecture Studio (plans & media)
Master/tower/floor/unit/parking/amenity/landscape/elevation/interior/exterior/
360/video uploads, CAD/BIM/3D asset support, plan version control, approved-vs-
conceptual labeling, interactive viewer, clickable unit mapping, auto unit
recognition, area/dimension explorer, plan compare/annotation, plan-to-inventory
mapping, change-impact detection, visual approval routing, customer PDF export.

### PropFlow SunPath / WindLab / Vista / Environmental
Solar position + shadow/daylight modelling; wind climate + CFD + ventilation;
floor-wise views/sightlines/verified photography vs render toggle; noise/air/
heat/water environmental profiles. All require engineering validation gates and
clear measured-vs-modelled labeling. None exist.

### PropFlow Building Intelligence / Immersive / Spatial AI / Data Factory
Tower & unit digital identity + full specification registers; 3D/AR/VR buying
experience; natural-language spatial Q&A with evidence citations; architectural
import pipeline, geometry mapping, simulation job manager, engineering review
queue, confidence indicators, controlled publication, change propagation.

### Unified operational controls & enterprise sidebar
Call-to-360 / call-to-document / call-to-comparison / call-to-visit / call-to-deal;
document-to-transaction; floorplan-to-inventory; inventory-to-marketing;
drawing-to-promise; property-to-construction / ownership-passport; AI-to-human
approval; unified permission engine; unified search; unified audit timeline;
evidence-driven automation; and the sidebar/page structure for admin, sales
workspace, buyer portal, and operator console.

---

## Commercial model: per-module enablement + module-count pricing (product owner directive)

Every module can be enabled or disabled per tenant from the operator console,
and a customer's price depends on how many modules they have enabled.

**Foundation that already exists (verified):**
- `operator/features.py` `FEATURE_CATALOG`: 16 stable-keyed `FeatureSpec`s, each
  default-off unless stated, so new capabilities never auto-activate for tenants.
- `operator/feature_models.py` `TenantFeature`: per-tenant operator override
  (enabled flag, reason, set_by_email).
- Resolution order: operator override → plan `features` map → catalog default
  (`features.resolve_features` / `feature_enabled`).
- `operator/feature_gate.py`: dependency to enforce a feature at route level.
- `plans.Plan.features` JSON: what each plan bundles.

**Gaps to implement the module-count pricing model:**
1. Per-module pricing: `FeatureSpec` has no price field; `Plan` has a single flat
   `price_paise`. Add a per-feature price (paise) to the catalog and/or plan.
2. Price computation: a service that sums prices of the tenant's *enabled*
   modules into the invoice amount instead of a flat plan price.
3. Catalog growth: the 16 keys do not cover the new modules (documents, connect/
   voice, buyervault, architecture, spatial, etc.). Each new module must add a
   `FeatureSpec` and gate its router with the key as it ships. Documents
   currently has no feature gate.
4. Billing sync: recompute the Razorpay subscription/invoice amount whenever the
   operator changes a tenant's module set.

This is an extension of existing operator+billing scaffolding, not a rebuild.

---

## Sequencing guidance for the orchestrator

Immediate (actively blocking the user today):
1. customers: add `POST /contacts` + `PATCH /contacts/{contact_id}`; fix blank list.
2. postsales: single-receipt GET, receipt void/reversal, installment-update route.
3. inventory: unit field update/delete.
4. Documents admin UI (nav + list + download/proof/void + generate buttons) — the
   backend shipped in 0e15689 but has no frontend surface.

Next releases: messaging trigger rules for visit/booking confirmations; site-visit
evidence upload; approval workflow foundation (needed by many catalogue items);
per-tenant AI provider config. Then the larger net-new modules above, each as an
owned workstream with license review before adopting any external/open-source
component. Nothing in this register was fetched or vendored from GitHub.
