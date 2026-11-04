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

<!-- Upcoming ADRs (added as iterations land):
     ADR-011 Report-delivery approach (with teleradiology literature rationale)
     ADR-012 Audit trail design
-->
