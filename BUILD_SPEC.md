\# BUILD\_SPEC.md — PROPFLOW → White-label Multi-tenant SaaS



\## 0. Working agreement (read first — applies to every phase)



\- Repo: PROPFLOW — FastAPI 3.12 backend (`backend/`, SQLAlchemy 2.0, Alembic, Pydantic v2,

&#x20; JWT auth, roles ADMIN/SALES\_EXECUTIVE/BUYER, in-process schedulers) + React 19/TS/Vite

&#x20; frontend (`frontend/`). Dev DB = SQLite; prod = PostgreSQL. 224 pytest tests exist and

&#x20; MUST stay green after every phase. Demo seeders must keep working.

\- Golden rules:

&#x20; 1. Match the repo's existing conventions (module layout, router registration,

&#x20;    response schemas, naming). Explore before writing.

&#x20; 2. Never break existing endpoints' behavior; extend, don't rewrite.

&#x20; 3. Every new cross-entity query path is tenant-scoped — no exceptions.

&#x20; 4. Add/adjust tests with every change. Run `python -m pytest tests -v` before reporting done.

&#x20; 5. New env vars go in `backend/.env.example` + this doc's env table + sane dev defaults.

&#x20; 6. Commit after each phase: `feat: phase N — <name>`.

\- Phases are sequential. Do not start phase N+1 until phase N's acceptance criteria pass.



\## Phase 0 — Repo reconnaissance \& baseline (output only, no code changes)



\- Run the stack locally (uvicorn :8000 + vite :5173 with SQLite), run full pytest suite,

&#x20; and document the baseline (pass/fail counts).

\- Produce `REPO\_MAP.md`: models with fields, all routers/paths, auth/JWT flow, scheduler

&#x20; inventory (e.g. site-visit reminder loop), notification module structure, seeders.

\- Flag any surprises vs this spec and propose adaptation BEFORE writing phase-1 code.



\## Phase 1 — Multi-tenancy core (the heart of the product)



\*\*Data model (one Alembic migration, reversible):\*\*

\- New table `tenants`: id, slug (unique), name/brand\_name, status (active/suspended),

&#x20; plan\_id (nullable for now), logo\_path, theme\_json, country, timezone, currency,

&#x20; created\_at, updated\_at.

\- Add `tenant\_id` (FK tenants.id, indexed, NOT NULL after backfill) to every domain table

&#x20; found in Phase 0 — minimum: users, projects, project\_facts, leads, conversations,

&#x20; messages, follow\_ups, visit\_slots, site\_visit\_bookings, notifications, marketing\_spends,

&#x20; audit\_logs.

\- Backfill: create tenant row "Default Tenant" (slug `default`), set all existing rows'

&#x20; tenant\_id to it. Add composite indexes (tenant\_id, id) on hot tables.



\*\*Backend changes:\*\*

\- Embed `tenant\_id` in JWT at login; add FastAPI dependency `get\_current\_tenant`

&#x20; (JWT claim → tenant row; 403 if suspended).

\- Add shared query helper `with\_tenant(query, Model)` and apply it to EVERY authenticated

&#x20; read/write in every router (lead lists, booking fetch, analytics, dashboards — all of it).

&#x20; Writes must stamp tenant\_id automatically.

\- Signup endpoint `POST /api/v1/tenancy/signup`: transaction creates tenant + first ADMIN

&#x20; user; returns login tokens.

\- Global rule: super-admin concept does NOT exist; all roles are tenant-local.



\*\*Acceptance (write these tests):\*\*

\- `test\_tenant\_isolation.py`: seed two tenants; each with users/leads/bookings.

&#x20; - Agent of tenant A cannot GET/PUT/DELETE any tenant-B entity (404/403, never data).

&#x20; - Analytics/funnel endpoints return tenant-A-only numbers.

&#x20; - Audit log reads are tenant-scoped.

&#x20; - Buyer login sees only own tenant's projects/visits.

\- Existing suite still passes (fixtures updated to include tenant).



\## Phase 2 — White-label + tenant settings



\- `GET/PUT /api/v1/tenancy/settings` (ADMIN only): brand\_name, logo (upload to storage),

&#x20; theme {primary color, dark-mode default}, currency, timezone, date format.

\- Frontend: after login, fetch tenant settings; apply brand name + logo + theme color in

&#x20; shell + auth pages; neutral PROPFLOW-free public landing (generic "by your company" slot).

\- Acceptance: two tenants show distinct brand in same browser (two profiles); logo upload

&#x20; persists; unauthorized users cannot PUT settings.



\## Phase 3 — Messaging trigger engine (headline commercial feature)



Goal: any business event fires rule-matched WhatsApp/SMS/email, templated + multilingual.



\*\*Structure (create `backend/app/modules/messaging/` or repo's equivalent home):\*\*

\- Models: `message\_templates` (tenant\_id, name, channel, language, body w/ merge tags,

&#x20; provider\_template\_name), `trigger\_rules` (tenant\_id, event, channel, template\_id,

&#x20; enabled, delay\_minutes), `message\_deliveries` (tenant\_id, channel, to\_address, body,

&#x20; provider, status queued/sent/delivered/failed, provider\_msg\_id, error, timestamps).

\- `providers/` — interface `Provider.send(to, template\_body, context) -> provider\_msg\_id`:

&#x20; - `GupshupWhatsApp` (template + session messages; env GUPSHUP\_API\_KEY, GUPSHUP\_APP\_NAME,

&#x20;   GUPSHUP\_SOURCE\_NUMBER)

&#x20; - `MSG91SMS` (env MSG91\_AUTH\_KEY, MSG91\_SENDER\_ID)

&#x20; - `SMTPEmail` (standard SMTP envs)

&#x20; - `LogProvider` (default dev fallback — writes to log, no keys needed)

\- `engine.py`: `emit\_event(event: str, tenant\_id, context: dict)` → find enabled

&#x20; trigger\_rules → apply delay (schedule) → render merge tags ({first\_name}, {project\_name},

&#x20; {visit\_time}, {sales\_name}) → dispatch via provider → write message\_deliveries row.

&#x20; Reuse the repo's existing scheduler task for delayed sends.

\- Wire `emit\_event` at: lead create, stage/status change, site-visit booked,

&#x20; site-visit reminder due (REPLACE existing in-app-only reminder action with engine emit),

&#x20; visit completed, visit no-show.

\- AI touch: use existing Groq client to auto-pick template language from lead's

&#x20; conversation language (en/hi/gu).

\- Admin UI: settings page for templates + trigger rules (CRUD, enable toggles),

&#x20; delivery log table with status filter, "send test" button.



\*\*Acceptance:\*\*

\- Unit: engine with fake provider — event→rule→rendered message→delivery row (idempotent,

&#x20; no double sends on retry).

\- Integration: POST a lead via API → within tick, `message\_deliveries` has queued/whatsapp

&#x20; row with correctly merged Hindi template when lead language=hi.

\- Existing suite green. LogProvider works with zero external keys.



\## Phase 4 — Lead ingestion connectors



\- \*\*Meta Lead Ads\*\*: `GET /api/v1/webhooks/meta` (hub.challenge verify, env

&#x20; META\_VERIFY\_TOKEN) + `POST` (X-Hub-Signature-256 verification via META\_APP\_SECRET;

&#x20; fetch lead via Graph API with META\_PAGE\_ACCESS\_TOKEN; map fields to lead schema;

&#x20; dedupe by phone/email; emit lead.created with source="meta\_ads"; record spend source).

\- \*\*Portal email ingestion (99acres / MagicBricks / Housing.com)\*\*: background task polls

&#x20; IMAP mailbox (env LEADS\_IMAP\_HOST/USER/PASS) every 3 min; per-portal parsers extract

&#x20; name/phone/email/project/budget; dedupe; emit lead.created with source=portal name;

&#x20; store raw payload for parsing forensics; admin page: connection test + last-run status.

\- Acceptance: pytest fixtures with recorded Meta payload + sample portal emails → correct

&#x20; lead rows, correct source attribution, dedupe proven (second identical email = no dup).



\## Phase 5 — Billing \& plan gating (Razorpay)



\- `plans` table: name, monthly\_price, currency, limits\_json (max\_users, leads\_per\_month,

&#x20; whatsapp\_msgs\_per\_month, features flags).

\- Razorpay subscription flow: create plan/subscription via API, hosted checkout page for

&#x20; client admin, webhook endpoint `/api/v1/webhooks/razorpay` (signature-verified) updating

&#x20; tenant.status / plan on payment events (activated, halted, past\_due → grace → suspended).

\- Enforcement: middleware checks limits on user-invite / lead-create / whatsapp-send;

&#x20; 402-style upgrade response; admin billing page (plan, usage meters, invoices).

\- Acceptance: test-mode Razorpay webhook fixtures drive tenant through full lifecycle;

&#x20; limit enforcement proven in tests.



\## Phase 6 — (SPEC LATER) Post-sales pack



Bookings → payment plans → installment demand letters → receipts ledger → broker

commissions → customer/broker portals. Detailed separately after Phase 5 ships.



\## Env additions (backend/.env)



| Var | Used by | Notes |

|---|---|---|

| GUPSHUP\_API\_KEY / GUPSHUP\_APP\_NAME / GUPSHUP\_SOURCE\_NUMBER | WhatsApp provider | required only when channel enabled |

| MSG91\_AUTH\_KEY / MSG91\_SENDER\_ID | SMS provider | optional |

| META\_APP\_SECRET / META\_VERIFY\_TOKEN / META\_PAGE\_ACCESS\_TOKEN | Meta webhook | |

| LEADS\_IMAP\_HOST / USER / PASS / MAILBOX | portal parser | e.g. leads@yourdomain.com |

| RAZORPAY\_KEY\_ID / RAZORPAY\_KEY\_SECRET / RAZORPAY\_WEBHOOK\_SECRET | billing | test mode first |

| MESSAGING\_PROVIDER\_DEFAULT=log | engine | switch to gupshup in prod |



\## Global security \& correctness notes



\- Provider/Razorpay credentials stored for tenants must be encrypted at rest (Fernet,

&#x20; key from env ENCRYPTION\_KEY).

\- Rate-limit public webhooks; replay-protection on Meta/Razorpay signatures.

\- All new tables get tenant\_id composite indexes; no N+1 in new endpoints.

\- Keep SQLite-dev / Postgres-prod compatibility in every migration (no PG-only types).

\- After each phase also run frontend `npm run build` (typecheck) when frontend changed.



