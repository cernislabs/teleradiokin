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

- **Authentication, roles & access scoping** — `Admin`, `ReferringClinician` (uploads
  studies, requests reads), `Radiologist` (reviews studies, writes reports). JWT-based auth.
  Records are scoped by **organization** (referring site): clinicians see only their own
  site's patients and studies, while radiologists and admins read across all sites.
- **Patient & encounter records** — demographics, identifiers, consent acknowledgment, and
  encounters linked to one or more imaging studies. Data model is *FHIR-leaning*, stored
  relationally with **JSONB** for flexible/extensible fields.
- **Imaging upload** — DICOM and common image formats, validated and stored outside the
  database behind a storage abstraction, with DICOM metadata extraction (modality, study
  date, body part, accession number) and lightweight compressed previews generated
  **asynchronously** so uploads never block the server.
- **Worklist & review** — radiologists see a queue of pending studies, open one, view the
  images in a browser DICOM viewer, and submit a report.
- **Reports** — structured findings, impression, and status (draft / final), linked to the
  study and patient, viewable and printable by the referring clinician.
- **Audit trail** — who accessed or changed each patient record, study, and report, with
  timestamps.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Language / runtime | Python 3.12+ |
| Web framework | FastAPI + Uvicorn (ASGI) |
| Validation | Pydantic v2 / pydantic-settings |
| ORM & migrations | async SQLAlchemy 2.0 + Alembic |
| Database | PostgreSQL 16 (JSONB for FHIR-leaning records) |
| Auth | JWT (python-jose) + bcrypt password hashing (passlib) |
| DICOM / imaging | pydicom + pylibjpeg (+ Pillow / NumPy for previews) |
| Async processing | FastAPI `BackgroundTasks` + `asyncio.to_thread` for CPU-heavy work |
| Frontend | Angular (served by nginx; `/api` reverse-proxied to the backend) |
| Orchestration | Docker Compose (db + backend + frontend) |

---

## Architecture (brief)

The backend follows a strict Clean Architecture; dependencies point inward
(api → services → domain; infrastructure implements the ports the services depend on):

```
backend/
├── app/
│   ├── api/            # FastAPI routers, endpoints, HTTP handling
│   ├── core/           # settings, JWT security, DI dependencies
│   ├── domain/         # Pydantic schemas, entities, enums (no DB dependencies)
│   ├── services/       # business logic, DICOM extraction, background tasks
│   ├── infrastructure/ # SQLAlchemy models, async DB session, filesystem/storage adapters
│   └── main.py         # FastAPI app factory + middleware
├── migrations/         # Alembic environment (async)
├── tests/
├── requirements.txt
└── Dockerfile
```

```
                 ┌─────────────┐      /api (reverse proxy)      ┌──────────────────┐
  Browser ─────► │  Angular    │ ─────────────────────────────►│  FastAPI /Uvicorn │
                 │  (nginx)    │◄───────────────────────────── │   :8000 (ASGI)    │
                 └─────────────┘                                 └────────┬─────────┘
                                                                          │
                                        async SQLAlchemy │ BackgroundTasks │ filesystem
                                                          ▼                ▼            ▼
                                                   ┌────────────┐   DICOM pipeline   study
                                                   │ PostgreSQL │   (pydicom →       storage
                                                   │  (JSONB)   │    preview JPEG)   volume
                                                   └────────────┘
```

- **domain** has no framework/DB dependencies — just Pydantic schemas, entities, enums.
- **services** hold business logic and the DICOM pipeline; CPU-heavy pixel work runs off
  the event loop (`asyncio.to_thread` / `BackgroundTasks`) so chunked uploads stay responsive.
- **infrastructure** implements storage and persistence (async SQLAlchemy, filesystem
  adapter with an S3-ready interface).
- **api** is thin: routers validate input and delegate to services.

The frontend is an Angular app with role-based views. User-facing strings are kept isolated
so they can be extracted into an i18n layer when French support is added.

---

## Running locally

Everything runs in containers, so the steps are the same on every OS — only how you install
Docker differs. All commands use Docker Compose **v2** (`docker compose`, with a space). If you
have the older standalone binary, use `docker-compose` (with a hyphen) instead.

### Prerequisites by operating system

**Linux**
- Install [Docker Engine](https://docs.docker.com/engine/install/) + the Compose plugin for
  your distro (e.g. `sudo apt-get install docker.io docker-compose-plugin`).
- Start Docker: `sudo systemctl enable --now docker`.
- Optional (run without `sudo`): `sudo usermod -aG docker $USER`, then log out/in.

**macOS** (Intel or Apple Silicon)
- Install [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
  (or `brew install --cask docker`), then launch Docker Desktop once so the engine starts.

**Windows 10/11**
- Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
  with the **WSL 2** backend (recommended), then launch it once.
- Run the commands below from **PowerShell**, **Windows Terminal**, or a WSL shell.

Verify your install on any OS:

```bash
docker --version
docker compose version
```

### Start the stack

From the project root:

```bash
# 1. Create your local env file from the template (edit secrets if you like).
#    Linux / macOS / WSL / Git Bash:
cp .env.example .env
#    Windows PowerShell:
copy .env.example .env

# 2. Build images and start all three services (add -d to run in the background).
docker compose up --build
```

First run downloads base images and builds the backend/frontend, so it takes a few minutes.
Migrations and seed accounts are applied automatically once the database is healthy.

| Service | URL |
|---------|-----|
| Frontend | http://localhost:4200 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/swagger |
| Health probe | http://localhost:8000/health |

### Stop / shut down

```bash
# If running in the foreground: press Ctrl+C, then:
docker compose down          # stop and remove containers + network (keeps the database)

docker compose down -v       # also delete the database volume (full reset / re-seed)

docker compose stop          # just pause containers without removing them
docker compose start         # resume them again
```

Your data persists in named volumes between `up`/`down`. Use `down -v` only when you want a
clean database (this wipes users, patients, studies, and uploaded files).

### Troubleshooting

- **Port already in use** (4200 / 8000 / 5432): stop the other process or change the host port
  in `docker-compose.yml`.
- **Windows line endings**: clone with Git's default autocrlf, or ensure `backend/entrypoint.sh`
  keeps LF endings (it must stay LF to run inside the Linux container).
- **"Cannot connect to the Docker daemon"**: Docker isn't running — start Docker Desktop
  (macOS/Windows) or `sudo systemctl start docker` (Linux).

Alembic migrations run automatically on backend startup (via the container entrypoint), and
seed accounts are created idempotently on first boot.

**Seed accounts** (passwords come from `.env`; defaults shown are from `.env.example`):

| Role | Email | Default password |
|------|-------|------------------|
| Admin | `admin@teleradiokin.org` | `Admin!2345` |
| Radiologist | `radiologist@teleradiokin.org` | `Radio!2345` |
| Referring clinician | `clinician@teleradiokin.org` | `Clinic!2345` |

The seeded clinician belongs to a sample organization (`Kinshasa General Clinic`) and sees
only that site's records; the radiologist and admin are cross-site. Log in at
http://localhost:4200. A sample patient (`MRN-0001`) with an encounter is seeded.
To try an upload: open the patient, pick an encounter, and upload a DICOM (`.dcm`) **or** an
ordinary JPEG/PNG (both are accepted) — it uploads in resumable chunks, is processed in the
background, and a compressed preview thumbnail appears when its status reaches `Pending`.

To review: open the **Worklist** from the dashboard (or log in as the radiologist), pick a
pending study, and open it in the full-size viewer — DICOM renders in-browser with
Window/Level, Pan, and Zoom; non-DICOM images are shown directly.

To report: in the viewer, the radiologist writes **findings** and **impression**, saves a
draft, then **finalizes** (which locks the report and marks the study `Reported`). The
referring clinician opens the same study and views or prints the report as a **PDF**.

To audit: log in as the **admin** and open **View the audit trail** from the dashboard (or
`GET /api/audit`). It shows who accessed or changed each patient, study, and report — with
actor, role, action, record, source IP, and UTC timestamp — filterable by action and record
type. The audit log is admin-only; other roles receive `403`.

> Secrets (JWT signing key, database credentials, seed passwords) are read from environment
> variables and are **not** committed to source. Configure them in `.env`.

---

## Testing

The suite needs no running database (it uses an in-memory SQLite engine) and no local
Python — run it in the backend image. From the project root:

```bash
# Build the backend image once (or reuse the one from `docker compose build`).
docker build -t teleradiokin-backend ./backend

# Run the tests inside it (dev-only deps installed on the fly).
docker run --rm -u 0 --entrypoint sh -v "$PWD/backend:/app" -w /app \
  teleradiokin-backend \
  -c "pip install -q -r requirements-dev.txt && pytest -q"
```

With a local Python 3.12 toolchain you can instead `cd backend && pip install -r
requirements-dev.txt && pytest`.

- **Unit tests** cover domain logic and the DICOM pipeline (metadata extraction, preview
  generation, validity checks).
- **Integration tests** cover each API surface — auth/roles, organization-scoped access,
  patients/encounters, chunked upload (DICOM and PNG), reports, and the audit trail —
  SQLite-backed for speed.
- **Hardening tests** cover config fail-fast, storage path-traversal/move, the `extra` size
  cap, pagination, and stale-processing recovery.
- **End-to-end smoke test** (`test_e2e.py`) exercises the whole flow through the HTTP API:
  clinician uploads a DICOM → background processing → radiologist reviews and reports →
  clinician downloads the PDF → admin inspects the audit trail.

---

## Intentionally deferred

- **French localization** — UI strings are kept extraction-ready, but no i18n layer yet.
- **Full HL7 FHIR** — the data model leans toward FHIR (JSONB) for extensibility but is not compliant.
- **Production hosting** — TLS termination, scaling, backups, and observability are not addressed.
- **Regulatory compliance** — HIPAA and local health-data regulations are not implemented.
- **PACS integration** — no DICOM C-STORE/C-FIND or PACS connectivity.
- **ML/data-science workloads** — the Python stack is chosen to enable these later; none are built yet.

---

## Project status & contributing

Work proceeds in small, reviewable increments. The current iteration, backlog, and status
log are in [`PROJECT_PLAN.md`](./PROJECT_PLAN.md). Each increment must build cleanly and pass
its tests before the next begins.
