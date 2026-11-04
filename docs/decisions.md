# Architecture Decision Records

Short, dated records of design decisions and their rationale. Kept proportionate to an
MVP: each entry states the decision, the context, and why the chosen option was simplest
among reasonable alternatives.

---

## ADR-001 — Core stack & solution layout
**Date:** 2026-11-04 · **Status:** ~~Accepted~~ **Superseded by [ADR-004](#adr-004--pivot-to-a-python--fastapi-backend)** (2026-11-04)

**Context.** Required stack was ASP.NET Core Web API (.NET 8) + Angular, cleanly layered with DI.

**Decision (original).** Four projects: `Teleradio.Domain`, `Teleradio.Application`,
`Teleradio.Infrastructure`, `Teleradio.Api`; dependencies pointing inward; no MediatR/CQRS.

**Status note.** The foundation (solution, layered projects, EF Core `DbContext`, health
endpoint, Docker build, passing tests) was built and verified green, then **replaced** by a
Python/FastAPI backend — see ADR-004. The clean-layering principle carries over to the new
stack; only the implementation technology changed.

---

## ADR-002 — Database: PostgreSQL + migrations
**Date:** 2026-11-04 · **Status:** Accepted (updated by ADR-004 to SQLAlchemy/Alembic)

**Context.** Need a relational store with migrations; prompt defaults to PostgreSQL.

**Decision.** PostgreSQL 16. Schema evolves through migrations applied automatically on
backend startup (short retry loop to tolerate container start order). Under the Python stack
(ADR-004) this is **async SQLAlchemy 2.0 + Alembic**, using **JSONB** columns for
FHIR-leaning/extensible record fields.

**Why.** PostgreSQL is free, well-supported, and the prompt default. Auto-migrate keeps
`docker-compose up` a single step for the MVP; a manual migration gate can be added later.

---

## ADR-003 — Containerization: Docker Compose for db + backend + frontend
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** Deliverable must run with a single `docker-compose up`.

**Decision.** One compose file with three services: `db` (postgres), `backend` (multi-stage
.NET build → aspnet runtime, non-root user), `frontend` (Angular built and served by nginx).
Secrets and connection details come from a `.env` file (see `.env.example`); none are
committed.

**Why.** Compose is the simplest orchestration that satisfies the single-command
requirement and mirrors how the pieces deploy together.

---

## ADR-004 — Pivot to a Python / FastAPI backend
**Date:** 2026-11-04 · **Status:** Accepted · **Supersedes:** ADR-001

**Context.** The organisation is consolidating infrastructure around Python to natively
support future machine-learning and data-science workloads (e.g. PyTorch, scikit-learn) on
the same imaging data the platform already handles. Maintaining a separate .NET service would
split the stack and force a data/serving boundary between the application and any future
model training or inference.

**Decision.** Replace the ASP.NET Core backend with Python 3.12 + **FastAPI/Uvicorn**,
**Pydantic v2**, **async SQLAlchemy 2.0 + Alembic** on PostgreSQL (JSONB for FHIR-leaning
records), and **pydicom + pylibjpeg** for DICOM processing. The Angular frontend is retained;
nginx reverse-proxies `/api` to Uvicorn on port 8000. The strict Clean Architecture layering
is preserved (`api` → `services` → `domain`; `infrastructure` implements the ports).

CPU-heavy DICOM work (pixel decoding, preview generation) is kept off the ASGI event loop:
the synchronous pipeline in `services/dicom.py` is invoked via `asyncio.to_thread` /
FastAPI `BackgroundTasks`, so chunked uploads and other requests stay responsive.

**Why.**
- **One language end-to-end for data + ML.** FastAPI serves the API while the same process
  space and libraries (NumPy, pydicom, and later PyTorch/scikit-learn) operate directly on
  pixel data — no cross-service hop or re-implementation.
- **Robust async I/O.** FastAPI/ASGI with async SQLAlchemy handles concurrent, slow,
  low-bandwidth uploads well; BackgroundTasks isolate CPU-bound decoding from request latency.
- **pydicom ecosystem.** Mature, Pythonic DICOM parsing with pluggable JPEG codecs
  (pylibjpeg), aligning imaging I/O with the future ML tooling.

**Trade-off.** The previously verified .NET foundation is discarded. Accepted deliberately
to avoid a polyglot backend and to position imaging data for in-process ML later.

---

## ADR-005 — Authentication & authorization approach
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** The MVP needs three roles (`Admin`, `ReferringClinician`, `Radiologist`),
stateless auth that works across the Angular SPA and the API, and password storage that is
safe by default. No external identity provider is in scope.

**Decision.**
- **Stateless JWT** (HS256, python-jose). The login endpoint verifies credentials and issues
  a signed access token carrying `sub` (user id), `roles`, issuer and audience; `/api/auth/refresh`
  re-issues a token for a still-valid session. The signing key comes from `JWT_KEY` (env).
- **bcrypt password hashing** via passlib. `bcrypt` is pinned to `4.0.1` (passlib 1.7.4 is
  incompatible with bcrypt ≥ 4.1).
- **Single role per user** stored as a portable (`native_enum=False`) enum column. The token
  still carries `roles` as a list, so multi-role is a non-breaking future change.
- **Authorization** via FastAPI dependencies: `get_current_user` (decodes the bearer token,
  loads an active user) and a `require_roles(...)` factory applied per endpoint.
- **Frontend**: an HTTP interceptor attaches the bearer token and redirects to `/login` on
  401; a route guard blocks unauthenticated navigation; the token is kept in `localStorage`.

**Why.** JWT keeps the API stateless (no server session store) and fits the SPA + reverse-proxy
topology. bcrypt is the well-understood default for password hashing. A per-endpoint role
dependency is explicit and readable, and keeps every route protected by default without a
global policy engine the MVP does not need.

**Trade-off.** `localStorage` tokens are simpler than httpOnly cookies but exposed to XSS;
acceptable for the MVP and revisited under production hardening. Logout is client-side only
(no server token revocation list) — adequate for short-lived tokens at this stage.

---

## ADR-006 — FHIR-leaning data model (relational + JSONB)
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** The MVP needs patient and encounter records that follow EMR practice and stay
extensible toward HL7 FHIR, without implementing the full standard now.

**Decision.**
- Model core, queryable attributes as **typed relational columns** named after FHIR fields:
  `Patient` (MRN identifier, `family_name`/`given_name`, `birth_date`, `sex` = FHIR
  administrative gender, consent acknowledgment + timestamp) and `Encounter`
  (`status` from a simplified FHIR Encounter status, `reason`, `occurred_at`, link to the
  referring clinician and patient).
- Add an **`extra` JSONB column** on each entity for extensible/less-structured attributes
  (addresses, secondary identifiers, future FHIR extensions) without schema churn.
- Enforce **consent acknowledgment at creation** (schema validation rejects an
  unacknowledged patient; the server stamps `consent_acknowledged_at`).
- `JsonB` is a portable column type: JSONB on PostgreSQL, generic JSON on SQLite (tests).

**Why.** Typed columns keep the hot query paths (lookups by MRN, worklist joins) indexable
and validated, while JSONB preserves FHIR-style extensibility cheaply. This is the common
"relational core + JSON extension" pattern and avoids both a full FHIR server and an
all-JSON schema that would be hard to query and validate at MVP scale.

**Trade-off.** Not FHIR-conformant (no FHIR resources/REST, no terminology bindings); the
field naming and JSONB escape hatch keep a future migration toward FHIR tractable.

---

## ADR-007 — Study storage abstraction (filesystem, S3-ready)
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** Study files must be stored outside the database, with a path to S3-compatible
object storage later.

**Decision.** A `StudyStorage` protocol (`save`, `append_bytes`, `open`, `size`, `delete`,
`full_path`) with a `LocalFilesystemStorage` implementation rooted at `STORAGE_ROOT_PATH`
(a Docker volume). Services depend on the protocol, not the implementation; path traversal
outside the root is rejected. Keys are relative (`studies/<id>/original.dcm`,
`studies/<id>/preview.jpg`, `_uploads/<id>`).

**Why.** The protocol keeps a future S3 adapter a drop-in change. Filesystem is the simplest
backend that meets the MVP and runs with zero extra infrastructure.

---

## ADR-008 — DICOM handling + async preview generation
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** Uploads must be validated as DICOM, have metadata extracted (modality, study
date, body part, accession), and get a lightweight preview for low-bandwidth remote viewing —
without blocking the ASGI server.

**Decision.** `pydicom` + `pylibjpeg` parse headers and decode pixels; previews are VOI-LUT
windowed, normalized to 8-bit, downsized, and saved as progressive JPEG (Pillow). Non-DICOM
images (PNG/JPEG) are validated with Pillow and get a JPEG preview too. Processing is
scheduled on FastAPI `BackgroundTasks`, and the CPU-heavy decode runs via
`asyncio.to_thread`. The study moves `Processing → Pending` on success, or `Failed` with a
recorded error, so a bad file never blocks the queue.

**Why.** Keeps the event loop responsive during concurrent slow uploads; compressed previews
suit low bandwidth; failures are isolated and observable.

---

## ADR-009 — Chunked/resumable upload for low bandwidth
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** The target environment has intermittent, low-bandwidth connectivity; a single
large multipart POST that fails near the end wastes scarce bandwidth.

**Decision.** A three-step protocol: `POST /api/studies/uploads` opens a session (declaring
filename + total size), `PUT /api/studies/uploads/{id}?offset=N` appends a chunk, and
`POST .../complete` validates and finalizes. The server tracks `received_bytes`; a client
that disconnects queries the session and **resumes from the reported offset**. Mismatched
offsets return 409 with the expected offset; size/type/DICOM validity are enforced at
append and completion. Per-chunk and total size caps are configurable. nginx is configured
with `proxy_request_buffering off` and no body-size cap for these routes.

**Why.** Resumability turns a dropped connection into a cheap retry of one chunk rather than
the whole file — the decisive property for this market. The explicit session model is
simpler and more debuggable than tus/multipart libraries at MVP scale, while remaining
compatible with a move to S3 multipart later.

---

## ADR-010 — In-browser DICOM viewer (cornerstone)
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** Radiologists need to open a study full-size and read it in the browser (zoom,
pan, window/level), per the chosen "embed OHIF/cornerstone" direction.

**Decision.** Embed the **cornerstone** stack (`cornerstone-core`,
`cornerstone-wado-image-loader`, `dicom-parser`) rather than the full OHIF application. The
backend serves the original object at `GET /api/studies/{id}/file`; the Angular viewer fetches
it (auth via the HTTP interceptor), hands the bytes to the wado-uri file manager, and renders
into an enabled element with Window/Level, Pan, and Zoom implemented directly on the
cornerstone viewport (no cornerstone-tools dependency). The viewer route is **lazy-loaded** so
cornerstone (~1.5 MB) stays out of the initial bundle. Web workers are disabled, so no extra
codec/worker assets are served. Non-DICOM images are shown directly.

**Why.** cornerstone gives real DICOM rendering with far less weight and configuration than a
full OHIF deployment — right-sized for one viewer screen at MVP. Serving the original file
(rather than standing up full DICOMweb/WADO-RS) is the simplest retrieval that feeds the
viewer; a DICOMweb endpoint can be added later without changing the client contract much.

**Trade-off.** With web workers off, **compressed transfer syntaxes** (e.g. JPEG2000) that
need codec wasm are not yet supported — uncompressed DICOM (what the pipeline accepts/produces)
renders today; codec support is a follow-up. Multi-frame/series navigation and measurement
tools are deferred.

---

## ADR-011 — Report model & delivery approach
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** Radiologists must produce a structured report (findings + impression + status)
bound to a study/patient, and the referring clinician must be able to view and print it.
A decision is needed on *how the report is delivered back* to the referring site.

**Decision.**
- **One structured report per study**, with distinct `findings` and `impression` fields and a
  `Draft → Final` status. Only the authoring radiologist/admin can edit; **finalizing locks
  the report** (edits return 409) and transitions the study to `Reported`. Drafting moves the
  study to `In Review`.
- **Delivery is in-platform**: the report is stored against the study/patient and surfaced to
  the referring clinician through the same application (read-only), with a **server-rendered
  PDF** (`GET /api/reports/{id}/pdf`) for viewing, printing, and local archiving. No email or
  external transport in the MVP.

**Why (literature & common practice).** Teleradiology guidance — notably the ACR–AAPM
practice parameters for teleradiology and for the *communication of diagnostic imaging
findings* — treats the report as the primary, auditable work product and encourages
**structured reporting** (also promoted by RSNA) with a clear preliminary-vs-final
distinction. Common teleradiology practice is to deliver the finalized report through the
platform/RIS, with a portable document (PDF) the referrer can view and print; a locked final
report preserves the integrity of the medical record. These parameters also require that
**urgent/critical or unexpected findings** be communicated directly (phone/non-routine
channel) in addition to the report — explicitly **deferred** here and noted below.

**Trade-off / deferred.** No addendum workflow after finalize (only create/lock for now); no
critical-results direct-notification channel; no digital signature or RIS/HL7 push. The
status model and PDF leave room to add these without reworking the data model.

---

## ADR-012 — Audit trail design
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** The MVP must record *who accessed or changed each patient, study, and report,
with timestamps*, queryable by an administrator. A decision is needed on the audit data
model, how events are captured without coupling to every service, and how recording failures
are handled.

**Decision.**
- **A single append-only `audit_events` table** (migration `0005`) modeled loosely on the
  FHIR *AuditEvent* resource: `action` (login/view/create/update/finalize/download),
  `entity_type` (session/patient/study/report) + `entity_id`, the actor (`actor_id` FK with
  `ON DELETE SET NULL`), a **denormalized `actor_email`/`actor_role` snapshot** so the trail
  survives user deletion, source `ip_address`, an optional JSONB `detail`, and the base
  `created_at` as the event time. Indexed on actor, entity type, entity id, and time.
- **Capture at the API boundary.** Events are recorded in the routers, where the authenticated
  user and request (IP) are available, after the primary action succeeds — not inside domain
  services (which stay persistence-agnostic). Instrumented flows: login; patient
  view/create/update; study upload/view/file-download; report create/finalize/update and PDF
  download.
- **Best-effort, non-blocking.** `audit.record(...)` catches and rolls back its own errors so
  an audit-write failure can never break the clinical action it accompanies.
- **Admin-only query.** `GET /api/audit` (role `Admin`) returns events newest-first with
  filters (actor, action, entity type/id, time window) and pagination; an Angular admin
  audit-log view consumes it.

**Why.** Access logging of PHI is a baseline expectation for medical systems (and a
prerequisite for the deferred HIPAA/local-regulation work); the ACR teleradiology practice
parameters likewise treat auditability of the report and its handling as part of the record.
An append-only, denormalized log keeps the trail intact and independent of mutable account
state, and recording at the boundary keeps instrumentation in one layer.

**Trade-off / deferred.** Boundary capture means only actions that reach an instrumented
endpoint are logged (not, e.g., direct DB edits or background-task internals); failed/denied
attempts (401/403) and failed logins are not yet recorded; no tamper-evidence (hash chaining),
retention policy, or export. The schema (action/entity enums + JSONB detail) extends to these
without a rework.

---

## ADR-013 — Testing strategy
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** The MVP needs confidence that each feature works and keeps working, without a
heavy test-infrastructure burden and without a local toolchain (all work runs through
Docker). A decision is needed on how tests exercise the async stack and the database.

**Decision.**
- **Pyramid, API-centric.** Unit tests cover pure logic (security primitives, the DICOM
  pipeline). The bulk are integration tests that drive the real FastAPI app through
  `httpx.ASGITransport` — no network, full routing/validation/auth — one module per surface
  (auth, patients/encounters, studies, reports, audit). One **end-to-end smoke test**
  (`test_e2e.py`) chains the whole flow: upload → background processing → review → report →
  PDF → audit.
- **In-memory SQLite for tests**, Postgres in production. Models use SQLAlchemy's portable
  `Uuid`/`JSON`-with-`JSONB`-variant types so the same schema runs on both. The test engine
  is a single shared in-memory connection (`StaticPool`), created via
  `Base.metadata.create_all` — so tests do not run Alembic and need no database container.
- **Background tasks run in tests.** `app.state.session_factory` is overridden to the test
  session factory, so `BackgroundTasks` (metadata + preview extraction) execute against the
  same in-memory DB and can be asserted on.
- **Docker-only runs.** Tests run inside the backend image (`requirements-dev.txt` layered
  on at run time), matching the no-local-toolchain constraint.

**Why.** ASGI-transport integration tests give high coverage per test at low cost and catch
wiring/auth regressions that unit tests miss; SQLite-in-memory keeps the suite fast and
container-free while the portable types preserve Postgres fidelity for the parts that matter.

**Trade-off / deferred.** SQLite does not exercise Postgres-specific behavior (JSONB operators,
true enum/constraint semantics, concurrency) or the Alembic migrations themselves — those are
validated by the live `docker compose up` boot (migrations run on real Postgres) rather than in
the unit suite. No load/performance tests; no frontend unit tests (the Angular build is the
current gate).

---

## ADR-014 — Security hardening pass
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** A senior review flagged several latent security issues in the MVP:
a committed default JWT key that silently applies if unset, API docs published by
default, credentialed CORS that isn't needed, a path-traversal guard using a weak
string prefix, and unbounded client JSONB.

**Decision.**
- **Fail-fast config** (`validate_security`, run at startup): outside development,
  refuse to boot if `JWT_KEY` is the known default or shorter than 32 chars. This
  turns a silent catastrophe (forgeable admin tokens) into a loud startup error.
- **API docs off by default** (`swagger_enabled=False`); dev enables them explicitly.
- **CORS `allow_credentials=False`** — auth is Bearer-token, not cookies.
- **Path-traversal guard uses `Path.is_relative_to`** (exact ancestor check) instead
  of a string prefix that treated a sibling like `<root>-evil` as inside the root.
- **`extra` JSONB capped** at 16 KiB per record (shared `bounded_extra` validator).

**Trade-off / deferred.** No token revocation/blocklist (logout stays client-side;
tokens live until expiry), no secrets manager, no WAF/security headers/TLS — those
remain production-hosting concerns.

---

## ADR-015 — Organization-scoped object-level access control
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** Reads were gated only by authentication, so any authenticated user could
fetch any patient, study, report, image, or PDF by id (an IDOR / broken-access-control
flaw). For a platform serving multiple referring sites with PHI, access must be scoped
to who may see a record, not merely whether the caller is logged in.

**Decision.**
- Introduce an **`Organization`** (referring site). **`ReferringClinician`s belong to one
  organization and see only that site's** patients, encounters, studies, and reports;
  **`Radiologist`s and `Admin`s are cross-site** (the remote readers serve every site).
- Routers derive an **`AccessScope`** from the current user and pass it to services, which
  (a) filter list queries by the patient's `organization_id` and (b) authorize single-record
  reads. A denied single-record read returns **404, not 403**, so record existence cannot be
  probed across sites.
- `organization_id` is denormalized onto `Patient` (studies/reports scope through their
  patient); users carry `organization_id` (null = cross-site).

**Why.** Per-tenant data isolation is a baseline expectation for medical systems and a
prerequisite for the deferred HIPAA/local-regulation work; the cross-site radiologist model
matches how teleradiology actually operates. Scoping in the service layer (not scattered in
routers) keeps the policy in one place with the queries it constrains.

**Trade-off / deferred.** Coarse-grained (org-level, not per-encounter assignment or
per-radiologist worklists); no cross-org sharing/referral workflow; admins are fully
cross-site. The `AccessScope` abstraction leaves room to refine to assignment-based access
later without touching routers.

---

## ADR-016 — Audit write strategy (synchronous vs. background)
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** Audit logging commits a row inside request handlers. Doing it synchronously on
every read (study view, file/PDF download) turns read-heavy endpoints into writes on the hot
path; doing it asynchronously everywhere risks losing security-relevant events on a crash.

**Decision.** Split by event criticality. **Security-relevant writes** (login, record
create/update, report finalize) are recorded **synchronously** so they are never lost.
**Read-path events** (view, download) are recorded **off the response path** via
`BackgroundTasks` on a fresh session, keeping request latency low; a lost view event on a hard
crash is acceptable. A shared request-scoped `Auditor` dependency exposes `log` (sync) and
`log_async` (background). Recording is best-effort — a failure rolls back and never breaks the
audited action.

**Trade-off / deferred.** Background events run in-process (not a durable queue); under a hard
crash a handful of in-flight view/download events can be lost. Acceptable for the MVP given the
criticality split; a durable log sink is future work.

---

## ADR-017 — Processing durability & maintenance
**Date:** 2026-11-04 · **Status:** Accepted

**Context.** DICOM processing runs in-process via `BackgroundTasks` (ADR-008). If the server is
killed mid-task a study is left `PROCESSING` forever, and abandoned chunked uploads leak temp
files and `upload_sessions` rows. A full external task queue is out of scope for the MVP.

**Decision.** Add **startup maintenance** instead of an external queue:
- **`recover_stale_processing`** marks any `PROCESSING` study `FAILED` with a clear re-upload
  message (after a restart no decode task survives, so such rows are orphaned).
- **`purge_stale_uploads`** deletes `open` upload sessions and their temp objects older than a
  TTL (default 24 h).
Both run in the lifespan startup hook.

**Why.** This gives self-healing and disk reclamation at near-zero complexity for a single-node
MVP, and names the boundary at which a real queue (arq/Celery) becomes worthwhile.

**Trade-off / deferred.** Startup-only (no periodic scheduler yet) and single-node (a second
replica restarting could fail another's genuinely in-flight study); an external queue with
retries/visibility remains the scaling path. Per-chunk upload commits are kept deliberately —
they are required for correct resume (a lagging offset would re-append bytes and corrupt the
file).

---

<!-- Upcoming ADRs (added as iterations land):
     (none pending)
-->
