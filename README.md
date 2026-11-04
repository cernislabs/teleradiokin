# Teleradiokin

A teleradiology platform MVP. Clinics and hospitals upload medical imaging studies
(X-ray, CT, MRI and other DICOM studies) and link them to a patient record; remote
radiologists review the studies in the browser and return structured written reports.

Built for the realities of **Central Africa**: low-bandwidth connections, intermittent
connectivity, and modest hardware — hence chunked/resumable uploads, compressed previews,
and graceful retries.

> ⚠️ **Early-stage MVP under active development.** Progress and the current iteration are
> tracked in [`PROJECT_PLAN.md`](./PROJECT_PLAN.md). Design decisions and their rationale
> live in [`docs/decisions.md`](./docs/decisions.md). This README describes the target
> stack and how to run it; features land iteration by iteration.

---

## What it does (MVP scope)

- **Authentication & roles** — `Admin`, `ReferringClinician` (uploads studies, requests
  reads), `Radiologist` (reviews studies, writes reports). ASP.NET Core Identity + JWT.
- **Patient & encounter records** — demographics, identifiers, consent acknowledgment, and
  encounters linked to one or more imaging studies. Data model is *FHIR-leaning* (extensible
  toward HL7 FHIR without implementing the full standard).
- **Imaging upload** — DICOM and common image formats, validated and stored outside the
  database behind a storage abstraction, with DICOM metadata extraction (modality, study
  date, body part, accession number) and lightweight compressed previews.
- **Worklist & review** — radiologists see a queue of pending studies, open one, view the
  images in a browser viewer, and submit a report.
- **Reports** — structured findings, impression, and status (draft / final), linked to the
  study and patient, viewable and printable by the referring clinician.
- **Audit trail** — who accessed or changed each patient record, study, and report, with
  timestamps.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | ASP.NET Core Web API (.NET 8) |
| Frontend | Angular |
| Database | PostgreSQL (EF Core + migrations) |
| Auth | ASP.NET Core Identity + JWT |
| DICOM | fo-dicom (Fellow Oak) for metadata + preview rendering |
| Storage | Local filesystem behind an `IStudyStorage` interface (S3-compatible target later) |
| Orchestration | Docker Compose (database + backend + frontend) |

---

## Architecture (brief)

The backend follows clean layering with dependency injection, kept proportionate to an MVP:

```
backend/
├── Teleradio.Api            # HTTP controllers, auth wiring, Swagger, DI composition root
├── Teleradio.Application    # use-case services, DTOs, interfaces (IStudyStorage, IAuditLog, …)
├── Teleradio.Domain         # entities, enums, domain rules — no external dependencies
└── Teleradio.Infrastructure # EF Core, Identity, filesystem storage, DICOM extraction
```

- **Domain** has no dependencies.
- **Application** depends only on Domain and defines the interfaces infrastructure implements.
- **Infrastructure** implements those interfaces (database, storage, DICOM).
- **Api** is thin — controllers delegate to application services; all wiring via DI.

The frontend is an Angular app with role-based views (login, patient records, upload,
radiologist worklist/viewer, report editor and print view). User-facing strings are kept
isolated so they can be extracted into an i18n layer when French support is added.

```
.
├── backend/            # ASP.NET Core solution (4 projects above)
├── frontend/           # Angular app
├── tests/              # unit, integration, end-to-end smoke tests
├── docker-compose.yml  # postgres + backend + frontend
├── docs/decisions.md   # architecture decision records
├── PROJECT_PLAN.md     # living agile project tracker
└── README.md
```

---

## Running locally

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### Start the stack

```bash
# 1. Copy the environment template and adjust secrets if needed
cp .env.example .env

# 2. Build and start database, backend, and frontend
docker-compose up --build
```

Once running:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:4200 |
| Backend API | http://localhost:8080 |
| API docs (Swagger) | http://localhost:8080/swagger |

Database migrations and seed data are applied automatically on backend startup.

### Seed accounts

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | _(see `.env.example`)_ |
| Radiologist | `radiologist` | _(see `.env.example`)_ |
| Referring clinician | `clinician` | _(see `.env.example`)_ |

A sample patient record is seeded for demonstration.

> Secrets (JWT signing key, database credentials, seed passwords) are read from environment
> variables and are **not** committed to source. Configure them in `.env`.

---

## Testing

```bash
# Backend unit + integration tests
dotnet test

# Frontend unit tests
cd frontend && npm test
```

- **Unit tests** cover domain and application/service logic.
- **Integration tests** cover the API and the upload pipeline.
- **End-to-end smoke test** exercises the upload → review → report flow.

---

## Intentionally deferred

These are out of scope for the MVP and documented so expectations are clear:

- **French localization** — UI strings are kept extraction-ready, but no i18n layer yet.
- **Full HL7 FHIR** — the data model leans toward FHIR for extensibility but is not compliant.
- **Production hosting** — TLS termination, scaling, backups, and observability are not addressed.
- **Regulatory compliance** — HIPAA and local health-data regulations are not implemented.
- **PACS integration** — no DICOM C-STORE/C-FIND or PACS connectivity.
- **Full-fidelity DICOM web viewer** — the MVP uses compressed server-generated previews.

---

## Project status & contributing

Work proceeds in small, reviewable increments. The current iteration, backlog, and status
log are in [`PROJECT_PLAN.md`](./PROJECT_PLAN.md). Each increment must build cleanly and pass
its tests before the next begins.
