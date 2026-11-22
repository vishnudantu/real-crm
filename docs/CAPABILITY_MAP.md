# PropFlow Capability Map — Present vs Planned (verified against HEAD)

**Verified on:** `main` @ `398fcf7` (2026-11-22) plus the workstreams noted as IN FLIGHT.
**Rule:** this file is updated after every merge. "Done" means endpoint + real data
+ tests shipped; UI noted separately when it is only backend. No aspirational entries
are marked done. This is the anti-placeholder ledger the founder keeps asking for.

## Legend
✅ Shipped & tested · 🔶 Backend shipped, UI missing/partial · 🔧 In flight (assigned agent) · ⬜ Not started

## Core platform (done)
✅ Multi-tenant shared-schema isolation (tenant_id on all business tables, tenant-claim JWT, scoped queries)
✅ Auth: Argon2 + JWT access/refresh/revoke + password reset + security_version + change-password
✅ Tenant branding & white-label UI (Manrope everywhere)
✅ Operator control plane: tenant lifecycle, plans, feature flags (17-key catalog), audit log,
  onboarding wizard, impersonation (900s, audited), usage meters, config patch, health checks
✅ Operator UI: Mission Control, Tenant 360 (branding/entitlements/usage/deployments), Audit Explorer
✅ Admin UI: grouped navigation, Settings deep-links (branding/AI/languages/reminders/assignment/
  messaging/widget/templates), My Account
✅ Website widget: per-tenant embed.js, session/chat/lead, DPDP consent gate, rate limits, AI replies
✅ AI assistant (Groq + OpenAI-compatible), fact-grounded, approved-facts only, tool: visit booking
✅ Messaging outbox with provider adapters + dispatch-time consent suppression
✅ Notifications & scheduled visit reminders
✅ Follow-ups, handoffs, conversations, bookings/visit slots (capacity-safe)
✅ Projects + versioned fact sheets with approve/reject
✅ Leads CRUD + dedup (OR normalized) + assignment + DPDP opt-out
✅ Meta Lead Ads: per-tenant IntegrationConnection, signature-verified webhook, OR-dedupe, evidence payload
✅ Portal email lead parsing
✅ Billing: Razorpay webhooks, subscriptions, period-correct plan limits
✅ Post-sales: bookings/plans/installments/append-only receipts with concurrency-safe MAX numbering
✅ Documents engine: versioned templates, pure-Python deterministic PDFs (demand letters + receipts),
  SHA-256 proof, tenant-safe download, void, outbox event integration
✅ Documents admin UI: library + proof drawer + issue buttons on the booking ledger
✅ Omnichannel: WhatsApp/Instagram/Messenger + web chat ingestion, encrypted per-tenant credentials,
  LiveKit + simulated calling with recording consent
✅ Customer graph backend: contacts/methods/opportunities, exact identity resolution, reversible merges
✅ Customer graph UI: directory, 360 timeline, stage board, merge center
✅ Inventory backend: canonical units, state machine, DB-enforced one-ACTIVE-hold-per-unit
✅ Inventory UI: SVG unit map, hold lifecycle actions, bulk CSV import with dry-run
✅ CI: backend matrix 3.12/3.13, frontend build + unit + Playwright E2E, Docker build, security scans

## In flight right now (assigned agents)
🔧 Customers: POST /contacts create + PATCH update + GET /customers/merges history
🔧 Postsales: GET single receipt, POST receipt void (reopen booking, void linked documents),
  PATCH installment (due_on/amount/status with constraints)
🔧 Inventory: PATCH unit (guard matrix locked-when-held/booked), DELETE only untouched DRAFT/APPROVED
🔧 Team chat: channels + members + unread counts + @mentions (backend + UI)
🔧 Integrations: guided Meta + Google Ads OAuth connect flows with health checks (resumed agent)

## Next workstream (queued, not started)
⬜ Buyer document portal + customer create/edit UI wiring
⬜ Per-tenant AI provider config UI + AI insights layer
⬜ Site-visit completion evidence (photo upload) + boss-approval for site-visit car
⬜ Project-type-aware inventory authoring (tower/floor vs plot vs suite)
⬜ Post-visit thank-you + booking-confirmation templates
⬜ Booking cancellation policy engine

## Longer-horizon catalogue (each an owned workstream when scheduled)
⬜ Service desk + SLA, knowledge base, CSAT
⬜ Construction milestones + evidence + construction-linked demand gating
⬜ Bank statement import + reconciliation confidence matching
⬜ Deal desk: cost sheets, offers, discount approval matrix
⬜ Custom role designer + delegation/OOO + approval policy engine
⬜ Channel partner OS (referral ownership, commission plans, payouts, disputes)
⬜ Buyer property passport (progress, documents, service)
⬜ Automation studio (versioned workflow engine + visual builder)
⬜ AI workforce registry + evaluations + kill switches
⬜ Business time machine (reality graph + point-in-time reconstruction)
⬜ Digital twin explorer + GIS
⬜ Field companion / offline capture
⬜ Custom object studio (business composer)
⬜ Marketplace / public developer API + outgoing webhooks
⬜ Executive scenario simulation + cash forecast
⬜ Board/investor read-only packs
⬜ SSO/SCIM/MFA, data-residency/DR, backup-restore verification

## Known accepted limitations (explicitly NOT faked)
- Buyer-scoped document download waits for buyer-passport; current docs are admin/sales-only.
- Demand letters: artifact issued + timestamp, not provider-accepted delivery proof.
- Meta page claim: no ownership verification call yet — required before public onboarding.
- `GET /deployments` list does not exist; the operator tab links to the audit log instead.
- StaticPool concurrency in SQLite tests required file-backed engines for true parallel semantics;
  those tests now document that explicitly.
- PDF writer is ASCII-only, single column, one font (non-Indic scripts need font embedding later).
- LiveKit calling is simulated until a tenant supplies a real server; UI marks this clearly.
