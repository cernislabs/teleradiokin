# Teleradiokin — Project Plan (Living Document)

> **Purpose.** This is the single source of truth for *where we are* and *what comes next*.
> It is maintained agile-style: work is organized into Epics and short Iterations (sprints).
> **Instructions for the next piece of work come from this file.** After every delivered
> increment, this file is updated: check off completed items, append a Status Log entry,
> and set the next iteration as *In Progress*.

- **Project:** Teleradiology MVP (upload studies → remote radiologist review → report)
- **Stack:** ASP.NET Core Web API (.NET 8) · Angular · PostgreSQL · Docker Compose
- **Target context:** Central Africa — low bandwidth, intermittent connectivity, modest hardware
- **Language:** All code/docs in English; frontend strings kept i18n-extractable (French later)
- **Last updated:** 2026-11-04
- **Current status:** `PLANNING` — not yet started
- **Active iteration:** _none (awaiting kickoff)_

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

### Iteration 0 — Foundation & Compose — `TODO`
- [ ] .NET solution with 4 projects: `Api`, `Application`, `Domain`, `Infrastructure`
- [ ] Angular app scaffolded; user-facing strings isolated for future i18n
- [ ] EF Core `DbContext` + initial migration; PostgreSQL connection via env vars
- [ ] `docker-compose.yml` runs postgres + backend + frontend; `docker-compose up` boots
- [ ] `README.md` skeleton + `docs/decisions.md` created (ADR-001: stack choices)
- [ ] CI-friendly test projects created (even if empty), build green

### Iteration 1 — Auth & Roles (E1) — `TODO`
- [ ] ASP.NET Core Identity + JWT issuance/refresh
- [ ] Roles seeded: `Admin`, `ReferringClinician`, `Radiologist`
- [ ] Role-based authorization policies; every endpoint protected by default
- [ ] Angular login screen + auth guard + token handling
- [ ] Seed users: 1 admin, 1 radiologist, 1 referring clinician
- [ ] Unit tests for auth/role logic
- [ ] ADR: auth approach

### Iteration 2 — Patient & Encounter (E2) — `TODO`
- [ ] Entities (FHIR-leaning names/fields): Patient, Encounter, (links to ImagingStudy)
- [ ] Demographics, identifiers, consent acknowledgment
- [ ] Migrations; CRUD endpoints with role authorization
- [ ] Angular patient list + detail/create screens
- [ ] Seed sample patient
- [ ] Unit/integration tests
- [ ] ADR: FHIR-leaning data-model decision

### Iteration 3 — Imaging Upload (E3) — `TODO`
- [ ] `IStudyStorage` abstraction + filesystem implementation (S3-ready)
- [ ] Chunked/resumable upload endpoint with graceful retry
- [ ] Validation: type, size, DICOM validity
- [ ] DICOM metadata extraction (fo-dicom): modality, study date, body part, accession
- [ ] Compressed preview/thumbnail generation
- [ ] Integration test for the upload→store→extract→preview pipeline
- [ ] ADR: storage + DICOM + preview + chunked-upload decisions

### Iteration 4 — Worklist & Viewer (E4) — `TODO`
- [ ] Radiologist worklist: queue of pending studies
- [ ] Study detail endpoint + Angular viewer over generated previews
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
- [ ] `IAuditLog` abstraction; records actor, action, entity, timestamp
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

- (none yet)

### Open decisions to confirm
- Build cadence: deliver all iterations end-to-end, or pause for review after each? _(pending)_
- Viewer: basic preview viewer (recommended, low-bandwidth) vs. embedded OHIF/cornerstone. _(pending)_

---

## 7. Status Log (append-only)

| Date | Iteration | What was delivered | Build/Tests | Next |
|------|-----------|--------------------|-------------|------|
| 2026-11-04 | — | Project plan created | n/a | Iteration 0 |

---

## 8. Seed data target (for acceptance)

- 1 Admin, 1 Radiologist, 1 Referring Clinician
- 1 sample Patient (with identifiers + consent)
- (optional) 1 sample Encounter + Study once upload pipeline exists
