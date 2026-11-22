# PropFlow / KEYLO — Complete Project Brief

A single-source overview of what this product is, how it is architected, what is
already built and tested, and what remains to be built. Read this first.

---

## 1. What this project is

**PropFlow (working name KEYLO) is a real-estate operating system** for property
developers. It runs the full journey of a property business in one tenant-scoped
system: capturing buyer enquiries, scheduling site visits, managing canonical
inventory (towers/floors/units), converting a booking into a payment plan,
collecting money against installments, issuing demand letters and receipts as
verifiable documents, and giving operators (the platform owner) and admins (each
developer) a control plane.

The long-term vision is much larger — an "everything" catalogue spanning calling,
voice AI, buyer document vaults, architectural/media management, spatial
intelligence (sun/wind/views), immersive buying, construction, finance, legal,
channel partners, service/handover, and frontier AI. That catalogue is captured in
`docs/EXPANSION_CATALOGUE.md`. **The vision is multi-year; what is real and tested
today is the operational core**, and this document separates the two honestly.

### Design principles that distinguish it
- **Multi-tenant by construction.** Every domain row is tenant-owned and every
  query is tenant-scoped; cross-tenant access returns 404, never 403-with-data.
- **Evidence over assertions.** Money, documents, holds, and merges are backed by
  immutable rows, hashes, and audit trails — not by a status flag alone.
- **Consent at dispatch.** Outbound messages re-check lawful basis at send time.
- **No half-baked screens.** Each module is delivered end-to-end (model → migration
  → service → route → tests) before the next begins. No stub endpoints.

---

## 2. Local project paths

- **Repository root:** `C:\Users\vishn\KEYLO`
- **This working copy (worktree):** `C:\Users\vishn\KEYLO\.claude\worktrees\agent-abe08540e7a6f79b8`
- **Backend:** `<worktree>\backend`
- **Frontend (admin/customer/operator UIs):** `<worktree>\frontend` (owned by other agents)
- **Docs:** `<worktree>\docs`
- **Shared Python interpreter (venv):** `C:\Users\vishn\KEYLO\backend\.venv\Scripts\python.exe`

Branch of this worktree: `worktree-agent-abe08540e7a6f79b8`. Nothing is pushed;
all work is local commits on top of `main` (base `0bbf115`).

### Run the tests
```
cd <worktree>\backend
C:\Users\vishn\KEYLO\backend\.venv\Scripts\python.exe -m pytest tests -q
```

---

## 3. Technology & architecture

### Stack
- **Language:** Python 3.13
- **Web framework:** FastAPI (sync), Pydantic v2 schemas
- **ORM:** SQLAlchemy 2 (synchronous `Session`)
- **Migrations:** Alembic (batch mode for SQLite-safe alters; plain DDL on PostgreSQL)
- **DB:** PostgreSQL in production, in-memory SQLite (StaticPool) for the isolated test suite
- **Config:** `pydantic-settings` (`app/core/config.py`); secrets via env, never committed
- **Auth:** JWT access + refresh with server-side revocation; role-based dependencies
- **PDF generation:** dependency-free, pure-Python PDF 1.4 writer (no external PDF lib)

### Layout (monorepo, modular backend)
```
backend/
  alembic/versions/        # ordered migrations (revision id chains)
  app/
    main.py                # FastAPI app factory + lifespan (schedulers)
    api/v1/router.py       # composes all module routers under /api/v1
    core/                  # config, exceptions, logging, security, india helpers
    db/                    # base (naming conventions), session, tenancy (TenantOwned)
    modules/               # one folder per domain (see below)
  tests/
    conftest.py            # isolated SQLite engine, auth/header factories
    unit/  integration/
docs/                      # specs, blueprint, expansion catalogue
frontend/                  # admin/customer/operator apps (other agents)
```

### Module shape (consistent convention)
Each `app/modules/<name>/` contains `models.py` (SQLAlchemy, `TenantOwned`),
`schemas.py` (Pydantic v2), `repository.py` (tenant-scoped persistence),
`service.py` (business logic), `router.py` (FastAPI endpoints), `exceptions.py`
(HTTP-mapped errors). Every tenant table gets a composite `(tenant_id, id)` index
emitted automatically by an `after_parent_attach` listener in `db/tenancy.py`.

### Cross-cutting patterns
- **TenantOwned mixin:** adds `tenant_id` FK + `tenant` relationship; indexes auto-added.
- **Numbering:** financial/document numbers are allocated per tenant from the MAX
  existing sequence (never COUNT), under a PostgreSQL transaction-scoped advisory
  lock (process lock on SQLite) so concurrent writers never collide or reuse numbers.
- **Idempotency:** receipts (idempotency key) and documents (unique
  kind+reference+template_version) return the original row on replay.
- **Append-only money/events:** receipts and unit status events are never edited or
  deleted; corrections are new states (void, transition) that preserve history.
- **Messaging outbox:** domain changes enqueue `MessageDelivery` rows in the same
  transaction; a dispatcher claims, re-checks consent, sends, and records outcomes.
- **Feature flags:** operator catalog + per-tenant overrides gate modules; pricing
  is intended to depend on how many modules a tenant enables (design documented).

---

## 4. What is BUILT and TESTED (verified)

The full backend suite currently passes (**487+ tests** and growing). Below, the
modules marked **[this session]** were built/extended in the current worktree.

### Core operational spine (pre-existing)
- **Auth & users** — register/login/refresh/revoke, change/reset password, roles
  (ADMIN, SALES_EXECUTIVE, BUYER), user CRUD + status.
- **Tenancy & settings** — tenant config, feature resolution, reminders, templates,
  languages, audit-logs, broadcast.
- **Leads** — full CRUD, duplicate check, assignment, opt-out, status lifecycle.
- **Bookings / site visits** — visit-slot CRUD, capacity-controlled booking,
  schedule-custom, cancel/reschedule/status.
- **Conversations / handoffs / follow-ups / notifications** — full lifecycle.
- **Projects & facts** — project CRUD + versioned, approve/reject fact sheets.
- **Operator console** — tenants list/create/status/config/usage/health,
  impersonation, plans, feature flags, deployments, audit-logs, onboarding.
- **Messaging engine** — template + trigger-rule CRUD, transactional outbox,
  consent-at-dispatch, send-test, retries/backoff.
- **Omnichannel** — WhatsApp/Instagram/Messenger inbox, channel credentials,
  browser calling via LiveKit (`CallRecord` room + `CallRecording` list).
- **Billing** — subscription summary, plans, Razorpay webhook.

### Swarm-built modules (parallel agents, consolidated on branch `consolidation`)
Eight new backend modules were built in parallel by isolated-worktree agents and
merged onto a single consolidated branch, with one linear migration chain
(single head `f7a8b9c0d1e2`, single base `692d4e5b740f`):
- **Module-count pricing** (`7a0beea`) — per-module `monthly_price_paise`,
  `compute_tenant_monthly_pricing`, `GET /operator/tenants/{id}/pricing`.
- **Team chat** (`cac7f0c`) — staff channels/messages with membership + edit.
- **Approvals foundation** (`7fab0be`) — generic approval request state machine
  (PENDING/APPROVED/REJECTED/CANCELLED), admin-only decisions, no self-approval.
- **Bank reconciliation** (`fec2aba`) — bank transaction ingestion with
  (tenant,account,utr) duplicate protection + UTR-exact / unique-amount match
  suggestions (no auto-posting).
- **Brokers / channel partners** (`b3eaf04`) — broker registry + commission rollup.
- **Tenant AI provider** (`25d9843`) — per-tenant AI provider config with
  Fernet-encrypted keys and masked read-back; assistant falls back to central.
- **Voice intelligence** (`4efa124`) — call transcription + AI summary with a
  pluggable provider interface + deterministic fake (no real provider wired).
- **Service desk** (`2803c19`+`17a466f`) — support tickets with SLA map, breach
  queue, TCK MAX-sequence numbering, validated transitions.

### Documents engine — **[this session, commit `0e15689`]**
Versioned, numbered, verifiable documents with deterministic PDFs.
- `DocumentTemplate` (DEMAND_LETTER / RECEIPT / STATEMENT), versioned per tenant,
  using the same `{merge_tag}` syntax as messaging.
- `Document` rows: tenant-unique numbers from MAX sequence per kind
  (`DOC-DEMAND-000001`, `DOC-RECEIPT-…`), idempotent per
  (kind, reference, template_version), immutable `payload_snapshot` (bank account
  masked to last 4), `content_sha256`, DRAFT/ISSUED/VOIDED.
- **Pure-Python deterministic PDF 1.4 writer** (no external lib — none was installed):
  real xref table, Helvetica base font, escaped literals, fixed timestamp so bytes
  are reproducible, ASCII-only (₹→"Rs."), Indian digit grouping, word wrap + page
  breaks. Unit tests parse the bytes and validate every xref offset.
- Local storage under `DOCUMENTS_STORAGE_DIR` with per-tenant subfolder, uuid
  filenames, path-traversal guards, exclusive create; storage failure rolls back the
  DB row (no ISSUED document without bytes).
- 7 endpoints: issue demand-letter, issue receipt PDF, list, get, download
  (sha256 header; 410 voided with reason; 404 cross-tenant), void, proof.
- `postsales.send_demand_letter` now delegates here and still returns the
  Installment with `demand_letter_sent_at` (back-compat preserved).
- Migration `b4c5d6e7f8a9` validated upgrade+downgrade on isolated SQLite.

### Customers create/update — **[this session, commit `f8eb2a1`]**
Fixed the reported "unable to create or update customer" gap.
- `POST /customers` — create a canonical contact via deterministic identity
  resolution; idempotent on existing email/phone; never clobbers curated data.
- `PATCH /customers/{contact_id}` — update display_name, primary_language, notes,
  status. MERGED cannot be set directly (must go through merge); merged contacts
  are read-only.
- RBAC: admin or sales-executive (buyer 403); cross-tenant 404. 8 tests.

### Postsales receipt void + installment update — **[this session, commit `947a9f6`]**
- Receipt gains `status` (POSTED/VOIDED), `voided_at`, `voided_by`, `void_reason`;
  rows stay append-only (void marks, never deletes). Ledger aggregates count only
  POSTED receipts.
- `void_receipt` recomputes the parent installment's paid state and reopens a
  CLOSED booking when a void leaves an installment unpaid; idempotent; serialized.
- `GET /sales-bookings/receipts/{receipt_id}` single-receipt fetch.
- `POST /sales-bookings/receipts/{receipt_id}/void` (admin, reason required).
- `PATCH /sales-bookings/installments/{installment_id}` updates due date, amount,
  status; amount can't drop below collected; amount/due-date blocked once
  PAID/WAIVED.
- Migration `c5d6e7f8a9b0` validated on isolated SQLite. 7 tests.

### Inventory unit update/delete — **[this session, commit `4d98719`]**
- `PATCH /inventory/units/{unit_id}` edits mutable fields (configuration, tower,
  floor, position, areas, plot, facing, views, saleable, rera disclosure).
  `internal_code` is immutable; status changes stay on the state machine.
- `DELETE /inventory/units/{unit_id}` removes only DRAFT units with no hold and no
  linked booking; anything progressed must be CANCELLED via the state machine.
- 6 tests (45 inventory tests total pass).

### Supporting docs **[this session]**
- `docs/EXPANSION_CATALOGUE.md` (`3f0e591`, `c0b8c2c`) — the full vision catalogue
  as a Present/Partial/Absent register + the per-module enablement / module-count
  pricing model design.

---

## 5. What is PARTIAL (foundation exists, needs build-out)

- **Collections automation** — milestone demands + versioned demand docs exist; no
  scheduled trigger engine, no approval gate, no delivery callbacks.
- **Calling** — LiveKit browser room + recordings list exist; no inbound dialer,
  IVR, queues, transfer/hold/conference, dispositions, DNC, wallboard, campaigns,
  SIP/telephony beyond LiveKit, or transcription.
- **Inventory** — flat units; no tower/floor/villa/commercial project-type authoring.
- **Site visits** — status PATCH only; no staff evidence/photo upload, no approval flow.
- **AI** — central provider settings (`ai_provider`, `ai_api_key`); no per-tenant
  provider config, no insights/scan layer, no agent registry/governance.
- **Team chat** — customer conversations exist; no internal team-chat module.
- **Documents admin UI** — backend is complete; no frontend surface yet.
- **Per-module pricing** — enable/disable scaffolding exists; the
  "price = f(enabled modules)" computation and Razorpay sync are not implemented.

---

## 6. What is NOT built (net-new, from the vision catalogue)

Nothing exists for these; each is a separate workstream. Full list in
`docs/EXPANSION_CATALOGUE.md`.

- **PropFlow Connect** — web dialer, IVR, queues, transfers, DNC, wallboard, campaigns.
- **PropFlow Voice Intelligence** — recording vault, transcription, AI call analysis.
- **PropFlow BuyerVault** — buyer document vault, verification workflow, secure sharing.
- **PropFlow Architecture Studio** — master/tower/floor/unit plans, renders, CAD/BIM.
- **Spatial intelligence** — SunPath (sun/shadow), WindLab (wind/CFD), Vista (views),
  environmental intelligence.
- **Building Intelligence / Immersive / Spatial AI / Property Data Factory** — unit
  digital identity, 3D/AR buying, natural-language spatial Q&A, asset pipelines.
- **Sales OS** — invisible CRM, buyer-intent twin, autonomous recovery, deal room.
- **Marketing / Growth** — campaign command centre, attribution, experiment lab.
- **Construction OS** — feasibility, construction twin, contractor/vendor, quality/safety.
- **Finance OS** — bank ingestion + reconciliation matching, cash-flow forecast,
  loan/mortgage, enterprise financial control (budget-vs-actual, maker-checker, ERP hub).
- **Legal / RERA / Registration** — agreement lifecycle, compliance studio, registration.
- **Channel partners** — broker 360, commission simulator/statements, partner growth.
- **Service / Handover / Community** — service desk + SLA, possession OS, property
  passport, resident/community OS, predictive maintenance.
- **Frontier AI** — agent organization, workforce builder, universal intent workspace,
  business time machine, consequence engine, adversarial boardroom, promise ledger,
  simulation universe, self-improving OS.
- **Role workspaces, field companion, decision room, 3D/AR, training OS, no-code app
  studio, integration marketplace, data-intelligence, fraud/anomaly, business continuity,
  website/credibility studio.**

---

## 7. Sequencing / what happens next

Recommended order (each an owned, tested workstream):
1. **Documents admin UI** — frontend surface for the shipped backend (nav, list,
   download/proof/void, generate buttons on installments/receipts).
2. **Module-count pricing implementation** — per-module price field, sum-enabled
   computation, catalog growth with route gates, Razorpay recompute (operator+billing).
3. **Messaging trigger rules** for site-visit/booking confirmations.
4. **Site-visit evidence upload** + an approval-workflow foundation (prerequisite for
   many catalogue items: boss approvals, discount routing, demand sign-off).
5. **Per-tenant AI provider config** + an insights layer.
6. Catalogue slices in order: Connect dialer → Voice transcription → BuyerVault →
   Architecture Studio → Spatial Q&A (on the existing inventory + documents data).

### Parallelism note
One agent = one worktree = one module at a time. Parallel module builds require
orchestrator-spawned worktrees (separate working copies); sub-agents inside a single
worktree would collide on shared files.

---

## 8. Honest progress statement

Against the full ~90-module vision: **~10% is real and tested**, ~10% is partial
scaffolding, ~80% is unbuilt. The operational core that a developer uses daily is
largely working, and this session fixed the specific bugs reported (customers
create/update, receipt void/installment edit, inventory edit) and shipped the
documents engine. The catalogue is a multi-year, multi-team roadmap — the numbers
here deliberately avoid counting stubs as features.

---

## 9. Commits this session (newest first)

| Commit | Module | Notes |
|--------|--------|-------|
| `4d98719` | Inventory | unit field update + guarded delete |
| `947a9f6` | Postsales | receipt void lifecycle, receipt GET, installment update |
| `f8eb2a1` | Customers | contact create/update endpoints |
| `c0b8c2c` | Docs | per-module enablement + module-count pricing design |
| `3f0e591` | Docs | expansion catalogue requirement register |
| `0e15689` | Documents | versioned document engine with deterministic PDFs |

All commits are local on `worktree-agent-abe08540e7a6f79b8`; nothing pushed.
Backend suite: 487 passed at the postsales commit; inventory adds 6 (45 inventory
tests green).
