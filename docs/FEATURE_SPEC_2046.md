# PROPFLOW 2046
## The Enterprise Real Estate Operating System
### Feature Expansion Master Specification for Claude Code

**Scope:** New capabilities and major expansions only. This is a feature specification, not a code audit, generic technology essay, prototype plan, or UI mockup.

**Repository:** `https://github.com/vishnudantu/real-crm`

**Reference:** `main` at `2475830e91` (22 November 2026). **Before implementing, inspect current HEAD again**: existing functionality may have changed. The recently committed additions include an omnichannel inbox, website widget, calling components, tenant feature flags, dispatch-time suppression, receipt concurrency safeguards, billing period meters, per-tenant Meta connections, and expanded CI. Inspect the latest implementations and extend them, rather than recreating them. Do **not** build duplicate modules for any of these.

**North star:** A real estate company should be able to run acquisition, customer relationships, sales, property inventory, negotiations, reservations, legal documentation, money movement, collections, construction visibility, possession, service, partner networks and executive decisions in one connected platform. Routine work should happen automatically. Any action that creates a legal, financial, privacy or material commercial consequence must have a clear policy, evidence trail and appropriate approval.

**Release standard:** Enterprise ready, complete workflows. No mock-only routes, static-only dashboards, buttons without behavior, simulated sending described as successful delivery, unpersisted settings, dead-end navigation, generic placeholder cards or UI shells. For each feature: full interface, domain model, validated API, permissions, real persistence, transactional correctness where relevant, event handling, automation, audit trail, alerts, exports, tests, observability and documented operational behavior.

**Priority key:** `P0` indispensable business foundation; `P1` enterprise completeness; `P2` major competitive differentiator; `P3` ambitious frontier capability. `P3` does not mean a fantasy feature; it must still have measurable success conditions and honest confidence indicators.

---

# PART I. THE NONNEGOTIABLE PRODUCT EXPERIENCE

## 1. Everything must feel like one product

- [P0] **Global command palette:** Find a customer, unit, project, payment, approval, ticket, document, workflow or configuration in one secure search. Commands such as “create visit,” “reserve unit,” “open payment ledger” and “assign customer” launch the actual authorized workflow.
- [P0] **Role-aware workspace switcher:** Operator, developer admin, sales, manager, finance, legal, inventory, customer care, channel partner and buyer each receive a purpose-built interface. Staff with several roles can switch workspace without losing context.
- [P0] **Navigation as a product system:** Collapsible groups, expandable submenus, active path, counts on actionable queues, favorites, recently used pages, full-text menu search, breadcrumbs, keyboard shortcuts, desktop collapse and mobile drawer. Hide inaccessible features, not simply gray them out; server permissions must independently enforce access.
- [P0] **Action Center:** Cross-module inbox of approvals, overdue actions, payment mismatches, SLA breaches, failed workflows, customer escalations and expiring unit holds. Every card links to source evidence and permits eligible one-click resolution.
- [P0] **Universal record timeline:** Every customer, unit, project, transaction and service case shows an auditable history of changes, communications, approvals, documents, ownership and automation actions.
- [P0] **Real workspaces, not grids alone:** Every module has list, detail, create/edit, timeline, bulk actions where relevant, attachments, filters, saved views, search, import/export, notifications, empty/error/loading states and explicit permissions.
- [P0] **Never lose the user's place:** Persistent filters and table settings, resumable drafts, optimistic UI only where safe, undo for reversible actions, deep links to nested records and history-preserving navigation.
- [P0] **Actionable notifications:** Deduplicated in-app notification center with priority, assignment, snooze, reminders, escalation, acknowledgement and resolution links. Notification preference center by role, channel and event.
- [P1] **Personal working home:** Each user chooses pinned metrics, widgets, work queues, saved searches, morning brief and preferred workspace, within organizational policy.
- [P1] **Strong mobile-first field operations:** Offline-capable site visit checklists, geolocation with explicit permission, photo capture, dictation, digital signatures and conflict resolution after reconnect.
- [P1] **Multilingual UX:** English first, with Telugu, Hindi and other Indian languages as configurable packs. Translation must cover navigational labels, notifications, documents and buyer interactions, with human review of legal or payment copy.
- [P2] **Conversational command interface:** Secure natural language requests can query business data, generate reports, prepare workflows and draft actions; the interface previews impact and requires confirmation for sensitive actions.
- [P2] **Adaptive UX:** Suggested next steps, role-specific shortcuts and contextual panels respond to current tasks, not opaque user profiling. Users can override, inspect and disable recommendations.
- [P3] **Spatial workbench:** Optional 2D/3D navigation from geographic area to project, building, floor, unit, asset and related records. This complements, rather than replaces, accessible tables.

## 2. The quality standard for EVERY menu item

A sidebar item is not complete merely because a page renders. Every visible feature must meet its applicable requirements:

1. The page solves a specific recurring task for a defined role, and its UI works with realistic data sets.
2. Search, filter, sort, pagination, saved views and bulk operations exist where useful, with predictable behavior for large data sets.
3. Users can create, view, update and complete the relevant business action, or see a justified read-only state.
4. Required documents, communications, comments, attachments, mentions and approvals are supported.
5. Every state transition has explicit business rules, validation, actor, timestamp, tenant scope and audit history.
6. Role permissions apply to navigation, page rendering, API routes, background jobs, exports and attachments.
7. Background operations show queued/running/succeeded/failed/cancelled status, retry behavior and error recovery; there is no fake success state.
8. Empty, loading, error, partial failure, conflict, offline, deleted and permission-denied states are deliberately designed.
9. Reports and KPIs come from authoritative records, are drillable and disclose data freshness and calculation definitions.
10. Screens support desktop, tablet and mobile where that role genuinely needs them, with keyboard and screen reader accessibility.
11. Feature activation is coherent: menu, route, entitlements, backend checks, automations and documentation all agree.
12. Operational tests cover permission boundaries, failure cases, concurrency, idempotency and at least one complete workflow.

---

# PART II. COMPLETE SIDEBAR AND WORKSPACE ARCHITECTURE

The top-level navigation must stay clean. Each section below describes the desired **collapsible menu group**, its subpages and the real workflows behind them. Users should never see every group at once unless their permissions justify it.

## 3. OPERATOR CONSOLE: SaaS platform owner and operations team

**The Operator is the company operating PropFlow, NOT a developer tenant administrator.** The Operator Console must manage the platform, customers, revenue, security, health, entitlements, ecosystem and AI operations without arbitrary access to buyer personal information.

### 3.1 Operator sidebar

| Group | Sidebar items and full screens | Core capability |
|---|---|---|
| **01. Mission Control** | Platform Overview; Live Operations; Revenue Pulse; Active Incidents; Operator Action Center | Real-time tenant, service, revenue, queue and incident health with drilldowns and ownership |
| **02. Organizations** | Tenant Directory; Create Tenant; Onboarding Pipeline; Tenant 360; Business Hierarchies; Domains & Branding; Data Regions; Tenant Lifecycle | Provision, verify, configure, merge where allowed, suspend, restore, close and export tenant records through governed workflows |
| **03. Plans & Entitlements** | Plan Catalog; Feature Bundles; Add-ons; Tenant Entitlements; Trials; Quotas & Meters; Commercial Exceptions; Pricing Experiments | Metered plans, multi-year contracts, named seats, credits, package overrides, grace windows, fair-use rules and approvals |
| **04. Platform Billing** | Subscription Ledger; Invoices; Payments; Credits & Refunds; Tax Documents; Dunning; Collections; Disputes; Revenue Recognition | Actual subscription finance with provider reconciliation and legally compliant evidence |
| **05. Infrastructure** | Environments; Deployments; Releases; Database Health; Storage & Backups; Queue Operations; Scheduled Jobs; Disaster Recovery; Service Status | Production-grade operations, rollbacks, capacity, restore tests and service objectives |
| **06. Integrations Ecosystem** | Connector Catalog; Tenant Connections; OAuth Applications; Webhook Deliveries; Integration Health; API Keys; Partner Apps; Marketplace Review | Provision, test, rotate, revoke, observe and monetize authenticated integrations |
| **07. Trust & Access** | Operator Directory; Operator Roles; SSO & Identity; MFA & Passkeys; Privileged Access; Session Review; Audit Explorer; Data Protection | Just-in-time access, least privilege, approvals and independent, immutable security evidence |
| **08. Automation Operations** | Workflow Registry; Run Monitor; Schedules; Failure Queue; Retries & Replays; Rate Limits; Notification Deliverability; Provider Status | Diagnose and recover workflows without editing customer data silently |
| **09. AI Control Plane** | Agent Registry; Model Registry; Tool Permissions; Knowledge Policies; Evaluation Lab; Prompt Versions; AI Costs; Safety Incidents; Human Reviews | Govern what agents know and do, measure accuracy and block unsafe actions |
| **10. Customer Success** | Onboarding Accounts; Adoption Health; Support Desk; Implementation Projects; Training; Renewals; At-risk Tenants; Customer Feedback | Run onboarding, support, success and churn-prevention journeys |
| **11. Product Operations** | Feature Flags; Release Channels; Experiments; Product Analytics; Feedback Boards; Global Templates; Localization; Announcements | Progressive rollout, product experiments, controlled template distribution and change governance |
| **12. Intelligence & Reports** | SaaS Economics; Tenant Cohorts; Utilization; Retention; Churn; Forecasts; Revenue Quality; Custom Report Builder | Understand unit economics and product performance with source-level drilldowns |
| **13. Governance & Settings** | Global Policies; Regional Rules; Consent Standards; Retention Defaults; Provider Contracts; Compliance Reports; Organization Settings | Versioned, jurisdiction-aware platform governance |

### 3.2 Operator-level must-have enhancements

- [P0] **Tenant 360 page:** Contract, plan, environments, feature flags, users, allowed usage metrics, billing health, deployment versions, tickets, incidents, AI spend and integration health in one view. Do not expose buyer conversations or tenant customer records by default.
- [P0] **Tenant onboarding wizard:** Organization identity, billing profile, logo/theme/domain, tenancy region, admin invitation, industry setup, project template, provider connections, test events, readiness checklist and activation.
- [P0] **Commercial entitlement engine:** Grant and revoke seat counts, modules, connector capacities, storage, automation executions, AI tokens/credits, service tiers and reserved capacity; record approvals and effective dates.
- [P0] **True SaaS metering:** Subscriptions, unique active seats, contacts, messages, AI credits, storage, document generation and automation runs must be metered by correct billing periods with overage policies and transparent statements.
- [P0] **Operator access boundary:** Tenant support access requires ticket, approved reason, short expiry, explicit scope, customer-visible trace where appropriate and immutable operator audit. No hidden omnipotent account.
- [P0] **Service operations:** Region/tenant-aware health status, failed webhook delivery, queue age, scheduler lag, error budgets, model provider downtime, recovery actions and incident owner.
- [P1] **Tenant safe-mode:** Temporarily disable high-risk automation, outbound communication, booking mutation or billing writes per tenant while preserving read access and audit.
- [P1] **Revenue protection:** Renewal schedules, grace periods, invoice disputes, collection follow-ups, credits, refunds, cancellations, taxes and dunning with tenant notifications.
- [P1] **Versioned connectors:** Credential health, expiry alerts, test connection, sync cursor, signed callbacks, backfill/replay, idempotency and scoped permissions.
- [P1] **Tenant portability:** Consent-aware export, verified import, archive, deletion schedules, migration preview, data mapping and disaster recovery procedures.
- [P2] **Operator AI copilot:** Explain incidents, summarize tenant adoption, draft support responses and propose safe operational actions; never read tenant PII without permission.
- [P2] **Workload forecasting:** Predict queue, AI inference, storage and integration capacity with confidence intervals and sensible scale-up recommendations.
- [P3] **Tenant simulation lab:** Before enabling new pricing, quotas, workflow templates or AI models, simulate aggregate business impact in an isolated sandbox using anonymized or synthetic data.

## 4. ADMIN CONSOLE: developer CEO, COO, sales head and business administrator

The Admin Console must be the operational nerve center of the property developer. Admin modules should use **logical sections** and configurable role permissions rather than one flat list of fifty links.

### 4.1 Admin sidebar

| Group | Sidebar items and full screens | Core capability |
|---|---|---|
| **01. Command Center** | Executive Overview; Today; Priority Queue; Revenue & Collections Pulse; Team Activity; Live Exceptions; Decision Feed | Business health, next actions, bottlenecks and forecast explanations |
| **02. Customers** | Customer Directory; Customer 360; Households & Relationships; Opportunities; Duplicates & Merges; Consent Center; Customer Segments; Lost & Reopened Leads | One customer across projects, sources, families and life stages |
| **03. Property Portfolio** | Project Directory; Phases & Buildings; Plotted Layouts; Unit Registry; Interactive Inventory Map; Floor Stacks; Property Documents; Digital Asset Library | Accurate hierarchy from project down to saleable unit |
| **04. Inventory & Pricing** | Live Availability; Unit Holds; Blocked Units; Price Books; Rate Cards; Charges & Taxes; Offers; Price Approvals; Inventory Audit | Controlled real-time saleability, prices and concessions |
| **05. Marketing & Growth** | Campaigns; Media Spend; Attribution; Offline Sources; Lead Capture; Forms & Landing Pages; Audiences; Conversion Quality; Experiment Lab; Creative Performance | Measure lead-to-collection economics, not vanity enquiries |
| **06. Sales Operations** | Pipeline Board; Sales Distribution; Territories; Teams; Targets; Site Visits; Task Queues; Sales SLA; Coaching; Performance; Opportunity Reviews | Manage people, processes and accountability |
| **07. Communication Hub** | Omnichannel Inbox; Calls; Call Recordings; Email; WhatsApp; Web Chat; Templates; Sequences; Outbound Campaigns; Deliverability; Contact Preferences | Full two-way communication, searchable and attributable |
| **08. Automation Studio** | Workflow Builder; Workflow Library; Active Runs; Schedules; Triggers; Escalation Policies; Failed Runs; Approval Steps; Automation Analytics | Tenant-configurable operational automation with safety rails |
| **09. Deal Desk** | Cost Sheet Builder; Negotiations; Proposal Versions; Discount Requests; Price Locks; Unit Reservations; Approvals; Booking Queue; Escalations | Controlled negotiations and booking decisions |
| **10. Bookings & Contracts** | Sale Bookings; Booking Applications; KYC; Agreements; Registration; E-sign; Document Checklists; Cancellation & Transfer; Amendments | Traceable contractual progression |
| **11. Finance & Collections** | Collections Overview; Customer Ledgers; Payment Plans; Upcoming Dues; Demand Notices; Reminder Campaigns; Payment Receipts; Bank Reconciliation; Part Payments; Overdues; Refunds; Charges & Waivers; Finance Approvals; Statements; Finance Reports | Real-money tracking with automated reminders, reconciliation and controls |
| **12. Channel Partners** | Partner Directory; Partner Onboarding; Listings Access; Referral Claims; Partner Leads; Booking Attribution; Commission Plans; Payables; Payouts; Disputes; Partner Performance | Transparent partner-led sales |
| **13. Construction & Progress** | Milestone Plans; Progress Updates; Evidence & Photos; Contractor Updates; Delay Risks; Buyer Communication; Construction-linked Demand Triggers | Truthful, approved project updates |
| **14. Handover & Ownership** | Possession Readiness; Snagging; Inspection Schedule; Handover Appointments; Keys & Documents; Warranties; Homeowner Records; Service Cases; Referrals | Lifecycle management after purchase |
| **15. Intelligence & Reports** | Revenue Analytics; Funnel Analysis; Cash Forecast; Inventory Velocity; Campaign ROI; Executive Scorecards; Forecast Models; Custom Reports; Scheduled Reports; AI Analyst | Actionable, explainable business reporting |
| **16. People & Approvals** | Staff Directory; Teams; Role Designer; Permissions; Delegations; Approval Matrix; SLA Policy; Targets; Incentives; Activity Audit | Enterprise organization and governance |
| **17. Integrations & Data** | Connected Apps; Lead Sources; ERP/Accounting; Banking; Telephony; Website Widget; API/Webhooks; Import Center; Export Center; Data Quality; Migration Jobs | Verified interoperability and controlled data movement |
| **18. Brand & Organization** | Company Profile; Business Units; Projects; Branding; Email Domains; Notification Identity; Offices; Working Calendars; Languages; Currency & Tax Profiles | Multi-brand, multi-office organization configuration |
| **19. Security & Compliance** | Access Policies; Audit Trail; Consent & Privacy; Retention; RERA Registers; Document Access; Data Subject Requests; Compliance Exceptions | Operational trust and evidence |
| **20. Settings** | Organization Defaults; Custom Fields; Pipeline Designer; Numbering Rules; Templates; Workflows; Pricing Policies; Notification Preferences; Feature Settings; Integrations Settings | Configuration without developer intervention |

### 4.2 Admin dashboard behavior

- [P0] Cards for booked revenue, collected cash, overdue receivables, expected cash, available units, held units, aging deals, pending approvals, active workflows and unresolved customer escalations.
- [P0] Every KPI is selectable and opens the correct underlying list with preapplied filters. Display as-of timestamp, currency, calculation and missing data warning.
- [P0] Actionable views: “15 holds expire today,” “8 payments require matching,” “5 agents missed response SLA,” “3 major discounts await approval.”
- [P1] Compare project, phase, city, sales team, source, channel partner, campaign, cohort and time period.
- [P1] Schedule executive email/PDF reports with verified delivery and access-controlled links.
- [P2] Ask plain-language questions, receive cited data and navigate directly to source transactions.
- [P2] Executive scenario planning: interest-rate, campaign budget, conversion and construction-delay assumptions yield transparent scenario results, not fabricated certainties.

## 5. SALES EXECUTIVE WORKSPACE

The sales user is often moving, calling, visiting projects and chasing documentation. Prioritize speed and context. Do not simply copy the Admin sidebar.

| Group | Sidebar items | Required behavior |
|---|---|---|
| **My Day** | Today's Plan; Smart Priorities; Overdue Actions; Activity Feed | Ordered work with reasons, one-click outcomes, reminders and SLA awareness |
| **Customers** | My Customers; New Assignments; Customer 360; Opportunity Pipeline; Lost/Revival Queue | Complete permitted history, notes, preferences, relationships and next actions |
| **Communications** | Unified Inbox; My Calls; Call Notes; Templates; Follow-up Sequences | Channel history, outcome capture, consent and approved messaging |
| **Properties** | Live Inventory; Unit Comparison; Project Library; Offers & Cost Sheets | Accurate availability, downloadable approved collateral, comparisons and calculations |
| **Visits** | My Calendar; Upcoming Visits; Check-in; Visit Outcomes; Reschedules; Route Planner | Verified attendance, travel context and post-visit workflow |
| **Deals** | My Proposals; Negotiations; Discount Requests; Reservations; Bookings in Progress | Submit offers, follow approvals, monitor expiring holds, finish documents |
| **Collections Assist** | Upcoming Customer Dues; Payment Link Requests; Payment Follow-ups; Issue Escalations | See authorized balances, never invent payment status or override ledgers |
| **Performance** | My Targets; Conversion Funnel; Response SLA; Coaching; Commission Outlook | Individual performance with clear definitions |
| **Workspace** | My Notifications; Saved Views; Personal Schedule; My Profile | Preferences, focus and task management |

**Sales power features:**
- [P0] One screen per customer with timeline, interests across projects, last communication, available matched units, budget, visits, proposals, outstanding tasks and permission-aware financial summary.
- [P0] Capture every call outcome via structured one-touch dispositions, next-action date and optional notes; prevent empty disposition data from faking an answered call.
- [P0] Instant unit comparison and versioned cost sheet, with mandatory price validity and tax disclaimers.
- [P0] Visit check-in, notes, attendee confirmation, photos where consented, and follow-up action created automatically.
- [P1] Voice-to-CRM dictation, reviewed before saving; speaker-specific transcription only with proper notice/consent.
- [P1] Smart next-best-action suggestions that explain their evidence, never force automatic persuasion.
- [P2] Offline field workspace for low-connectivity sites with later authenticated sync, merge resolution and safe retry.
- [P2] Personalized “morning briefing” on customers requiring attention and approval or collections exceptions.

## 6. SALES MANAGER / REGIONAL HEAD WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Team Command** | Team Overview; Today; SLA Breaches; Coverage Gaps | Team productivity, response quality, lead ownership gaps |
| **Pipeline** | Team Opportunities; Forecast; Stalled Deals; Deal Reviews; Target vs Actual | Accurate stage probability, age, deal quality and management actions |
| **Distribution** | Assignment Rules; Workload; Territories; Reassignments | Fair, policy-driven assignment with conflicts and history |
| **Sales Enablement** | Coaching; Call Reviews; Training; Knowledge Updates; Playbooks | Feedback with supporting evidence, manager sign-off and privacy controls |
| **Approvals** | Discount Approvals; Lead Transfers; Booking Exceptions; Special Terms | Authority limits, delegation, expiry and audit |
| **Reports** | Performance; Source Quality; Team Forecast; Visit Conversion | Consistent cross-team comparisons and exports |

## 7. FINANCE / COLLECTIONS WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Finance Today** | Cash Position; Due Today; Reconciliation Exceptions; Approval Queue | True cash visibility and exceptions, not dashboard approximations |
| **Receivables** | Customer Ledgers; Payment Plans; Installments; Aging; Credit Balances | Every charge, payment, adjustment and obligation tied to the correct booking |
| **Automation** | Reminder Calendar; Communication Policy; Delivery Status; Failed Notices; Escalation Rules | Fully scheduled campaigns and recoverable failures |
| **Cash Operations** | Payment Links; Bank Transactions; UTR Matching; Deposits; Suspense Account; Unapplied Receipts | Unique transaction references and exact reconciliation |
| **Documents** | Demand Letters; Receipts; Tax Invoices; Statements; Credit Notes; Refund Letters | Approved, numbered, downloadable and traceable documents |
| **Exceptions** | Disputes; Waivers; Part Payments; Overpayments; Reversals; Refunds; Chargebacks | Governed resolution with full financial history |
| **Control & Reports** | Approvals; Segregation of Duties; Audit; Receivables Forecast; Collection Effectiveness | Financial safeguards and audit-ready reporting |

## 8. INVENTORY / PRICING / REVENUE MANAGEMENT WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Property Registry** | Projects; Buildings/Blocks; Floors; Plots; Units; Inventory Import | Canonical hierarchical saleable assets |
| **Inventory Control** | Availability Map; Unit Holds; Blocked Units; Reservation Requests; Conflicts | Transactional controls and visible ownership |
| **Pricing** | Rate Cards; Premiums; Charges; Tax Rules; Price Books; Offer Rules; Price Version History | Transparent calculations and effective dates |
| **Approvals & Insights** | Price Exceptions; Release Queue; Velocity Map; Demand Heatmap; Unsold Inventory Risk | Approvals and explainable intelligence |

## 9. MARKETING / GROWTH WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Marketing Today** | Campaign Pulse; New Leads; Source Health; Quality Alerts | Real source quality and funnel health |
| **Acquisition** | Campaigns; Ad Accounts; UTMs; Landing Pages; Forms; Offline QR/Call Tracking | First-party tracking across online and offline sources |
| **Nurture** | Audience Segments; Journeys; Creative Library; Message Templates; Consent | Permissions-aware, suppression-safe outreach |
| **Attribution** | Lead-to-Booking; Lead-to-Cash; Cross-Touch Paths; Offline Conversions | Attribute actual revenue, with methodology disclosed |
| **Experimentation** | A/B Tests; Creative Insights; Budget Scenarios; Conversion Diagnostics | Controlled experiments and evidence-backed optimization |

## 10. LEGAL / DOCUMENTS / REGISTRATION WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Legal Today** | Pending Reviews; Expiring Documents; Registration Calendar; Exceptions | Upcoming legal work and accountable owners |
| **Contracts** | Agreement Templates; Draft Agreements; Version Comparison; Review Queue; E-sign; Executed Documents | Clause versioning, approval and signature evidence |
| **Customer Compliance** | KYC; Authorized Signatories; POAs; Nominee Data; Consents; Legal Holds | Encrypted document handling and verification status |
| **Transactions** | Allotment; Transfers; Cancellations; Refund Terms; Registration Checklist | Traceable decisions and required documents |
| **Registers & Audit** | Project Registers; Approval Documents; Disclosure Versions; Retention; Legal Audit | Jurisdiction-specific recordkeeping and defensible history |

## 11. PROJECT / CONSTRUCTION WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Project Delivery** | Projects; Milestones; Tasks; Contractor Updates; Delay Risks | Schedule and milestone accountability |
| **Evidence** | Site Photos; Inspection Records; Certifications; Approvals; Quantity/Progress Evidence | Dated, reviewed and source-linked evidence |
| **Customer Communication** | Approved Progress Bulletin; Upcoming Milestones; Delay Notices; Buyer Questions | No speculative completion claims |
| **Handover Preparation** | Snag Readiness; Units Ready; Inspections; Handover Dependencies | Workflow from construction to possession |

## 12. CUSTOMER SUPPORT / HANDOVER WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Service Desk** | Open Cases; Priority Queue; Escalated Cases; SLA Calendar | Ownership, categories, service clocks and resolution proof |
| **Possession** | Handover Calendar; Inspections; Snag Lists; Key Handover; Documents | Checklists, evidence and buyer acceptance |
| **After-sales** | Warranties; Maintenance Issues; Contractor Assignment; Customer Updates | Life-cycle service linked to exact unit and asset |
| **Quality** | Satisfaction; Reopened Cases; Root Causes; Service Analytics | Measurable service reliability |

## 13. CHANNEL PARTNER / BROKER PORTAL

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Partner Home** | My Dashboard; Announcements; Target & Earnings | Own-only data with current plan and commission terms |
| **Inventory** | Approved Projects; Live Availability; Offers; Marketing Collateral | Permissioned live availability, limited customer visibility |
| **My Customers** | Register Lead; Referral Status; Conflict Requests; Visit Scheduler | Verified ownership claims and duplicate dispute workflow |
| **Deals** | My Pipeline; Proposals; Bookings; Documentation | Own attributed deals and clear progress |
| **Commissions** | Eligible Commission; Statements; Invoices; Payout Tracking; Disputes | Rules, tax treatment and payout status |
| **Learning & Support** | Training; Certifications; Partner Desk; Profile & KYC | Onboarding and support |

## 14. BUYER / PROPERTY OWNER PORTAL

| Group | Sidebar items | Required behavior |
|---|---|---|
| **My Home** | Overview; My Properties; Important Dates; Notifications | Personalized milestones and next steps |
| **Discover** | My Recommendations; Compare Units; Saved Homes; Virtual Tours; Visit Booking | Live authorized property data, no fake availability |
| **My Purchase** | Reservation Status; Booking Summary; Payment Plan; Statements; Documents; Agreement Status | Complete, verified transaction history |
| **Payments** | Upcoming Dues; Pay Securely; Payment History; Receipts; Payment Issues; AutoPay Preferences | Official balance, payment links, verified payment state and self-service help |
| **Construction** | Progress Timeline; Approved Site Updates; Photos; Milestones; Estimated Possession | Latest approved progress with publication date |
| **Possession** | Inspection; Snag Reports; Handover Appointment; Key Documents; Warranties | Customer-driven readiness and acknowledgement |
| **Service & Community** | Support Tickets; Maintenance Requests; Referrals; Community Updates | Post-possession relationship and support |
| **My Account** | Household/Co-buyers; Documents & KYC; Communication Preferences; Consent & Privacy; Profile & Security | Secure joint-buyer permissions and privacy rights |

**Buyer portal principles:** Clear mobile experience, no employee controls, never surface another buyer's unit or personal information, no surprise payment demands, verified receipts only, useful explanations in the customer's preferred language, and human support available at every critical step.

## 15. INVESTOR / BOARD / EXECUTIVE READ-ONLY WORKSPACE

| Group | Sidebar items | Required behavior |
|---|---|---|
| **Portfolio** | Executive Summary; Project Performance; Revenue & Collections; Inventory Exposure | Trusted aggregate portfolio data |
| **Forecasts** | Cash Forecast; Sales Forecast; Construction Delivery; Scenarios | Transparent assumptions and confidence |
| **Governance** | Risks; Exceptions; Material Approvals; Compliance Reports | Material issues and decision log |
| **Board Packs** | Monthly Packs; Quarter Comparison; Exports; Scheduled Delivery | Permissioned snapshots and versioned reports |

---
# PART III. DOMAIN FEATURES TO ADD

## 16. The Unified Customer and Opportunity Graph

**Problem to eliminate:** One person becomes unrelated duplicate lead rows for every project or new enquiry. A real enterprise needs one identity with many opportunities and relationships.

- [P0] **Customer master:** People and organizations with stable identifiers, preferred name, phones/emails, verified contact points, language, communication preferences, household links, legal contacts and contextual notes.
- [P0] **Many opportunities per customer:** Every customer can simultaneously enquire about multiple developments, units and budgets. Opportunities track project, stage, owner, source, value, confidence, dates, outcomes and loss reasons.
- [P0] **Customer 360:** Unified timeline of all leads, visits, WhatsApp, calls, emails, notes, proposals, holds, documents, payments, ownership and service cases, with access restrictions at item level.
- [P0] **Identity resolution:** Match normalized phone/email, external IDs and verified relationships using deterministic rules first. Suggested fuzzy merges require user review and a reversible audit trail.
- [P0] **Relationship graph:** Co-buyers, spouses, family contacts, authorized representatives, trustees, nominees, companies, introducers, decision makers and referral edges. Consent and access remain per individual.
- [P0] **Contact validation and provenance:** Record who supplied contact data, originating channel, source evidence, last verification, contactability and permitted purposes. Never silently treat acquired contact data as marketing consent.
- [P0] **Cross-project journey:** Preserve campaign history and customer interests without falsely assigning all future bookings to the newest source.
- [P1] **NRI/overseas buyer profile:** Country, timezone, document requirements, authorized POA and appointment coordination without hardcoding legal treatment by nationality.
- [P1] **Buying intent profile:** Needs, budget range, move timeline, location preferences, amenities, deal-breakers, finance preferences and explicit customer corrections.
- [P1] **Duplicate resolution center:** Candidate matches, match reason, conflict fields, merge preview, source preservation, audit and undo policy.
- [P1] **Data quality score:** Missing owner, invalid contacts, stale requirements, missing consent provenance, unresolved duplicate and stale source mapping shown as correctable exceptions.
- [P2] **Temporal customer memory:** Dated preferences and contradictions. “Was looking for 2 BHK in June, switched to 3 BHK in October”; time-aware AI context, not static overwrites.
- [P2] **Explainable opportunity health:** Time since contact, customer interactions, visit evidence, budget fit and unresolved objections with human-readable drivers. Do not treat demographic traits as conversion propensities.
- [P2] **Opportunity graph visualization:** Relationship between buyer, family, projects, partner, executive, proposal and inventory; click through to authorized source records.
- [P3] **Consent-driven customer concierge:** Customers can proactively update needs via secure channel, authorize property alerts, request comparison packs and manage their relationship memory.

**Completed when:** One buyer can own multiple opportunities, identities merge safely, historical source attribution remains intact, and the user sees a reliable, permissions-aware customer history from any channel.

## 17. The Living Property Graph and Inventory Engine

The most important missing product capability is a canonical, transaction-safe inventory model.

- [P0] **Hierarchical property registry:** Developer → brand/business unit → development → phase → block/tower/layout → floor/sector → unit/plot/villa → parking/storage and optional saleable add-ons.
- [P0] **Unit identity:** Globally stable unit ID, tenant-scoped display code, project hierarchy, carpet/built-up/plot area with units, configuration, facing, orientation, floor, views, classification and legal identifiers.
- [P0] **Availability state machine:** Draft, Approved for Sale, Available, On Hold, Reserved, Booked, Sold, Blocked, Under Dispute, Cancelled and Released. Define every authorized transition and effective time.
- [P0] **Exclusive unit reservations:** Atomic transaction, database-enforced conflict prevention, user and customer ownership, reason, expiry, renewal limit, approval status and historical chain. No double-booking even with parallel API requests.
- [P0] **Automatic hold expiration:** Timer-driven release with warnings, policy exceptions, locking and event trail. Expired holds release availability only when no binding transaction supersedes the hold.
- [P0] **Inventory reconciliation:** Compare unit book, bookings and receipts for inconsistent states; flag mismatches rather than silently correcting binding transactions.
- [P0] **Bulk onboarding:** CSV/XLSX import with field mapping, preview, collision checks, validation errors, downloadable error report and safe repeat import.
- [P0] **Unit-level source of truth:** Proposals and cost sheets reference a versioned unit and its price book; facts are not copied into untraceable strings.
- [P1] **Interactive unit explorer:** Tower elevation, floor stack, grid of plots, availability color layers, unit details, filters, side-by-side comparison, linked documents and inventory activity.
- [P1] **GIS and geo-referenced layouts:** Map polygons for sites, plots and facilities; project pins, access roads, nearby amenities and authoritative coordinates.
- [P1] **Unit grouping:** Bulk block/unblock with approvals for management holds, staff units, reserved allocations, legal disputes and maintenance.
- [P1] **Inventory release calendar:** Planned launch by phase, allocation quotas, pre-launch waitlists and priority groups; permissioned allocation management.
- [P1] **Price book by unit attributes:** Base rate, floor rise, corner/view/facing premiums, PLC, amenity charges, parking, fees, applicable taxes, discounts, effective dates and validity.
- [P1] **Pricing version archive:** Every adjustment stores old/new value, reason, authority, effective date, optional scenario simulation and approvals.
- [P1] **Unit-specific official collateral:** Floor plans, site plans, specification sheets, photos, approvals and versioned legal disclosures.
- [P2] **Demand/availability heatmaps:** Compare actual enquiries, visits, holds, bookings, price elasticity observations and unsold exposure by unit class and area.
- [P2] **Inventory fit engine:** Recommend available units that satisfy buyer-stated requirements and budget, with exact explanation of each match and disqualification.
- [P2] **Live interactive digital twin:** 2D/3D asset graph tied to unit status, documents, construction milestones, snagging and service records. Must disclose render quality/source and never present fictional construction progress as reality.
- [P2] **Supply risk diagnostics:** Detect unhealthy concentration of slow-selling units, prolonged blocks and pipeline mismatch, with measured confidence.
- [P3] **Spatial scenario engine:** Test release schedules, unit mix and price-book revisions against actual demand, financing assumptions and historical outcomes; provide confidence ranges.

**Completed when:** Two concurrent users cannot reserve the same unit, every sale points to a canonical unit, availability stays consistent across all channels and the interactive map exactly matches transactional data.

## 18. Enterprise Deal Desk and Pricing Governance

- [P0] Versioned, itemized **cost sheets** with saleable unit reference, area basis, base consideration, mandatory/optional charges, discounts, taxes, registration estimates and payment schedule.
- [P0] **Quote expiration** and price validity window; previous versions remain viewable but cannot be mistaken for current approved price.
- [P0] **Negotiation record:** Customer ask, proposed price, rationale, comparable inventory, expected margin (when authorized), concessions and approver comments.
- [P0] **Approval matrix:** Rules by absolute discount, discount percentage, floor price, project, role, transaction value, nonstandard terms, partner involvement and exceptions.
- [P0] **Serial and parallel approvals:** Sales manager, revenue head, finance, legal and director as required. Delegation, absence rules, escalation, reapproval on edits and approval expiry.
- [P0] **Reservation linkage:** Accepted deal conditions must be immutably linked to approved price and unit hold; no booking under stale approvals.
- [P1] **Counteroffer management:** Documented rounds, acceptance, rejection, customer communication, internal deadlines and authority boundaries.
- [P1] **Special concessions:** Waived amenities, parking assignment, free upgrades, brokerage exceptions and installments linked to commercial impact.
- [P1] **Booking packet readiness:** Payment verification, identity documents, reservation expiry, signatory checks and agreement requirements visible in one checklist.
- [P2] **Deal simulation:** Show discount impact on project price integrity, inventory velocity, collection timing and comparable deals, with explicit assumptions.
- [P2] **Negotiation copilot:** Draft a defensible counterproposal within approved rules; no independent authority to promise a price or execute a sale.
- [P3] **Portfolio-level pricing advisor:** Recommend price-book adjustments from verified demand, absorption and inventory, reviewed for fairness and consumer protection, always subject to approval.

## 19. Full Contracting and Sales Transaction Lifecycle

- [P0] Booking application, buyer/co-buyer details, KYC collection, authorized signatory verification, project/unit linkage, approved terms and booking fee record.
- [P0] Contract status workflow: application → document verification → approval → agreement drafting → execution → registration → possession readiness → completed, with explicit cancellation branches.
- [P0] Template library for application forms, booking confirmations, allotment letters, agreement packs, demand letters, receipts, refund statements and owner handover documents.
- [P0] **Document versions and evidence:** Source template version, merged data snapshot, approver, generated time, immutable signed copy, checksum, send status, recipient access and acknowledgment.
- [P0] **KYC/document vault:** Document type, expiry, verification state, restrictions, redaction, encryption and role-based access.
- [P0] **Cancellation workflow:** Request, reason, terms, charges, outstanding amounts, approvals, refund instructions, inventory release dependencies and customer communication.
- [P0] **Transfer/nominee/co-buyer amendment:** Ownership and interest changes require approved evidence, audit and applicable contractual process.
- [P1] **E-sign integration:** Provider-backed signing flows, identity proofing, signing order, signer reminders, rejection paths, webhook verification and retained evidence.
- [P1] **Registration calendar:** Jurisdiction-specific checklist, appointment schedule, stamp duty guidance from approved rules, registration number and uploaded final deed.
- [P1] **Milestone audit:** No unit marked sold solely because a salesperson advanced a pipeline stage; sale status follows recorded documentary and payment criteria.
- [P2] **Contract intelligence:** Highlight missing clauses or inconsistent commercial details against approved templates, with legal review and source references.
- [P3] **End-to-end buyer document passport:** Customer retains authorized access to verified historical versions throughout resale, support and ownership transitions.

## 20. FINANCE OS: Collections, reminders, matching, receivables and refunds

**This is a flagship system, not a sidebar ornament. All routine reminders and collections processing should be automated according to configurable policy. Actual money movement must be independently verified.**

### 20.1 Receivable and financial master data

- [P0] Every executed booking has a canonical account ledger with customer(s), unit, consideration, deposits, adjustments, discounts, payment-plan version, outstanding, overdue, credit balance and audit.
- [P0] Payment plan types: fixed dates, construction-linked stages, time-linked stages, booking/possession milestones, customized schedules and authorized amendments.
- [P0] Installment records include due date, due amount, paid amount, remaining amount, grace period, status, plan version, tax components, interest/penalty terms if applicable, document evidence and dispute status.
- [P0] Use ledger journal entries for charges, collections, reversals, credits, refunds and adjustments; never overwrite a past money event to correct history.
- [P0] Separate **due**, **demand issued**, **payment initiated**, **payment settled**, **bank matched**, **receipt issued** and **account reconciled** states. They are not interchangeable.
- [P0] Configurable reference numbering for each legal entity/project and financial document type, allocated safely under concurrency with no duplicate numbers.
- [P0] Permissions and maker/checker separation: The user who initiates a sensitive adjustment or refund cannot alone approve and release it, except under a recorded policy exception.
- [P1] Multi-entity accounting and project cost center mapping, with separate tax registrations and bank accounts where required.
- [P1] Explicit handling for split buyers, one payment covering several installments, one installment paid across multiple transactions, overpayments, refunds and transfers.
- [P1] Customer payment statement with date, reference, applicable installment, evidence, balance after transaction and downloadable official documents.

### 20.2 The automated payment reminder engine

Each tenant and optionally each project/payment-plan class can configure reminder ladders. **All example offsets below are editable policies, not universal legal defaults.**

| When | Automatic action | Expected outcome / routing |
|---|---|---|
| **15 days before due** | Send personalized upcoming installment statement with approved payment options | Record delivery outcome; permit customer questions |
| **7 days before due** | Reminder with amount, due date, unit, secure verified payment link and support channel | Stop if settled or legally paused |
| **3 days before due** | Preferred-channel reminder and optional alternate-channel fallback | Deduplicate to avoid harassment |
| **Due date** | Due-today alert with verified outstanding amount | Create relevant in-app task if customer requests help |
| **1 day overdue** | Gentle overdue notice after grace-period evaluation | Escalate only if configured and lawful |
| **3 days overdue** | Collection specialist work item and customer message | Assign owner, SLA, dispute option |
| **7 days overdue** | Escalation to collections manager with aging reason and delivery history | Manager reviews and chooses permitted next action |
| **15 days overdue** | Finance review of installment, dispute, financial hardship, contract clauses and notices | Approval required for material communication or charges |
| **30 days overdue** | High-priority recovery review with documents and legal-policy checks | No threats, unsupported penalties or autonomous legal action |

**Automation rules:**
- [P0] Every reminder is evaluated at execution time against **live outstanding amount**, settled payments, grace period, customer disputes, policy pauses, bankruptcy/legal hold, opt-out/consent and communication windows.
- [P0] Per-channel and per-recipient permissions; approved WhatsApp templates where required, registered SMS templates where required, authenticated email identity and correct language.
- [P0] Contact routing preferences: WhatsApp → email → SMS → human task, configurable with consent and allowed fallback. Missing contact details should create an exception, not silently disappear.
- [P0] Never send an overdue reminder when an installment has already been settled or officially suspended.
- [P0] Suppress duplicates from concurrent workers, webhook retries or schedule resync; log skip reason, policy version and execution ID.
- [P0] Track **queued → submitted → provider accepted → delivered → read (if available) → failed → retried → suppressed**, with correlation to installment and customer.
- [P0] Dynamically build the notice from approved ledger values, not AI guesses. Template preview must show the exact customer-facing amount.
- [P0] Timezone-aware business calendar, customer quiet hours, working days and regional holidays. Defer appropriately rather than sending at midnight.
- [P0] Automatic opt-out, bounce and invalid-number suppression. User-initiated transactional communications need purpose-specific policy treatment rather than blanket marketing opt-in assumptions.
- [P0] Customer response such as “I have paid,” “need time,” “wrong amount,” “send statement,” or “talk to accounts” must create an appropriately categorized task or verified next step, not be ignored.
- [P0] Change of due date, installment amendment, booking cancellation or payment settlement must cancel or recalculate scheduled notices.
- [P0] Communication frequency caps and escalation limits to prevent harassment and repeated reminders across multiple installments for the same customer.
- [P1] Group pending installments into one clear statement when allowed, while retaining individual ledger and reminder histories.
- [P1] Manager calendar showing the next 30/60/90 days of planned notices, eligible recipients, expected costs and paused campaigns, with dry-run preview.
- [P1] Reminder experiment controls: test permitted templates/timing on opt-in cohorts with accurate delivery and collections outcome measures.
- [P2] Predicted collection delay risk using relevant payment history and project/contract evidence, with explainable reasons and no punitive autonomous decision.
- [P2] Customer-selectable digital reminders and calendar integration with one-click “request payment assistance.”

### 20.3 Automatic demand letters

- [P0] Scheduled or milestone-triggered demand notice only after verifying approved contractual trigger and, where applicable, certified construction milestone.
- [P0] Generate a versioned, numbered PDF and optionally email/WhatsApp delivery link with legal entity details, unit, customer, installment, tax, bank details, due date, payment instructions and references.
- [P0] Review and approval stage for milestone-linked or exception demands. Approval evidence attached before any external delivery.
- [P0] Real send integration and delivery callbacks, archived dispatch record, customer download link and follow-up schedule.
- [P0] Corrected letters produce new versions and explicit supersession; never quietly overwrite an issued legal notice.
- [P1] Bulk demands to approved cohorts, with preview, sample validation, exception handling and rate-limit control.
- [P1] Customer acknowledgment and secure dispute flow linked to a named finance owner.

### 20.4 Payment collection and bank reconciliation

- [P0] Payment link creation against a particular booking or installment, with exact amount, expiry, payer instructions and verified provider reference.
- [P0] Real payment provider webhooks, signature verification, replay protection, settlement callbacks and immutable raw event record with sensitive fields protected.
- [P0] Bank transaction ingestion through supported feeds or secure statement upload with import job status, date/amount/UTR parsing and repeat-file protection.
- [P0] Match by virtual account or verified reference first, then permitted amount/date/customer heuristics; uncertain matches remain in an exception queue.
- [P0] **Auto-post only when reconciliation policy establishes sufficient evidence.** Never mark a customer as paid from a screenshot, WhatsApp assertion or raw payment link click.
- [P0] Full and partial receipts, split allocations, unapplied cash, duplicates, reversals, dishonored transactions, payment failure and chargeback cases.
- [P0] Finance inbox for unmatched payments, wrong-unit credits, duplicate UTRs, payment reversals and overpayments; allow reviewed allocation/correction with history.
- [P0] Receipt generation after verified payment posting, correct numbering, approved signature/stamp where appropriate, customer delivery and downloadable copy.
- [P0] Automatic cancellation of reminders only for settled amounts; partially paid installments produce corrected residual notices.
- [P0] End-of-day controls: ledger balance, provider settlement, bank credits and recognized receipt totals reconcile or generate named exceptions.
- [P1] Multi-bank feeds and configurable payment rails, payment provider fees, settlement differences, bounced instruments, interest and tax withholding where applicable.
- [P1] Refund/chargeback reconciliation with prior receipt references, account balance adjustments and audit.
- [P1] Accounting export/sync to supported ERP, with exactly-once business semantics, batch review and reconciliation reports.

### 20.5 Exceptions, disputes and collections operations

- [P0] Customer “paid but not reflected” ticket with UTR, date, amount, bank details and secure evidence attachment; assigned to finance with target SLA.
- [P0] Scheduled deferred payment promises: authorized “promise to pay” with agreed date, manager approval when necessary, reminder policy adjustment and breach handling.
- [P0] A formal dispute state pauses or adjusts communications according to policy; dispute has owner, evidence, outcome and customer communication.
- [P0] Interest, late fee, discounts, waiver and grace-period calculation engine controlled by actual contract terms and applicable laws; require approval for discretionary exceptions.
- [P0] Refund workflows: customer request, verified beneficiary details, dues/netting, approval chain, maker/checker, payout confirmation, reversal and customer receipt.
- [P1] Collections segmentation by installment class, age, amount, project, reason, promised date, owner, response and communication outcome.
- [P1] Agent workload planning, call queues, task escalation, call disposition and customer service coordination.
- [P1] Collections performance: due vs collected, on-time collection %, overdue aging buckets, DSO if meaningful, recovery time, payment failure reasons and promise-to-pay reliability.
- [P2] Explainable cash forecast by due schedules, verified customer promises, historic settlement patterns and scenario assumptions; show uncertainty and missing data.

### 20.6 Payment automation acceptance scenarios

Every scenario must pass end-to-end tests through genuine persistence, event processing and mocked *provider boundaries* in tests:

1. **D minus 7:** An eligible unpaid installment receives one approved reminder; every provider status is recorded.
2. **Already paid:** A payment settles before a scheduled run; dispatcher suppresses the stale reminder and records why.
3. **Partial payment:** ₹2 lakh due, ₹50,000 settled. The next reminder clearly requests only the verified remaining ₹1.5 lakh.
4. **Duplicate callback:** The bank/payment provider retries the same captured event; there is one posted financial entry, one receipt and no double credit.
5. **Payment pending:** Payment link clicked but bank not settled; do not issue a paid receipt.
6. **Bank mismatch:** Similar amount with weak customer reference; hold in matching queue, do not auto-assign.
7. **Opt-out/consent change:** A queued marketing or optional message is evaluated under its purpose and suppressed if no longer permitted.
8. **Due-date extension:** Finance approves an extension; pending notices are recalculated and the old due-date campaign is cancelled.
9. **Cancellation:** Customer booking is cancelled; future installment reminders are stopped; any refund follows approved rules.
10. **Dispute:** Customer disputes the charge; escalation and sending follow configured dispute policy and audit.
11. **Provider outage:** No silent success. Backoff, rate limits, controlled retries, alerts and replays work with idempotency.
12. **Two simultaneous receipts:** Unique numbering, correct remaining balance and unambiguous allocation are preserved.
13. **Multi-tenant collision:** Identical customer phone and payment amount in two developer tenants cannot leak or cross-post.
14. **Month boundary and timezone:** Scheduling produces the correct reminder day/time for each customer and tenant jurisdiction.
15. **Executive drilldown:** CFO clicks overdue KPI and sees the exact ledger transactions and outstanding balance that produced it.

## 21. Fully Automated Communication and Customer Journey Studio

Build on the existing messaging and omnichannel foundation. Do not duplicate inbox or channel provider modules.

- [P0] **Two-way conversation continuity:** Contact timeline across WhatsApp, Instagram, Facebook Messenger, web chat, telephony, SMS and email, linked to correct customer/opportunity and consent purpose.
- [P0] **Workflow-driven sequences:** Welcome, lead follow-up, meeting confirmations, missed visits, proposal delivery, reservation expiry, KYC reminders, agreement signing, collection notices, construction updates, handover and service closure.
- [P0] **Campaign governance:** Audience preview, consent eligibility count, sender identity, rate limits, approved templates, duplicate suppression, budget cap, send-time calendar, human approval and opt-out paths.
- [P0] **Delivery observability:** Provider message ID, enqueue and dispatch times, acknowledgment, delivery/read events when available, failure cause and replay history.
- [P0] **Conversation ownership:** Team queue, assignment, reassignment, transfer, internal notes, mentions, SLA timers, collision detection and handoff summary.
- [P0] **Call workflows:** Click to call/softphone through authorized provider, phone number masking where required, call disposition, recording notice/consent, recordings access, transcription and follow-up.
- [P0] **Website widget settings:** Per-project knowledge, language, theme, routing, lead capture policy, consent notices, operating hours and test/simulation environment.
- [P1] **Journey builder:** Visual branching by customer behavior, project interest, time delay, call outcome, delivered/read state, purchase status and explicit preference; use verifiable events.
- [P1] **Contact suppression ledger:** Record reasons and source for unsubscribes, bounces, do-not-contact and purpose-limited preferences; enforce centrally before every send.
- [P1] **Translation control:** AI drafts localized messages, but legal/financial templates require locked approved translations.
- [P1] **Reputation and deliverability management:** Email SPF/DKIM/DMARC health, bounce and spam status, WhatsApp template status, SMS compliance registration, provider throughput and quota monitoring.
- [P2] **Conversation intelligence:** Optional compliant transcription, sentiment cues as nonauthoritative signals, objection detection, missing answer alerts and conversation summarization with citations.
- [P2] **Customer response workflows:** “Send floor plan,” “What is due?”, “Visit tomorrow,” “Speak to manager” dispatch to correct rules and owner, with AI limited to authorized tool actions.
- [P2] **Send-time optimization:** Choose within permitted business windows based on actual engagement, subject to fairness and user choice.
- [P3] **Persistent multilingual customer concierge:** Customer can resume the same verified journey across digital channels without losing task context or being tricked into believing automation is human.

## 22. Growth Intelligence, Lead-to-Cash Attribution and Marketing Automation

- [P0] Multi-touch source event ledger: click, campaign, UTM, form submission, incoming call, walk-in, broker claim, visit, opportunity, booking, received cash and refund.
- [P0] Offline source attribution via unique QR campaigns, approved call-tracking numbers, project signage and event leads, with data-source confidence.
- [P0] Ad platform connectors with incremental sync, account authorization, source health, metrics mapping, error log and failure alert.
- [P0] Lead quality validation: duplicate identity, invalid contact, spam patterns, zero contactability, irrelevant geography/project interest, unknown source and suspected bot submissions. Never discard leads silently.
- [P0] Correct source and deal ownership precedence, with override approvals and change log.
- [P1] Marketing dashboards for spend → qualified opportunities → site visits → reservations → bookings → real collections, including attribution windows and refund adjustments.
- [P1] Campaign calendar, budgets, cost caps, target audiences, asset library, signed-off creative, tracking links and conversion experiments.
- [P1] Event ingestion from Meta, Google Ads and property portals, with verified integration policy and channel-specific capabilities.
- [P1] Automatic alerts for sudden junk lead spikes, broken landing pages, unassigned lead surges, API disconnects and high cost per qualified conversion.
- [P2] Explainable media mix modeling and incremental lift tests with confidence rather than unsupported exact attribution.
- [P2] “Quality, not volume” campaign recommendations tied to downstream cash performance, not only cost per lead.
- [P2] Privacy-aware first-party segmentation, suppression and remarketing audiences with user rights and minimum cohort size.
- [P3] Marketing strategy simulator comparing scenario budgets, conversion distributions, sales capacity and estimated cash realization.

## 23. Channel Partner Network OS

- [P0] Tenant-isolated broker/agency identities, firms, agents, branches, licenses/KYC as applicable, bank payout details and agreement records.
- [P0] Partner-specific inventory and price visibility, approved project access, embargoes and marketing collateral version control.
- [P0] Referral registration with evidence, first registration rules, expiry, customer consent, conflicts, appeals and fair review.
- [P0] Clear partner opportunity timeline without exposing other partners' or developer customers' confidential records.
- [P0] Rule-based commission plans: project, unit type, partner tier, validity dates, booking/money milestones, splits and clawback triggers.
- [P0] Commission ledger: accrued, eligible, approved, invoiced, paid, reversed and disputed; verified proof and maker/checker payouts.
- [P1] Partner self-service portal: inventory, referral submissions, visits, deal stage, commission statements, invoice upload and payout tracking.
- [P1] Duplicate lead ownership disputes with time-stamped evidence and approval escalation.
- [P1] Partner performance, training/certification, campaign assets, co-marketing and incentive programs.
- [P2] Channel network heatmap revealing partner effectiveness by area/project and verified collections outcomes.
- [P3] Transparent partner matching for new launches based on documented performance, quality and market coverage, without hidden preferential allocation.

## 24. Construction, Handover and Ownership Lifecycle

- [P0] Approved milestone register with owners, dates, dependency graph, required certification, status and evidence.
- [P0] Unit/project progress updates with original media, capture date, location metadata where safe, reviewer, approval and published revision.
- [P0] Construction-linked payment trigger must depend on **verified approved milestone**. No automatic demand based only on an AI image or contractor claim.
- [P0] Buyer-visible progress timeline with actual vs planned, explanation of changes and last updated date.
- [P0] Readiness checklist for each unit: inspections, approvals, utilities, punch items, agreement and account balance requirements, customer communications and handover appointment.
- [P0] Digital snag list with photo evidence, location/asset mapping, severity, owner, target date, customer confirmation, reinspection and closure.
- [P1] Possession scheduling, keys/handover inventory, device/access card tracking, documentation acknowledgement and milestone signature.
- [P1] Warranty/asset register with vendor, period, maintenance schedule, claim and repair history linked to customer and unit.
- [P1] Case management with triage, SLA, internal/external assignee, escalation, visit schedule, evidence and satisfaction feedback.
- [P2] Construction dependency risk engine, detecting delayed predecessors and likely buyer impact with documented evidence.
- [P2] Digital property passport: plans, approvals, agreement, receipts, registration, insurance where integrated, warranties, maintenance and service history.
- [P3] Real-time building asset twin when authorized IoT/BMS integrations exist: equipment health, maintenance events and verified asset location; no pretend live telemetry.

---
# PART IV. THE AUTONOMOUS OPERATING LAYER

## 25. Automation Studio: A genuine enterprise workflow platform

The current event-driven messaging engine must grow into a general business automation platform. It must coordinate data, documents, humans, providers, timelines and exceptions. A user should be able to configure ordinary business processes without editing application code.

### 25.1 Visual workflow designer

- [P0] **Visual canvas** with trigger, conditions, actions, wait, branch, parallel, approval, assign, notify, generate document, verify payment, create task, invoke connector, loop over controlled collections and end nodes.
- [P0] **Real workflow execution** with persisted state, deterministic decisions, durable timers, retries, backoff, idempotency, checkpoints and resume after restart.
- [P0] **Trigger catalogue:** Record created/changed, stage change, due date reached, payment settled, webhook received, visit concluded, approval granted, booking cancelled, hold expiring, document signed, customer replied, SLA breached, inventory changed, construction milestone certified, service ticket reopened and scheduled interval.
- [P0] **Condition library:** Tenant, project, customer profile, opportunity stage, consent purpose, elapsed time, due balance, overdue days, unit status, role, amount threshold, plan type, partner, message delivery and working calendar.
- [P0] **Action library:** Create/update permitted record, assign owner, request approval, generate PDF, send approved message, schedule visit, reserve/release unit through canonical engine, create payment link, request reconciliation, escalate case, create task, publish approved update, post internal alert, create ticket, call authorized integration.
- [P0] **Builder validation:** Type-safe fields, missing credential checks, unbound variables, invalid states, impossible branches, circular triggers, unbounded loops, missing approval and consent violations detected before activation.
- [P0] **Versioned publishing:** Draft → validate → review → activate → monitor → pause → rollback. Active runs keep their original rules or transition through an explicit migration strategy.
- [P0] **Run explorer:** Exact workflow version, event, entity, actor, branch, output, duration, dependencies, provider response, errors, retries and approvals. Individual runs can be paused, cancelled, retried or replayed only when safe.
- [P0] **Dry-run sandbox:** Simulate a specific customer/booking/ledger state and show every intended side effect without actually sending, posting money or modifying live inventory.
- [P0] **Execution safety:** Step rate limits, per-tenant quota, concurrency caps, retry policy, dead-letter queue, loop detection and maximum action budget.
- [P0] **Global suppression and policy gate:** Before outbound action, consult consent, contact policy, templates, verified ledger, service status, active holds and permission boundaries. Fail closed for missing mandatory evidence.
- [P0] **Manual override:** Authorized staff can pause a workflow for a record with reason and expiry, or request human continuation.
- [P1] **Reusable subflows:** Approval chain, send statement, confirm booking, verify customer identity, follow up, dispute routing and payment reconciliation steps can be used across many workflows.
- [P1] **Variable inspector and timeline replay:** Explain why a condition was true, which data version was used and who approved the action.
- [P1] **Workflow templates marketplace:** Tenant-specific approved templates, global templates that can be safely imported, template version pinning and documented compliance assumptions.
- [P1] **Human task orchestration:** Due date, owner, delegation, escalation, substitute approver, reminders, attachments, priority and audit.
- [P1] **Operational calendar and holiday policies:** Business hours, timezone, local holiday calendar, nonworking-day rollover, working-day offsets and provider send windows.
- [P2] **Natural-language workflow creator:** “When a visit is missed, ask for a reschedule, then notify the sales owner after a day” generates a previewable workflow that a human validates and publishes.
- [P2] **Automation analytics:** Estimated hours saved, actual task completion rate, delivery reliability, workflow failure rate, customer resolution and business outcome attributable to each automation.
- [P3] **Process mining and optimization:** Analyze opted-in event logs to identify repetitive work, bottlenecks and recommended workflows, with traceable evidence and a before/after trial.

### 25.2 Mandatory workflow governance

- Every workflow belongs to a tenant or carefully bounded platform scope.
- Every executed step records provenance, input data version, generated output, recipient, external request ID and disposition.
- The same business event must not initiate duplicate charges, holds, receipts, payouts or legally binding communications.
- Financial postings, contractual edits, inventory reservation and other material actions use authoritative domain services, never an AI-generated direct database write.
- Workflow edits with material commercial effects require approval and versioned change history.
- A temporary provider outage must not lose a scheduled installment reminder or order the wrong next step.
- Workflows remain inspectable and controllable by authorized administrators even when the original employee leaves.

## 26. The Master Automation Catalogue: End-to-end business triggers

**Every item below should be supported as a template or composable automation.** Configurable eligibility, timing, language, escalation, pause conditions, approvals and delivery outcome apply to all relevant workflows.

| Workflow family | Trigger → automated actions | Escalation / stop condition |
|---|---|---|
| **New lead response** | Ingest lead → validate/dedupe → attribute → route → acknowledge within SLA → create prioritized task | Unknown mapping, invalid details, missing consent, assignment SLA breach |
| **Routing overflow** | Owner unavailable or queue capacity exceeded → reroute to eligible pool → notify manager | All agents unavailable, tenant policy conflict |
| **Lead nurture** | Interest recorded → send authorized project-specific material → observe replies → assign next action | Opt-out, changed interest, booking made, delivery failures |
| **Lost lead revival** | Eligible dormant opportunity → owner approval/policy gate → authorized reengagement | No lawful contact permission, previous rejection, customer refusal |
| **Duplicate identity** | New matching contact → queue candidate merge → show evidence → approve linking | Contradictory identities or sensitive mismatch |
| **Call outcome** | Call ends → capture verified outcome → summarize consented recording → suggest action | Missing consent or inadequate transcript confidence |
| **Customer objection** | Staff tags objection → prepare approved answer and document → create follow-up | No approved fact or commercial rule |
| **Missed response SLA** | Contact not handled by target → notify owner → escalate manager → queue overflow | Customer responded or case resolved |
| **Scheduled visit** | Slot reserved → confirmation → directions/checklist → reminders → attendance capture | Visit cancelled, customer opts out where applicable |
| **Missed visit** | No-show verified → ask to reschedule via permitted channel → owner follow-up | Customer declines, visit already rescheduled |
| **Visit completed** | Outcome saved → update opportunity → send approved materials → request proposal action | Incomplete report or buyer not interested |
| **Unit match** | Verified customer requirements or inventory changes → recalculate candidates → notify owner | No fit, customer preference disallows proactive notification |
| **Hold expiry** | Unit hold nearing expiry → warn owner and customer if policy allows → request extension → release atomically on expiry | Booking converted, manager extension approved |
| **Pricing exception** | Negotiated offer breaks policy → generate approval case with impact → serial/parallel routing | Rejected or stale price version |
| **Proposal follow-up** | Valid quote sent → timed check → salesperson task → version expiry warning | Buyer response, quote expired or replaced |
| **Booking application** | Accepted proposal → document/KYC checklist → verify unit hold → approval queue | Missing evidence, compliance hold, expired reservation |
| **Agreement execution** | Draft approved → send signature request → track signer status → chase pending signatures | Rejection, legal amendment, signing expiry |
| **Unit transfer** | Transfer request → legal checklist → finance verification → pricing/inventory approval → document updates | Approval missing or conflicting ownership |
| **Booking cancellation** | Approved cancellation → freeze future installments/reminders → compute obligations/refund → inventory release process | Pending dispute, refund approval, legal hold |
| **Payment plan activation** | Booking/contract verified → create installment schedule → validate sums/taxes → publish buyer statement | Missing terms, inconsistent totals |
| **Construction certification** | Milestone approved → eligible demand batch generated → finance/legal review → publish authorized notices | Evidence missing, milestone dispute |
| **Installment reminder** | Due-date offset reached → real-time ledger check → permitted multichannel notice → delivery monitoring | Paid, paused, dispute, opt-out policy, outside contact window |
| **Overdue escalation** | Due + configured grace passed → owner task → manager escalation → finance review | Settled or approved extension |
| **Customer promise to pay** | Promise recorded → reminders rescheduled → owner tracking → breached promise escalation | Customer payment settled or promise superseded |
| **Payment link** | Authorized request → provider link → expiry monitoring → customer status update | Link expired, failed, paid, duplicate request |
| **Payment settlement** | Signed provider event/bank credit → matching → ledger posting → receipt → buyer confirmation → close/open residual balance | Mismatch, reversal, uncertainty, duplicate |
| **Unmatched bank credit** | Statement imported → confidence match fails → finance exception assigned → SLA reminder | Reconciled or rejected with evidence |
| **Partial payment** | Verified partial credit → allocate per policy → reproject outstanding → refresh remaining reminders | Allocation ambiguity or dispute |
| **Payment reversal** | Chargeback/refund/bounce confirmed → reverse ledger via adjustment → invalidate prior current status → notify finance | Needs manager approval and customer communication |
| **Refund execution** | Approved cancellation/credit → beneficiary verification → maker/checker → payout processing → bank reconciliation | Unknown bank details, approval missing, provider failure |
| **Broker commission** | Eligibility milestone reached → compute accrual → verify claims → approval → statement → payout and clawback | Dispute, cancellation, incomplete conditions |
| **Construction updates** | Verified site evidence published → segment eligible owners → send project update | Unapproved, misleading or stale material |
| **Possession readiness** | Dependencies satisfied → offer inspection slot → collect snag list → resolve → schedule handover | Unresolved critical snag, missing approvals/finance clearance |
| **Warranty expiry** | Covered asset nearing expiry → notify homeowner and service team | Asset transferred, preference settings |
| **Customer grievance** | Case created → classify/assign → SLA timer → resolution evidence → satisfaction request | Safety issue, critical breach, customer rejection |
| **NPS/customer feedback** | Service milestone completed → optional survey → case or improvement task | Customer opted out, duplicate survey |
| **Renewal of integration** | Credential nearing expiry → alert integration owner → authorized reconnect → test sync | Permission failure, revoked access |
| **Failed webhooks** | Provider webhook processing failed → safe retry → dead-letter triage → replay with idempotency | Payload invalid or security failure |
| **Privacy request** | Access/correction/deletion request → verify identity → legal retention policy → approvals → fulfillment evidence | Legal hold, identity not verified |
| **Daily management brief** | Business-day schedule → gather authorized KPI snapshot → generate cited highlights → deliver | Data stale, inconsistent ledger, report policy |
| **Portfolio exception detection** | Significant KPI, SLA or ledger anomaly → create verified alert with evidence → assign review | False positive acknowledged or resolved |

### 26.1 Automation experience rules

- Users can see *why* a reminder or escalation occurred, not just that it happened.
- A customer replying to an automated message can reach a named human when needed.
- Inbound replies automatically update the correct open conversation and customer opportunity, not a disconnected inbox.
- An approval can be taken on mobile with full context and evidence, and declined with reason.
- Every triggered action can be located from both the workflow run and the source business record.
- Reporting distinguishes generated, sent, delivered and actually acted upon. No inflated “automation success” counts.

## 27. AI Agent Workforce: precise scope, authority and measurements

**Build specialized tool-using agents, not separate isolated chatbots.** Agents share authorized domain context through tools, maintain a decision log and stop safely when evidence is insufficient. Human users must see what was proposed, done and blocked.

| Agent | What it can do | What it must never do autonomously |
|---|---|---|
| **Customer Concierge** | Explain approved projects, find matching units, book site visits, summarize next steps | Invent availability, commitments, discounts or approved legal facts |
| **Lead Triage** | Assess contactability, route opportunities, identify duplicates, create tasks | Reject/discriminate using protected traits or silently discard enquiries |
| **Sales Preparation** | Prepare account briefs, visit dossiers, draft follow-ups and proposals | Change authoritative price or promise approval |
| **Unit Matchmaker** | Rank currently saleable units by customer-stated constraints and show why | Hide viable options for opaque business steering |
| **Negotiation Copilot** | Compare proposal with price policy and suggest approved options | Commit discounts or issue binding offers without authority |
| **Revenue Analyst** | Explain sales funnel, inventory velocity, campaign returns and anomalies | Present speculative data as actual financial results |
| **Collections Coordinator** | Schedule verified reminders, prepare statements, route disputes and promise tasks | Mark money paid without bank/provider evidence, threaten customers or invent penalties |
| **Finance Reconciliation Assistant** | Suggest matches and explain differences with confidence/evidence | Post uncertain credits or approve own exceptions |
| **Document Intelligence** | Draft approved template packets and highlight missing fields | Replace legal review or execute documents without signature authority |
| **Construction Coordinator** | Aggregate verified progress evidence and flag dependencies | Certify a milestone or create payment obligation from unverified input |
| **Partner Success Agent** | Help brokers register referrals and understand status/commission rules | Decide disputes without review or expose competing partners' data |
| **Service Resolution Agent** | Classify tickets, route work, draft updates, suggest knowledge answers | Certify unsafe repairs or close disputed issues without evidence |
| **Executive Chief of Staff** | Morning briefing, board pack prep, KPI questions, scenario analysis, approval preparation | Override business controls or modify finance documents directly |
| **Platform Reliability Agent** | Diagnose failed runs, recommend retry, summarize incidents | Access tenant PII or perform privilege escalation without authorization |
| **Compliance Evidence Agent** | Collect source-backed audit records, surface missing documentation, flag retention obligations | Make final legal determinations without qualified review |

### 27.1 Mandatory Agent Experience and Governance

- [P0] **Agent directory:** Name, purpose, authorized data, enabled tools, owner, escalation path, cost budget, production status and test evaluation results.
- [P0] **Tool authorization:** Fine-grained actor, tenant, record and action checks for every tool call; never accept “the AI said so” as authority.
- [P0] **Action preview and approvals:** Sensitive changes show intended before/after, affected parties, source data, warnings, cost and approver.
- [P0] **Evidence-linked answers:** Answers about prices, unit status, receipts, project details or compliance refer to approved exact records and timestamps.
- [P0] **Uncertainty and refusal:** Agent says when data is unavailable, stale or contradictory, offers a human handoff and records the reason.
- [P0] **Audit of agent execution:** Prompt/config version, selected model, retrieval set identifiers, tool calls, outputs, approvals, costs and policy decision history with proper protection of sensitive text.
- [P0] **Privacy separation:** User and tenant data is never blended into another tenant's agent memory; redaction and retention controls apply to prompts and transcripts.
- [P1] **Agent testing center:** Grounding accuracy, booking safety, amount correctness, multilingual understanding, abuse tests, tool misuse, latency, fallback, spend and acceptance criteria.
- [P1] **Model routing and fallback:** Cheap model for classification, stronger model for complex reasoning, deterministic service for actual money/inventory; cost ceiling and failover by feature.
- [P1] **Agent confidence and handoff policy:** Low-confidence intent or identity matching → clarification or staff review. No irreversible action on a model confidence score alone.
- [P2] **Multi-agent task board:** Example: booking specialist hands to legal for paperwork and collections for verified dues, each acting through explicit workflow with customer-visible state.
- [P2] **User-editable long-term context:** Agents retain structured permitted facts with dates, allow correction/deletion according to policy and never treat unverified inference as a customer fact.
- [P3] **Continual simulation and agent evaluation:** Use synthetic deal histories and realistic edge cases before agent/tool upgrades; compare safe outcomes, not only language quality.

## 28. Decision Intelligence: a business nervous system

- [P0] KPI definition library with one consistent formula, authoritative source, filters, owner and freshness indicator.
- [P0] Drill-through from reports to underlying ledger, deal, unit, campaign, task and approval records; no unsupported “AI made this up” aggregate.
- [P1] **Cash collection forecast:** Due schedules + historical settlement evidence + approved promises and project dependencies, displaying scenario bands.
- [P1] **Sales pipeline forecast:** Stage movement, buyer interest, actual visits and verified historical conversion with confidence and data sufficiency markers.
- [P1] **Inventory absorption analysis:** Sold/held/available at project/unit-type level, price/mix and aging comparisons.
- [P1] **Customer service reliability:** Ticket response, resolution, reopening, root cause and customer satisfaction linked to operational actions.
- [P1] **Sales capacity model:** Workload per executive, touch coverage, follow-up backlog and real active time, avoiding invasive employee surveillance.
- [P2] **Predictive stalled deal warnings:** Explain delay patterns, missing documents, missed calls and inventory mismatch with user-dismissible suggestions.
- [P2] **Campaign to cash optimization:** Compare campaigns by long-term realized value after reversals/cancellations, not only booked revenue.
- [P2] **Scenario workbench:** Model marketing changes, price-book changes, launches, cancellations, cash collection timing and capacity, with clear assumptions and rollback.
- [P2] **Anomaly investigation assistant:** Detect and explain improbable ledger totals, lead source swings, conversion drop, repeated discounts, unusual partner claims and double-entry breaks.
- [P3] **Executive digital business twin:** A simulated portfolio model connecting demand, supply, cash, staff capacity, launches and construction dependencies. Simulations remain labelled as projections.
- [P3] **Counterfactual explanations:** “What changed relative to last month, and which documented events explain it?” with reproducible analytical evidence and alternative explanations.

---
# PART V. ENTERPRISE FOUNDATIONS TO ADD

## 29. Organization Model, Role Designer and Approval Authority

The current admin/sales/buyer role baseline must be expanded into organization-level policy while preserving tenant boundaries.

- [P0] **Organization hierarchy:** Parent developer, legal entities, brands, business units, regions, offices, project teams and third-party agencies, with scoped reporting.
- [P0] **Custom role designer:** Admin-defined roles composed of granular capabilities, not brittle single enum strings. Start from professionally curated role templates for CEO, COO, Sales Head, Executive, Finance Head, Collections, Legal, Inventory, Marketing, Construction, Customer Support and Broker.
- [P0] **Permission dimensions:** Resource, action, scope (own/team/project/region/organization), field sensitivity, financial threshold, time window and approval requirement.
- [P0] **Maker/checker and separation of duties:** Configurable for prices, concessions, finance postings, refunds, commission payouts, buyer ownership changes, inventory release and sensitive export.
- [P0] **Approval Policy Designer:** Thresholds, conditional stages, sequential/parallel routing, evidence requirements, escalation, overdue paths and versioned delegation.
- [P0] **Out-of-office delegation:** Temporary authorities by exact scope and expiry, recorded with delegated actor identity; no silent inherited superuser rights.
- [P0] **Reassignment and departure:** Move open tasks, opportunities, approvals, scheduled jobs and shared inbox ownership when employees leave or roles change, preserving provenance.
- [P1] **Policy simulator:** Preview what a selected role could read/export/change on a specific record and why, before publishing role changes.
- [P1] **Just-in-time permission elevation:** Approval-backed short-lived privileged access, automatically revoked and auditable.
- [P1] **Regional office policy and RERA access filters:** Projects and legal entities expose only appropriate records to staff based on verified duties.
- [P2] **Risk-adaptive controls:** Additional verification for unusual bulk export, very large discount, critical payment action or atypical sign-in, with clearly explained challenges.

## 30. Security, Privacy, Audit and Compliance Workspaces

These are user-facing product capabilities, not just infrastructure concerns.

- [P0] **Tenant and record-level isolation** enforced for reads, writes, background jobs, files, search, analytics, agent tools and exports. No tenant should discover that another tenant's customer exists.
- [P0] **MFA and passkeys**, device/session management, role change revocation and meaningful audit of authentication events.
- [P0] **Enterprise identity:** SSO/SAML/OIDC and SCIM provisioning/deprovisioning as plan-gated capabilities, with group-to-role mapping and recovery.
- [P0] **Purpose-specific consent center:** Acquisition source, lawful basis/permission, channel, purpose, evidence, capture method, expiry, change, opt-out, suppression and contact-window preferences.
- [P0] **Data rights portal:** Authenticated access, correction, export, erasure where permitted, grievance request, identity verification and completion receipt.
- [P0] **Retention and legal holds:** Configurable schedule by tenant, category and jurisdiction, with approved preservation and defensible deletion.
- [P0] **Document access controls:** View/download/share restrictions, expiry, recipient authentication, watermarking where needed and per-document audit.
- [P0] **Auditable business actions:** Who did what, when, under what role, old/new values, source event, AI contribution and approval evidence, with tamper-evident storage strategy.
- [P0] **Security operations dashboard:** Access anomalies, failed logins, webhook validation errors, broad exports, unusual refunds and automation policy violations routed to accountable staff.
- [P1] **Compliance policy packs:** Configurable local RERA disclosures, tax templates, document retention, communications regulations and legal-entity rules, all reviewed by qualified staff before activation.
- [P1] **Audit report builder:** Generate complete evidence packages for specific booking, payment, project, consent, agreement, approval and data access events.
- [P1] **Access review campaigns:** Quarterly/periodic recertification, unowned roles, inactive users, expired delegations and manager sign-off.
- [P1] **Field-level masking:** Bank data, government IDs, financial details, phone numbers, customer documents and recorded conversations are exposed only where needed.
- [P2] **Continuous control monitoring:** Automated exceptions for missing approvals, undocumented overrides, unmatched settlements, incomplete customer consents and expired compliance artifacts.
- [P3] **Verifiable transaction provenance:** Independently checkable cryptographic receipts and tamper evidence for significant events; do not mistake blockchains for a substitute for accurate business records.

## 31. Integrations, APIs, Marketplace and Data Portability

- [P0] **Unified Integrations Center:** Per-tenant connector status, credentials, owner, approved scopes, last success, last failure, data sync delay, webhooks, quotas and renewal requirements.
- [P0] **API management:** Versioned REST endpoints for relevant resources, service accounts, scoped OAuth/API credentials, rate limits, usage dashboard, developer documentation and test environment.
- [P0] **Reliable webhooks:** Subscriptions to domain events, signed delivery, event IDs, retry schedule, dead-letter status, replay action and versioned payload schema.
- [P0] **Bulk import/export center:** Templates, field mapping, duplicate preview, validation, referential checks, async progress, downloadable failures and rollback/correction policy.
- [P0] **Accounting and banking connectors:** Product-adapted integration with Tally-compatible exports and supported accounting/ERP/banking providers, verified reconciliation and change monitoring. Actual bank writes require explicit authorization.
- [P0] **Telephony and messaging connector extension:** Authorized providers with verified inbound events, recordings where permitted, message template status and usage tracking.
- [P1] **Document, e-sign and identity connectors:** E-signature, secure document storage, identity validation and official document generation through policy-appropriate vendors.
- [P1] **Project systems:** BIM/document repositories, project management software, construction progress evidence and service ticket platforms with source versioning.
- [P1] **Developer integration sandbox:** Synthetic data, webhook simulator, OAuth scopes, sample events, integration tests, error debugging and usage metrics.
- [P1] **Connector marketplace:** Approved integrations, capabilities, billing visibility, permission grants, vendor verification, installation and uninstall with data-handling disclosures.
- [P2] **Enterprise workflow interoperability:** Bidirectional workflow handoffs to external systems with exactly-once business intent and conflict resolution policy.
- [P3] **Customer-authorized portability:** Export a verified property passport and transaction history in structured standardized format for legitimate third-party services with explicit customer approval.

## 32. Data Platform and Universal Search

- [P0] **Canonical event catalogue:** Versioned domain events for lead, customer, opportunity, inventory, price, approval, visit, communication, payment, agreement, handover and support.
- [P0] **Audit-quality business timestamps:** Created, effective, approved, received and processed time distinguish when facts happened and when the platform learned about them.
- [P0] **Universal tenant-scoped search:** Exact/partial search by customer name/phone, unit number, booking ID, UTR, receipt, document, campaign and case, with row/field permission protection.
- [P0] **Cross-module entity linking:** Any record opens related authorized entities and history without copying mutable state in multiple places.
- [P1] **Search relevance tuning:** Aliases, spelling tolerance, multi-language transliteration, fuzzy results as suggestions only and exact match prioritization for financial IDs.
- [P1] **Saved analytics datasets:** Trusted materialized metrics, lineage, refresh schedules, permissions and reproducible query version.
- [P1] **Data quality command center:** Orphaned or stale external IDs, mismatched balances, missing source, invalid phone, broken unit references, source version differences and duplicate document versions.
- [P2] **Semantic knowledge search:** Retrieve approved facts, policies, contracts and project documents with permissions and source citations; do not use a semantic match to prove payment.
- [P2] **Natural-language reports:** Convert questions to validated analytics queries with policy check, visible filters and source records.
- [P3] **Business knowledge graph:** Trace why a commercial decision happened through customer, campaign, unit, quote, approval, payment and agent interactions, with time-aware relationships.

## 33. Enterprise Collaboration and Work Management

- [P0] Comments and internal notes on customers, deals, units, approvals, finance exceptions, service cases and project milestones, with attachments, mentions and access boundaries.
- [P0] Typed task and activity system: task kind, owner, priority, SLA, due date, related record, state, dependency and proof of completion.
- [P0] Calendar synchronization for sales visits, internal reviews, payment commitments, registration and handover appointments, with timezone and organizer controls.
- [P0] Shared work queues and rotation rules, with ownership history and automatic escalation if unclaimed.
- [P1] Multi-party approval inbox with filters for deadline, amount, materiality, project, role and substitute approver.
- [P1] Management briefs and meeting preparation automatically assembled from source-backed actions, including owner and deadline.
- [P1] Project-specific playbooks, training, knowledge revisions and required-reading acknowledgments.
- [P2] Cross-module collaborative workspace: assemble a deal room with permitted participants, tasks, documents, approvals, notes and single source record links.
- [P3] Meeting-to-action extraction from consented transcript with human review, action ownership and due date sync.

## 34. Vertical Editions and Multi-Asset Capability

Start with residential developers, but design the model so the platform can expand without replacing its core.

- [P1] **Plotted development edition:** Layout approvals, plot polygon, facing, road width, corner/park frontage, title-document register, plotting phases and plot-specific charges.
- [P1] **Apartment edition:** Tower, floor, flat, parking allocation, clubhouse/amenity charges, construction milestones, unit-wise snagging and association handover.
- [P1] **Villa edition:** Plot + built structure, upgrade packages, custom construction options, elevation and handover assets.
- [P2] **Commercial edition:** Shop/office inventory, lease vs sale, area measures, recurring obligations, fit-out milestone, renewals and occupancy documentation.
- [P2] **Mixed-use edition:** Retail/residential/commercial verticals inside one project with distinct inventory classes, tax and approval policies.
- [P2] **Brokerage/agency edition:** Multi-developer property catalog, permissioned developer integrations, referral ownership and co-broker attribution.
- [P3] **Multi-country edition:** Locale-specific contracts, area measures, taxes, data regions, communication rules, currency, timezones and regional legal packs, without assuming an India-only schema.

## 35. Financial and Commercial Control Beyond Collections

- [P0] **Price and offer profitability:** Display authorized floor price, total concessions, booked value and cash realization, with finance-approved source definitions.
- [P0] **Revenue and cash differentiation:** Booking value, contracted value, invoiced demand and actual bank-collected cash are always separate KPIs.
- [P0] **Brokerage and sales commission settlements:** Recognized eligibility, clawbacks, deductions, payment approval and verified beneficiary.
- [P0] **Bulk discount approval controls:** Prevent unauthorized systemic underpricing from batch adjustments or AI-proposed changes.
- [P1] **Cost-center allocation and GL mapping:** Booking, taxes, fees, commissions, payment reversals and credits linked to reporting dimensions.
- [P1] **Reconciliation closing workflow:** Daily close, month-end close, incomplete items, signoff and reopen policy with audit.
- [P1] **Financial document center:** Tax invoices/receipts/credit notes/ledger statements according to appropriate classification, numbering and legal requirements.
- [P2] **Project liquidity intelligence:** Forecast upcoming collections, payment-plan obligations and launch cash needs using approved planning inputs, with caveats.
- [P3] **Financial stress-test simulator:** Test slower collections, higher cancellations, stalled launches and inventory release timing against prospective cash outcomes.

---

# PART VI. WHAT MAKES PROPFLOW 20 YEARS AHEAD

## 36. The ten long-term flagship experiences

These must have a real data dependency, measurable benefit and an honest boundary between recommendation and autonomous execution.

### 36.1 One conversation runs an entire authorized business workflow [P2]
An approved user can ask: “Prepare a comparison of three available three-bedroom units for this customer, reserve the chosen unit for two hours under our normal policy, request a manager discount review and send the approved proposal after sign-off.” PropFlow prepares a complete staged plan, shows required approvals and executes only permitted steps, with a live progress timeline and recoverable failures.

### 36.2 A real digital twin of every sellable asset [P2/P3]
The same unit exists consistently in inventory, its floor plan, pricing, availability, reservation history, agreement, construction progress, snag list, warranty and ownership passport. A digital twin is useful because its underlying model is authoritative, not because a 3D animation looks expensive.

### 36.3 Customer memory owned and correctable by the customer [P2]
A buyer can view and correct their recorded preferences, communications permissions, household relationships and key documents. The customer chooses whether to receive recommendations and can inspect why a unit is suggested.

### 36.4 An executive control room that explains its numbers [P2]
Every number, warning and forecast can be drilled down into ledger entries, units, campaigns and human actions. “Why is the project behind?” produces evidence and plausible explanations, not invented managerial prose.

### 36.5 Self-recovering workflows [P2]
A failed external provider call enters a recoverable queue. The system distinguishes transient errors from permanent failures, retries safely, shows a responsible human and never duplicates a receipt, hold or message.

### 36.6 A continuously checked business graph [P2]
Cross-system integrity rules detect: sold unit marked available; receipt without settlement evidence; commission paid before eligibility; collections reminder on fully settled installment; booking contract with expired price; signed document later overwritten; project progress claim without certified evidence. Each issue becomes a resolution case.

### 36.7 Real-time customer trust dashboard [P2]
Buyers know their verified payment state, upcoming obligations, official documents, progress publication date, service requests and escalation owners. A customer should not have to chase the developer for information that already exists.

### 36.8 Approval-native autonomous operations [P2]
The system can prepare 95% of repetitive work while keeping decisions with the right people. Price changes, legal notices, refund payments, bank matches and inventory commits are governed by explicit approval and policy.

### 36.9 Market and project simulation instead of guesswork [P3]
Management can compare realistic scenarios for launches, incentives, construction schedules, campaign budgets and inventory mix using historical data and transparent confidence bands. The output is labelled forecast, never fact.

### 36.10 A genuine real estate network with customer permission [P3]
Optional ecosystem for buyers, authorized brokers, banks, lawyers, document providers, project teams, customer support and owners, where each organization sees only approved information and every transfer is tracked. This is an interoperability feature, not an unregulated marketplace for personal data.

## 37. Cross-feature innovations that compound over time

- [P2] **Evidence first UX:** Every impactful recommendation has “Why?”, “Source”, “Last checked”, “Confidence/limitations” and “What changes if I act?” where meaningful.
- [P2] **Intent-based task surfaces:** Instead of opening five modules, a finance user selects “Resolve this payment mismatch” and sees only the relevant ledger, UTR, documents, customer communication and approvals.
- [P2] **Policy-aware AI actions:** “Can I do this?” explains the actual governing policy and gives the correct approval path.
- [P2] **Tenant-specific operational playbooks:** Developers configure how they sell, receive money, approve discounts, communicate and manage handover without code forks.
- [P2] **Predictive exceptions:** Human-actionable warnings from measurable data: bottleneck, risk of missed visit, high probability of hold expiry, late construction dependency, unresolved collection task.
- [P2] **Generative UI for internal questions:** AI can assemble an ephemeral, data-grounded investigation page from authorized charts, records and actions without granting extra permissions.
- [P2] **System of measurable outcomes:** Quantify money reconciled, customers contacted appropriately, holds prevented from conflicting, approval turnaround and service resolution, not just tasks or AI tokens consumed.
- [P3] **Digital relationship passport:** Customers can authorize another service provider to verify selected facts from their purchase without handing over whole documents or their entire history.
- [P3] **Adaptive rollout intelligence:** Platform operator can predict which tenant cohorts benefit from new features using aggregate adoption patterns and safe opt-in pilots.
- [P3] **Trustable AI collaboration:** Specialized agents coordinate under explicit policy; each agent's contribution is attributable and reversible where possible.

---

# PART VII. THE CATEGORY-DEFINING CAPABILITIES THAT LEAP BEYOND TODAY'S MARKET

**Competitive premise:** A product does not beat Zoho, Freshworks, Salesforce or a specialist real estate suite by copying their CRM tables and adding an AI chat window. PropFlow must match serious enterprise workflow depth, then become an **evidence-driven, spatially aware, agent-operable real estate business platform**. The following are additional capabilities; they are not statements that competing products lack every individual feature.

## 38. The Competitive Bar: What PropFlow Must Equal, Then Surpass

The current competitive baseline includes Zoho CRM's workflows, customization, AI and agent tooling; Freshdesk's service desk, AI agent studio and customer support automation; and Sell.Do's real estate inventory, negotiations, partner management, collections, communications and AI. References for product verification: [Zoho CRM features](https://www.zoho.com/crm/features.html), [Freshdesk AI agents](https://www.freshworks.com/freshdesk/ai-agents/customer-service/), [Sell.Do real estate CRM](https://www.sell.do/real-estate-crm), [Sell.Do post sales and collections](https://www.sell.do/real-estate-crm/post-sales-and-collections).

| Product discipline | Enterprise parity to add | PropFlow's next-generation leap |
|---|---|---|
| CRM platform depth | Custom modules, fields, relationships, layouts, validation, pipelines, cadences, reporting, marketplace, SSO | User-defined business objects become automatically searchable, permission-aware, automatable and available as approved AI tools |
| Service desk depth | Omnichannel cases, priority routing, SLA, knowledge, CSAT, QA, escalation, field service and self-service | Property-aware support sees exact unit, documents, contractor, warranty, construction milestone and resident evidence |
| Real estate depth | Inventory, price sheets, negotiated discounts, agreements, banks, partner portals, collections and possession | One transactionally consistent property graph from map to sale to settlement to owned asset passport |
| Marketing depth | Campaign planning, audience segmentation, sources, UTM, attribution, automation and experiment control | Finance-verified marketing contribution to booked value, net recognized revenue and cash actually collected |
| AI agent depth | Agent directory, agent builder, tool use, evaluation, routing, observability and approvals | A governed collective of role-specific agents that can operate long-running cross-department workflows with proof of every step |
| Data depth | Dashboards, forecasts, custom reports, warehouse connectors, data quality | A time-aware business graph that detects contradictions and answers “why” with traceable records |
| Collaboration | Tasks, approvals, chat, meetings, comments, external stakeholders | Secure deal rooms spanning customer, broker, developer, bank, lawyer and service provider with selective disclosure |
| Enterprise SaaS | Plans, entitlements, audit, policies, billing, observability, integrations | Customer-configurable operating system plus operator-safe AI diagnostics, regional deployment and portable data |

**A non-negotiable positioning rule:** Do not label a basic chatbot “agentic.” Do not call a list of bank transactions “reconciliation.” Do not call an animated floor plan a “digital twin.” The distinguishing capability must be backed by live, governed business actions.

## 39. PropFlow Business Composer: A No-Code Enterprise Application Platform [P1/P2]

This is essential to compete with general platforms, not a nice-to-have configuration page.

- [P1] **Custom Object Studio:** Tenant admins can define business objects such as Landowner, Joint Development Agreement, Referral Campaign, Contractor, Site Inspection, Broker Invoice, Fit-out Package or Escrow Milestone without editing source code.
- [P1] **Field Builder:** Text, rich text, numbers, money, percentages, dates, ranges, address, phone, status, URL, geolocation, files, choice lists, lookup, multi-record relationship, formula, rollup, computed age and immutable evidence fields.
- [P1] **Relationship Builder:** One-to-one, one-to-many, many-to-many, parent/child, cross-object references with deletion restrictions and tenant-safe link rules.
- [P1] **Pipeline Designer:** Custom states, allowed transitions, mandatory fields, reason codes, conditional actions, SLAs, stage guardrails, approval stages and terminal-state logic.
- [P1] **Visual Layout Studio:** Drag-and-drop record sections, responsive fields, conditional visibility, multi-step forms, card and detail layouts, tabbed panels, context actions and dashboard widgets.
- [P1] **Custom View Studio:** Grid, kanban, calendar, timeline, map, relationship graph, summary board and grouped list from the same object source.
- [P1] **Formula and Calculation Engine:** Server-validated calculations with testing, currency precision, null safety, policy limits and explicit effective dates.
- [P1] **Business Rules Studio:** Validation, conditional requirements, auto-population, duplicate policy, unique field constraints and cross-record consistency checks.
- [P1] **Permission Studio:** Object, record, field, attachment, action and workflow-step permissions; manager hierarchy, jurisdiction, project and team scopes.
- [P1] **Custom Reporting:** Custom objects participate in approved report dimensions, filters, joins, metrics and audit history automatically.
- [P1] **Import Studio:** Spreadsheet mapping, dry run, merge policy, duplicate preview, row diagnostics, rollback approach and provenance.
- [P1] **Config Package Management:** Export/import signed configuration packages between sandbox and production, preview breaking changes and retain previous versions.
- [P2] **Natural Language App Builder:** Admin asks “Build a contractor inspection module with seven stages, evidence uploads and two approvals”; PropFlow creates a draft object schema, views and workflow that must pass policy validation before publication.
- [P2] **AI Tool Auto-Registration:** Approved custom objects expose read/write capabilities to agents with the same permissions and confirmation gates as human UI operations.
- [P2] **Generated Portal Experiences:** Create tenant-branded customer, partner or contractor mini-portals from approved objects and forms, with real account access boundaries.
- [P2] **Tenant App Marketplace:** Private and public reusable business modules for project types and countries, with versioning, compatibility, licensing and security review.
- [P3] **Business Application Compiler:** Automatically proposes consistent CRUD, dashboards, role actions, workflows, documentation and test cases from a tenant's declared business process, while prohibiting unsafe auto-deployment.

**Definition of complete:** A tenant administrator can create a new custom object, define its workflow, publish a role-restricted navigation page, import data, perform valid state transitions, automate an event, query it from a report, expose a controlled agent tool and package the configuration for another tenant's sandbox. Every step uses real persisted objects, not generated mock UI.

## 40. Autonomous Work Orchestration: From Instructions to Verified Outcomes [P2/P3]

The AI interface should not answer with “Here are the steps.” It should be able to assemble and execute a **permissioned work plan** with real outcomes.

- [P2] **Task-to-Outcome Planner:** User requests an outcome such as “Resolve all visits scheduled tomorrow without assigned executives.” The system lists affected records, proposed allocation plan, required permissions and predicted exceptions.
- [P2] **Structured Execution Plan:** Every task has objective, permitted tools, input snapshot, owner, deadline, step dependencies, approval gates, compensation action and success check.
- [P2] **Long-Running Work Orders:** Multi-day operations continue through events and approvals without requiring the original chat session to stay open.
- [P2] **Agent-to-Agent Handovers:** Sales agent can create a Finance work request, Finance can request Legal document review, and Legal can return an exception. All handovers use typed work items and shared evidence pointers, not unstructured chatter.
- [P2] **Action-Level Permissions:** Authorization is re-evaluated on every step, even if the initiating user had permission at planning time.
- [P2] **Human Review Stations:** Finance, legal, compliance and discount approvals surface a material impact preview, source evidence, options and recorded decision.
- [P2] **Safe Compensation:** If a later step fails, reversible prior steps are rolled back through approved compensation workflows. Irreversible facts remain in the audit trail.
- [P2] **Run Memory:** Agents know previous attempted work, skips, errors, approved instructions and validated results without inventing success.
- [P2] **Agent Playground:** Test a planned operation on synthetic tenant data and compare outcomes before activation.
- [P2] **Outcome Verification:** “Send 40 reminders” is not successful when 40 queue rows exist; it reports submitted, accepted, delivered, failed, suppressed and replied numbers separately.
- [P2] **Human-Interrupt and Kill Switch:** Suspend, step into, pause, terminate or reassign an AI work order at tenant, agent, workflow or individual-run level.
- [P2] **Spend and Resource Budget:** Stop or seek approval if token usage, provider charges, contact frequency or operational impact crosses allowed budget.
- [P2] **Approval Graph:** A decision can require parallel Finance and Legal consent or sequential Manager → Director → CFO approval, with substitutes, expiry and escalation.
- [P3] **Negotiation Preparation Swarm:** Pricing, Inventory, Finance and Legal agents independently analyze a proposed deal and prepare a consensus brief with disagreements surfaced. A human decides the binding offer.
- [P3] **Autonomous Reconciliation Preparation:** At daily close, the agent network collects bank events, identifies likely matches, prepares exception queues and leaves only high-risk cases for finance confirmation.
- [P3] **Continuous Process Optimization:** Propose a redesigned workflow based on measured bottlenecks, test in an isolated simulation and request human approval before publishing.

**Example outcome:** “Arrange 35 investor visits to two projects next Saturday within three buses and ten executives” should produce a proposed capacity-checked schedule, vehicle/venue dependencies, invite cohort, message drafts, assigned owners and approval steps. Successful execution means the underlying reservations, communications and resource assignments are persisted and verified.

## 41. The Living Property Universe: Beyond a CRM Inventory Grid [P2/P3]

- [P1] **Canonical Spatial Address:** Country → state → city → neighborhood → project → phase → tower/block → floor/road → unit/plot → room/parking/asset; every entity gets stable identifiers and change history.
- [P1] **Geospatial Property Search:** Map by available inventory, possession target, permitted budget, amenities, project stage, travel accessibility and verified location constraints.
- [P1] **Verified Asset Document Graph:** Link sanctioned plans, permissions, title files, certifications, versions, site inspection evidence and disclosure status to the exact project/unit.
- [P2] **Floor Stack With Time Slider:** Travel back to any authorized date to see whether a unit was available, held, offered, booked, cancelled, released or sold, and why.
- [P2] **Visual Price Anatomy:** Click any unit and show base rate, facing/floor premiums, amenities, parking, fees, taxes, promotion, discount authority, price version and total buyer cost.
- [P2] **Floor Plan Intelligence:** Extract candidate room sizes from architect-approved drawings and clearly distinguish measured dimensions from uncertain document parsing.
- [P2] **Sunlight and Orientation Scenario:** For buildings with verified geometry and location, show seasonal sun angle/shadow simulations with confidence and assumptions.
- [P2] **Construction Provenance Timeline:** Certified milestone, source evidence, inspector, date, approved buyer disclosure and communication history in one traceable record.
- [P2] **Property Changes History:** A shift in advertised area, plan, parking allocation, facing, title status or price automatically flags affected proposals, bookings and buyer disclosures.
- [P2] **Property Similarity Finder:** Recommend available alternatives when a unit is sold or blocked, weighted by buyer-stated constraints and transparent match reasons.
- [P2] **Neighborhood Intelligence Layer:** Verified commute estimates, amenities, environmental and infrastructure layers with update dates and source credibility.
- [P2] **Plot Intelligence:** Polygon boundaries, corner/road frontage, setbacks, terrain context and approval metadata from reviewed geospatial data.
- [P2] **Parking and Add-on Resource Graph:** Store parking, storage, terraces and other allocatable assets with standalone reservation/transfer controls.
- [P3] **BIM Linkage:** Where source models exist, associate unit lifecycle records with BIM/IFC identifiers, material schedules, snag reports and building systems.
- [P3] **Point-in-Time Digital Twin:** Render verified building, floor and unit geometry plus documented state at a chosen date. All statuses are pulled from canonical data rather than colored textures manually entered in a 3D asset.
- [P3] **Remote Visit Twin:** A permitted customer explores the project interactively, asks questions about the visible unit, opens approved documents and requests a live executive transfer.
- [P3] **Construction Change Detector:** Compare approved drone/site imagery or other authorized evidence to milestone plans; generate review suggestions, never certify progress automatically.
- [P3] **Project Simulation Studio:** Test hypothetical unit mix, tower launch order, price bands and absorption under explicit assumptions and finance-controlled constraints.
- [P3] **Building Lifecycle Twin:** After possession, connect unit/warranty/asset register, reported issues, work orders, building manuals and energy data where available.
- [P3] **Selective Property Credential:** Issue verifiable, revocable claims about documents or paid amounts to an authorized customer or partner without exposing the entire account file.

**Definition of complete:** A buyer viewing unit A-1204, a salesperson reserving it, finance reviewing payment, legal preparing the deed and support tracking its bathroom warranty are always looking at the **same underlying unit identifier**. If the unit was already sold, no channel can offer it as available.

## 42. Freshdesk-Class Property Service Cloud [P1/P2]

Customer service can become an independent category-leading product, not just a “tickets” page.

### 42.1 Service-desk modules to add

- [P1] **True Unified Case Inbox:** Email, WhatsApp, web chat, in-app form, phone, field complaint and social channels enter one cases workbench, with channel source and full activity trail.
- [P1] **Omnichannel Conversation-to-Case:** Convert a conversation into a case without losing the customer, property, message history or original channel.
- [P1] **Advanced SLA Policies:** Separate first response, next response, resolution, contractor attendance, handover and emergency clocks; support regional work calendars and paused states.
- [P1] **Case Routing:** Class, severity, project, location, asset category, contract/warranty, customer language, staff skill, workload and shift availability.
- [P1] **Parent/Child Cases:** A building-wide water leak creates a parent incident and property-specific child cases, with shared updates and each customer's data kept separate.
- [P1] **Problem Management:** Repeating cases aggregate into a verified root-cause investigation with owner, linked sites, corrective tasks and publishable fix.
- [P1] **Knowledge Base:** Internal runbooks, resident guides, project-specific FAQs, versioning, approvals, expiration and per-audience access control.
- [P1] **Service Forms:** Tenant-configured service request intake with asset, photos, severity, access instructions, warranty evidence and appointment preferences.
- [P1] **Field Service Dispatch:** Technician directory, service areas, skill matrix, availability, routes, work orders, equipment, checklists, materials and customer appointments.
- [P1] **Technician Mobile Workbench:** Offline work orders, authorized photos, check-in, signature, replaced part, safety inspection and completion evidence.
- [P1] **Customer Self-Service:** Case creation, status, appointment, knowledge search, service documents, warranty eligibility and accessible escalation.
- [P1] **Warranty Rules:** Asset-specific warranty period, exclusions, vendor responsibilities, claim history, proof requirements and authorized exception handling.
- [P1] **Contractor Scorecards:** First-time-fix rate, repeat repair, appointment adherence, SLA misses, customer ratings and evidence quality.
- [P1] **Quality Assurance Reviews:** Sample cases, check policy and accuracy, score resolution, request manager review and correct coaching actions.
- [P1] **Customer Feedback:** CSAT, issue-specific surveys, reopening, complaint about resolution and verified closure acknowledgments.
- [P1] **Proactive Case Communications:** Automatic verified updates on appointment, delay, technician ETA, parts, critical incidents, resolution and reopening.
- [P1] **Service Catalog and Chargeability:** Distinguish warranty-covered, paid, building-common-area and third-party responsibilities; present authorized charges before work starts.
- [P1] **Incident Command:** Major service outage page with site impact map, coordinator, vendor, timeline, verified updates and affected residents.
- [P1] **Case Merge/Split:** Preserve original evidence and ownership when merging duplicates or separating distinct issues.
- [P1] **Customer Contact Governance:** Safe contact hours, redaction, abusive-content reporting, accessibility needs and consent preferences.

### 42.2 Service intelligence beyond conventional helpdesk

- [P2] **Property Context Copilot:** When a resident reports water ingress, the agent sees approved unit specifications, warranty, prior cases, building-wide patterns and service resources.
- [P2] **First-Contact Resolution Assistant:** Propose verified knowledge steps and clearly distinguish self-service-safe advice from work requiring a certified technician.
- [P2] **Predictive Maintenance Alerts:** From authorized equipment data and actual failure history, propose inspections for HVAC, pumps, elevators and utilities; require facility-owner acceptance.
- [P2] **Building-Wide Early Warning:** Detect unusual case clusters across units or floors and notify facilities, without exposing the complainants to unrelated residents.
- [P2] **Photo-to-Case Triage:** Extract likely asset and damage category from a resident photo, label suggestions as uncertain and request technician verification.
- [P2] **Multilingual Voice Case Creation:** Resident speaks in Telugu, Hindi, English or supported languages; service agent confirms the transcript and files a structured case.
- [P2] **Customer-Friendly Resolution Proof:** Show work performed, materials changed, technician notes, warranty effect, before/after evidence and ability to reopen.
- [P2] **Recovery Orchestrator:** If repeated work fails, automatically route to a senior technician, property manager and approved goodwill/compensation workflow.
- [P3] **Community Reliability Map:** Show anonymized recurring building issues, root causes, corrective work and long-term recurrence risk to authorized property managers.
- [P3] **Lifetime Home Maintenance Passport:** Maintain replaceable equipment, paint, waterproofing, service contracts and owner-authorized maintenance history during ownership and transfer.

**Definition of complete:** A complaint can originate through WhatsApp, become a property-linked case, trigger the correct SLA, book a technician, record work evidence, update the buyer automatically, resolve with proof, collect CSAT and reopen with prior history. Nothing is lost between inbox, work orders and customer portal.

## 43. Platform Ecosystem, App Marketplace and Integration Fabric [P1/P2/P3]

- [P1] **Unified Integration Directory:** Ad networks, property portals, email, WhatsApp, telephony, identity, storage, accounting, banking, payment gateways, e-sign, maps, data warehouses, calendars, BI and project systems.
- [P1] **Connector Self-Test:** Permission scope, authentication validity, webhook reachability, sample record, mapping, quota and error visibility before activation.
- [P1] **Bidirectional Data Contracts:** Define source of truth and permitted update direction per field, not blind two-way synchronization.
- [P1] **Integration Run History:** Every sync has cursor, job status, row counts, conflicts, retries, partner error, redaction and reprocessing controls.
- [P1] **Event Catalog:** Publish documented business events such as CustomerMerged, UnitHeld, BookingSigned, DemandIssued, PaymentSettled, CaseEscalated, AgentActionApproved.
- [P1] **Customer-Owned API Keys and OAuth Apps:** Scope, expiry, rotation, IP conditions, permissions, rate limits, developer logs and revocation.
- [P1] **Integration Mapping Studio:** Visual field transforms, validation, preview, external-key management and recoverable DLQ.
- [P1] **Webhooks as a Product:** Signed outbound events, subscriptions, delivery attempts, ordering guarantees as supported, replay, redelivery and version migration.
- [P2] **Connector Builder:** A developer can package a connector with auth, triggers, action schemas, mapping, events, docs and tests for operator review.
- [P2] **Verified Marketplace:** Approved apps display publisher, data scopes, security posture, change log, version support, pricing, dependencies and tenant install approvals.
- [P2] **Private Enterprise Marketplace:** Large developer groups publish internal forms, reports, workflows and connectors to approved subsidiaries or branches.
- [P2] **Agent Capability Marketplace:** Secure install of pre-reviewed agent roles and actions, constrained by tenant controls and local evaluation requirements.
- [P2] **Cross-organization Consent Gateway:** Allow a customer to disclose specific facts to a lender, lawyer or broker, for a limited purpose and duration, with revocation and access record.
- [P2] **Verified External Actions:** Outside partners can submit status/events, but cannot silently overwrite canonical money, unit availability or legal records.
- [P2] **One-Click Data Migration Lab:** Map from popular CRMs and spreadsheets into canonical identities/opportunities, with preview, conflict queues and post-migration verification.
- [P3] **Portable Business Process Packs:** A developer can move a verified process, its approved templates, roles, automation tests and agent tools between environments without copying tenant-specific PII.
- [P3] **Federated Ecosystem Discovery:** Permissioned discovery of relevant verified services and listings across participating organizations, with explicit contractual terms and tenant isolation.

## 44. The Real Estate Network Graph: Multi-Party Collaboration at Scale [P2/P3]

- [P2] **Verified Organization Registry:** Developers, approved brokers, agencies, banks, legal firms, contractors, inspectors and maintenance providers with entity verification and role-limited capabilities.
- [P2] **Deal Room:** A secure workspace for one transaction, containing customer-approved participants, approvals, conditions, deadlines, versions, correspondence and verified completions.
- [P2] **Selective Data Sharing:** Share only explicitly permitted project facts, application fields, KYC documents or payment confirmations. Never grant a bank access to a seller's full CRM.
- [P2] **Referral Provenance:** Signed referral record, first valid registration, contested claims, agreed expiry, commercial terms, duplicate handling and decision trail.
- [P2] **Broker Collaboration:** Joint brokers can collaborate under configurable commission-split contracts and evidence-backed referral ownership.
- [P2] **Lender Workspace:** With customer authorization, request documents, track conditional pre-approval, valuation, sanction requirements, disbursement stages and outstanding dependencies.
- [P2] **Registration Coordination:** Share approved document checklist and appointment status with legal service providers, supporting evidence and version controls.
- [P2] **Contractor Portal:** View assigned inspections, work orders, required proof, appointment windows, approved parts and payment status without unrelated customer records.
- [P2] **Owner Association Transition:** Controlled transfer of allowed project asset documentation, facility manuals, warranty registers and common-area records to a verified association.
- [P2] **Developer-Independent Owner Passport:** Allow customers to retain access to permitted purchase evidence and ownership support after the initial developer account changes status.
- [P2] **Network Reputation:** Verified fulfillment metrics based on consented measurable performance, with appeal and correction paths, not unmoderated numerical labels.
- [P3] **Composable Transaction Network:** In one governed workflow, a borrower, lender, developer and lawyer can complete sequential required steps without duplicated data entry.
- [P3] **Verified Property Credential Exchange:** Time-bound signed attestations of narrow facts such as document received, construction milestone certified, sanctioned loan condition complete or payment settlement confirmed.
- [P3] **Customer-Controlled Relationship Transfer:** On resale or ownership transfer, customer can initiate a controlled data transfer based on legal authority and seller policy, preserving a record of disclosure and consent.

## 45. New AI Specialists and the Agent Studio [P2/P3]

Extend the already specified agent workforce with these precise specialties. A unique agent exists only if it has a distinct job, tools, measurable outcome and escalation policy.

| Specialist | Authorized mission | Must stop and escalate when |
|---|---|---|
| **AI Business Architect** | Turn admin descriptions into draft objects, fields, layouts, rules, documentation and workflow tests | Tenant changes affect data meaning, access, billing or legal permissions |
| **Journey Architect** | Draft customer journeys across ads, enquiry, visit, negotiation, booking and ownership | Marketing and transactional consent cannot be established |
| **Property Research Analyst** | Compare relevant source-backed neighborhoods, project facts and verified amenities | External data is stale, conflicting or unreliable |
| **Deal Assembly Agent** | Collect current unit facts, approved prices, customer requirements, correct drafts and required approvals | Price, unit status or contract terms are ambiguous |
| **Banking Readiness Agent** | Prepare consented customer loan document checklist and outstanding conditions | Regulated lender decision, valuation or credit eligibility is required |
| **Visit Logistics Agent** | Propose resource-constrained schedules for vehicles, sales teams and grouped visits | Capacity, travel assumption or resource confirmation is missing |
| **Buyer Communication Agent** | Draft messages in the customer's preferred language using approved verified facts | No legal contact basis, template, approved amount or safe recipient |
| **Legal Clause Auditor** | Compare draft against the tenant's approved contract language and flag differences | Material interpretation or legal advice is needed |
| **Property Evidence Auditor** | Flag contradictory layouts, disclosure documents, unit dimensions and approved plan versions | The source cannot be authenticated |
| **Release Gatekeeper** | Check if launch materials contain current approved price, availability, RERA facts and disclaimer | Missing authorization or conflicting claims |
| **Revenue Leakage Hunter** | Detect mismatched discounts, lost referrals, waived charges and unreconciled concessions | Financial posting or disciplinary judgment is required |
| **Collection Recovery Planner** | Recommend compliant intervention for overdue accounts with source evidence | Customer dispute, hardship, legal hold or threatened enforcement |
| **Service Cluster Analyst** | Detect repeating faults across a floor, tower, material batch or contractor | Safety-critical engineering advice or certification is required |
| **Construction Evidence Summarizer** | Assemble approved progress digest and map it to milestones | Certification or third-party evidence is absent |
| **Customer Advocate** | Identify overdue promises, missed callbacks and unresolved service, then create accountable tasks | Customer privacy or unsupported claims might be exposed |
| **Partner Dispute Investigator** | Reconstruct referral timeline, lead origin, consent and commercial ownership | Claim depends on discretionary policy or conflicting evidence |
| **SaaS Adoption Coach** | Help tenant admins activate real modules, configure workflows and understand adoption drop-offs | Sensitive tenant data requires elevated access |
| **Support Incident Diagnostician** | Correlate failed jobs, integration status and recent releases to propose remediation | A high-risk production action lacks review |
| **Quality Guardian** | Continuously test proposed agent workflows against synthetic edge cases and known policy failures | Evaluation coverage is insufficient or policy not defined |
| **Executive Scenario Analyst** | Build auditable planning scenarios from trustworthy metrics, explicitly listing assumptions | User asks to present a prediction as guaranteed result |

**Agent Studio must include** process designer, tool catalog, dataset/knowledge permissions, versioned instructions, simulated conversations, supervised training feedback, human-review configuration, KPI definitions, model choices, max-spend rules, multilingual evaluation, prompt-injection tests, data residency policy, release stages, kill switches and rollback.

## 46. Radical but Useful Customer and Sales Experiences [P2/P3]

A true 2046 product should make difficult work disappear, not merely add more menu links. Add these signature experiences, each linked to live business systems.

1. [P2] **One-minute buyer brief:** On opening a valid customer, show what they want, what they were told, what remains unresolved, what inventory fits and the safe next action, all with source links.
2. [P2] **Zero-search workbench:** A salesperson's screen rearranges approved modules around the current customer or unit, preserving a predictable manual navigation option.
3. [P2] **Zero-entry visit:** After a permitted site meeting, dictation and checked checklists propose CRM updates for executive confirmation, with structured next steps.
4. [P2] **No-silent-failure deal:** An open opportunity is continuously checked for missing contacts, approvals, deadlines, inventory clashes and unanswered customer questions.
5. [P2] **Offer as an executable contract preview:** A negotiated quote clearly distinguishes provisional offer from signed agreement, with exact price versions and approver authority.
6. [P2] **Property recommendation explanations:** “Matched because north facing, 1,450 sq ft and within ₹1.1 crore” with source details, trade-offs and customer override.
7. [P2] **Spatial inquiry:** Buyer selects a room or plot on a verified visual map and asks a question directly about that location.
8. [P2] **Immersive neighborhood lens:** For documented data, display commute, nearby services, sunlight and public infrastructure alongside the property without overclaiming certainty.
9. [P2] **Verified construction time travel:** Customer compares certified project progress at two dates and sees what changed, with documentation references.
10. [P2] **Customer-controlled memory:** Buyer can inspect, correct or request removal of allowed preference data, rather than being invisibly profiled forever.
11. [P2] **Family decision room:** Customer can invite spouse/co-buyer/family reviewers with selective permissions, comparison notes and a shared visit plan.
12. [P2] **Honest budget explorer:** Show full ownership cost, charges, taxes and optional finance examples; label estimates and correct price validity.
13. [P2] **Property shortlisting calendar:** Buyers can schedule multiple visits through one capacity-aware sequence with clear travel breaks and available executives.
14. [P2] **Property hold with countdown:** Buyer sees time remaining on a legally allowed temporary hold and the exact process to extend or release it.
15. [P2] **Proof-based payment center:** One screen differentiates due, paid, settled, reconciled, documented and disputed transactions.
16. [P2] **Always-correct balance request:** “How much is pending?” returns a finance-authoritative amount with calculation date and any unresolved transfers clearly flagged.
17. [P2] **Promise tracker:** Every documented promise from developer or service desk has owner, due date, evidence and customer-visible resolution state.
18. [P2] **Construction Q&A with evidence:** Buyer asks why a milestone shifted and receives the developer-approved explanation and source document, not invented reassurance.
19. [P2] **Service case via photo:** Photo creates a draft structured issue linked to property/asset; customer confirms description and severity.
20. [P2] **Warranty intelligence:** Automatically surface coverage and vendor based on unit, asset, installation date and validated contract.
21. [P2] **Ownership continuity:** Handover transforms the buyer portal into a home/asset portal without losing authorized historical documents.
22. [P2] **Language continuity:** Buyer can switch between Telugu, Hindi and English while keeping exact financial amounts and document meanings unchanged.
23. [P2] **Executive decision microscope:** CEO clicks a KPI outlier and gets underlying records, timeline, competing explanations and actions with owners.
24. [P2] **Cross-project movement intelligence:** A customer moving from villa to apartment interest keeps one relationship history and explicit opportunity records.
25. [P2] **Revenue-at-risk heatmap:** Show exactly which units/deals/payments create near-term forecast exposure, along with uncertainty, not false certainty.
26. [P3] **Agent-produced operating day:** On approval, AI assembles visits, customer follow-ups, collections exception reviews and approvals into a feasible day plan.
27. [P3] **Digital twin conversation:** A user asks “Show all unsold units below ₹90 lakh that receive afternoon sun according to approved geometry” and the verified visual map responds.
28. [P3] **Hypothetical development studio:** Test a different product mix or launch date using clearly labelled scenario data; never write forecast results back as actual inventory.
29. [P3] **Permissioned city-scale market lens:** Aggregate approved public and tenant-owned data to compare launch conditions and locality risk with privacy safeguards.
30. [P3] **Portable homeowner passport:** Explicitly authorized third parties can verify a narrow credential without accessing unrelated property history.
31. [P3] **Customer-guided virtual inspection:** Buyer and agent jointly annotate an approved floor plan, compare upgrade options and generate a formal reviewed action list.
32. [P3] **Smart dispute explainer:** Reconstruct price change, referral conflict or payment mismatch from signed timelines and approval evidence, then open the right review task.
33. [P3] **Business-time rewind:** Admin asks “What was true on the day this offer was issued?” and sees the price, unit status, policies and approvals effective at that timestamp.
34. [P3] **Impact-before-action:** Before a bulk repricing, campaign pause, interest waiver or unit release, preview affected customers, finance implications and approval requirements.
35. [P3] **Autonomous ops with proof:** A requested safe operation is not declared complete until external acknowledgments, state changes and audit evidence agree.
36. [P3] **Invisible migration assistant:** Tenant imports old CRM data, reviews confidence-ranked matches, fixes exceptions, and preserves source provenance with a final migration quality report.
37. [P3] **Service-wide incident intelligence:** Repeated complaints reveal a probable common infrastructure fault, triggering an engineering inspection case rather than dozens of disconnected replies.
38. [P3] **Real-time trust feed:** A buyer sees verified status updates on booked unit, document verification, authorized payments, official construction milestone and assigned service resolution.
39. [P3] **Explainable business assistant:** Each factual answer includes its source, freshness, scope, calculation and exactly what the system could not verify.
40. [P3] **Self-updating process playbooks:** The system proposes improvements based on documented bottlenecks, simulated outcomes and operator/user approval, never silently changing policies.

## 47. Collections Autopilot: Advanced Enterprise Rules Beyond Reminder Schedules [P1/P2]

The earlier Finance OS defines the mandatory reminder ladder. Add these capabilities to make the system genuinely strong under real-world load:

- [P1] **Automated Promise-to-Pay:** Capture customer-stated commitment as a structured event with due date, amount, responsible collector, evidence and a bounded reminder flow; do not treat promises as settled cash.
- [P1] **Customer Dispute Pause:** “Amount is wrong” places eligible disputed installments into the configured review workflow, cancels inappropriate escalation and alerts finance.
- [P1] **Milestone-gated Demand Creation:** Construction-linked installment becomes billable only after approved evidence and contract milestone criteria are satisfied.
- [P1] **Complex Payment Plans:** Split payments, balloon milestones, negotiated rescheduling, grace periods, late charges where contractually valid and ledger-safe amendments.
- [P1] **Collection-Account Assignment:** Virtual bank account, verified UPI/payment gateway, payment reference and beneficiary mapping per customer/booking where supported.
- [P1] **Bank Statement Automation:** Scheduled authorized import, secure portal download where permitted, CSV/XLSX/SFTP/API ingestion, format normalization, duplicate detection and exception queue.
- [P1] **Reconciliation Confidence Rules:** Automatically match only exact or high-assurance cases under approved policy; money with uncertain provenance stays in suspense.
- [P1] **Remittance Advice Parser:** Extract structured candidate amounts and UTRs from emails or documents as suggestions, not proof of settlement.
- [P1] **Auto Receipt Issuance:** After verified settlement and match, issue a compliant official receipt, distribute it, update the account and cancel outdated notices.
- [P1] **Automated Reminder Cancellation:** At each dispatch, cancel reminders for paid, cancelled, stayed, waived, disputed or rescheduled obligations as configured.
- [P1] **Interest/Charge Calculator:** Versioned contract-based calculations with line-item explainability, authorized exceptions and proper legal review.
- [P1] **Refund Workbench:** Eligibility calculation, deductions, KYC/beneficiary check, maker/checker approvals, payout-provider initiation, bank confirmation and customer notice.
- [P1] **Payment Failure Recovery:** Trigger verified retry links or assisted contact on provider failure; never blindly repeat a debit without authorization.
- [P1] **Finance Hierarchy:** Collections executive, AR supervisor, regional finance, finance controller, CFO, legal and operator each receive exactly their approved tasks.
- [P1] **Collection Route Optimization:** Suggest the least intrusive compliant next action using customer preference, previous contact success and verified balance, not sensitive personal inference.
- [P1] **Multi-entity Collections:** Separate company, project, GST registration, contract beneficiary and payout account, with inter-company accounting controls.
- [P1] **Daily Cash Close:** System schedules reconciliation, raises unmatched deposits, provides exception ownership and produces auditable sign-off.
- [P1] **Monthly Collections Campaign:** Preview recipients and amounts, deduplicate across installments, respect holidays/quiet hours, approval for bulk launch and delivery tracking.
- [P1] **Chargeback and Reversal Handling:** Reverse appropriate ledger entries with explicit references; reinstate accurate balances and re-evaluate notifications only after authoritative state change.
- [P2] **Collections Scenario Planner:** Predict expected receipts by project and week, with best/base/stress scenarios and assumptions.
- [P2] **Cash Realization Attribution:** Associate original campaign, source, sales opportunity and customer with collected cash, while avoiding unsupported causal claims.
- [P2] **Customer Payment Assistant:** Provide safe statements, download link, dispute request, secure payment redirect, payment assistance options and human finance contact.
- [P3] **Financial Controls Sentinel:** Continuously detect unapproved receipt edits, duplicate collection references, inconsistent allocations, sold-unit mismatches and suspicious commission settlement patterns.

**Acceptance sequence:** A construction milestone is approved → demand letter generated and authorized → appropriate future reminders scheduled → customer pays via provider → provider and bank verify settlement → receipt issued → account ledger updated → remaining reminders suppressed → management collections dashboard and customer's payment passport update. This must work across parallel workers, retries, failures and partial payments.

## 48. Autonomous Growth OS: Real Estate Marketing 20 Years Forward [P2/P3]

- [P1] **Real Campaign Objects:** Platform, account, campaign, ad set, creative, UTM, form, spending period, agency, budget, project and lead provenance linked to actual customer outcomes.
- [P1] **Offline Attribution:** Unique QR codes, tracking numbers, hoarding IDs, on-ground events, newspaper insert IDs and walk-in origins with dedupe and clear uncertainty.
- [P1] **Marketing Approval Desk:** Creative claims validation, media budgets, territory/targeting approvals, agency sign-off, launch checklist and performance history.
- [P1] **Customer Journey Audiences:** Exact customer segments by consent, project interest, legitimate first-party engagement, opportunity stage and exclusion rules.
- [P1] **Creative Evidence Library:** Approved product claims, current prices, projects, RERA references, media rights, version expiry and channel-ready variants.
- [P2] **Campaign-to-Cash Truth:** Attribute inquiries through qualified opportunities, site visits, booking, agreement, actual collection, cancellation and refund.
- [P2] **Marketing Spend Waste Detector:** Flag duplicate audiences, rising cost per qualified visit, stalled campaigns, mismatched source tags and lead volume without collections.
- [P2] **Creative Claim Guardian:** Before an ad is published, verify that advertised inventory, prices, project status, promised possession, RERA details and amenities are still approved.
- [P2] **Lead Quality Root Cause:** Diagnose why source A creates volume but low visits, or source B produces low volume but strong cash collections, with campaign and sales response context.
- [P2] **Budget Reallocation Workbench:** Present proposed moves with assumptions, confidence, likely effects and approval; publishing to ad platforms is an explicitly authorized action.
- [P2] **Instant Campaign Landing Pages:** Generate and publish branded pages from approved project facts, source-specific tracking, consent and validated lead forms.
- [P2] **Journey Recovery:** Detect a neglected but consented customer opportunity and propose an approved outreach or human follow-up based on documented context.
- [P2] **Regional Language Creative QA:** Generate localized drafts but require approved factual and cultural review before external publication.
- [P2] **Campaign Experiment Builder:** Holdout groups, allocation, stopping rules, statistical caveats and downstream cash outcomes.
- [P3] **Property-Demand Simulation:** Model likely product-mix demand under inventory, price, season, source quality and marketing spend assumptions.
- [P3] **Creative Intelligence Co-Pilot:** Explain which facts, formats and channels appear associated with high-quality outcomes; distinguish correlation from causation.
- [P3] **Marketing and Sales Operating Loop:** The system proposes action across campaigns, sales staffing, appointment capacity and inventory readiness as one coordinated plan.

## 49. A Unified Navigation Standard for ALL Portals [P0/P1]

The sidebar architecture in Part II is mandatory. Add this explicit product contract so implementation cannot degrade into a flat list or unconnected pages:

- [P0] **Every primary group is navigable and meaningful.** E.g. Admin → Finance → Collections → Reminder Calendar opens a functional calendar, not a dashboard copy.
- [P0] **Menu taxonomy is stable:** Group → Submodule → View/record/action. Use consistent nouns and avoid overlapping duplicate items such as “Payments” in five places without context.
- [P0] **Operator navigation remains cross-tenant control, never tenant business admin.** Operator can see usage, subscriptions, service/incident metadata and approved support traces, not buyers' private data by default.
- [P0] **Admin navigation maps to departments:** Command Center, CRM, Projects, Inventory, Marketing, Sales, Communications, Deals, Finance, Documents, Partners, Customer Experience, Construction, Automation, Intelligence, Organization and Settings.
- [P0] **Specialized portals:** Sales, Sales Manager, Finance, Marketing, Inventory, Legal, Construction, Support, Channel Partner, Buyer, Board/Investor and Contractor each show relevant pages; no “everyone is Admin” shortcut.
- [P0] **Identity and workspace switching:** One person may have Finance and Admin capability in the same tenant but receives a different audited authority per action. Support staff cannot infer finance authority from a visible link.
- [P0] **Sidebar badges show real counts** for pending approvals, overdue installments, unread conversations, visit check-ins, failed automations, open service cases and incidents.
- [P0] **One canonical route per concept, multiple contextual entry points.** A payment ledger linked from buyer, admin and finance must use shared canonical data with different allowed presentation.
- [P0] **Deep-linked submodule permissions:** A user cannot bypass role restrictions by typing the URL, opening a saved link, calling an API or invoking an agent tool.
- [P0] **No dead-end click:** Every nav item has live list, detail, action, empty state, loading/error handling, export where relevant and contextual next steps.
- [P0] **Responsive consistency:** Desktop expanded/collapsed sidebar, tablet nested drawer and mobile accessible navigation; context actions stay discoverable.
- [P0] **Global search:** Search available navigation items by human language and synonyms, while respecting account permissions.
- [P1] **Admin-configurable workspace visibility:** A tenant can hide, reorder and rename permitted menu sections without changing backend authorization.
- [P1] **Department-specific saved navigation:** Finance favorites Collection Aging and Reconciliation Exceptions; Sales favorites Today and My Deals; Owner favorites My Property and Payments.
- [P1] **Accessibility:** Full keyboard navigation, focus restoration, screen reader labels, compact density options, clear pending/unread semantics and reduced motion.
- [P2] **Task-aware navigation:** Suggest the next permitted destination after completing a task, with a visible explanation and easy override.
- [P3] **Universal Action Mode:** A permitted user can describe a task and launch the exact existing form/workflow, with editable review, rather than learning an arbitrary menu hierarchy.

### 49.1 Operator sidebar example as complete nested navigation

```text
Operator Console
  Mission Control
    Platform Overview
    Live Service Status
    Incidents and Escalations
    Cross Tenant Action Queue
  Organizations
    Tenant Directory
    Tenant Onboarding
    Tenant 360
    Domains and Branding
    Regions and Data Residency
    Tenant Lifecycle
  Subscriptions and Revenue
    Plans and Feature Bundles
    Subscription Ledger
    Metering and Overage
    Billing and Invoices
    Payments, Credits and Dunning
  Platform Operations
    Environments and Deployments
    Queues and Jobs
    Backup and Recovery
    Webhook and Provider Health
  Product and AI
    Release Channels
    Feature Flags
    AI Agent Registry
    Models and Evaluation
    Automation Run Control
    Experiment and Rollout Control
  Customer Success
    Onboarding Projects
    Tenant Support Desk
    Renewal Risks
    Product Adoption
  Trust and Ecosystem
    Operator Roles and Access
    Privileged Support Requests
    Security and Audit
    Connector Marketplace
    Regional Policies
  My Workspace
    Notifications
    Tasks and Approvals
    Profile and Sessions
```

### 49.2 Developer Admin sidebar example as complete nested navigation

```text
Developer Admin Console
  Command Center
    Executive Overview
    Today's Priorities
    Action and Approval Center
    Revenue Pulse
    Collections and Delivery Alerts
  CRM and Customers
    Customer Directory
    Customer 360
    Opportunities and Pipelines
    Households and Co Buyers
    Customer Preferences and Consents
    Duplicates and Merge Review
  Projects and Inventory
    Project Registry
    Phases, Towers and Plots
    Units and Parking
    Living Inventory Map
    Unit Holds and Reservations
    Unit Price History
    Project and Unit Documents
  Sales and Deals
    Lead Distribution and Routing
    Sales Teams and Territories
    Site Visits and Appointments
    Deals, Offers and Negotiations
    Discount Approval Queue
    Booking and Contract Desk
    Sales Coaching and Performance
  Marketing and Growth
    Campaigns and Media Spend
    Landing Pages and Lead Forms
    Audiences and Journeys
    Creative Evidence Library
    Campaign Attribution
    Conversion and Cash Intelligence
  Communications
    Unified Inbox
    Calling and Call QA
    WhatsApp, SMS and Email
    Templates and Journeys
    Delivery and Consent Center
  Finance and Collections
    Accounts Receivable
    Payment Plans and Installments
    Reminder Calendar
    Demand Letters
    Payment Gateway and Bank Matching
    Receipt Ledger
    Refunds and Adjustments
    Collections Aging and Forecast
    Reconciliation and Close
  Legal and Documentation
    Contract Template Studio
    Agreement Drafting and Review
    E Sign and Registration
    Buyer KYC and Documents
    Cancellations and Transfers
  Broker and Partner Network
    Channel Partner Directory
    Referral and Ownership Registry
    Partner Deals and Access
    Commission and Payout Ledger
  Construction and Customer Success
    Certified Milestone Tracker
    Construction Evidence
    Handover and Snagging
    Service Desk and Warranties
    Customer Feedback
  Automation and AI
    Automation Studio
    Run Monitor and Failure Queue
    AI Agent Studio
    Agent Activity and Approvals
    Knowledge and Policy Center
  Analytics and Planning
    Executive Intelligence
    Funnel, Inventory and Revenue
    Scenario Simulation Studio
    Custom Report Builder
  Organization and Platform
    Teams, Roles and Permissions
    Custom Objects and Forms
    Integration Marketplace
    Audit, Privacy and Retention
    Branding and Module Configuration
```

### 49.3 Role portal acceptance for each sidebar

1. Sales user can complete lead → contact → visit → proposal → hold → booking handoff without entering Admin.
2. Finance user can complete demand → reminder → bank match → receipt → reconciliation → close without entering Admin.
3. Support user can complete inbound complaint → case → field technician → proof → CSAT without entering Admin.
4. Broker can register a legitimate referral, see permitted availability, follow booking status and track accurate commission without seeing another broker's customers.
5. Buyer can select a property, book a visit, see accepted offers, pay verified dues, access documents, request service and retain their property passport.
6. Operator can onboard a tenant, configure plan, observe service health, resolve permitted incident and manage renewal without accessing private tenant CRM data.
7. Marketing user can run campaign → captured lead → site visit → booking → collection attribution with consistent IDs and no fake metrics.
8. Inventory manager can perform unit import → availability check → price release → authorized hold → confirmed sale with no double sell.

## 50. The Enterprise No-Skeleton Guarantee: Fully Working Business Scenarios [P0/P1]

Claude Code must treat the following as required feature demonstrations, not optional UI screenshots:

| Scenario | End-to-end behavior that must actually work |
|---|---|
| **Customer has three enquiries** | One customer record, three opportunities, correct source events and separate project permissions; no accidental data loss from dedupe |
| **Two sales agents reserve the same unit** | Exactly one authorized hold succeeds and one receives an explainable conflict; no phantom availability |
| **A manager rejects discount** | Offer remains uncommitted, requester gets reason, unit price stays unchanged, customer messaging follows approved path |
| **Customer pays installment early** | Provider/bank settlement verified, receipt posted once, outstanding recalculated, scheduled reminders cancelled and portal updated |
| **Customer makes partial payment** | Correct partial credit, remaining demand, adjusted reminder message and honest payment status |
| **Customer disputes amount** | Eligible collection escalation is paused, finance case assigned, owner receives evidence and customer can track resolution |
| **Webhook arrives five times** | Event is processed once; no duplicate customer, hold, money posting, receipt or external message |
| **Agent suggests an unapproved action** | Tool refuses, reason logged, human approval or safe alternative presented |
| **Cross-tenant record ID submitted** | No unauthorized data returned through URL, list, export, search, background job or AI tool |
| **Provider is unavailable** | Work queued/retried safely, customer informed only of verified send state, operator sees incident and retry history |
| **Project unit is blocked** | Sales, buyer, partner, pricing, marketing and AI recommendation views honor that state without stale promises |
| **Legal changes an agreement** | New version, comparison, reviewer, superseded drafts and signature state retained |
| **Broker disputes referral ownership** | Evidence timeline, rules, neutral review, explicit resolution and commission recalculation recorded |
| **Customer files warranty case** | Exact unit and asset, warranty eligibility, SLA, technician assignment, visit proof, buyer updates and CSAT |
| **New tenant is activated** | Tenant branding, users, roles, flags, plans, sample data isolation, payment/provider setup and operator audit all work |
| **Custom module published** | Field layout, permissions, forms, reports, events, automation and secure agent access all work from one published configuration |
| **Payment amount changed after letter prepared** | Outdated pending letter is invalidated and correct version requires proper review; no stale amount dispatched |
| **High-volume scheduled campaign** | Batching, limits, suppression, late consent changes, delivery receipts, retries and accurate reconciliation of outcomes |
| **Multi-day AI work order** | Plan persists, awaits approvals, resumes correctly, reports blocked steps, survives service restart and shows traceable outcome |
| **Application/data outage** | Health status, user feedback, queue recovery, backup/restore plan and integrity verification are demonstrable |

## 51. The 2046 Differentiation Scorecard [P0/P2]

Do not judge progress by feature count alone. Build dashboards that measure whether the system is genuinely extraordinary:

| Outcome | Primary metric | Proof of correctness |
|---|---|---|
| Customer response | Verified first human or authorized automated response latency | Message provider and conversation event timestamps |
| Sales execution | Lead → qualified → visited → contracted conversion with cohort definitions | Canonical opportunity and visit stage history |
| Inventory trust | Number of conflicting holds or double allocations | Database reservation invariants and concurrency tests |
| Collections autonomy | Portion of eligible reminders/demands executed without manual work | Policy evaluation + queued/sent/delivered ledger + approvals |
| Money correctness | Unreconciled transaction count, aging and duplicate-post prevention | Bank/provider evidence and double-entry ledger consistency |
| Customer trust | Time to satisfy valid information requests and resolve cases | Customer portal event and service history |
| Agent reliability | Verified work-order outcomes / initiated work orders | Tools, audited state transitions and external acknowledgments |
| Human workload | Hours of verified routine work eliminated | Task completions with approved reference baselines |
| Forecast accuracy | Realized results versus forecast interval, by cohort | Versioned snapshots, objective backtesting and confidence bands |
| Commercial quality | Concessions, realized cash and profitability per product | Price-book versions, approvals, official ledgers and cost assumptions |
| Service quality | SLA compliance, repeat-fix rate and recurrence | Case and work-order timelines with documented closures |
| SaaS dependability | Availability, error budget, recovery time and failed-automation age | Production telemetry and operator incident records |
| Enterprise extensibility | Time to launch fully governed custom business module | App Studio build/publish/test/run workflow |
| Data portability | Time to export, verify and migrate consent-authorized data | Export manifests, integrity checks and import reconciliation |

**The true “20 years ahead” outcome:** A user should be able to trust that PropFlow understands the customer, property, transaction, evidence and next authorized action as one system, without reconciling five separate spreadsheets or chasing disconnected departments.

## 52. Feature Delivery Order: Working Operating Systems, Not Empty Sprints

This is a **feature dependency order**. Every stage must ship functioning work across UI, domain, permissions, automation, reporting and tests; do not create placeholders for later phases.

1. **First complete: Customer graph + Opportunity graph + Property inventory + Transaction-safe unit holds + role-specific navigation.** These fix the foundational business object model that every advanced feature needs.
2. **Second complete: Full Deal Desk + real price/cost sheets + approval matrix + booking transactions + document lifecycle.** Make selling a unit verifiable.
3. **Third complete: Finance OS end-to-end + automated payment reminders + demand letters + bank reconciliation + receipts + refund approvals.** Make financial operations autonomous without compromising evidence.
4. **Fourth complete: Freshdesk-class service desk + technician workflows + buyer property passport + handover and warranties.** Become the post-sale operating system, not only a sales CRM.
5. **Fifth complete: App Studio + custom business objects + rules + report builder + tenant role designer.** Compete with flexible enterprise platforms.
6. **Sixth complete: Agent Studio + governed long-running work orders + multi-agent coordination + policy enforcement and evaluation.** Make AI truly operational.
7. **Seventh complete: Digital property twin + geospatial explorer + certified construction evidence + planning simulation.** Make visual intelligence actionable and verified.
8. **Eighth complete: Partner ecosystem + developer/lender/legal/contractor deal rooms + selective credentials and interoperable marketplace.** Build long-term network effects.
9. **Ninth complete: Autonomous growth, campaign-to-cash intelligence, advanced executive simulation and outcome optimization.** Close the loop from acquisition to realized money and customer trust.

**Finish line for each release:** A real tenant can start and finish the promised workflow with actual role-restricted data, correct business state changes, valid communications, traceable financial behavior and meaningful recovery when external systems fail. Nothing is “complete” because it looks attractive in a browser.

---

# HANDOFF TO CLAUDE CODE

Read this entire file, then inspect the **current** repository HEAD, actual routes, components, models and existing feature flags. Treat the content as the **new feature destination**, not instructions to duplicate existing implementations. Design complete sidebars and real functional pages for Operator, Admin and specialized user portals. Prioritize the canonical customer and property graphs, atomic unit reservations, deal desk, full financial automation, collections reminders, enterprise support suite and business application studio. Implement one integrated business capability at a time, with real workflow completion and no placeholders, demo-only logic or unverified claims. Never let AI bypass permissions or autonomously perform irreversible legal, financial or high-risk actions. Preserve working features while expanding them.
