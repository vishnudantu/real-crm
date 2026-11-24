# PropFlow Capability Map — Present vs Planned (verified against HEAD)

**Verified on:** `main` @ `b81dbd9` (2026-11-24) plus the workstreams noted as IN FLIGHT.
**Rule:** this file is updated after every merge. "Done" means endpoint + real data
+ tests shipped; UI noted separately when it is only backend. No aspirational entries
are marked done. This is the anti-placeholder ledger the founder keeps asking for.

## Legend
✅ Shipped & tested · 🔶 Backend shipped, UI missing/partial · 🔧 In flight (assigned agent) · ⬜ Not started

## Module-by-module matrix (all 42 backend modules, verified 2026-11-24)

Endpoint counts are decorator counts on each module's routers. "Admin/sales UI" and
"buyer UI" are yes / no / partial based on whether a dedicated page exists in
`frontend/src`. Test files are representative, not exhaustive. This table is the
authoritative answer to "how many modules are complete and working": **42 modules,
41 with live endpoints, 397 API v1 routes, all backend + frontend suites green.**

| Module | Endpoints | Admin/sales UI | Buyer UI | Test file(s) | Honest note |
|--------|-----------|----------------|----------|--------------|-------------|
| auth | 9 | yes (login/profile) | yes | test_auth.py, test_authorization.py | UI complete |
| users | 11 | yes | no | test_users.py | UI complete |
| tenancy | 6 | partial (operator) | no | test_tenancy.py, test_tenant_isolation.py | Tenant lifecycle; operator UI |
| projects | 14 | yes | partial (fact sheet) | test_projects.py, test_facts.py | UI complete |
| leads | 11 | yes | no | test_leads.py | UI complete |
| conversations | 8 | yes | yes | test_conversations.py | UI complete |
| bookings | 19 | yes | partial (visits) | test_bookings.py, test_visit_evidence.py | UI complete |
| follow_ups | 8 | yes | no | test_follow_ups.py | UI complete |
| handoffs | 5 | yes | no | test_handoffs.py | UI complete |
| notifications | 6 | yes | no | test_notifications.py | UI complete |
| dashboard | 9 | yes | no | test_dashboard.py | UI complete |
| settings | 13 | yes | no | test_settings.py | UI complete |
| messaging | 11 | yes | no | test_messaging_flow.py, test_messaging_engine.py | UI complete |
| operator | 27 | yes (operator console) | no | test_operator_control_plane.py | Operator-only, not admin UI |
| connectors | 2 | partial | no | test_connectors.py | Backend + guided connect UI |
| integrations | 19 | yes | no | test_integrations*.py | UI complete |
| inventory | 14 | yes | no | test_inventory*.py | UI complete (unit map, holds, CSV) |
| inventory → intelligence | 5 | yes | no | test_inventory_intelligence.py + 5 unit files | UI complete (Module 20 dashboard) |
| billing | 4 | partial | no | test_billing.py | Razorpay webhooks; no dedicated admin page |
| postsales | 14 | yes | no | test_postsales*.py, test_receipt_integrity.py | UI complete (booking ledger) |
| construction | 5 | yes | no | test_construction.py | UI complete (milestones) |
| reconciliation | 5 | yes | no | test_reconciliation.py | UI complete |
| documents | 9 | yes | no | test_documents.py, test_document_pdf.py | UI complete (library + proof) |
| teamchat | 13 | yes | no | test_teamchat.py, test_team_chat.py | UI complete |
| service_desk | 18 | yes | no | test_service_desk.py | UI complete + KB |
| omnichannel | 11 | yes | no | test_omnichannel*.py | UI complete (inbox) |
| tenant_ai | 3 | partial | no | test_tenant_ai*.py | Per-tenant AI provider config |
| voice_intel | 5 | yes | no | test_voice_intel.py | UI complete (call intel) |
| connect_dialer | 8 | yes | no | test_connect_dialer.py | UI complete (dialer) |
| approvals | 4 | yes | no | test_approvals.py, test_approval_side_effects.py | UI complete |
| buyer_docs | 11 | partial (admin) | partial | test_buyer_docs.py | Buyer vault; buyer portal wiring partial |
| collections | 7 | yes | no | test_collections*.py | **UI added this branch** (command centre) |
| deal_desk | 10 | partial | no | test_deal_desk*.py | Backend + cost-sheet UI partial |
| executive | 2 | yes (cockpit) | no | test_executive*.py | Cockpit UI complete |
| handover | 21 | yes | partial | test_handover*.py | Handover/possession OS |
| solar | 5 | yes | no | test_solar_*.py | UI complete (Sun & Facing studio) |
| sales_floor | 3 | yes | no | test_sales_floor.py | My Day + war room UI |
| brokers | 5 | yes | no | test_brokers.py | UI complete (partner registry) |
| customers | 11 | yes | no | test_customers*.py | UI complete (directory, 360, merges) |
| ai_assistant | 2 | partial (embedded) | partial | test_ai_assistant.py, test_ai_assistant_unit.py | Grounded assistant; embedded in buyer/sales |
| messages | 1 | partial | partial | test_conversations.py | Message send; part of conversations |
| assistant | 0 | no | no | (library) | Library-only, no endpoints |
| plans | 0 | no | no | (library) | Library-only, plan catalog data |

**API-only (no dedicated UI page) — the honest gap list:**
- `billing` (Razorpay webhooks; limits enforced, no admin billing page)
- `assistant`, `plans` (library-only by design, not user features)
- `deal_desk` (backend complete; cost-sheet UI partial)
- `tenant_ai` (provider config; no standalone insights dashboard)
- `ai_assistant`, `messages` (embedded, not standalone pages)

Everything else has a dedicated admin/sales UI. Buyer-facing UI is intentionally
narrow (buyer dashboard, conversations, visits, fact sheet, document vault) — the
buyer property passport is still the accepted gap noted below.

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
