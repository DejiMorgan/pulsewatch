# PulseWatch

**API performance and reliability monitor**
**Developed as a portfolio project by Arabome Obadiah Ayodeji**

PulseWatch checks HTTP endpoints on a schedule, records the response time and outcome of each check, and tracks incidents when services fail repeatedly. It has a React dashboard for reviewing monitor health, response-time history, incidents and notification delivery.

I built this project to work through practical backend problems: scheduling jobs safely, recording operational evidence, handling failures without duplicating incidents, and separating the HTTP API from the worker that executes checks.

> **Release status:** Portfolio release candidate. The backend test suite passes locally, but live PostgreSQL, a full frontend production build, Docker deployment and production network controls still need to be verified. Do not expose the service to untrusted users until those checks are complete.

## Stack

- Python, FastAPI, SQLAlchemy, Alembic
- PostgreSQL 16
- React, TypeScript, Vite
- Docker Compose; optional Caddy HTTPS reverse proxy
- GitHub Actions for backend, PostgreSQL and frontend checks

## Main capabilities

- Register HTTP(S) monitors with a configurable interval, status expectation and failure threshold.
- Run scheduled or manual checks; persist timestamp, latency, status and error context.
- Review sampled availability and latency percentiles (P50, P95 and P99).
- Open an incident after repeated failed checks; resolve it following a successful check.
- Configure email and HTTPS webhook alerts; keep delivery history and retry failed notifications.
- Sign in with an administrator or viewer account. Administrators manage monitors and rules; viewers have read-only access.
- Run with a separate API, worker, database and dashboard container.

## Local setup

**Prerequisites:** Docker Desktop with Compose. From the repository root:

```bash
cp .env.example .env
```

Replace the example credentials. The `POSTGRES_PASSWORD` must agree with the password in `DATABASE_URL`. Keep `ENVIRONMENT=development` for local use.

```bash
docker compose up --build -d
docker compose ps
docker compose exec api python -m app.bootstrap_admin
```

The bootstrap command requires the `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables, supplied securely. See [deployment instructions](PHASE5_DEPLOYMENT.md) and [release checklist](docs/RELEASE_CHECKLIST.md) for details.

Local dashboard: `http://localhost:3000`
OpenAPI documentation: `http://localhost:8000/docs`
Health: `http://localhost:8000/health`
Database readiness: `http://localhost:8000/ready`

These addresses work only after the containers successfully start.

## Run backend tests

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
DATABASE_URL=sqlite+pysqlite:// python -m pytest -q
```

The latest local run completed **16 passing backend tests**. This suite uses SQLite and mocks for specific network behaviors. It is not a substitute for the PostgreSQL integration test, which is configured in CI and still needs to run on an actual CI runner.

To build the frontend, run `cd frontend && npm install && npm run build` from the repository root. The full build has not been independently validated in the packaging environment.

## Design notes

The API handles configuration and reads, while the worker performs outbound health checks and notification delivery. A lease helps a second worker recover unfinished scheduled work. Database uniqueness constraints limit duplicated alert-event records; external notification delivery is still at least once. The system reports **observed check availability**, not a contractual uptime guarantee.

For implementation details and a diagram, read [Architecture](docs/ARCHITECTURE.md). For the security assumptions, read [Security](SECURITY.md). For known gaps and verification tasks, see [Release checklist](docs/RELEASE_CHECKLIST.md).

## Repository guide

| Location | Purpose |
|---|---|
| `backend/app/` | API, database models, worker, monitoring, alerts and authentication |
| `backend/alembic/` | Schema migrations |
| `backend/tests/` | Backend regression and security tests |
| `backend/integration/` | PostgreSQL smoke-test entry point |
| `frontend/` | Dashboard |
| `scripts/` | Deployment smoke check |
| `.github/workflows/ci.yml` | Automated checks |
| `docs/` | Architecture, engineering decisions, case study and release evidence |

## Project status

This repository is suitable for code review and local evaluation. Publication as a public service should follow the release gates in `docs/RELEASE_CHECKLIST.md`. Screenshots, published benchmarks and live uptime claims should only be added after collecting actual measurements from a running deployment.

**Author:** Arabome Obadiah Ayodeji
**License:** MIT — see `LICENSE`.
