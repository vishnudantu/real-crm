# PROPFLOW Repository Map — Phase 0 Baseline

> **Phases 1–5 complete (2026-11-21).** Multi-tenant foundation, white-label UI, messaging
> engine, operator control plane, lead connectors, and Razorpay billing are implemented and
> committed. **268 backend tests pass**, frontend build + 7 unit tests + 3 branding E2E pass,
> migration upgrade/rollback/re-upgrade + alembic check clean on disposable and dev DB, demo
> seed + reset verified, local API verified against migrated DB (login, tenant listing,
> public branding, RBAC). Generic OpenAI-compatible AI provider layer added (OpenAI/Azure/
> self-hosted) alongside Groq. One-click cloud deploy script at `deploy/cloud_install.sh`.
>
> **Migrated and verified locally (2026-11-21):** `backend/propflow_dev.db` was backed up and
> migrated to head `e8f2a3b4c5d6` (`alembic check` reports no drift). All existing rows were
> backfilled to the default tenant (`00000000-0000-0000-0000-000000000001`) with zero
> `tenant_id` NULLs and zero foreign-key violations; tenant-local project-slug uniqueness is
> enforced. The running API was verified against the migrated DB (liveness/readiness, admin
> login, tenant-scoped listing, public branding, RBAC).
>
> **Deferred / follow-ups identified by code review (deliberate, not bugs in current behavior):**
> - `app/db/tenancy.py::with_tenant()` and the `db.info["tenant_id"]` session tag are declared
>   but not yet wired as an enforcement guard. Isolation relies on explicit repository
>   predicates, covered by `test_tenant_domain_isolation.py`. Add a `do_orm_execute` filter
>   or a static "unscoped query" scanner as hardening in a later pass.
> - `auth/service.py::revoke_refresh_token()` is currently unused (logout revokes all user
>   tokens via `revoke_all_user_refresh_tokens`). Remove or wire per-token logout later.
> - `conversations/service.py` allows an ADMIN to post with `sender_type=BUYER` and a null
>   `sender_id` (pre-existing pattern). Decide whether admins should spoof buyer messages.
> - `User.email` remains globally unique (Phase 1 compatibility decision). Public registration
>   therefore reveals cross-tenant email existence and blocks reusing an email across tenants;
>   moving to unique `(tenant_id, email)` requires a tenant selector on login/register/reset.
> - `frontend` bundle is ~1.5 MB (>500 kB chunk warning); route-level code-splitting is a
>   performance follow-up.
> - Browser E2E for portal flows (buyer/sales/admin) and PostgreSQL-backed CI are pending;
>   current E2E covers tenant branding only.

**Captured:** 2026-11-19
**Revision:** `9ff6d74` (`Add build spec`)
**Scope:** Read-only reconnaissance for `BUILD_SPEC.md`. No application code was changed. The pre-existing modification to `frontend/package-lock.json` was left untouched.

## 1. Verified local baseline

| Check | Result |
|---|---|
| Backend runtime | Existing `backend/.venv`: Python 3.14.4, pytest 9.1.1 |
| Backend dependencies | `python -m pip check`: no broken requirements |
| Frontend runtime | Node 22.22.2, npm 10.9.7; existing `frontend/node_modules` used |
| Development database | Existing `backend/propflow_dev.db` via SQLite configuration in `backend/.env` |
| Migration state | Current and head revision both `f7e8d9c0b1a2` |
| API | Uvicorn on `http://127.0.0.1:8000`; `GET /api/v1/health` returned 200 |
| Database readiness | `GET /api/v1/health/ready` returned 200 with database `ok` |
| Frontend | Vite 8.3.6 on `http://127.0.0.1:5173/`; HTTP 200 |
| Backend tests | **229 collected; 229 passed; 0 failed; 0 skipped** |
| Test duration | 159.00 seconds (2m38s) |
| Test warning | One `StarletteDeprecationWarning` concerning `httpx`; no test failure |

Commands used:

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests -v
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd frontend
npm run dev -- --port 5173 --strictPort
```

The first server-start attempt failed because both ports were temporarily occupied. A retry succeeded; no unrelated processes were stopped. No seeders were run against the existing development database, and no external AI calls or production PostgreSQL connection were used. The frontend HTTP smoke check does not substitute for browser E2E coverage or a production build.

### Test isolation

`backend/tests/conftest.py` forces `ENVIRONMENT=testing`, overrides `get_db`, and creates/drops in-memory SQLite tables per database-backed test. Roles are seeded only in those test databases. Groq interactions are mocked. PostgreSQL migrations/connectivity are not exercised by this suite.

## 2. Architecture and conventions

PROPFLOW is a **synchronous, single-tenant FastAPI modular monolith** with a React/TypeScript frontend.

- `backend/app/main.py`: app factory, lifespan, CORS, shared error handlers, root route, scheduler startup/shutdown.
- `backend/app/api/v1/router.py`: assembles all module routers under `/api/v1`.
- `backend/app/core/`: validated `pydantic-settings`, logging, exceptions.
- `backend/app/db/`: declarative `Base`, global SQLAlchemy engine/session factory, `get_db` dependency. SQLite uses `check_same_thread=False`; other databases use pooling and pre-ping.
- `backend/app/modules/`: domain-oriented modules. The common layering is `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.
- `backend/alembic/`: 13 linear migrations, currently ending in `f7e8d9c0b1a2`. `alembic/env.py` imports every model module explicitly.
- `frontend/src/`: portal-based React modules (`admin`, `buyer`, `sales`, `auth`) plus shared pages/components. Tailwind CSS 4 tokens are in `src/index.css`.
- Browser verification includes both legacy Puppeteer scripts in `frontend/scripts/` and Playwright specs in `frontend/tests/e2e/`.

**Important implementation detail:** `frontend/vite.config.ts` sets the development base path to `/projects/PROPFLOW/`. Both `/` and `/projects/PROPFLOW/` returned 200 in the local HTTP smoke check. Production uses `/`.

**No tenancy abstraction exists yet:** there are no tenant models, tenant JWT claims, tenant query helpers, tenant-specific settings, or tenant fixtures. Existing role/ownership and assignment restrictions are not tenant isolation. Several services perform cross-module model imports despite the older design document describing stricter service boundaries.

## 3. ORM data model — all fields

There are **20 ORM tables**. UUID primary keys are named `id` unless stated otherwise. `UUID` means SQLAlchemy `Uuid`; `datetime` columns are declared timezone-aware. Python-side default timestamps are not shown separately where `created_at`/`updated_at` are listed.

### Identity, access, and tenancy prerequisites

| Model / table | Fields |
|---|---|
| `Role` / `roles` | `id`; `name` (unique string); `description`; `created_at` |
| `User` / `users` | `id`; `full_name`; `email` (unique string); `password_hash`; `phone`; `role_id` → `roles.id` (RESTRICT); `is_active`; `is_verified`; `created_at`; `updated_at` |
| `RefreshToken` / `refresh_tokens` | `id`; `user_id` → `users.id` (CASCADE); `token_hash`; `expires_at`; `created_at`; `revoked_at` (nullable) |
| `RevokedAccessToken` / `revoked_access_tokens` | `jti` (string primary key); `user_id` → `users.id` (CASCADE); `expires_at`; `created_at` |

### Projects and facts

| Model / table | Fields |
|---|---|
| `Project` / `projects` | `id`; `name`; `slug` (unique string); `location`; `description`; `rera_number`; `status` (`DRAFT`/`ACTIVE`/`INACTIVE`); `created_by` → `users.id` (RESTRICT); `created_at`; `updated_at` |
| `ProjectFact` / `project_facts` | `id`; `project_id` → `projects.id` (RESTRICT); `category`; `question`; `answer`; `status` (`DRAFT`/`APPROVED`); `updated_by` → `users.id` (RESTRICT); `pending_category`; `pending_question`; `pending_answer`; `created_at`; `updated_at` |
| `FactVersion` / `fact_versions` | `id`; `fact_id` → `project_facts.id` (CASCADE); `previous_answer` (nullable); `new_answer`; `version_number`; `changed_by` → `users.id` (RESTRICT); `created_at` |

Fact versions record answer changes only. Unique constraint: `(fact_id, version_number)`.

### Leads and assignments

| Model / table | Fields |
|---|---|
| `Lead` / `leads` | `id`; `full_name`; `email`; `phone`; `project_id` → `projects.id` (RESTRICT); `source`; `status`; `budget_min`; `budget_max`; `preferred_configuration`; `consent_to_contact`; `opted_out`; `opted_out_at`; `opted_out_reason`; `created_at`; `updated_at` |
| `LeadAssignment` / `lead_assignments` | `id`; `lead_id` → `leads.id` (CASCADE); `executive_id` → `users.id` (RESTRICT); `assigned_by` → `users.id` (RESTRICT); `assigned_at`; `unassigned_at` (nullable) |

`Lead` does **not** have a direct `buyer_id` or stored language. Buyer ownership is currently inferred by email matching. `Lead.current_assignment` is a view-only relationship where `unassigned_at IS NULL`; an indexed partial unique constraint enforces one active assignment.

Lead source enum: `WEBSITE`, `PROPERTY_PORTAL`, `SOCIAL_MEDIA`, `HOARDING`, `REFERRAL`, `OTHER`.
Lead status enum: `NEW`, `CONTACTED`, `QUALIFIED`, `NOT_INTERESTED`, `VISIT_BOOKED`, `VISIT_CANCELLED`, `VISITED`, `CONVERTED`, `LOST`.

### Conversations and messages

| Model / table | Fields |
|---|---|
| `Conversation` / `conversations` | `id`; `lead_id` → `leads.id` (CASCADE); `project_id` → `projects.id` (RESTRICT); `buyer_id` → `users.id` (RESTRICT); `status`; `created_at`; `updated_at` |
| `Message` / `messages` | `id`; `conversation_id` → `conversations.id` (CASCADE); `sender_type`; `sender_id` → `users.id` (SET NULL); `content`; `status`; `created_at` |

Conversation status: `ACTIVE`, `CLOSED`, `ARCHIVED`. Message sender: `BUYER`, `ASSISTANT`, `SALES_EXECUTIVE`, `SYSTEM`. Message status: `SENT`, `DELIVERED`, `READ`. No persisted `language` field exists on conversations or messages.

`app/modules/messages/models.py` re-exports the models from `conversations/models.py`; it does not define another table.

### Site visits and bookings

| Model / table | Fields |
|---|---|
| `VisitSlot` / `visit_slots` | `id`; `project_id` → `projects.id` (CASCADE); `start_time`; `end_time`; `capacity`; `is_active`; `address`; `latitude`; `longitude`; `notes`; `created_at`; `updated_at` |
| `Booking` / `bookings` | `id`; `slot_id` → `visit_slots.id` (RESTRICT); `lead_id` → `leads.id` (RESTRICT); `project_id` → `projects.id` (RESTRICT); `buyer_id` → `users.id` (RESTRICT); `executive_id` → `users.id` (SET NULL); `status`; `cancellation_reason`; `cancelled_at`; `cancelled_by_id` → `users.id` (SET NULL); `notes`; `created_at`; `updated_at` |

The physical booking table is `bookings`, not `site_visit_bookings`. Booking status: `PENDING`, `CONFIRMED`, `CANCELLED`, `COMPLETED`, `NO_SHOW`. Capacity considers both pending and confirmed reservations. The PostgreSQL partial index on `(lead_id, slot_id)` excludes only cancelled bookings; SQLite does not receive that partial-index predicate in the migration/model.

### Handoffs and follow-ups

| Model / table | Fields |
|---|---|
| `Handoff` / `handoffs` | `id`; `conversation_id` → `conversations.id` (CASCADE); `lead_id` → `leads.id` (CASCADE); `project_id` → `projects.id` (CASCADE); `executive_id` → `users.id` (SET NULL); `created_by_id` → `users.id` (SET NULL); `status`; `reason`; `summary`; `resolution_notes`; `assigned_at`; `resolved_at`; `resolved_by_id` → `users.id` (SET NULL); `created_at`; `updated_at` |
| `FollowUp` / `follow_ups` | `id`; `lead_id` → `leads.id` (CASCADE); `project_id` → `projects.id` (CASCADE); `executive_id` → `users.id` (RESTRICT); `scheduled_at`; `type`; `priority`; `status`; `notes`; `next_action`; `outcome`; `outcome_notes`; `completed_at`; `created_at`; `updated_at` |

Handoff status: `PENDING`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CANCELLED`. Handoff reason: `BUYER_REQUESTED`, `FACT_UNAVAILABLE`, `AI_FALLBACK`, `COMPLEX_QUERY`, `OTHER`. Only PostgreSQL has the active-handoff partial unique index in the current model.

Follow-up type: `CALL`, `WHATSAPP`, `EMAIL`, `MEETING`, `OTHER`; priority: `LOW`, `MEDIUM`, `HIGH`; status: `PENDING`, `COMPLETED`, `CANCELLED`; outcome: `INTERESTED`, `NOT_INTERESTED`, `NO_RESPONSE`, `CALLBACK_REQUESTED`, `CONVERTED`. `category` is a computed property, not a column.

### Notifications, templates, settings, analytics, and audit

| Model / table | Fields |
|---|---|
| `Notification` / `notifications` | `id`; `user_id` → `users.id` (CASCADE); `type`; `title`; `message`; `is_read`; `read_at`; `idempotency_key` (nullable); `lead_id` → `leads.id` (SET NULL); `booking_id` → `bookings.id` (SET NULL); `handoff_id` → `handoffs.id` (SET NULL); `project_id` → `projects.id` (SET NULL); `created_at`; `updated_at` |
| `NotificationTemplate` / `notification_templates` | `id`; `name`; `type`; `channel`; `title_template`; `body_template`; `variables` (JSON list); `is_active`; `updated_by_id` → `users.id` (SET NULL); `created_at`; `updated_at` |
| `SystemSetting` / `system_settings` | `key` (string primary key); `category`; `value` (JSON object); `description`; `updated_by_id` → `users.id` (SET NULL); `updated_at` |
| `MarketingSpend` / `marketing_spends` | `id`; `project_id` → `projects.id` (CASCADE, nullable); `source`; `period_start` (date); `period_end` (date); `amount` (`Numeric(14,2)`); `notes`; `created_by_id` → `users.id` (SET NULL); `created_at`; `updated_at` |
| `AuditLog` / `audit_logs` | `id`; `action`; `actor_id` → `users.id` (SET NULL); `actor_name`; `actor_email`; `resource_type`; `resource_id`; `details` (JSON object); `created_at` |

## 4. Router and path inventory

All application paths below were enumerated from the live FastAPI route registry. Excluding documentation/OpenAPI, there are **105 method/path routes**: root, two health checks, and **102 API v1 routes**. Access labels are the current boundaries to preserve and extend with tenant checks; detailed business transitions remain in services.

| Area | Method and path (prefixed by `/api/v1`) | Current access / purpose |
|---|---|---|
| Health | `GET /health`; `GET /health/ready` | Public liveness / database readiness |
| Auth | `POST /auth/register` | Public BUYER registration |
| Auth | `POST /auth/login` | Public; returns access and opaque refresh token |
| Auth | `GET /auth/me` | Authenticated current profile |
| Auth | `POST /auth/refresh` | Public token rotation; returns new access token |
| Auth | `POST /auth/logout`; `POST /auth/revoke-all` | Authenticated refresh-token revocation |
| Auth | `POST /auth/reset-password` | Public direct reset by email/new password; uniform response |
| Users | `GET, POST /users`; `GET /users/metrics` | ADMIN |
| Users | `GET, PATCH /users/{user_id}` | Self or ADMIN; role changes are restricted |
| Users | `PATCH /users/{user_id}/status` | ADMIN |
| Projects | `POST /projects`; `GET /projects/metrics` | ADMIN |
| Projects | `GET /projects` | Authenticated; non-admins see active projects |
| Projects | `GET, PATCH, DELETE /projects/{project_id}` | Authenticated read; ADMIN write; delete refuses dependent records |
| Facts | `POST, GET /projects/{project_id}/facts` | ADMIN create; authenticated role/status-aware read |
| Facts | `GET, PATCH, DELETE /facts/{fact_id}` | Authenticated role/status-aware read; ADMIN write |
| Facts | `POST /facts/{fact_id}/approve`; `POST /facts/{fact_id}/reject`; `GET /facts/{fact_id}/versions` | ADMIN |
| Leads | `POST /leads` | **Public** intake; active project; per-process IP rate limit |
| Leads | `GET /leads`; `GET /leads/duplicates/check` | ADMIN/assigned SALES_EXECUTIVE; duplicate check is ADMIN-only |
| Leads | `GET, PATCH /leads/{lead_id}`; `PATCH /leads/{lead_id}/status` | ADMIN or current assigned SALES_EXECUTIVE |
| Leads | `POST /leads/{lead_id}/assign`; `GET /leads/{lead_id}/assignments` | ADMIN assignment; ADMIN/assigned executive history |
| Leads | `GET /leads/mine` | Authenticated buyer leads matched by email |
| Leads | `POST /leads/{lead_id}/opt-out`; `GET /leads/opted-out` | Authenticated ownership/role check; latter intended for ADMIN |
| Conversations | `POST /conversations`; `POST /conversations/start` | Authenticated; role/ownership checks in service |
| Conversations | `GET /conversations`; `GET /conversations/{conversation_id}` | Buyer ownership, executive assignment/active project, or ADMIN |
| Conversations | `PATCH /conversations/{conversation_id}/status` | Authorized participant; ADMIN required for archive |
| Messages | `POST, GET /conversations/{conversation_id}/messages` | Authorized conversation access and sender restrictions |
| Messages | `GET /messages/{message_id}` | Authorized through parent conversation |
| Assistant | `POST /conversations/{conversation_id}/chat`; `POST /assistant/chat` | Authenticated buyer conversation boundary; Groq client injected |
| Slots | `POST /slots`; `PATCH, DELETE /slots/{slot_id}` | Authenticated; service enforces ADMIN. DELETE soft-deactivates |
| Slots | `GET /slots/available`; `GET /slots`; `GET /slots/{slot_id}` | Authenticated; service controls role/project visibility |
| Bookings | `POST /bookings` | Authenticated buyer/staff boundary; consent and capacity enforced |
| Bookings | `GET /bookings`; `GET /bookings/{booking_id}` | Buyer/executive/ADMIN scoping |
| Bookings | `GET /bookings/metrics` | ADMIN via service |
| Bookings | `POST /bookings/schedule-custom` | Authenticated; service enforces ADMIN/SALES_EXECUTIVE |
| Bookings | `POST /bookings/{booking_id}/cancel`; `POST /bookings/{booking_id}/reschedule` | Authorized participant/admin |
| Bookings | `PATCH /bookings/{booking_id}/status` | ADMIN/assigned executive via service |
| Follow-ups | `POST /follow-ups` | Authenticated; assigned executive or ADMIN |
| Follow-ups | `GET /follow-ups`; `GET /follow-ups/metrics` | Role-scoped listing/metrics |
| Follow-ups | `GET, PATCH /follow-ups/{follow_up_id}` | Authorized executive or ADMIN |
| Follow-ups | `POST /follow-ups/{follow_up_id}/reschedule`; `/complete`; `/cancel` | Authorized executive or ADMIN |
| Handoffs | `POST /handoffs`; `POST /conversations/{conversation_id}/handoff` | Authorized buyer/staff boundary |
| Handoffs | `GET /handoffs`; `GET /handoffs/{handoff_id}` | Buyer ownership, assigned executive, or ADMIN |
| Handoffs | `POST /handoffs/{handoff_id}/assign`; `PATCH /handoffs/{handoff_id}/status` | Service-level role/assignment checks |
| Notifications | `GET /notifications`; `GET /notifications/unread-count` | Current user's own records |
| Notifications | `GET /notifications/{notification_id}`; `PATCH /notifications/{notification_id}/read`; `POST /notifications/mark-all-read` | Current user's own records |
| Notifications | `POST /notifications/reminders/trigger` | ADMIN manual scan |
| Dashboard | `GET /dashboard/summary`; `GET /dashboard/trends` | ADMIN or role-scoped SALES_EXECUTIVE |
| Dashboard | `GET /dashboard/sources`; `GET /dashboard/executives` | ADMIN |
| Marketing | `POST, GET /dashboard/marketing-spend` | ADMIN |
| Marketing | `GET, PATCH, DELETE /dashboard/marketing-spend/{spend_id}` | ADMIN |
| Settings | `GET /settings`; `PATCH /settings/reminders`; `PATCH /settings/ai-assistant`; `PATCH /settings/languages`; `PATCH /settings/lead-assignment` | ADMIN router guard |
| Settings | `POST /settings/reminders/trigger` | ADMIN manual scan |
| Templates | `GET /settings/templates`; `GET, PATCH /settings/templates/{template_id}`; `POST /settings/templates/{template_id}/reset` | ADMIN |
| Audit | `GET /settings/audit-logs` | ADMIN; filterable/paginated |
| Broadcast | `GET /settings/notifications`; `POST /settings/notifications/broadcast` | ADMIN platform-wide view/broadcast |
| Other | `GET /` (no v1 prefix); `/docs`; `/openapi.json` | Public application info/documentation |

## 5. Authentication and token lifecycle

1. Public registration always creates a BUYER account. Admin-created users can have one of the three fixed roles; no public admin registration exists.
2. Passwords use Argon2 with a 12–128 character strength policy. Email addresses are normalized; login failures are intentionally non-enumerating.
3. `login_user` issues a JWT access token and opaque refresh token. Refresh tokens are stored only as Argon2 hashes and expire after seven days by default.
4. JWT access claims: `sub` (user UUID), `role`, `type=access`, `jti`, `iat`, `exp`, `iss`, `aud`. **No `tenant_id` claim.**
5. `get_current_user` checks the bearer JWT signature, issuer, audience, expiry, required claims/type, JTI revocation, user existence, and `is_active`. The user's current role is read from the database for authorization.
6. `/auth/refresh` verifies and revokes the matched refresh token, then issues a replacement refresh token and a new access token. The refresh response does not return the rotated replacement token, which needs a deliberate compatibility decision before changing this contract.
7. Logout/revoke-all revoke the user's active refresh tokens. Although `RevokedAccessToken` and its dependency check exist, the current logout route does not record the current JWT JTI; its docstring says the access token remains usable until expiry.
8. A public direct password-reset endpoint updates the password without a reset token. This is pre-existing behavior, not a Phase 0 change; preserve its endpoint contract unless separately authorized to alter it.

## 6. Scheduler and background work

There is one application scheduler: the global `ReminderScheduler` in `backend/app/modules/notifications/scheduler.py`.

- App lifespan starts it outside testing when `REMINDER_SCHEDULER_ENABLED=true` (default); shutdown cancels the task and disposes the database engine.
- An asyncio loop calls synchronous work via `asyncio.to_thread`, then sleeps for `REMINDER_POLL_INTERVAL_SECONDS` (default 60 seconds).
- Each scan opens its own `SessionLocal`, loads all future `CONFIRMED` bookings, and creates buyer and assigned-executive reminders at the 24-hour and 2-hour thresholds.
- Buyer reminders require contact consent and no opt-out. Executive reminders do not require buyer consent.
- Idempotency keys follow `reminder_{24h|2h}_{booking_id}_{recipient_id}`. Both an in-memory lookup and a notification idempotency uniqueness constraint are used.
- No durable job queue, scheduler lease, or distributed locking exists. The 24-hour condition also remains true inside the 2-hour window; the distinct keys intentionally generate both notifications.
- Manual scan endpoints: `/notifications/reminders/trigger` and `/settings/reminders/trigger` (both ADMIN).
- No IMAP polling, outbound-provider queue, or other scheduler exists.

## 7. Notification and settings structure

`app/modules/notifications/` contains:

- `models.py`: in-app notification, type enum, idempotency/domain links.
- `repository.py`: notification reads/writes and future confirmed-booking scan.
- `service.py`: creation and event-specific helpers for lead assignment, handoff assignment/status, booking confirmation/cancellation; notification listing/read APIs.
- `scheduler.py`: direct reminder generation; **not** a general delayed-message scheduler.
- `router.py`, `schemas.py`, `exceptions.py`: current-user notification API and admin reminder trigger.

`app/modules/settings/` separately owns `SystemSetting`, `NotificationTemplate`, and `AuditLog` plus admin APIs. Defaults are seeded by `ensure_defaults_seeded`: reminders, AI assistant, languages (English/Hindi/Gujarati enabled, Marathi disabled), and assignment rules.

Templates use placeholders such as `{project_name}`, `{slot_time}`, and `{executive_name}`, but there is no general runtime rendering engine. Runtime notification/reminder messages are currently hardcoded in `notifications/service.py` and `scheduler.py`. Notification types include `VISIT_REMINDER_24H/2H`, booking events, lead/handoff events, and `SYSTEM`. Follow-ups store channel choices but do not deliver messages. There is no WhatsApp/SMS/email provider adapter or delivery-status ledger; SMTP settings present in `.env.example` are not consumed by `Settings`.

## 8. Seeders and demo scripts

| Script | Purpose / tenancy implications |
|---|---|
| `scripts/seed_roles.py` | Idempotently seeds the three global roles. |
| `scripts/create_admin.py` | Trusted interactive/environment-driven first-admin provisioning. |
| `scripts/setup_dev_database.py` | Calls `Base.metadata.create_all`; seeds roles, baseline accounts, Bangalore/Hyderabad/Gurgaon projects/facts, sample leads/slots/bookings/spend, and settings/templates. Missing account passwords are securely generated. |
| `scripts/prepare_demo_environment.py` | Creates the larger Hyderabad demo, described as 45 buyers, 3 projects, 125 leads, conversations, visits, follow-ups, handoffs, notifications, audit and spend. Uses a fixed November 7, 2026 anchor. `--reset` deletes matching demo data. Re-running also resets core demo-account password hashes. Calls `create_all` directly. Not executed during Phase 0. |
| `scripts/seed_follow_ups.py` | Adds follow-ups against existing leads/users. |
| `scripts/setup_test_buyer_portal.py` | Manual buyer-portal fixture data setup, not the pytest fixture mechanism. |

Seeders construct domain records directly, so Phase 1 must supply tenant IDs consistently in both initial data and reset/lookup behavior. Global settings/templates and global unique email/slug constraints require explicit redesign for multi-tenancy.

## 9. Conflicts, surprises, and proposed adaptations

These are planning inputs only. **Phase 1 must not begin until these adaptations are accepted.**

### A. Multi-tenancy scope (blocks Phase 1)

**Observed:** The spec's minimum list omits existing tenant-relevant tables: `fact_versions`, `lead_assignments`, `handoffs`, `notification_templates`, `system_settings`, `refresh_tokens`, and `revoked_access_tokens`. It also names `site_visit_bookings`, whereas the actual table is `bookings`.

**Proposed adaptation:** Treat `tenants` as the isolation root and add `tenant_id` to **all user/business/security-token tables**, not merely the listed minimum. Include assignment/history rows so a history endpoint cannot leak another tenant through a parent join. Add tenant-aware parent-child relationship validation and enforce same-tenant writes in services. Global `roles` may remain a fixed catalog. Replace or scope global uniqueness of `users.email`, `projects.slug`, `system_settings.key`, notification idempotency keys, project slot times, and similar tenant-local resources.

### B. Unauthenticated lead intake (blocks Phase 1)

**Observed:** `POST /api/v1/leads` has no JWT; project selection and an IP rate limiter are its public boundary. Requiring tenant context on every authenticated route does not resolve tenant assignment here.

**Proposed adaptation:** Preserve this public endpoint and its request/response behavior. Resolve an explicit, validated tenant/project mapping before creating a lead; do not trust a client-supplied internal tenant ID without validating that the target project belongs to it. Scope duplicate detection, source attribution, and notifications to that tenant. Do not expose cross-tenant duplicate information publicly.

### C. Authentication is more than a single access token (blocks Phase 1)

**Observed:** Login issues JWT access plus opaque refresh tokens. Refresh-token rotation, revocation, active-user checks, and public buyer registration already exist. The backend's refresh response omits the rotated refresh token, so frontend storage/refresh behavior must be checked before any contract change.

**Proposed adaptation:** Put `tenant_id` in every newly issued access token, including refresh. Scope tenant status checks to login, refresh, and authenticated requests. Rotate/return refresh credentials consistently without silently breaking existing clients. Reuse the existing JWT decoder and authorization guards rather than adding a parallel auth path. Tenant suspension needs an explicit rule for public registration/intake and refresh tokens.

### D. Existing notification/template/reminder split (Phase 3 adaptation)

**Observed:** In-app notifications and their service-generated text are separate from admin-managed `notification_templates`. The scheduler creates immediate in-app records, not delayed provider jobs. No lead/conversation/message language field exists.

**Proposed adaptation:** Introduce the new messaging module/delivery ledger rather than overloading the `notifications` table. Reuse or migrate template management deliberately, preserving existing settings APIs where required. Add delayed delivery rows consumed by a tenant-scoped scheduler path; do not use the existing reminder function as a generic queue without redesign. For language, persist a validated detected language or derive it deterministically from recent messages, with `en` fallback; avoid an unreliable blocking LLM call in the lead-creation transaction.

### E. Documentation is stale and internally inconsistent (no baseline blocker)

| Topic | Documentation | Current implementation / verification |
|---|---|---|
| Test count | `README.md` and `BUILD_SPEC.md`: 224; `docs/TECHNICAL_DESIGN.md`: 229 | Actual: 229 passed |
| Backend Python | Prerequisites: 3.12/3.13; spec says “FastAPI 3.12” | Actual venv: Python 3.14.4; suite passes on it |
| SQLite default | Root README/deployment show `sqlite:///./propflow_dev.db` | `backend/.env.example` defaults to PostgreSQL; actual `.env` uses SQLite |
| Auth hashing | Design document says bcrypt | Code uses Argon2 |
| Lead ownership | Design ER links users directly to leads | `Lead` has no `buyer_id`; conversations/bookings do. Buyer lead listing matches email |
| Message language | Design lists `messages.language` | No such field |
| Booking table/status | Design describes `bookings` with `SCHEDULED`; build spec says `site_visit_bookings` | Actual `bookings`, defaults `CONFIRMED`; also `PENDING` |
| Frontend verification | README says Puppeteer; design/testing says Playwright | Both are present |
| Charts | Design mentions Recharts | Current frontend uses custom SVG charts; no Recharts dependency |
| Environment coverage | Design/deployment list settings not in `.env.example` | Scheduler/Groq tuning settings exist in code but are missing from the template; SMTP template values are not code settings |
| Deletion/auth limitations | Older sections describe unsupported features | Projects/facts hard-delete and refresh revocation now exist |
| `backend/README.md` | Quick start hardcodes `E:\PROPFLOW\backend` | Current checkout is elsewhere; command is not portable |

### F. Existing baseline quality/security concerns (not changed in Phase 0)

- Public password reset requires only email and a new password; no proof of ownership is required. This is a high-priority pre-existing security concern for a multi-tenant service.
- Refresh-token lookup scans stored tokens, potentially performing many Argon2 verifications; logout does not revoke the presented access-token JTI.
- Some PostgreSQL partial unique indexes lack SQLite equivalents, so green SQLite tests do not prove identical constraint behavior on PostgreSQL.
- Broad admin notification/settings APIs and global unique resource keys need tenant scoping, not just role preservation.
- Existing tests cover current behavior but not the required two-tenant adversarial matrix or PostgreSQL production behavior.

## 10. Requested frontend/font direction

The user requested a multi-tenant module and **no serif fonts anywhere in the project UI**.

Current state: `frontend/src/index.css` sets body text to Manrope and `--font-display` to DM Serif Display with Georgia/serif fallbacks. `font-display` and the `.serif` class are used across the landing page and portals, and the DM Serif Display package is loaded.

**Required adaptation:** Make font replacement part of Phase 2 branding. Remove the DM Serif Display import/dependency, map all display typography to an explicit sans-serif stack, replace/retire serif usages without losing heading hierarchy, and search the final source for `font-display`, `.serif`, `font-family: ... serif`, and DM Serif references. Verify both typecheck/build and rendered pages across buyer, sales, admin, and auth views. This is a separate frontend deliverable; no font code was changed during Phase 0.

## 11. Phase 0 result

- [x] Read root README, `docs/`, and build spec.
- [x] Established existing local SQLite backend + Vite frontend.
- [x] Ran the complete backend pytest suite: **229/229 passed**.
- [x] Documented all models/fields, all application routes, auth/token flow, scheduler, notification structure, and seeders.
- [x] Identified conflicts and proposed adaptations before implementation.
- [ ] No commit created; the user did not request one.
