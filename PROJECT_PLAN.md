# Teleradiokin — Project Plan (Living Document)

> **Purpose.** This is the single source of truth for *where we are* and *what comes next*.
> It is maintained agile-style: work is organized into Epics and short Iterations (sprints).
> **Instructions for the next piece of work come from this file.** After every delivered
> increment, this file is updated: check off completed items, append a Status Log entry,
> and set the next iteration as *In Progress*.

- **Project:** Teleradiology MVP (upload studies → remote radiologist review → report)
- **Stack:** Python 3.12 · FastAPI/Uvicorn · Pydantic v2 · async SQLAlchemy 2.0 + Alembic · PostgreSQL (JSONB) · pydicom/pylibjpeg · Angular · Docker Compose
- **Stack note:** pivoted from ASP.NET Core to Python/FastAPI on 2026-11-04 — see ADR-004 and the pivot entry in §6
- **Target context:** Central Africa — low bandwidth, intermittent connectivity, modest hardware
- **Language:** All code/docs in English; frontend strings kept i18n-extractable (French later)
- **Last updated:** 2026-11-04
- **Current status:** `MILESTONE PAUSE` — Iteration 3 (Imaging Upload) DONE & verified; awaiting user test before Iteration 4 (Worklist & Viewer)
- **Active iteration:** Iteration 4 — Worklist & OHIF/cornerstone viewer (next)
- **Cadence:** build phases back-to-back; **pause at milestones** (after Auth, after Upload, after Reports) for the user to run `docker-compose up` and test
- **Env note:** no local Python / .NET / Angular toolchain — all build/test/run goes through Docker (python:3.12-slim, node, compose)

---

## 1. How to use this file

1. **Starting work?** Look at *Active iteration* above and the first iteration marked
   `TODO` / `IN PROGRESS` in Section 4. That is the current instruction.
2. **Each iteration has a Definition of Done (Section 5).** Do not mark it complete until
   the build passes and its tests are green.
3. **Finishing a deliverable?** Update this file in the same change:
   - tick the iteration's checkboxes,
   - set its status to `DONE` and the next one to `IN PROGRESS`,
   - update *Current status*, *Active iteration*, and *Last updated* at the top,
   - add a dated entry to the **Status Log (Section 7)**.
4. **Scope changes or new instructions** go into the **Backlog / Notes (Section 6)** so the
   plan stays the source of truth.

---

## 2. Goals & non-goals

**MVP goal:** one radiologist and a small number of referring sites can work end to end —
upload an imaging study, review it in the browser, and return a structured report, with a
full audit trail.

**Explicitly deferred (not in MVP):**
- French localization (UI strings kept extraction-ready only)
- Full HL7 FHIR (data model is *FHIR-leaning*, not compliant)
- Production hosting / TLS hardening / scaling
- Regulatory compliance (HIPAA, local health-data law)
- PACS integration
- Full-fidelity DICOM web viewer (basic preview viewer at MVP)

---

## 3. Epics (MVP scope, priority order)

| # | Epic | Outcome |
|---|------|---------|
| E1 | **Auth & roles** | Admin, ReferringClinician, Radiologist; Identity + JWT; role-based authorization |
| E2 | **Patient & encounter records** | EMR-style, FHIR-leaning: demographics, identifiers, consent, encounter↔study |
| E3 | **Imaging upload** | Chunked upload, validation, filesystem storage behind S3-ready interface, DICOM metadata + preview |
| E4 | **Worklist & review** | Radiologist pending queue, study viewer |
| E5 | **Reports** | Structured findings/impression/status (draft→final), PDF, clinician view + print |
| E6 | **Audit trail** | Who/what/when on patient, study, report access & changes |

Cross-cutting: **clean layered architecture + DI**, **security**, **tests**, **docs**.

---

## 4. Iterations (sprints)

> Statuses: `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED`

### Iteration 0 — Foundation & Compose — `DONE`
- [x] FastAPI app with Clean Architecture layout (`api`/`core`/`domain`/`services`/`infrastructure`/`main.py`)
- [x] Angular app scaffolded; `/api` proxy wired (dev proxy.conf.json + nginx reverse proxy)
- [x] async SQLAlchemy session + portable declarative base; Alembic env (async) + PostgreSQL via env vars
- [x] `docker-compose.yml` runs postgres + FastAPI (Uvicorn :8000) + frontend
- [x] `README.md` + `docs/decisions.md` (ADR-001..004) updated for the Python stack
- [x] pytest suite green (health endpoint + DICOM pipeline unit tests)
- [x] `docker-compose up` end-to-end boot verified — all 3 images build; db healthy, backend `/health` 200, frontend 200, `/swagger` 200, nginx `/api` proxy reaches backend

### Iteration 1 — Auth & Roles (E1) — `DONE`
- [x] JWT issuance/refresh (python-jose) + bcrypt hashing (passlib, bcrypt 4.0.1); `User` model + `0001` migration
- [x] Roles: `Admin`, `ReferringClinician`, `Radiologist` (enum); seeded accounts idempotent on startup
- [x] Role-based authorization via `get_current_user` + `require_roles(...)` dependencies; `/api/users` admin-only
- [x] Angular login screen + auth guard + HTTP interceptor (Bearer, 401→login); `@angular/localize` added for i18n extraction
- [x] Seed users: 1 admin, 1 radiologist, 1 referring clinician (`@teleradiokin.org`)
- [x] Unit tests (hash/token) + integration tests (login, /me, role enforcement) — 13 pass
- [x] ADR-005: auth approach

### Iteration 2 — Patient & Encounter (E2) — `DONE`
- [x] Entities (FHIR-leaning): `Patient` + `Encounter` with typed columns + `extra` JSONB; migration `0002`
- [x] Demographics, MRN identifier, consent acknowledgment (required at creation, timestamped)
- [x] CRUD endpoints with role authorization (`/api/patients`, `/api/encounters`; write = Admin/Clinician, read = all)
- [x] Angular patient list + create form + detail (with encounters); dashboard link; i18n-marked
- [x] Seed sample patient (`MRN-0001`) + a seeded encounter
- [x] Unit/integration tests — 22 pass total (+9 for patients/encounters)
- [x] ADR-006: FHIR-leaning data model (relational + JSONB)

### Iteration 3 — Imaging Upload (E3) — `DONE`
- [x] `StudyStorage` protocol + `LocalFilesystemStorage` (append/size/delete; S3-ready)
- [x] Chunked/resumable upload endpoint (open → PUT chunk@offset → complete) with resume + 409-on-offset-mismatch
- [x] Validation: type, size (per-chunk + total caps), DICOM validity + image validity
- [x] DICOM metadata extraction (pydicom): modality, study date, body part, accession
- [x] Compressed preview generation via `BackgroundTasks` + `asyncio.to_thread`; `Study` model + migration `0003`
- [x] Preview endpoint (`GET /api/studies/{id}/preview`), study list/get; Angular upload UI (chunked, progress, thumbnails)
- [x] Integration tests for upload→store→extract→preview (27 pass total); live DICOM upload verified end-to-end
- [x] ADR-007 (storage), ADR-008 (DICOM/preview), ADR-009 (chunked upload)

### Iteration 4 — Worklist & Viewer (E4) — `TODO`
- [ ] Radiologist worklist: queue of pending studies
- [ ] Study detail endpoint + **OHIF/cornerstone** DICOM viewer embedded in Angular
- [ ] DICOMweb (WADO-RS)-style retrieval endpoint to serve study data to the viewer
- [ ] Role-scoped access (radiologist sees queue; clinician sees own)
- [ ] Tests for worklist filtering/authorization

### Iteration 5 — Reports (E5) — `TODO`
- [ ] Structured report entity: findings, impression, status (draft, final)
- [ ] Report linked to study + patient; create/edit (radiologist)
- [ ] Draft→final transition; referring clinician view + print (server-rendered PDF)
- [ ] Angular report editor + read/print view
- [ ] Tests for report lifecycle & authorization
- [ ] ADR: **report-delivery approach** (with teleradiology literature/practice rationale)

### Iteration 6 — Audit Trail (E6) — `TODO`
- [ ] Audit-log service; records actor, action, entity, timestamp
- [ ] Applied to patient, study, report access & changes
- [ ] Audit records queryable by Admin
- [ ] Tests covering audit capture on key flows

### Iteration 7 — Hardening, Tests & Docs — `TODO`
- [ ] End-to-end smoke test: upload → review → report
- [ ] Fill test coverage gaps (domain, services, API, pipeline)
- [ ] Finalize README (run instructions, architecture brief, deferred list)
- [ ] Finalize `docs/decisions.md`
- [ ] Verify clean `docker-compose up` + full suite green on fresh checkout

---

## 5. Definition of Done (every iteration)

- Code builds (backend + frontend) with no errors.
- New logic covered by tests; **existing + new tests pass**.
- Endpoints enforce role-based authorization; no patient data exposed without auth.
- Secrets read from environment variables, not committed.
- Any design decision recorded in `docs/decisions.md` with a short rationale.
- This `PROJECT_PLAN.md` updated (checkboxes, status, Status Log).

---

## 6. Backlog / Notes / Change requests

_New instructions, scope changes, and decisions-to-make are captured here before they enter an iteration._

### 🔀 Architectural pivot — .NET → Python/FastAPI (2026-11-04)
Directive received to consolidate the stack on Python for future ML/data-science workloads.
Executed immediately (see ADR-004):
- **Purged** the ASP.NET Core `backend/` and rebuilt it as a FastAPI/Uvicorn backend with
  the mandated Clean Architecture layout (`app/api`, `core`, `domain`, `services`,
  `infrastructure`, `main.py`; `migrations/`, `tests/`, `requirements.txt`, `Dockerfile`).
- **async SQLAlchemy 2.0 + Alembic** on PostgreSQL (JSONB for FHIR-leaning records);
  **pydicom + pylibjpeg** for DICOM; **BackgroundTasks / `asyncio.to_thread`** for the
  async DICOM preview pipeline.
- **docker-compose** rebuilt: Uvicorn on **:8000**, Angular retained and proxying `/api`.
- Docs (README, decisions.md) rewritten for the new stack.

**New immediate tasks surfaced by the pivot:**
- Verify `docker-compose up` builds all three images and the backend health probe passes.
- Auth iteration now uses JWT (python-jose) + bcrypt (passlib) instead of ASP.NET Identity.
- Patient/encounter models will use SQLAlchemy + Postgres JSONB (It.2).
- Wire the existing `services/dicom.py` pipeline into the chunked-upload endpoint (It.3).

### Resolved decisions
- **Build cadence (2026-11-04):** phases run back-to-back; pause at milestones — after Auth (It.1), after Upload (It.3), after Reports (It.5).
- **Viewer (2026-11-04):** embed **OHIF/cornerstone** for real in-browser DICOM viewing (It.4). Requires a DICOMweb-style retrieval endpoint; previews still generated for low-bandwidth worklist thumbnails.

---

## 7. Status Log (append-only)

| Date | Iteration | What was delivered | Build/Tests | Next |
|------|-----------|--------------------|-------------|------|
| 2026-11-04 | — | Project plan created | n/a | Iteration 0 |
| 2026-11-04 | 0 (.NET) | .NET solution scaffold, 4 layered projects, EF Core `DbContext`, Angular scaffold, compose | ✅ build + 2 tests green | pivot |
| 2026-11-04 | pivot | ADR-004: purged .NET; rebuilt backend on FastAPI/Pydantic/async SQLAlchemy/pydicom; compose→:8000; docs rewritten | ✅ pytest green | finish It.0 verify |
| 2026-11-04 | 0 (FastAPI) | Foundation complete: `docker-compose up` builds+boots all 3 services; health/swagger/frontend/proxy verified | ✅ 5 pytest + live boot green | Iteration 1 — Auth |
| 2026-11-04 | 1 — Auth | JWT+bcrypt auth, roles, `User` model + migration, seeded accounts, Angular login/guard/interceptor, `@angular/localize`. Live-verified: login/role-enforcement/proxy all correct | ✅ 13 pytest + frontend build + live auth flow green | **milestone pause** → It.2 Patients |
| 2026-11-04 | 2 — Patients | `Patient`/`Encounter` models (JSONB), migration `0002`, role-scoped CRUD, consent enforcement, Angular patient list/form/detail, sample patient+encounter seed | ✅ 22 pytest + frontend build + live CRUD/role checks green | It.3 Imaging Upload |
| 2026-11-04 | 3 — Upload | Chunked/resumable upload, DICOM+image validation, `Study` model + migration `0003`, async preview pipeline, preview endpoint, Angular upload UI. Live: chunked DICOM → Pending+metadata+JPEG preview via proxy | ✅ 27 pytest + frontend build + live upload→preview green | **milestone pause** → It.4 Worklist/Viewer |

---

## 8. Seed data target (for acceptance)

- 1 Admin, 1 Radiologist, 1 Referring Clinician
- 1 sample Patient (with identifiers + consent)
- (optional) 1 sample Encounter + Study once upload pipeline exists
