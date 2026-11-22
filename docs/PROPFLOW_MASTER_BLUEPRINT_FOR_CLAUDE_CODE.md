# PROPFLOW
## The Real Estate Intelligence Operating System
### Master repository review, technical remediation plan, product architecture, feature specification and Claude Code execution brief

**Prepared:** 21 November 2026  
**Repository:** https://github.com/vishnudantu/real-crm  
**Branch reviewed:** `main`  
**Reviewed revision:** `a7fa5163fb3c5ed6baeef96eb271ed7d6e9ff3db`  
**Status:** Product strategy and read only code review. This document is a build specification, not a claim that new features have been implemented.  
**Audience:** Claude Code, engineering, product, QA, design, security, founders.

---

# 0. MANDATORY INSTRUCTIONS TO CLAUDE CODE

You are taking over an **existing working repository**. Do not rebuild it from scratch, change its technology stack on impulse, or replace existing code with unverified scaffolding. The goal is to grow PropFlow into an exceptional, reliable, configurable, AI native platform for developers, broker networks, buyers, sales teams, finance teams and property owners.

**Working rules, in order of precedence:**

1. **READ THE EXISTING CODE FIRST.** Inspect the actual current `main` branch, run the existing application and test suite, inspect migrations, map data ownership and dependencies, and determine if this document's findings remain accurate. This document describes the reviewed November 21 snapshot; the repository may have changed.
2. **PRESERVE WORKING FUNCTIONALITY.** Existing leads, conversations, fact sheets, site visits, handoffs, follow ups, messaging, billing, SaaS operator, branding and post sales modules must remain operational.
3. **DO ONE IMPLEMENTATION SLICE AT A TIME.** Finish one cohesive vertical slice, including schema, APIs, UI, permissions, tests and documentation, before starting another. Do not create dozens of incomplete placeholders.
4. **PROTECT DATA.** Do not delete records, reset databases, run destructive migrations, or modify production secrets. Always provide tested migration and rollback procedures. Seed only explicitly designated development or test databases.
5. **KEEP THE ARCHITECTURE CONTROLLED.** Retain the current Python/FastAPI/SQLAlchemy/Alembic/PostgreSQL and React/TypeScript/Vite/Tailwind modular monolith. Add infrastructure only for a demonstrated requirement. No premature microservices rewrite.
6. **BACKEND ENFORCES AUTHORIZATION.** UI guards are not sufficient. Every tenant owned read, write, export, upload, background operation, websocket and AI action needs enforceable server side scope.
7. **AI DOES NOT OVERRIDE BUSINESS RULES.** Language models can recommend, extract, summarize and draft. Financial posting, binding offers, discounts, unit reservations, external messages and legal commitments require deterministic validation and the defined human approval policy.
8. **NO FALSE COMPLETION CLAIMS.** A file, route, button or component stub is not a finished feature. Provide test evidence and demonstration instructions at the end of each phase.
9. **NO MOCK CONNECTOR PRESENTED AS LIVE.** External services and payment providers need signed webhook verification, reconciliation, idempotency, retry handling, secrets management and a clearly labeled sandbox mode.
10. **ASK FOR PERMISSION BEFORE MATERIAL ACTIONS.** Do not deploy, alter external accounts, send messages to actual customers, charge customers, trigger paid APIs, move data to third parties or change live tenant data without explicit authorization.
11. **DESIGN FOR INDIA FIRST, GLOBAL BY CONFIGURATION.** RERA, GST, DPDP, WhatsApp, Indian financial conventions and multilingual journeys are essential, but market and regulatory assumptions must be configurable and verified rather than hardcoded.
12. **UPDATE THE WORK LOG.** After every completed slice, write: changes, impacted files, migrations, tests, screenshots or demo route, known limitations, risks, and the next single task.
13. **DO NOT GUESS.** If the actual code contradicts this specification, document the discrepancy and follow the current implementation safely. Do not fabricate integrations, metrics, compliance certifications or testing results.
14. **MAINTAIN A SINGLE SOURCE OF TRUTH.** Inventory, ledgers, customer identity, permissions and statuses must not diverge across screens, agents and services.

## First execution instruction

**Start with the P0 foundation audit and repair, not the flashy AI features.** Read `README.md`, `REPO_MAP.md`, `PROJECT.md`, `TECHNICAL_DESIGN.md`, `BUILD_SPEC.md`, the Alembic migrations, the active API routers and test suite. Execute backend pytest, frontend production build, frontend unit tests and browser tests where the environment allows. Produce a short `CURRENT_STATE_AUDIT.md` that identifies verified functionality, security/financial blockers, and implementation ordering. Then begin the single most important P0 fix with tests. Do not implement all roadmap phases in one pass.

---

# 1. EXECUTIVE PRODUCT MANDATE

## 1.1 The product we are building

**PropFlow is not just a real estate CRM. It is a Real Estate Intelligence Operating System.**

One platform should eventually run the business of developing, marketing, selling, financing, handing over and servicing real estate. It must understand **properties, people, relationships, commitments, money, approvals, communication and time** as connected, reliable data. Teams should not have to switch between a spreadsheet, WhatsApp, telephony dashboard, inventory diagram, marketing tools, payment ledger and a generic CRM to answer simple operational questions.

**North star:**

> Every property, person, commitment, transaction and decision is connected. PropFlow knows the business context, detects changes, recommends the next action, and executes authorized work with a full audit trail.

The phrase *20 years ahead* is a design ambition, not a promise of speculative technology. Win through unusually good workflow design, data trust, speed, automation, extensibility, explainable intelligence and a polished user experience.

## 1.2 What PropFlow must not become

- A collection of unrelated dashboards.
- A generic chatbot with access to customer data.
- A sales lead spreadsheet with a premium skin.
- A product with 100 toggles and no coherent workflows.
- A financial system that can double allocate a unit or misstate outstanding balances.
- A multi tenant SaaS product where organizations can see each other's records.
- An AI agent that quietly sends messages or changes prices without permission.
- A product sold as legally compliant merely because it has a consent checkbox.
- An application depending on one founder or one vendor's API keys for all tenants.

## 1.3 Target customers

1. **Residential developers:** single project, multiple projects, plotted developments, villas, apartments, townships, premium and luxury developments.
2. **Commercial developers:** offices, shops, commercial complexes, warehouses and mixed use assets, where the domain models support them.
3. **Real estate sales organizations:** internal sales, external sales partners and channel partner networks.
4. **Enterprise developer groups:** multiple brands, legal entities, locations, projects, portfolios and business units.
5. **Buyers and allottees:** individuals, family co buyers, NRIs, investors and institutional buyers, with appropriate lawful handling.
6. **Future adjacency:** property management, leasing, rentals, owner associations, referral networks and property aftercare. These are future modules, not reasons to destabilize the sales foundation.

## 1.4 Key competitive requirement

Match fundamental operational coverage before positioning intelligence as differentiation. Relevant classes of competing software include established real estate CRMs, sales and marketing automation suites, developer ERPs, channel partner tools and customer portals. Concrete products to benchmark include Sell.Do, Buildesk and LeadSquared where relevant, as well as more general CRM and customer experience leaders. Verify their current features before making marketing claims.

---

# 2. CURRENT REPOSITORY BASELINE

## 2.1 Verified codebase facts

At the reviewed revision, the repository has approximately **489 tracked files** and a Python backend organized into **19 functional module router areas**. The stack is:

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, React Hook Form, Zod, Lucide, Framer Motion.
- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic, Alembic.
- **Persistence:** PostgreSQL for intended production use, SQLite for some local testing/development.
- **AI:** Groq plus an OpenAI compatible client abstraction.
- **Infrastructure:** Docker Compose, backend pytest, frontend Playwright and Node based unit tests, GitHub Actions CI.
- **Business model:** Shared schema multi tenancy with `tenant_id`, tenant branded workspaces and a separate operator control plane.

The GitHub Actions run for reviewed commit `a7fa516...` completed successfully on November 21, 2026. Its Python 3.13 job output reports **292 passing tests**, and its Python 3.12, frontend build and Docker image build jobs also reported success. **This does not establish production readiness or prove that browser tests and external integrations pass.**

Evidence:

- Repository: https://github.com/vishnudantu/real-crm
- CI run: https://github.com/vishnudantu/real-crm/actions/runs/44921085472
- API composition: `backend/app/api/v1/router.py`
- Frontend routes: `frontend/src/App.tsx`
- Backend modules: `backend/app/modules/`
- Current migrations: `backend/alembic/versions/`

## 2.2 Existing modules worth preserving

| Domain | Existing implementation | Direction |
|---|---|---|
| Authentication | JWT login, refresh tokens, revocation, password reset, roles | Extend with MFA, scoped permissions and stronger tenant identity |
| Tenancy | Tenant entities, shared schema partitioning, white label settings | Extend with enterprise org hierarchy, isolation tests and tenant provisioning maturity |
| Projects | Project records, fact sheets, approved facts and versions | Extend to full property hierarchy and document knowledge |
| Leads | Intake, status, assignment, duplicate checks, search | Re model into contacts + interests/opportunities while preserving API compatibility |
| Conversations | Buyer conversations and messages | Extend to a unified, channel independent interaction timeline |
| AI assistant | Fact grounded answers, visit tools, provider abstraction | Extend to controlled agent orchestration and evidence grounded outputs |
| Site visits | Slot allocation, capacity enforcement, reschedule, cancellation | Extend to route planning, virtual visits, check in, feedback and visit ROI |
| Follow ups | Scheduling, due and overdue states | Extend to next best action and workflow rules |
| Handoffs | AI to executive transfer with summary | Extend to supervisor escalations and workload routing |
| Messaging | Templates, trigger rules, provider adapters, outbox | Add inbound messaging, delivery receipts, consent gates and reliable workers |
| Notifications | Internal notifications and scheduled visit reminders | Add preference center, reliability metrics and omnichannel rules |
| Dashboard | Conversion and source metrics | Extend to metric catalog, attribution, inventory and financial intelligence |
| Connectors | Meta leads, property portal email parsing | Add durable integration installation/configuration and health monitoring |
| Post sales | Sale bookings, installment plans, receipts, commissions | Harden financial controls and extend to contracts, reconciliation and handover |
| Billing | Razorpay webhook path, subscriptions, limits, invoices | Correct metering and production subscription lifecycle handling |
| Operator | Tenant management, plans, audit and provisioning | Extend to customer success operations, feature entitlements and support access policies |
| Settings | Templates, system settings, audit log | Extend with versioned, tested configuration and approval rules |

## 2.3 Current UX footprint

The reviewed React app provides public pages and buyer, sales, admin and SaaS operator areas. The sales area includes dashboard, leads, conversations, visits, follow ups, notifications and profile. Admin includes users, projects, visits, analytics, sale bookings, settings and audit. Buyer includes project information, conversations, visits and profile. Operator includes tenants, plans, users and audit.

**Important:** The presence of a route or module does not mean it is fully production complete. Confirm it end to end.

---

# 3. CODE REVIEW FINDINGS AND REQUIRED REMEDIATIONS

The findings below are based on **source inspection**, not runtime exploitation or a penetration test. Treat them as engineering hypotheses to reproduce and fix. Validate against the current branch before editing.

## P0. Financial and inventory integrity

### P0.1 No authoritative unit inventory and enforceable unique sale reservation

**Observed:** `SaleBooking` stores a `unit_number` string. The reviewed sale booking flow validates that a converted lead has not already been booked, but does not lock and reserve an authoritative unit record. See:

- `backend/app/modules/postsales/models.py`
- `backend/app/modules/postsales/service.py` (`create_booking`)

**Risk:** Multiple customers can potentially be associated with the same physical unit; unit identifiers are not a safe inventory ledger.

**Required fix:** Introduce an explicit `property_units` domain, unique property identity, reservation/hold lifecycle, concurrency safe transition, sale booking reference to `unit_id`, database constraints and transactional idempotency. Do not merely add a frontend color coded grid. Migration must preserve legacy `unit_number` and map or quarantine ambiguous records for human reconciliation.

**Tests:** simultaneous hold requests, simultaneous booking requests, hold expiry, rebooking after cancellation, permissions, tenant isolation, duplicate requests and rollback on payment/document failure.

### P0.2 Receipt ID allocation and installment balance concurrency

**Observed:** `record_receipt()` constructs an ID from `count(receipts)+1`, then computes outstanding and posts without explicit per installment locking.

- `backend/app/modules/postsales/service.py` (`record_receipt`, approx. lines 161 to 226)

**Risk:** Two concurrent requests can issue the same receipt number and/or race on remaining installment balance.

**Required fix:** Use a tenant scoped atomic sequence/counter, database row locks or serializable strategy where justified, idempotency key, immutable posting event and separate void/reversal rather than editing the original financial event. Reconcile totals from postings.

**Tests:** parallel receipt requests, partial payment, overpayment rejection, retrying the same payment webhook, reverse/void lifecycle, ledger consistency.

### P0.3 Demand letters are tracked as sent, not proven delivered documents

**Observed:** `send_demand_letter()` marks `demand_letter_sent_at`. There is no demonstrated generated artifact, signed dispatch evidence or receipt proof in this function.

- `backend/app/modules/postsales/service.py` (`send_demand_letter`)

**Required fix:** A versioned template + generated document + immutable snapshot + approved sender + outbound event + delivery receipt + failure handling. Do not set sent status until transmission is accepted by the outbound provider; distinguish queued, sent, delivered, opened, failed and acknowledged where the provider supports these states.

## P0. Data privacy and outbound communication

### P0.4 Recheck consent at actual dispatch time

**Observed:** The outbound worker processes queued `MessageDelivery` records without an explicit fresh recipient consent check. A lead can opt out after a trigger is queued.

- `backend/app/modules/messaging/dispatcher.py`

**Required fix:** Before provider calls, resolve linked customer/lead and verify current lawful purpose, consent or other valid legal basis, opt out, channel preference, time window and do not contact status. Record decision and suppression reason. Stop or cancel pending sends after opt out where applicable. Transactional outbox alone is not a consent engine.

**Tests:** opt out after queueing, before dispatch, in between retries, on one channel only, after lead merge and during tenant suspension.

### P0.5 Do not manufacture source consent

**Observed:** Connector ingestion uses `consent_to_contact=True` while constructing the lead, without an evidence record in that function.

- `backend/app/modules/connectors/service.py`

**Required fix:** Ingest source consent evidence as metadata, distinguish permission to process a lead from permission for a marketing channel, map the actual lead form agreement, maintain source and timestamp, and suppress unproven or disallowed outbound campaigns. Obtain counsel reviewed India DPDP rules and telecommunications messaging policies before claiming compliance.

## P0. Integration defects and reliability

### P0.6 Meta page mapping lookup mismatch

**Observed:** The Meta webhook's `_active_project_for_meta` calls `session.get(SystemSetting, ("default", "meta_page_projects"))`. The setting primary key consists of `(tenant_id, key)`, where `tenant_id` is a UUID. This appears inconsistent and may prevent correct routing.

- `backend/app/modules/connectors/router.py`
- `backend/app/modules/settings/models.py`

**Required fix:** Dedicated `integration_connections` and `integration_project_mappings` keyed by tenant + provider + external account/page/form. Validate page ownership. Verify signatures using the right app secret. Store durable event IDs and payload metadata. Implement provider token management and expiry alerts.

### P0.7 Connector duplicate logic and identity semantics

**Observed:** `ingest_lead` builds conditions from email and phone and sends all into `.where(*conditions)`. When both exist, a record must match both to be treated as duplicate. The core lead duplicate checker uses OR matching instead. The connector and main intake therefore disagree.

- `backend/app/modules/connectors/service.py`
- `backend/app/modules/leads/repository.py`

**Required fix:** Centralized identity resolution. But do not blindly merge all matching phone numbers: family members can share a number, and two people can share an agency email. Provide confidence score, match evidence, merge preview, reversible merge linkage, household relationships and human review for uncertain matches.

### P0.8 Billing limits are not per period

**Observed:** `ensure_within_plan_limits()` counts all leads and sent WhatsApp messages when comparing to fields named `leads_per_month` and `whatsapp_msgs_per_month`.

- `backend/app/modules/billing/service.py` (`ensure_within_plan_limits`)

**Required fix:** Explicit subscription billing period and usage ledgers, limit checks against period specific records, atomic meter reservations and reconciliation with webhooks. Clarify what happens on downgrade and trial expiration.

### P0.9 Verify Razorpay event uniqueness and ordering

**Observed:** The webhook computes an event ID from provider ID, event type and timestamp and may create an invoice from captured payment data. Verify behavior when provider retries, sends out of order events or delivers different events with shared timestamps. There is no proof this is unsafe in all cases, but it merits a formal reconciliation test.

- `backend/app/modules/billing/service.py` (`process_webhook`)

**Required fix:** Prefer provider stable event IDs when supplied, capture raw signed events, make processing idempotent, model state transitions explicitly, protect against stale event regressions, and reconcile from provider transaction identifiers. Never treat a SaaS subscription payment and a buyer property installment as the same accounting ledger.

## P1. Platform structure and security

### P1.1 Global user email uniqueness blocks flexible multi tenancy

**Observed:** `User.email` is globally unique while each user also belongs to a tenant.

- `backend/app/modules/users/models.py`

**Consequence:** A consultant or salesperson using the same email for two developers cannot have two standard tenant memberships. This might be intentional today, but conflicts with future enterprise collaboration.

**Plan:** Introduce `identities`, `organizations`, `memberships`, and membership scoped roles. Unique email on identity; an identity can belong to multiple organizations. Handle tenant switch explicitly and keep all tokens tenant scoped. Do not change this before mapping current login and migration behavior.

### P1.2 Roles too coarse

Current built in roles are `BUYER`, `SALES_EXECUTIVE`, `ADMIN`, plus separate operator roles. Introduce policy based permissions and contextual scope. Distinguish owner, finance approver, legal, inventory manager, marketing lead, team leader, relationship manager, channel partner and customer. See Section 11.

### P1.3 Tenant isolation must cover every data path

The reviewed app uses tenant scoped services and has tenant isolation tests. That is a useful foundation. However, the `TENANT_TABLES` tracking set in `backend/app/db/tenancy.py` does not appear to include every newer domain table such as all messaging tables. Determine exactly how it is used before claiming a leak. Add automated schema introspection, negative access tests, association integrity constraints and background worker isolation tests. Consider PostgreSQL row level security as a second layer only after evaluating service and worker consequences.

### P1.4 Background messaging worker correctness

The outbox has idempotency keys and compare and swap claims, which is good. But the dispatcher performs provider network calls during a database session and appears to commit only after the batch, raising the operational question of concurrent claims, external side effects before durable commit, worker restart behavior and retries after an uncertain provider response. Redesign with explicit claim transaction, committed state, external send, completion transaction and provider idempotency where supported. Include dead letter queue, per provider circuit breaker, rate limits, costs and observability.

### P1.5 CI and deployment incomplete for production

The reviewed CI runs backend pytest, frontend compile/build and Docker build. It does not run the installed frontend unit and Playwright browser test scripts as part of that workflow. Current Docker Compose runs development servers and has demonstration defaults. Create separate dev, test, staging and production configurations, production secrets, TLS, security scanning, database backup testing, staged rollout and rollback gates.

### P1.6 Documents still refer to previous project identities

`PROJECT.md` and `TECHNICAL_DESIGN.md` contain older MVP language and Keylo references. Preserve historical documents if useful, but create a canonical up to date architecture and product documentation index. Do not make new engineers infer which spec controls the codebase.

## P1. Architectural data model problems

1. A tenant wide duplicate lead rejection is not a customer identity graph. One person may enquire about several projects and have several distinct opportunities.
2. Free form `unit_number` is not a normalized property inventory model.
3. Money requires separate immutable payment events, allocations, adjustments, refunds and bank reconciliation, not just a receipt table.
4. Tenant branding alone is not an enterprise organization hierarchy.
5. Project fact sheets need versioned provenance, approval state, effective dates and applicable scope to power trustworthy agent responses.
6. Event driven messages must distinguish internal domain events from channel specific outbound deliveries.
7. An audit log is not automatically a full change history. Sensitive entity changes need actor, before/after, reason, correlation ID and retention rules.

---

# 4. TARGET SYSTEM ARCHITECTURE

## 4.1 Six business operating systems

### A. Customer OS

Contacts, household relationships, lead events, buying interests, opportunities, identity resolution, consent, omnichannel history, customer engagement and personalized experiences.

### B. Property OS

Projects, legal entities, phases, plots, buildings, towers, floors, property units, specifications, GIS geometry, floor plans, imagery, pricing, inventory status and digital twin views.

### C. Revenue OS

Campaigns, sources, lead capture, attribution, routing, qualification, sales pipeline, visits, proposals, negotiations, forecasting, channel partner distribution and sales performance.

### D. Transaction OS

Holds, booking commitments, approvals, cost sheets, payment plans, collections, bank reconciliation, receipts, taxes, contracts, document signing, commissions, refunds and cancellations.

### E. Experience OS

Buyer portal, appointments, construction milestones, document vault, handover, snag management, support tickets, warranties, referrals and ownership experience.

### F. Platform OS

Organizations, memberships, roles, entitlements, billing, event log, workflow studio, integration marketplace, audit, security, data governance, configuration and operator tools.

**Cross cutting foundation:** data contracts, domain events, reliable jobs, authorization, observability, agent runtime, policy engine, design system and analytics metric catalog.

## 4.2 Preserve modular monolith; make boundaries explicit

Suggested module ownership over time:

```text
backend/app/
  core/               # shared configuration, security, errors, observability
  db/                 # SQLAlchemy session, transaction and tenancy primitives
  modules/
    auth/             # existing, evolve identities and sessions
    tenancy/          # existing, evolve organizations and memberships
    users/            # existing, evolve policy based access
    customers/        # NEW canonical people, household, identities
    opportunities/    # NEW one customer to many project interests
    projects/         # existing, extend project hierarchy
    inventory/        # NEW authoritative units, availability, holds
    pricing/          # NEW price lists, offers, discounts, snapshots
    leads/            # existing, evolve lead events and acquisition
    conversations/    # existing, unified interaction records
    communications/   # NEW inbound channels, phones, email, consent
    messaging/        # existing outbox and provider delivery
    bookings/         # existing SITE VISITS, not property sale bookings
    postsales/        # existing sale bookings and payment plans
    collections/      # NEW immutable money ledger and reconciliation
    documents/        # NEW document generation, templates and signatures
    partners/         # NEW broker firms, people, referrals, commissions
    approvals/        # NEW policy driven approval engine
    workflows/        # NEW durable automation execution
    events/           # NEW typed domain event catalog and outbox
    analytics/        # NEW metric catalog, derived measures, attribution
    ai_assistant/     # existing buyer assistant, extend carefully
    agents/           # NEW bounded agent orchestration and evaluations
    support/          # NEW customer issues, handover, warranties
    integrations/     # NEW durable OAuth and provider connections
    connectors/       # existing lead intake adapters
    billing/          # existing SaaS billing, do not mix with buyer money
    operator/         # existing SaaS operations
    settings/         # existing tenant settings and audit
```

These are **logical boundaries**. Do not generate all of them as empty directories. Create a real module only when its first vertical slice is implemented.

## 4.3 Runtime building blocks

| Capability | Initial choice | When to extend |
|---|---|---|
| Primary transactional database | PostgreSQL | Scale vertical first; partition hot tables later based on evidence |
| API | FastAPI REST, OpenAPI | Add realtime channels only when user experience needs them |
| Frontend | Existing React + TypeScript | Maintain shared patterns, routes and type safety |
| Database migrations | Alembic | Keep forward and backward compatible phased deployments |
| Background jobs | Explicit durable job/outbox worker | Add Redis/BullMQ equivalent or Python task queue only if load needs it; avoid two competing queue systems |
| Event schema | Typed versioned domain events | Add broker only when throughput/ownership merits it |
| Search | PostgreSQL full text + trigram where appropriate | Dedicated search engine when scale and query complexity justify |
| Geographic | PostGIS for spatial inventory where required | Avoid approximating legal plot geometry with arbitrary pixels |
| Asset storage | Tenant scoped encrypted object storage | Signed URLs, virus scan, access expiry, lifecycle retention |
| Caching | Tenant scoped cache with invalidation strategy | Never cache authorization or stale inventory as authoritative truth |
| Analytics | Reproducible warehouse export/derived tables | Separate analytical database at meaningful data volumes |
| LLMs | Existing provider abstraction | Route by task, quality, latency, cost and data policy |
| Observability | OpenTelemetry compatible traces, logs, metrics | Correlate agent actions, API, database and delivery providers |
| Feature flags | Server controlled, tenant scoped | Progressive exposure, paid entitlements and safe rollbacks |

## 4.4 General architectural rules

- Transactional commands execute in explicit units of work.
- Publish domain events after or within the same transaction via a transactional outbox; do not publish unsaved changes.
- Consumers process events idempotently and record completion/failure.
- Commands and queries have authorization and tenant context at the service boundary.
- Use tenant scoped uniqueness for tenant owned business entities.
- Avoid cross tenant foreign keys by enforcing composite references or service checks; verify with automated tests.
- Maintain an immutable business activity timeline that can explain major decisions and state changes.
- Use optimistic concurrency for most edits and row level locks for scarce resources like property holds and payment allocation.
- Every public write endpoint needs abuse controls, identity checks, request size limits and rate limiting.
- Separate AI generated assertions from verified facts, estimates and external third party data.

---

# 5. CANONICAL DATA MODEL AND MIGRATIONS

## 5.1 Identity and customer graph

Create the following concepts **without deleting current `leads`**:

**`people` or `contacts`**: canonical customer identity within a tenant, normalized names, locale, preferred communication, privacy status, external references, created/updated metadata.

**`contact_methods`**: email, phone, messaging address, verification state, normalization, preferred status, validity and source.

**`customer_relationships`**: spouse, household member, co buyer, attorney, authorized representative, referral relationship; consent and access rights vary by relationship.

**`opportunities`**: one contact/household to one project/property need; configuration, budget, timeline, purchase purpose, source, stage, owner and probabilities. One contact can have several opportunities.

**`lead_events`**: individual enquiries or captures with form, campaign, UTM, referrer, click IDs and originating integration. Multiple enquiry events can attach to one customer and different opportunities.

**`contact_merge_history`**: merge actor, reason, evidence, source and destination IDs, event timestamp, merge reversibility, deduplicated methods and dependent mapping.

**`consent_events`**: data purpose, channel, source, legal basis, accepted/revoked timestamp, policy version, evidence reference and contact identity. Store only necessary evidence, secured appropriately.

**`interaction_events`**: inbound/outbound calls, WhatsApp, email, SMS, site visit interactions, notes and support interactions with channel, participants, timestamp, source and provenance.

### Data migration approach

1. Add new tables and nullable cross references.
2. Backfill one contact identity per existing lead unless reliable matching evidence supports safe grouping.
3. Create one initial opportunity per existing lead.
4. Keep existing lead API read and write compatibility until the frontend is migrated.
5. Add adapters and dual read validation, not uncontrolled dual writes.
6. Establish a clear system of record, migrate screens and tools, then deprecate old semantics in stages.
7. Make customer merge reversible through recorded mapping and review when appropriate.
8. Test with multiple projects, shared phone numbers, existing site visits and sale bookings.

## 5.2 Property model

Minimum normalized hierarchy:

```text
Tenant
  Organization / Legal Entity
    Portfolio / Brand
      Project
        Phase / Development Section
          Building / Tower / Block (when applicable)
            Floor (when applicable)
              Unit
        Plotted Layout / Survey Block (when applicable)
          Plot / Parcel Unit
```

Key proposed entities:

- `projects`: extend existing safely with region, developer legal entity, coordinates, sale type, project lifecycle and publication.
- `project_phases`: phase hierarchy, launch status, approval data and milestone dates.
- `property_units`: immutable internal ID, human friendly display ID, unit category, typology, dimensions, floor/tower/plot location, sale eligibility, availability, orientation, views, area definitions, amenities, parking, associated drawings, geo reference and current version.
- `unit_status_events`: immutable chronological transitions and reasons.
- `unit_holds`: unit, opportunity, actor, expiry, ownership, channel, hold reason, state and idempotency key.
- `unit_reservations`: binding reservation record with approval, amount/terms and expiration.
- `unit_media`: photos, floor plan, RERA approved layouts, virtual tours, video and source metadata.
- `price_books`: effective dated versions by project, phase, unit class and allowed audience.
- `unit_price_versions`: price by component including base, floor rise, orientation, amenities and taxes where relevant; effective timestamps and approval evidence.
- `unit_cost_sheets`: immutable customer facing proposal snapshots and versioned line item computation.
- `property_location_geometry`: geospatial objects with provenance and a clear distinction between illustrative layout geometry and surveyed/legal geometry.

**Unit state examples:** `DRAFT`, `NOT_RELEASED`, `AVAILABLE`, `HELD`, `RESERVED`, `BOOKED`, `AGREEMENT_PENDING`, `SOLD`, `CANCELLED`, `BLOCKED`, `OFF_MARKET`. Explicitly define allowed state transitions and authorized actors. Do not assume `CANCELLED` means inventory instantly becomes available; rules differ for refunds, legal hold and management approval.

### Non negotiable inventory invariants

1. A unit cannot have two active conflicting holds/reservations/sales.
2. A hold cannot outlive its expiration without a separately authorized extension.
3. A sale booking must reference an existing valid `unit_id` from the same tenant and project.
4. The relevant price version and approved discount must be snapshotted at the binding transaction.
5. All unit state transitions need actor, reason and chronological event.
6. Inventory availability shown to buyers may be cached for display, but **must be verified in the write transaction**.
7. Bulk inventory imports require previews, schema validation, duplicate detection, reconciliation and dry runs.

## 5.3 Money and commitments

**Do not treat a receipt row as a full financial ledger.** Build:

- Sale agreements and agreement versions.
- Approved obligations/payment schedules.
- Payment intent and provider transactions.
- Bank receipts/imports and statement lines.
- Immutable receipt postings and allocation to obligations.
- Separate refund/void/adjustment events with approval.
- Payment event idempotency and unique external references.
- Reconciliation exceptions and review queue.
- Tax treatments as configurable, professionally reviewed components.
- Finance period closing and restricted historic edits.
- Broker commission accrual, eligibility and payment status.
- Payment disputes, chargebacks and failed transaction recovery.

Use integer minor units for posted monetary amounts, or appropriately constrained Decimal in money computation. Currency must be explicit and tenant aware. Never use binary float for ledger values. Keep accounting truth separate from AI estimations.

## 5.4 Events and workflow data

Define `domain_events`, `workflow_definitions`, `workflow_versions`, `workflow_runs`, `workflow_steps`, `workflow_waits`, `approval_policies`, `approval_instances`, `approval_decisions`, `integration_events`, `job_executions`, and `webhook_deliveries` progressively.

**Event envelope contract:**

```json
{
  "event_id": "uuid",
  "event_type": "inventory.hold.created",
  "schema_version": 1,
  "tenant_id": "uuid",
  "aggregate_type": "unit",
  "aggregate_id": "uuid",
  "occurred_at": "2026-11-21T12:00:00Z",
  "actor": { "kind": "user", "id": "uuid" },
  "correlation_id": "uuid",
  "causation_id": "uuid-or-null",
  "idempotency_key": "business-key",
  "payload": { "unit_id": "uuid", "hold_id": "uuid" }
}
```

Schema versions and backwards compatible event consumers are mandatory. Never put full customer PII or bearer tokens into general purpose event payloads or logs.

---

# 6. COMPLETE FEATURE SYSTEM: CUSTOMER OS

## 6.1 Unified customer 360

**Required screens:** customer explorer, customer detail timeline, relationship graph, opportunity workspace, consent/preferences, merge review, activity feed.

**Capabilities:**

- Single canonical identity per tenant with multiple phones/emails and verification status.
- Multiple opportunities across projects, priorities and sales teams.
- Household and co buyer relationships with explicit legal and communication boundaries.
- NRI customer profile with preferred time zone, currency display, communication language, visit type and support needs, without discriminatory scoring.
- Buyer intent profile: purpose, timeframe, unit type, city, must haves, budget, financing readiness, blockers, constraints and project interests.
- Lead source provenance and cross touch attribution.
- All conversations, visits, proposals, payments, handovers and service history in one chronology.
- Duplicate detection with conservative confidence, explainable match evidence and human reviewed merge.
- Visibility and ownership rules for shared customers and channel partner attribution.
- Explicit contact preferences, data retention, export requests and data access rights workflow.
- VIP handling only as configurable service level, not improper privacy bypass.
- Tags, custom fields, saved filters and custom views.
- Search across contact, contact methods, opportunity, project, unit and authorized document metadata.
- Import/export with field mappings, templates, dry run, audit and PII permission gates.

## 6.2 Intelligent customer timeline

Show activities as a meaningful story: enquiry created; called; questions asked; unit matched; site visit scheduled; attended; quotation sent; offer submitted; discount approved; hold created; booking confirmed; payment cleared; document signed; construction update; handover; support issue resolved.

Every event should expose **what happened**, **when**, **who performed it**, **whether it succeeded**, **what changed** and **which source supports it**. AI summaries must link back to actual events and must be editable as annotations, not substituted for source evidence.

## 6.3 Opportunity management

- Separate customer identity from project specific opportunity.
- Configurable stage definitions with constrained transitions.
- Opportunity owner and sales team membership.
- Probability fields: explicit human forecast, model estimate and evidence.
- Primary property, alternate shortlisted properties, proposed price and financing status.
- Loss reason taxonomy and follow up rules.
- Stale opportunity flags, dormant reactivation flows and suppression rules.
- Forecast changes over time; preserve previous forecasts for accuracy measurement.
- Opportunity deduplication without deleting valid separate interests.
- Conversion from opportunity to proposal, hold, sale and post sale lifecycle.

## 6.4 Relationship and referral graph

Track introducers, brokers, past buyers and legitimate referrals. Build consent and rights aware referral claims, duplicate resolution, commission eligibility, conflicts and audit. Do not expose one customer's private data to another merely because they are in the same graph.

---

# 7. COMPLETE FEATURE SYSTEM: PROPERTY OS

## 7.1 Inventory Control Center

The flagship real estate experience.

- Project overview: plots, towers, phases, number of units, live unit states and commercial indicators.
- Live 2D layout map for plotted developments and floor stack view for apartments.
- Filter by unit status, type, area, facing, view, price, floor, configuration, release stage and availability date.
- Search by plot number, survey reference, tower/floor/unit or internal inventory ID.
- Click a unit to see approved photos, floor plans, fact sheet, price breakdown, legal disclaimers, sales timeline and allowed actions.
- Unit hold and release actions with role and policy gating.
- Real time changes using server events or controlled polling, always confirmed on write.
- Visual conflict and expiry indicators.
- Export approved price lists and availability sheets with expiry/version watermarks.
- Side by side property comparison for sales team and buyer.
- Bulk import from CSV/Excel with preview, validation, dry run and rollback plan.
- Configurable custom unit attributes per property type.
- Inventory release controls by phase, launch date, region or partner cohort.
- History of status, price and reservations, never silently overwritten.
- Distinguish marketable, reserved and legally blocked inventory.

## 7.2 Interactive visual inventory

**Phase 1:** High quality 2D SVG or Canvas layout with a data bound unit hit map. Actual unit identity and geometry must come from verified uploaded project plans, not AI guessed geometry.

**Phase 2:** Floors and towers with selectable stacks, filtered status overlays and virtual tour linkages.

**Phase 3:** GIS map and optional 3D digital twin, including land parcel boundaries and infrastructure context when properly sourced. Keep survey/approval accuracy labels visible.

**Critical:** A beautiful illustrative 3D model must never be presented as legally authoritative plot shape, dimensions or boundaries.

## 7.3 Pricing engine

- Versioned project, category and unit price books.
- Cost sheet builder with components, taxes, concessions, government fees and optional financing illustration.
- Effective dates and scheduled price changes with approval.
- Price floors, maximum discount, exception and approval chain.
- Promotion eligibility and combinability rules.
- Approval expiry and cost sheet snapshot at booking.
- Separate public, partner and internal price visibility.
- Margin and cost impact from discounts, accessible only to authorized users.
- Scenario comparison; no automatic binding discount without approval.
- Evidence and explanation for every pricing rule.

## 7.4 Future property intelligence

- Demand heat maps by configuration, budget and project, with sampling caveats.
- Unit liquidity/absorption forecasts with calibrated uncertainty.
- Launch phase optimization and inventory aging views.
- Price response simulation from historical outcomes, not fabricated certainty.
- Project competitor database with dated provenance and manual verification.
- Area context and mobility estimates from approved mapping providers.
- Geospatial project portfolio map and inventory exposure.
- Construction updates linked to phases and units.

---

# 8. COMPLETE FEATURE SYSTEM: REVENUE OS

## 8.1 Marketing acquisition and attribution

- Captures from Meta forms, Google Ads, website forms, QR codes, hoardings, WhatsApp, property portals, call providers, referrals and offline events.
- Standardized UTM/source/campaign/adset/ad/creative/click fields.
- Privacy respecting first party event collection and offline conversion reporting with user permission.
- Campaign spend imports and reconciliation.
- Cost per lead, qualified lead, visit booked, visit attended, booking and revenue/collections by channel.
- First touch, last touch, linear and configurable attribution with clear definitions; advanced attribution only when data supports it.
- Campaign quality and lead fraud/spam indicators.
- Creative performance library linked to resulting enquiry quality.
- Funnel analysis by project, channel, team and cohort.
- Real time operational alerts: sudden lead drop, missed webhook, rising duplicate or spam rate.
- Lead form quality recommendations without discriminatory personal profiling.
- Marketing performance predictions with confidence and evidence.
- Proposed budget changes require human approval; no ad spend change on agent whim.

## 8.2 Lead routing and sales productivity

- Round robin, weighted, geography, language, team, project, channel, skill and workload based routing.
- Presence and availability aware assignments and office hours.
- Escalations for unclaimed leads, stale follow ups and high interest opportunities.
- Assignment fairness and distribution performance reporting.
- Follow up queue with context and next action suggestions.
- Automatic call and message activity capture from integrated channels.
- Mobile friendly quick actions and offline tolerant visit notes, where feasible.
- Daily briefing that tells executives whom to contact and why.
- Stage transitions, validation requirements and accountable owners.
- Coaching from permitted, consented recordings and transcripts.
- One tap supervised summary and meeting preparation.
- Clear sales commissions, targets and dispute tracking.

## 8.3 Visit Experience Engine

Extend existing site visit booking:

- Multi project visit journey and optimized itinerary.
- Sales executive and site host availability.
- Internal calendar sync and conflict detection.
- Visitor directions, location verification, parking instructions and arrival help.
- Visit check in using QR, assisted location or staff confirmation with consent.
- Customer preferences and questions before arrival.
- Virtual tour alternatives for out of town customers.
- Onsite presentation and unit comparison tools.
- Visit outcome capture with evidence and customer feedback.
- Missed visit rebooking workflow.
- Visit show rate, site to booking rate, wait times and sales cycle time.
- Site team logistics for special events and launches.

## 8.4 Deal Desk and negotiation

- Generate approved proposals and cost sheets from inventory and price books.
- Track quote version, validity, selected unit and financial components.
- Record objections, alternatives, negotiated offers and counteroffers.
- Multi level approvals for discounts, payment plan exceptions, hold extensions, inventory release and cancellation.
- Clear separation between draft offer, management approved offer and binding reservation.
- Approval deadline, delegation, out of office, escalation and withdrawal.
- Approver sees margin, comparables, policy reason, precedent and audit history, subject to permissions.
- Offer outcome and pricing leakage analytics.

## 8.5 Channel Partner Network

- Broker firm and individual onboarding with appropriate KYC and documentation.
- Partner invitation, approval, suspension, region/project entitlements.
- Project collateral and allowed inventory feed.
- Referral registration with customer consent and duplicate/ownership resolution.
- Lead claim windows and disputes with audit trail.
- Partner specific performance, visit rates, conversions and collections.
- Tiered commission schedules, accrual, release conditions and clawback.
- Payout requests, approved payment status and tax documentation.
- Channel partner portal with mobile first experience.
- API integration for partner firms where permitted.

---

# 9. COMPLETE FEATURE SYSTEM: TRANSACTION OS

## 9.1 Unit holds and bookings

- Atomic hold acquisition and expiry.
- Binding booking path with identity, approved offer, payment milestones and required approvals.
- Deposit recording and provider/bank reconciliation.
- Reservation transfer/extension only via authorized workflows.
- Booking cancellation, sale reversal and unit release with separate policies.
- Double allocation prevention at database level.
- Booking audit and snapshot of conditions at the time of acceptance.
- Required declarations and jurisdiction specific documentation checks.

## 9.2 Financial operations

- Payment plan creation using controlled templates.
- Fixed, milestone based, construction linked and configurable installments.
- Demand letter document creation and delivery proof.
- Collections calendar, expected versus actual cash flow and aging.
- Partial receipts, overpayments, unallocated cash, adjustments and authorized refunds.
- Bank statement reconciliation, exception handling and duplicate detection.
- Payment receipt and invoice generation where legally appropriate.
- Escalation by amount, aging, contract terms and communications preference.
- Role limited manual postings and approval chains.
- Reversible correction events, never silent overwrites.
- Broker commission ledger separate from property buyer ledger.
- Comprehensive outstanding balance derivation from posted transactions.
- Time zoned audit, exports, financial closure and reconciliation reports.

## 9.3 Legal and documentation workflow

- Versioned templates with approved owner and effective dates.
- Customer and project data merge with validation.
- Agreement preparation checklist and legal approval gate.
- E signature provider abstraction with supported audit evidence.
- Document status: drafted, reviewed, approved, sent, viewed, signed, rejected, expired.
- Secure buyer document vault with precise access rules.
- Controlled expiry and replacement of superseded documents.
- RERA project disclosures and approval reference tracking, with legal verification.
- Registration checklist and appointment coordination.
- Exportable transaction packet and immutable history.

## 9.4 Handover and after sales

- Construction milestone timeline by phase and unit.
- Buyer facing progress updates from verified project staff.
- Document collection checklist and completion state.
- Possession appointment and handover inspection.
- Snag reports with annotated photos, contractors and deadlines.
- Warranty and service request ledger.
- Escalation rules for unresolved customer support cases.
- Unit owner transfer and buyer profile management where legally appropriate.
- Referrals, reviews and relationship programs using explicit consent.

---

# 10. THE NEXT GENERATION AI SYSTEM

## 10.1 Principles

The core differentiator is **a controlled, context aware action system**, not twelve disconnected chatbot panels. Introduce AI agents after identity, inventory, consent, events and policy foundations are reliable.

- Model output is untrusted input to deterministic tools.
- Retrieval includes source, version, scope, approval state and relevance.
- Every tool is typed, permission checked, tenant scoped, validated and logged.
- Agents have a task scope, cost budget, timeout, model policy, sensitivity class and permitted action list.
- Stateful actions require clear approvals and human handoff.
- Prompt injection content from customers, websites, files and provider messages cannot override system rules.
- The buyer's information must not be passed to the wrong tenant or third party.
- Default to suggestion/draft, not autonomous external execution.
- Agent memory should summarize or reference authoritative records, not silently become a parallel customer database.
- High value claims require traceable records; hallucinations must fail safely.
- Evaluate agents on real operational scenarios, including negative and adversarial tests.

## 10.2 Agent catalog

### Agent 1. Lead Qualification

Inputs: enquiry, known opportunity, approved project details, permitted conversation history.  
Outputs: structured qualification, missing fields, likely intent, next action suggestion, handoff.  
Constraints: do not infer sensitive personal traits, do not mark someone ineligible based on proxies, cannot independently reject a customer.

### Agent 2. Buyer Concierge

Inputs: approved fact sheets, versioned price disclosures, actually available inventory and visit slots.  
Outputs: grounded answers, approved unit comparisons, visit suggestions, prepared proposal.  
Constraints: no invented availability or legal/financial claims, explicit handoff for unsupported facts.

### Agent 3. Sales Copilot

Inputs: assigned opportunities, permitted conversations, activities, tasks and unit context.  
Outputs: daily brief, suggested follow ups, call preparation, draft replies and meeting summaries.  
Constraints: actual contact requires current consent and approval rules.

### Agent 4. Inventory Matching

Inputs: customer criteria, price books and available inventory.  
Outputs: ranked matching units with reason and tradeoffs.  
Constraints: deterministic eligibility and availability checks; explain recommendations.

### Agent 5. Visit Coordinator

Inputs: visit slots, staff schedules, project locations and user preferences.  
Outputs: recommended schedule, confirmed booking through validated tool, reminders and post visit task suggestions.  
Constraints: no double booking and no silent cancellation.

### Agent 6. Conversation Intelligence

Inputs: consented recordings/transcripts and chat events.  
Outputs: factual summary, questions unanswered, objections, commitments, next steps and quality coaching.  
Constraints: disclose recording rules, preserve provenance and correctable summaries.

### Agent 7. Deal Risk

Inputs: opportunity state, proposal age, hold deadlines, approved pricing, payment milestones and activities.  
Outputs: risk flags, explanations and recovery suggestions.  
Constraints: separate statistical estimates from verified operational facts.

### Agent 8. Revenue Intelligence

Inputs: campaign data, opportunities, visits, bookings and collections.  
Outputs: funnel explanations, channel anomalies, forecast ranges and proposed campaign actions.  
Constraints: no unapproved ad account spend changes.

### Agent 9. Collections Assistant

Inputs: actual receivables, paid postings, due dates, legal templates and preferences.  
Outputs: collection work queues, compliant message drafts and exceptions.  
Constraints: cannot change ledger, accept/offered settlements, or threaten customers.

### Agent 10. Document Assistant

Inputs: approved contract templates, verified profile/unit/price facts and applicable forms.  
Outputs: draft cost sheets, demand letter documents, booking packet and checklist.  
Constraints: legal and financial approval and immutable final snapshot.

### Agent 11. Customer Care

Inputs: ticket, unit, warranty and verified project records.  
Outputs: triage suggestion, assignment, response draft and escalation.  
Constraints: no unsupported repair or warranty promises.

### Agent 12. Executive Intelligence

Inputs: authorized metric catalog, structured business events and user permissions.  
Outputs: cited boardroom answers and drill down reports.  
Constraints: no direct unrestricted SQL; use governed, parameterized analytics tools and suppress unauthorized results.

## 10.3 Agent runtime design

Core entities: `agent_definitions`, `agent_versions`, `agent_runs`, `agent_tool_calls`, `agent_approvals`, `agent_evaluations`, `model_usage` and `knowledge_sources`.

Each run records:

- tenant, initiating actor and optional beneficiary;
- request and task class;
- model/provider and prompt/template version;
- data sources referenced and their versions;
- tools requested, permitted, denied and executed;
- structured output, confidence where calibrated, citations and policy decisions;
- model and tool token/cost/latency;
- final outcome, human approval and rollback or compensating action if applicable.

## 10.4 Agent action permission levels

| Level | What agent can do | Example |
|---|---|---|
| 0. Read | Retrieve allowed facts | Find project amenities |
| 1. Analyze | Summarize and recommend | Suggest next best lead |
| 2. Draft | Prepare reversible content | Draft a WhatsApp response or cost sheet |
| 3. Low risk authorized execute | Perform rule validated reversible action | Create internal task or book a confirmed visit slot with customer authorization |
| 4. Human approval required | Queue action and await authorized decision | Send external campaign, extend unit hold, approve discount |
| 5. Prohibited without dedicated deterministic process | Never independently authorize | Move money, execute legal agreement, release confidential data, override compliance |

Business risk and tenant policy determine the actual permission; the table is not a substitute for an implementation security matrix.

## 10.5 Memory architecture

Use three distinct layers:

1. **Authoritative data:** property units, transactions, payments, customer records, consent, approved project facts.
2. **Retrieval memory:** indexed references to authorized documents, customer events, policies and knowledge, respecting version and revocation.
3. **Ephemeral agent task state:** short lived working context and derived notes, expiring or retained according to policy.

Do not store permanent unverified AI assumptions as facts. Every derived insight must be clearly labeled with evidence and creation date.

## 10.6 Explainable predictions

Forecasts and scores should expose training cohort, date, input data sufficiency, evaluation results, bias tests and uncertainty. Start with rules and simple statistical baselines; only use complex models if they outperform on out of time validation. Never market a probabilistic sales estimate as a guarantee.

## 10.7 Natural language analytics

Examples:

- "Which projects had the highest visit to booking conversion this month?"
- "Which leads have been promised a callback but have no completed task?"
- "What was actual collection against demand for the last quarter?"
- "Show available east facing plots within the approved budget range."
- "How many units are being held beyond policy?"
- "Compare campaign spend and collections, noting attribution limitations."

Use a governed metric semantic layer. Answers must show filters, date range, source data timestamp, calculation logic, permission scope and link to drill down. Do not let the model invent SQL for arbitrary tenant tables in production.

---

# 11. APPROVALS, PERMISSIONS AND GOVERNANCE

## 11.1 Required organizational roles

Create a configurable role and permission system supporting at least:

- Platform operator and support operator, separate from tenant business identities.
- Tenant owner and organization administrator.
- Group CEO / managing director / director with authorized portfolio visibility.
- Regional head / project head.
- Sales director / sales manager / team leader / executive.
- Marketing head / campaign operator.
- Inventory manager.
- Finance head / accountant / collector / approver.
- Legal officer / document approver.
- Customer experience and handover manager.
- Channel partner admin and individual partner agent.
- Customer and co buyer, with explicit transaction entitlements.
- Auditor / read only reviewer.
- Optional external vendor/contractor for strictly scoped tasks.

## 11.2 Permission model

Permissions are **action + resource + scope + condition**. Examples:

```text
leads.read                    scope=assigned | team | project | portfolio
leads.assign                  scope=team | project
customers.export              scope=allowed_only, approval_required=true
inventory.hold.create         scope=authorized_project
inventory.hold.override       approval_required=true
pricing.offer.create          scope=authorized_project
pricing.discount.approve      max_discount_by_policy
payments.record               scope=authorized_entity
payments.reverse              dual_approval=true
documents.generate            scope=allowed_template
contracts.finalize            legal_approval=true
agents.execute                tool_allowlist=approved
analytics.sensitive.read      field_and_row_policy=true
```

**Mandatory:** no reliance on frontend only role checks. Every query and command receives tenant and effective membership context; object ownership, project scope and field level exposure are enforced in services. Explicitly test joins, imports, exports, document URLs, webhooks, background jobs and AI tools.

## 11.3 Approval engine features

- Visual policy editor with draft, test, approval and published states.
- Conditions based on amounts, discounts, project, unit class, role, customer risk and exception type.
- Sequential and parallel approver groups.
- Quorum, dual control, segregation of duties and maker checker requirements.
- Substitution/delegation with expiry and evidence.
- Reassignment and escalation.
- Immutable decision records, timestamps and comments.
- Request withdrawal, rejection and re submission.
- Preview/simulation on sample transactions before policy activation.
- Change versioning and effective dates.
- “Why was this approved?” audit replay.

## 11.4 Compliance capabilities

- DPDP aligned privacy policies and controls with legal review, including applicable rules, notices, purposes, withdrawal, erasure/retention obligations, grievance routing and children's data safeguards where applicable.
- Marketing and telecom messaging consent/policy controls, including applicable templates, opt out and quiet hours.
- RERA related project fact provenance, publishing and disclosures with state specific requirements verified by counsel.
- GST and tax treatments reviewed by competent finance/legal professionals.
- Data residency and cross border transfer rules based on client contract and applicable law.
- Retention policy, customer data access/export, correction, deletion/anonymization where legally permissible, litigation holds and audit retention.
- No unsupported claim of certification or regulatory compliance.

---

# 12. WORKFLOW AUTOMATION STUDIO

## 12.1 Product experience

An administrator should be able to build workflows visually without writing code:

**Trigger → Filter → Rule → Permission Check → Action / Approval → Wait → Outcome → Audit**.

Examples:

1. New Meta lead → resolve identity → create opportunity → assign available executive → create first contact task → report SLA.
2. Site visit booked → check consent → send approved confirmation → schedule reminders → request feedback → update visit outcome.
3. Unit hold expiring → notify assigned executive → request authorized extension → release after policy expiry.
4. Approved cost sheet → send proposal via authorized channel → track receipt → create follow up.
5. Installment due → compute outstanding → approve compliant communication → send → reconcile payment.
6. Complaint overdue → assign supervisor → alert service manager → record escalation.

## 12.2 Builder features

- Versioned workflow templates by business use case.
- Drag and drop editor with readable conditions and accessible keyboard alternatives.
- Tenant scoped event catalog, structured action catalog and variable schema.
- Preview of eligible records and example path.
- Dry run and simulation mode.
- Approval before activation for high impact workflows.
- Effective dates, maintenance windows and rate limits.
- Retries, backoff, timeout, dead letter state and manual replay.
- Step execution log with inputs redacted and outputs referenced safely.
- Rule conflict detection and cyclical workflow prevention.
- Conditional branches, wait for event, deadlines and compensating actions.
- Workflow quotas and estimated channel costs.
- Global kill switch, per workflow pause and per tenant disable.
- Controlled AI assistant to draft workflow definitions, never publish without human review.

## 12.3 DSL and runtime

Use versioned JSON schema for declarative workflow definitions, compiled and validated server side. No user provided arbitrary Python or JavaScript execution on the backend. Action invocation goes through typed registry and service authorization. Preserve historical workflow version for every run.

---

# 13. UI / UX PRODUCT DESIGN SYSTEM

## 13.1 Design mandate

This must look and feel like a premium 2030s application, **not a template admin dashboard**. A beautiful UI does not compensate for broken workflows; prioritize information clarity, speed and safe decisions.

**Design characteristics:** sophisticated, precise, content dense where needed, calm, fast, accessible, customizable per tenant and exceptionally polished. Avoid random gradients, excessive glass, unreadable contrast, gratuitous motion and decorative AI effects.

## 13.2 Four core UX surfaces

1. **Executive Command Center:** finance, conversion, inventory, exceptions, forecasts and approvals with drill downs. Ideal for desktop and tablet.
2. **Sales Mission Control:** highly optimized single customer workspace and prioritized tasks, quick actions, call/message context, mobile ready.
3. **Inventory Studio:** layout/floor/plot map, filters, side panel, hold/quote/compare and history.
4. **Buyer Property Passport:** mobile first journey from discovery to booking, payments, construction, handover and service.

Additional dedicated workspaces: Marketing, Finance & Collections, Channel Partners, Legal & Approvals, Customer Care, SaaS Operator.

## 13.3 Information architecture

### Developer / Admin navigation

```text
Overview
  Command Center
  Alerts & Exceptions
  Executive Reports
Customers
  People & Households
  Opportunities
  Conversations
  Activities
Sales
  My Work / Team Queue
  Site Visits
  Offers & Deal Desk
  Reservations
Properties
  Projects & Phases
  Inventory Studio
  Price Books
  Documents & Media
Marketing
  Campaigns
  Lead Sources
  Attribution & Spend
  Creative Intelligence
Partners
  Partner Directory
  Referrals
  Commissions
Transactions
  Sales Bookings
  Collections
  Reconciliation
  Contracts & Documents
Experience
  Customer Portal
  Handover
  Support & Warranties
Intelligence
  Ask PropFlow
  Forecasts
  Recommendations
  Agent Activity
Automation
  Workflows
  Rules & Approvals
  Integrations
Administration
  Members & Roles
  Brand & Tenant Settings
  Privacy & Compliance
  Audit & Security
  Billing & Usage
```

This is a target taxonomy, not a mandate to show all navigation items before implementation. Display modules only when functional and enabled, preserve current routes with redirects while changing navigation.

## 13.4 Component standards

- Global command search with permissions and keyboard shortcut.
- Consistent entity detail side panel with breadcrumbs and deep links.
- List/table/card/map modes based on task, not aesthetic preference.
- User controlled saved views, filters, column visibility and exports.
- Progressive disclosure of secondary data and advanced controls.
- Loading skeletons, actionable empty states, inline validation, specific errors.
- Optimistic updates only for reversible operations; inventory/finance confirmation must be authoritative.
- Contextual activity timeline, comments, mentions and file attachments.
- Full accessibility support: keyboard, focus, contrast, screen reader semantics, reduced motion and responsive layouts.
- Localization, number formatting, unit systems, time zones and date precision.
- High performance for large lists through server pagination, filtering and virtualization where justified.
- Responsive mobile design for field sales and buyers; do not merely shrink desktop tables.
- Real time updates with visible freshness and conflict resolution.
- Color semantics for status must include readable text and icons, never color alone.
- Design tokens for type, color, spacing, elevation, charts, motion and tenant theming.

## 13.5 Product interactions that matter

- One click from campaign to actual customers and realized sales.
- One click from a customer to every relevant interaction.
- One click from a property to availability, price, history and authorized action.
- One click from a blocked deal to approval request and evidence.
- One click from a reported metric to underlying records and calculation.
- One click from AI suggestion to **why** it was suggested and the final human decision.

## 13.6 Visual quality acceptance

Do not sign off based on one attractive landing page. Demonstrate actual workflows at desktop, tablet and mobile widths: lead capture, customer merge, project selection, inventory hold conflict, proposal approval, receipt posting, finance export and buyer handover. Assess accessibility and performance.

---

# 14. REAL WORLD WORKFLOWS TO IMPLEMENT END TO END

## Scenario A. Fast, responsible lead acquisition

1. A buyer completes a Meta lead form.
2. Verified webhook records incoming event and source.
3. Connector resolves tenant and project with configured mapping.
4. Identity resolver finds possible existing contact and preserves enquiry event.
5. System creates or links a project specific opportunity.
6. Lead assignment engine selects eligible executive.
7. Consent policy determines approved channel contact.
8. Authorized reply is dispatched or a task is assigned.
9. SLA starts; dashboard exposes accepted, contacted and unresolved counts.
10. Failures enter a review queue with replay, never vanish silently.

**Success:** No lost legitimate leads, no duplicate identity explosion, no unauthorized messages and auditable source attribution.

## Scenario B. Property matching and visit

1. Buyer requests 3 BHK under a configured budget.
2. Assistant checks verified project facts and active inventory.
3. Buyer sees available matching alternatives and transparent tradeoffs.
4. Buyer chooses an available visit slot.
5. Backend validates slot and assignment within transaction.
6. Consent aware confirmation and reminders are queued.
7. Salesperson receives context, directions and customer questions.
8. Check in and outcome recorded.
9. Follow up and next best action generated for review.

**Success:** No invented facts, visit overbooking, or disconnected history.

## Scenario C. Two buyers want the same unit

1. Two sales executives open the same available unit.
2. Both request hold at approximately the same time.
3. Database commits only one successful active hold.
4. Losing request receives explicit conflict and recommended alternatives.
5. Winning hold has owner, expiration and immutable event.
6. If expired, release happens through controlled worker and notifies applicable participants.
7. Booking validates current hold ownership and price version.

**Success:** Zero double allocation, including retries and crashes.

## Scenario D. Discount request

1. Salesperson prepares cost sheet and asks for an exception.
2. System computes all approved price components and policy thresholds.
3. Approval engine routes request to correct approver(s).
4. Every decision records user, timestamp, original and amended terms and reason.
5. On approval, cost sheet receives a version and expiration.
6. Buyer receives approved proposal only after channel policy check.
7. A revised request invalidates or supersedes prior terms as policy requires.

**Success:** No unauthorized concessions or unclear proposal versions.

## Scenario E. Payment and receipt integrity

1. Customer pays partial installment through supported channel.
2. Provider or bank event is authenticated and idempotently recorded.
3. System finds obligation and applies payment through controlled posting.
4. A unique receipt number is allocated atomically.
5. Balance and stage reflect committed ledger entries.
6. Customer receives receipt through approved delivery path.
7. Repeated webhook does not duplicate payment.
8. Unmatched payments go to finance reconciliation.

**Success:** No double receipt numbers, overpaid installment races or unreconciled silent payments.

## Scenario F. NRI customer experience

1. Buyer chooses preferred time zone and communication method.
2. AI shows verified inventory and a virtual viewing option.
3. Customer can request video call at available hours.
4. Cost sheet uses authoritative INR financial values and clearly labeled display currency conversions when enabled.
5. Co buyer or legal representative gets only explicitly authorized access.
6. Documents and progress updates remain in a secure property passport.

**Success:** An internationally usable experience without weakening local legal controls.

## Scenario G. Developer leadership asks a question

Prompt: "What is blocking this quarter's revenue?"  
System returns: project specific expected collections, overdue obligations, unbooked/high demand units, pending offers, approval bottlenecks and a calculation trace. It distinguishes invoiced, contracted, collected and forecast values. Leadership can drill into records subject to permissions.

**Success:** Auditable answer with definitions and no fabricated financial certainty.

---

# 15. DEEP ANALYTICS AND DECISION ENGINE

## 15.1 The metrics catalog

Every metric needs a documented name, definition, calculation, allowed dimensions, numerator, denominator, time attribution, owner, freshness and source tables.

| Metric | Definition requirement |
|---|---|
| Lead response time | Event timestamp to first successful human or approved automated contact; distinguish both |
| Contact rate | Unique opportunities contacted over eligible opportunities; define period cohort |
| Qualified rate | Qualified opportunities divided by relevant acquisition cohort |
| Visit booked / attended | Distinguish scheduling, actual attendance and cancellation |
| Visit to booking conversion | Define cohort and attributable sale date |
| Cost per visit | Applicable attributable marketing spend divided by valid visits |
| Cost per booking | Applicable spend divided by validated bookings |
| Sales velocity | Units or gross booking value per period, by project and type |
| Net realization | Realized sale amount net of defined concessions, not marketing headline price |
| Collections efficiency | Actual cleared receipts vs obligations due in period |
| Aging | Balance overdue by documented aging bucket |
| Inventory absorption | Units sold divided by released inventory in cohort |
| Hold leakage | Expired holds, manual overrides, excessive lock time |
| Revenue forecast accuracy | Historical predicted vs actual, separated by forecast horizon |
| Lead source ROI | Attribute revenue and cost with disclosure of model assumptions |
| Team productivity | Meaningful outcomes, not simply call count |
| Customer experience SLA | Time to respond and resolve service/complaint cases |
| AI effect | Controlled evaluation comparing permitted outcomes and baseline |

## 15.2 Reports

- Executive day/week/month operating view.
- Project absorption, booked vs sold vs collected.
- Marketing attribution and source quality.
- Sales team activity and pipeline conversion.
- Inventory heatmaps, aging and blocked units.
- Price realization, discount approval and exception leakage.
- Channel partner contribution and commission obligations.
- Demand versus collections and aged receivables.
- Site visit outcomes and resource utilization.
- Service and handover performance.
- SaaS tenant usage, cost and entitlement status.
- Agent quality, cost, latency, approval and failure rates.

## 15.3 Analysis rules

- Preserve historical snapshots when source records change.
- Provide a single canonical currency and explicit conversion method.
- Make filters/date ranges visible.
- Show data freshness.
- Prevent accidental cross tenant aggregation except strictly anonymized, explicitly allowed operator level platform analytics.
- Export permission must not exceed screen viewing permission.
- Suppress or aggregate small cohorts where privacy risks warrant it.

---

# 16. INTEGRATIONS AND EXTENSIBILITY

## 16.1 Integration catalog

**Marketing:** Meta Lead Ads, Google Ads offline conversions, form/web capture, QR and landing pages, supported real estate portals, campaign spend feeds.  
**Communication:** Meta WhatsApp Business Platform or authorized BSP, approved SMS providers, email, telephony and call center providers, calendar integrations.  
**Finance:** Razorpay where appropriate, payment gateways, bank statement import, accounting software connectors after transaction reconciliation is proven.  
**Identity/document:** approved eSign providers, document vault, SMS/email verification, developer supplied identity verification, regulatory documentation providers where contracted.  
**Property and operations:** mapping/GIS providers, verified plan imports, storage, construction milestone feeds, optional ERP connectors.  
**Analytics and export:** webhooks, governed APIs, warehouse connectors, BI exports.

## 16.2 Connector framework requirements

- Tenant owned connection with provider type, authentication reference, status and scopes.
- Credentials in secret manager, not ordinary database JSON or client bundles.
- OAuth/authorization and token refresh where applicable.
- Signed webhook validation, deduplication and durable raw event reference.
- Provider account/page/form to project mappings.
- Retry and dead letter controls; rate limiting and exponential backoff.
- Inbound payload validation and quarantining.
- Per integration last success, last failure, latency, error class and usage cost.
- Disconnect/revoke handling.
- Sandbox/test mode and mocked contracts for CI.
- Field mapping editor and import preview.
- Reconciliation of missing/failed events.
- Tenant admin installation and permission approval.
- Clearly separate *configured*, *connected*, *healthy*, *paused* and *unsupported*.

## 16.3 Public developer ecosystem

Eventually add versioned OpenAPI, outgoing webhooks, signed apps, OAuth scopes, integration rate limits, dev keys, audit, sandbox tenants and partner documentation. Do not publish an open integration marketplace until the permission and secret management models are mature.

---

# 17. WHITE LABEL SAAS, PACKAGING AND TENANT OPERATIONS

## 17.1 Tenant productization

- Brand identity: name, logo, colors, typography tokens, favicon, emails, customer portal domain.
- Multi project and business entity organization models.
- Configurable feature and role entitlements.
- Plans priced using metered usage with accurate period calculations.
- Trial/onboarding with test data separation.
- Data import wizard with validation and rollback.
- Admin guided project setup and fact verification.
- Tenant feature flagging and staged rollout.
- Transparent usage and cost dashboard.
- Tenant health and connector alerts.
- Subscription upgrades/downgrades, invoice handling and state reconciliation.
- Offboarding, data export, retention and deletion policy.
- Support access: customer approved, time limited, logged and least privilege; operators must not have undocumented unrestricted data access.

## 17.2 Plan architecture

Create **entitlements**, **meters** and **billing** as separate concepts.

Entitlements: what a tenant may use.  
Meters: what was consumed in a specific period, counted atomically.  
Billing: how the provider charges and reconciles payment.

Avoid plan code such as `if plan == "premium"` scattered through APIs. Use a central entitlement check, period aware meters, limits, quota reservation and consistent UX for limits reached.

## 17.3 Deployment tracks

- Shared SaaS for small to mid sized developers.
- Enterprise isolated database/deployment option only when commercially justified and security/process tools support it.
- Platform operator console with health, usage and support action governance.
- Regional hosting and retention configurable by contractual and legal requirements.

---

# 18. SECURITY, RELIABILITY AND NONFUNCTIONAL REQUIREMENTS

## 18.1 Security baseline

- Threat model and secure data flow diagram.
- MFA for high privilege users, secure recovery, session management and device revocation.
- Tenant scoped service authorization and field level protection.
- Signed and expiring object storage URLs.
- Encrypted transport, secrets manager, secrets rotation and least privilege service accounts.
- Parameterized queries and schema validated inputs.
- Rate limiting at shared gateway, not only process local memory.
- Anti abuse and bot defense on public intake endpoints.
- Provider webhook authentication and replay protection.
- Audit of privileged actions and sensitive exports.
- Data access/download logs, retention and deletion workflow.
- Log redaction for credentials, PII and financial details.
- Secure dependency and supply chain scanning.
- Cross tenant integration, access and background job tests.
- Explicit customer and partner access boundaries.
- Backups encrypted and recovery tested.
- Security incident response and data breach handling playbook.

## 18.2 Operational reliability

Suggested **initial engineering targets**, subject to measurement and architecture review:

| Property | Initial target |
|---|---|
| Transactional inventory double allocation | Zero in concurrency tests and production invariant monitors |
| Financial double posting | Zero after duplicate delivery and retry testing |
| Core API availability | Target 99.9% once production operations support it; measure honestly |
| Interactive UI responsiveness | Prioritize sub 2 second median for common screens on representative connections; define p95 by workflow |
| Lead intake event loss | Zero silently lost; failures are retained and replayable |
| Background delivery processing | At least once processing with business idempotency and dead letter handling |
| Tenant data separation | No unauthorized cross tenant access in automated and adversarial tests |
| Recovery | Explicit RPO/RTO defined with owner and verified restore tests |
| Deployment | Repeatable staging release, migration check, rollback plan and health verification |
| Feature rollout | Tenant scoped flags, metrics and kill switches for risky launches |

Do not use these numbers as customer promises until instrumentation and test evidence support them.

## 18.3 Performance

- Load test search, list, reports, lead ingestion, inventory hold and event worker independently.
- Profile database queries and build indexes from actual workloads.
- Avoid N+1 queries and unbounded list endpoints.
- Paginate all tenant owned lists.
- Batch and async process external API I/O when safe.
- Cap agent context and model spend by tenant and use case.
- Prevent excessive retries and cascading failures.
- Make file upload size/type/scan rules explicit.

## 18.4 Disaster recovery

- Backup schedule, offsite immutable retention where appropriate, encryption.
- Regular point in time recovery exercises and sample tenant restoration tests.
- Secrets and infrastructure as code recovery procedures.
- Audit ledger disaster recovery integrity.
- Integration re synchronization and message replay policy.
- Communication plan for incidents.

---

# 19. QUALITY ASSURANCE AND TEST STRATEGY

## 19.1 Test pyramid

**Unit:** validators, prices, money calculations, permission predicates, workflows, matching, AI tool parameters.  
**Database integration:** migrations, row locks, unique constraints, tenant scoping, outbox consistency and transaction rollback.  
**API contract:** OpenAPI schema tests, authentication, authorization, errors, pagination and idempotency.  
**External connector contract:** signed webhook fixtures, provider failure modes, duplicates, retries, out of order delivery, token expiry.  
**Frontend unit:** forms, state management, data table, inventory visuals, tenant themes, approval interactions.  
**Browser E2E:** important workflows through all portals at representative breakpoints.  
**Security:** cross tenant object ID attempts, privilege escalation, PII export, agent tool abuse, prompt injection, replay attack.  
**Load:** thousands of concurrent enquiries, multiple salespeople holding units, high volume messaging and analytics.

## 19.2 Every feature must include

1. Backend service with valid permission scope.
2. Migration with reversible or safe recovery path.
3. API contract and typed schema.
4. Frontend complete workflow including errors and empty states.
5. Automated tests and negative cases.
6. Audit events and observability.
7. Documentation and example screenshots or repeatable demo instructions.
8. Migration/backward compatibility plan where existing entities change.
9. Feature flag and rollback plan for risky releases.
10. Verified acceptance criteria.

## 19.3 Critical negative tests

- Tenant A requests Tenant B's resource by direct UUID.
- Salesperson guesses a different executive's lead ID.
- Buyer attempts to see another buyer's document.
- Agent tries to call unapproved tool with forged arguments.
- Imported file includes malicious formula / unexpected sheet structure.
- Consent revoked after marketing message queued.
- Provider webhook arrives 10 times, out of order.
- Two users hold the same unit concurrently.
- Two finance users post receipt to same installment concurrently.
- Background job crashes after external send but before local commit.
- Price changes between proposal and booking.
- Membership revoked during an active browser session.
- Tenant suspended during long running workflow.
- Bulk import stops halfway and resumes safely.
- PII appears in metrics or logs through exception handling.
- Workflow attempts endless self triggering recursion.

---

# 20. ROADMAP: BUILD IN VERTICAL SLICES

This is an **ordering proposal**, not a promise of delivery dates. Phase completion should be decided by evidence. Do not start the next phase until the current phase's exit gates are met.

| Phase | Priority | Main outcome | Exit gate |
|---|---|---|---|
| 0. Stabilize | Immediate | Current code verified, critical bugs fixed, reliable CI | Verified tests, source grounded audit, P0 fixes and migration plan |
| 1. Customer foundation | P0/P1 | Unified identity and multiple opportunities | Existing leads retained, multi project customer works, zero tenant leakage |
| 2. Live inventory | P0 | Unit model, holds, prices, 2D inventory studio | No double allocation in concurrency tests |
| 3. Sales execution | P1 | Sales cockpit, routing, visits, offers, approvals | Full enquiry to approved reservation demo |
| 4. Communication hub | P1 | Two way inbox, calling/WhatsApp connectors, consent gates | Real provider sandbox success with retry/opt out tests |
| 5. Finance integrity | P0/P1 | Ledger, receipts, reconciliation, demand docs | Concurrent payments and provider retries reconcile exactly |
| 6. Intelligence first | P1 | Sales copilot, unit matching, governed analytics | Evidence grounded results and controlled evaluations |
| 7. Automation platform | P1/P2 | Workflow studio and approval policies | Versioning, simulation, durable execution and kill switch |
| 8. Distribution network | P2 | Partner portal, referrals, disputes, commissions | Verified ownership and payable amounts |
| 9. Buyer experience | P2 | Property passport, documents, construction, handover | End to end buyer journey without leaking customer data |
| 10. Predictive leadership | P2 | Forecasts, scenario planning, advanced intelligence | Historical accuracy measures, uncertainty, drill down |
| 11. Ecosystem | P3 | Marketplace, developer API, ERP, portfolio scale | Security review, versioned contracts and tenant control |

## 20.1 Phase 0: Stabilize the current repository

**Goal:** Make the present system trustworthy.

**Tasks:**

1. Execute and document tests across Python 3.12 and 3.13, frontend build, frontend unit and E2E.
2. Compare all Alembic migrations with current models; detect missing tenant ownership and wrong foreign keys.
3. Reproduce receipt ID concurrency and missing installment locks, then fix transaction logic with tests.
4. Reproduce Meta mapping and connector duplicate mismatch, then fix with tests.
5. Implement period correct plan quotas and concurrency checks.
6. Enforce consent at dispatch and cancel/suppress pending prohibited deliveries.
7. Verify webhook replay, out of order event handling and payment provider invoice uniqueness.
8. Review password reset, token storage, device sessions, login rate limits and brute force controls.
9. Add frontend unit and E2E jobs to CI, plus dependency and secrets scans.
10. Update repository documentation and clearly separate development defaults from production configuration.
11. Add health checks for connections/workers, error alerts and structured correlation logging.
12. Inventory all external API credentials and make sandbox/live differentiation explicit.

**Exit gates:** green full test matrix, documented security findings, no known P0 financial or consent risks in test scenarios, successful database migration in staging, startup and rollback runbooks.

## 20.2 Phase 1: Customer identity + opportunities

Deliver one contact with multiple enquiries and project opportunities, complete timeline and conservative deduplication. Preserve all existing lead references and existing screens via compatibility adapters. Include migrations, endpoints, buyer/security scope, UI and E2E.

## 20.3 Phase 2: Inventory + hold lifecycle

Deliver normalized units, CSV import, validated status, an atomic hold API, price version reference and an interactive 2D inventory studio. Prevent sale booking without enforceable unit claim after migration, but provide a controlled path for legacy records.

## 20.4 Phase 3: Deal desk + approvals

Deliver project specific pricing, cost sheet builder, negotiated offer and explicit approval chains, all tied to inventory and opportunity. Do not allow the proposal service to bypass current booking validations.

## 20.5 Phase 4: Messaging + telephony

Build a unified interaction timeline with inbound replies and delivery statuses. Fix dispatch transactions, add channel consent, secure connectors and operational health. Support explicit opt in provider connections.

## 20.6 Phase 5: Payments + documents

Financial ledger, robust unique receipt allocation, reconciliation, immutable demand letters, role gated corrections and customer property passport financial view.

## 20.7 Phase 6 and beyond: AI and automation

Start with two agents that materially improve workflow: Sales Copilot and Inventory Matcher. Add evaluation harness, citations, audit and human gating. Only then layer more agents and workflow builder. Advanced features must be based on trustworthy data and measurable usefulness.

---

# 21. DETAILED ACCEPTANCE CRITERIA FOR INITIAL PRIORITY FEATURES

## 21.1 Financial concurrency fix

- Given two simultaneous payment recording requests against an installment with insufficient balance for both, exactly one succeeds and the other receives a well defined business conflict.
- No duplicate receipt numbers occur under high concurrency.
- A repeated request using the same idempotency key returns the prior result without a new ledger entry.
- Failed transactions leave no partial ledger mutation.
- Generated receipt number is unique in the applicable tenant scope.
- Tenant A cannot see, modify, reverse or allocate Tenant B's receipts.
- Correction is through authorized void/reversal, not deleting history.

## 21.2 Consent dispatch fix

- A message queued before opt out is suppressed at dispatch after opt out.
- SMS, WhatsApp and email preferences are evaluated independently, together with purpose where applicable.
- The suppression event is audit visible.
- An opted out record cannot re enter campaigns through connector replay or customer merge.
- Internal operational notifications are treated separately from customer marketing contact based on validated policy.
- Disabled, suspended or deleted tenants cannot generate new external sends.

## 21.3 Customer multiple opportunity model

- A single customer may have opportunities for more than one project.
- Each opportunity maintains its owner, stage, campaign and visits.
- Search by verified phone or email returns the right canonical record with linked opportunities.
- Household members may share contact methods but remain separate people when evidence requires it.
- Existing lead and visit records remain accessible after migration.
- All endpoints enforce tenant and role permissions.

## 21.4 Inventory holds

- 100 concurrent hold attempts for one eligible unit produce at most one active winning hold.
- A valid hold expires and is released exactly once.
- A stale inventory view cannot create conflicting inventory claim.
- A new booking consumes an active permitted hold transactionally.
- Repeated API requests are idempotent.
- A manual override requires configurable approved permission and audit.
- Buyer sees only approved price details and allowed inventory visibility.

## 21.5 AI sales copilot

- Suggestions link to underlying approved project/customer facts or clearly identify a heuristic.
- Agent cannot see other tenant or unauthorized user opportunities.
- Agent cannot change price, reserve unit, post payment or send an external message without authorized tool paths.
- Agent logs version, tool invocation, evidence and outcome with sensitive data redaction.
- Fallback succeeds gracefully if model provider times out or quota is exhausted.
- Adversarial prompts cannot override tenant/permission enforcement.

---

# 22. CLAUDE CODE ENGINEERING WORKFLOW

## 22.1 Before any implementation

```bash
# Run in the existing repository. Do not run destructive seed/reset commands.
git status --short
git log -5 --oneline
# Read documentation and core module layout first.
# Confirm Python and Node versions, environment and available dependencies.
```

Then execute the repository's documented test commands in a safe environment. Baseline commands, adjusted to actual environment:

```bash
cd backend
python -m pytest tests -q --tb=short

cd ../frontend
npm ci
npm run build
npm run test:unit
npm run test:e2e
```

E2E tests may require installed browser binaries and a test server. Do not mark browser testing passed if it cannot run. Record environmental blockers.

## 22.2 Standard feature delivery loop

1. Read affected existing models, services, repository queries, routers, schemas, frontend screens and tests.
2. Write a concise design note identifying existing behavior, invariants, dependencies and migration requirements.
3. Identify one end to end use case and its exact acceptance criteria.
4. Add safe migration and constraints.
5. Add service logic and enforce authorization/transaction boundaries.
6. Add API schema/routes; retain backwards compatibility.
7. Implement complete frontend flow with validation and failure states.
8. Add unit, integration, concurrency, E2E and cross tenant negative tests.
9. Run formatting, type checks, build and relevant full test suite.
10. Update documentation, screenshots/demo instructions and the change log.
11. Report files changed, tests and limitations; stop for review before the next major phase.

## 22.3 Mandatory PR template

```text
FEATURE / FIX:
WHY IT MATTERS:
CURRENT BEHAVIOR:
PROPOSED BEHAVIOR:
DATA MODEL & MIGRATION:
API & UI CHANGES:
TENANT AND PERMISSION CHECKS:
CONCURRENCY / IDEMPOTENCY:
CONSENT / PRIVACY CONSEQUENCES:
TESTS RUN & OUTPUT:
BACKWARDS COMPATIBILITY:
DEPLOYMENT & ROLLBACK:
KNOWN GAPS:
SCREENSHOTS / DEMO STEPS:
NEXT SINGLE TASK:
```

## 22.4 What Claude Code must NOT do

- Replace the entire UI with a new frontend unrelated to current routes.
- Rewrite PostgreSQL models without migration plan.
- Remove old tests to make CI green.
- Add database tables with names that duplicate existing domain meaning.
- Create fake API success responses.
- Hardcode tenant IDs, project IDs, provider tokens, passwords or payment rates.
- Implement production messaging against personal WhatsApp accounts or unofficial workarounds.
- Automatically ship unreviewed AI generated contract language to customers.
- Build a 3D digital twin before verified property inventory exists.
- Publish pricing or property claims from unapproved sources.
- Declare DPDP, RERA, accounting or security compliance without expert and evidence backed review.
- Send any actual messages, change live resources or deploy without explicit authorization.

---

# 23. STARTER BACKLOG FOR ISSUE TRACKING

Suggested issue IDs and dependency ordering:

| ID | Priority | Task | Dependencies |
|---|---|---|---|
| PF-001 | P0 | Verify baseline, map real status and test matrix | None |
| PF-002 | P0 | Harden receipt allocation and installment concurrency | PF-001 |
| PF-003 | P0 | Add dispatch time consent gate and suppression tests | PF-001 |
| PF-004 | P0 | Fix Meta project mapping and connector identity logic | PF-001 |
| PF-005 | P0 | Correct per period billing meter logic | PF-001 |
| PF-006 | P0 | Strengthen CI, staging deployment and observability | PF-001 |
| PF-007 | P1 | Review global user identity and tenant memberships | PF-001 |
| PF-008 | P1 | Introduce customer canonical identity and opportunity schema | PF-003, PF-004 |
| PF-009 | P1 | Backfill customer/opportunity while preserving old leads | PF-008 |
| PF-010 | P0 | Implement unit inventory, status and atomic holds | PF-001 |
| PF-011 | P0 | Migrate sale bookings to enforceable unit references | PF-010, PF-002 |
| PF-012 | P1 | Build inventory import and 2D layout UI | PF-010 |
| PF-013 | P1 | Versioned price books and cost sheet snapshots | PF-010 |
| PF-014 | P1 | Role and contextual permission engine | PF-007 |
| PF-015 | P1 | Approval policies and decision ledger | PF-014 |
| PF-016 | P1 | Offer, discount and hold extension workflows | PF-013, PF-015 |
| PF-017 | P1 | Unified interactions and inbound connector architecture | PF-008, PF-003 |
| PF-018 | P1 | Durable external message delivery refactor | PF-003 |
| PF-019 | P1 | Buyer property passport foundation | PF-008, PF-011 |
| PF-020 | P1 | Immutable finance ledger and reconciliation | PF-002, PF-011 |
| PF-021 | P1 | Generated demand letters and document lifecycle | PF-020, PF-015 |
| PF-022 | P1 | Governed metrics catalog and query APIs | PF-008, PF-010, PF-020 |
| PF-023 | P1 | Sales copilot with evidence and human review | PF-008, PF-017, PF-014 |
| PF-024 | P1 | Inventory matching agent with permissions | PF-010, PF-013, PF-023 |
| PF-025 | P2 | Versioned workflow engine and visual builder | PF-015, PF-018 |
| PF-026 | P2 | Channel partner onboarding and referral ownership | PF-008, PF-014 |
| PF-027 | P2 | Broker commission reconciliation | PF-026, PF-020 |
| PF-028 | P2 | Customer service, handover and warranty system | PF-019 |
| PF-029 | P2 | Forecasts and scenario planning | PF-022 |
| PF-030 | P3 | API developer portal and integration marketplace | PF-014, PF-018 |

**Priority rules:** A P0 blocker can leapfrog roadmap order. PF-010 inventory is foundational and should start promptly after immediate financial/privacy risks are contained. Do not interpret numerical IDs as rigid waterfall delivery order.

---

# 24. WHAT SUCCESS LOOKS LIKE

## 24.1 Product success

- A single customer can safely explore and transact across multiple projects without fractured history.
- Salesperson does not need spreadsheets for property availability or follow up context.
- Team lead can locate and resolve blocked opportunities quickly.
- Developer leadership can trace sales, collections and bottlenecks from reliable data.
- Inventory state cannot contradict a committed transaction.
- Customer receives timely, accurate, permission appropriate communication.
- Broker and finance operations are auditable and reconciled.
- Buyer portal remains useful after sale and handover.
- AI improves the speed and quality of work without becoming a security or operational risk.

## 24.2 Measurement framework

Define the baseline before measuring improvement. Candidate metrics:

- Median and p95 first meaningful response time.
- Valid leads assigned in SLA.
- Missed follow up rate.
- Lead to visit, visit attended to booking and booking to collection conversion.
- Revenue and collection forecast accuracy.
- Inventory hold and double allocation exception count.
- Reconciliation accuracy, unmatched payments and aged receivables.
- Approval turnaround time.
- Channel partner disputes and commission resolution time.
- Customer support and handover SLAs.
- Agent accepted suggestion rate, factual accuracy, cost and escalations.
- Tenant onboarding time, feature adoption, retention and healthy integration percentage.

These are metrics to measure, not fabricated targets or existing business results.

---

# 25. FUTURE FORWARD BETS (ONLY AFTER THE FOUNDATION WORKS)

A product aiming to feel a generation ahead can invest in the following carefully staged capabilities.

### 25.1 Spatial real estate interface

A shared map and property canvas becomes the main way to understand an entire development. Search by geography, available views, orientation, route, unit, phase, buyer intent and upcoming infrastructure. Use legally reliable geometry when representing boundaries.

### 25.2 Explainable revenue simulator

A director adjusts launch phase timing, advertising budget, target collection schedule or proposed incentives and sees scenario ranges with sensitivity analysis, assumptions and uncertainty. No magical "guaranteed revenue" output.

### 25.3 Proactive operating brief

Each manager receives a compact morning report: blocked approvals, expiring holds, overdue collections, unassigned enquiries, site visit problems and actionable exceptions, with clear reasons. Users can drill into records and approve action.

### 25.4 Natural language workplace, not a standalone chatbot

A universal command surface embedded into project, customer, inventory and finance screens. Questions and suggestions automatically inherit authorized context. The AI cannot bypass policy or silently change the system.

### 25.5 Durable property passport

One secure digital dossier follows the property through enquiry, reservation, legal documents, payments, construction milestones, handover, warranty and service. Owners retain access to the documents they are entitled to, regardless of who the salesperson was.

### 25.6 Negotiation and sales coaching intelligence

Evidence linked analysis of consented interactions helps executives anticipate missing information, prepare options and understand objections. Explanations must be respectful, testable and free of unjustified assumptions about protected traits.

### 25.7 Portfolio wide predictive operations

Models identify patterns in sales velocity, service delays, collections risk and project launch readiness, with transparent uncertainty and human review. Use historical ground truth, drift monitoring and independent evaluation.

### 25.8 Composable real estate workflows

Organizations can adjust a powerful shared platform to their own sales and operational processes through configuration, not forks. Versioned rules, permissions, approvals and APIs create real ecosystem defensibility.

---

# 26. FIRST EXACT PROMPT TO GIVE CLAUDE CODE

Copy the following into Claude Code **with this Markdown document in the repository**:

> Read `PROPFLOW_MASTER_BLUEPRINT_FOR_CLAUDE_CODE.md` in full and treat it as the target product specification, not a signal to implement every module now. First inspect the current repository and verify the reviewed baseline. Read the existing README, repo map, architecture docs, Python modules, database models/migrations, frontend routes and current tests. Run the existing safe tests, document pass/fail evidence, and create a `CURRENT_STATE_AUDIT.md` with a source based gap matrix. Then implement the highest risk reproducible P0 issue: make installment receipt posting concurrency safe, uniquely numbered and idempotent while preserving existing APIs, records, tenant boundaries and tests. Complete the migration, service, test suite and documentation in one finished vertical slice. Do not change production data, send external messages, deploy, or rewrite the application. After finishing, report exact files changed, tests executed, migration safety and the next proposed single task. If the issue is already fixed on the current branch, demonstrate that and proceed to the next verified P0 gap instead.

## 26.1 First follow on prompts (one at a time)

**After first financial integrity slice is complete:**

> Now review the existing messaging outbox and implement dispatch time customer consent and suppression enforcement. Account for revocation after queueing, tenant suspension, channel purpose, retries and audit. Preserve the existing provider adapters. Implement full negative tests and show end to end evidence; do not send live external messages.

**After consent fix is complete:**

> Review Meta lead connector page mapping, identity matching and webhook idempotency. Correct verified flaws using proper tenant scoped integration mappings, preserve lead provenance, add safe migrations and integration tests, and improve operational error reporting. Do not claim live Meta functionality without a configured provider sandbox test.

**After connector fix is complete:**

> Design and implement Phase 1 canonical customer identity plus multiple project opportunities using an additive migration. Keep existing lead APIs operational and preserve historical visits, conversations, sale bookings and source attribution. Deliver one fully tested UI workflow, negative tenant access tests, and a migration/backfill verification report. Stop after this completed slice.

**After identity work is complete:**

> Implement Phase 2 property inventory as a real transactional domain: normalized project unit hierarchy, state events, atomic hold acquisition/expiration/release, pricing version linkage, and cross tenant permissions. First deliver backend invariants and concurrency tests, then a complete interactive 2D inventory studio, with no placeholder screens. Preserve existing sale booking records and provide a reconciled migration path to `unit_id`.

---

# 27. FINAL DECISION FRAMEWORK

When deciding whether to add a feature, Claude Code and product leadership should ask:

1. Is there a real developer, executive, sales, finance, partner or buyer problem that this solves?
2. Does this connect to the shared customer/property/transaction data model?
3. What authoritative records does it rely on?
4. Who can see, approve, execute, reverse and audit the action?
5. How does the feature behave under concurrency, failure, timeout and retries?
6. Does it reduce manual work or genuinely improve a decision?
7. Can this capability be configured across different developers without code forks?
8. Can we measure its success against a baseline?
9. Is the user experience considerably better than existing industry tools?
10. Can we show a real working workflow, not a mockup or promotional claim?

**The moat is not more feature checkboxes.** It is a trusted, deeply interconnected real estate operating model, with exceptional workflow execution, integrated customer and property history, transparent finance, thoughtful AI and a product teams actually enjoy using.

**Build reliable foundations first. Then build the magic on top.**

---

## Appendix A. Source inventory inspected

Relevant paths directly retrieved in review:

```text
README.md
PROJECT.md
BUILD_SPEC.md
TECHNICAL_DESIGN.md
REPO_MAP.md
.github/workflows/ci.yml
docker-compose.yml
frontend/package.json
frontend/src/App.tsx
frontend/src/admin/AdminLayout.tsx
frontend/src/sales/SalesLayout.tsx
frontend/src/sales/SalesPlaceholderPages.tsx
backend/requirements.txt
backend/app/main.py
backend/app/api/v1/router.py
backend/app/db/tenancy.py
backend/app/modules/auth/dependencies.py
backend/app/modules/auth/security.py
backend/app/modules/auth/service.py
backend/app/modules/auth/router.py
backend/app/modules/users/models.py
backend/app/modules/leads/models.py
backend/app/modules/leads/repository.py
backend/app/modules/leads/router.py
backend/app/modules/leads/service.py
backend/app/modules/leads/schemas.py
backend/app/modules/projects/models.py
backend/app/modules/tenancy/models.py
backend/app/modules/tenancy/router.py
backend/app/modules/settings/models.py
backend/app/modules/messaging/models.py
backend/app/modules/messaging/engine.py
backend/app/modules/messaging/dispatcher.py
backend/app/modules/messaging/scheduler.py
backend/app/modules/messaging/router.py
backend/app/modules/messaging/providers/factory.py
backend/app/modules/connectors/models.py
backend/app/modules/connectors/service.py
backend/app/modules/connectors/router.py
backend/app/modules/connectors/meta_leads.py
backend/app/modules/connectors/portal_email.py
backend/app/modules/postsales/models.py
backend/app/modules/postsales/service.py
backend/app/modules/postsales/repository.py
backend/app/modules/postsales/router.py
backend/app/modules/postsales/schemas.py
backend/app/modules/billing/models.py
backend/app/modules/billing/service.py
backend/app/modules/billing/router.py
backend/app/modules/operator/dependencies.py
backend/app/modules/operator/service.py
backend/app/modules/operator/deployments.py
backend/app/modules/notifications/scheduler.py
backend/app/modules/ai_assistant/tools.py
backend/app/modules/ai_assistant/service.py
backend/app/modules/ai_assistant/provider.py
backend/tests/integration/test_tenant_isolation.py
backend/tests/integration/test_tenant_domain_isolation.py
```

This is a source inspection of important files and repository topology, **not an exhaustive line by line security audit of all 489 files**.

## Appendix B. Document authority and freshness

The old `PROJECT.md` describes an earlier MVP and states that a full CRM, WhatsApp and post sales are out of scope. Those historical statements have been superseded in the actual November 21 repository, which includes SaaS, messaging and post sales implementations. This master blueprint establishes the **target direction**, but the checked out source and its migration history establish **present implementation truth**.

**End of master blueprint.**
