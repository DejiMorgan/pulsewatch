# PulseWatch Phase 4 — Reliability and Release Engineering

## What changed

- Alembic migration system replaces `create_all` during container startup.
- Monitoring workers acquire **recoverable time-bound leases**. A crashed worker no longer permanently postpones an unfinished probe. A probe from an obsolete lease is discarded instead of overwriting a newer claim.
- Check result, incident transition, lease release and next schedule time are committed in one transaction for scheduled probes.
- Readiness route `GET /ready` checks database connectivity; `GET /health` remains a liveness route.
- API-key comparison is constant-time; `ENVIRONMENT=production` refuses placeholder/short keys or private targets.
- Container restart policies and API readiness health checks added.
- GitHub Actions CI definition for Python tests, migration smoke test and React build.
- Phase 4 regression tests added.

## Fresh installation

1. Install Docker Desktop.
2. `cp .env.example .env`
3. Generate a new API key: `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
4. Set `API_KEY` to the generated value. Set a strong `POSTGRES_PASSWORD`, **and modify DATABASE_URL accordingly** (the password is embedded in that connection string). Keep `ALLOW_PRIVATE_TARGETS=false`.
5. Run `docker compose up --build -d`.
6. Verify `curl http://localhost:8000/ready` and open http://localhost:3000.

**Important:** The dashboard still stores the shared API key in sessionStorage. This is an **isolated localhost demonstration**, not a safe internet-exposed production login. Keep the ports bound to 127.0.0.1 as provided.

## Upgrading an existing Phase 3 installation

**Make a verified database backup before attempting any migration.** Run these steps while the API, worker and dashboard are stopped to prevent writes or races. Keep your existing `.env` rather than replacing it. Add `ENVIRONMENT=development` and `CHECK_LEASE_SECONDS=60` to the existing `.env`.

1. Stop app processes without deleting data:
   `docker compose stop api worker dashboard`
2. Back up PostgreSQL (uses the existing DB credentials):
   `docker compose exec -T db pg_dump -U pulsewatch -d pulsewatch -Fc > pulsewatch_backup.dump`
3. Replace code with Phase 4 and rebuild images without starting API processes:
   `docker compose build api worker dashboard`
4. Existing Phase 3 databases already contain the baseline tables but have no `alembic_version` tracking table. **Run the baseline stamp exactly once**:
   `docker compose run --rm --no-deps api alembic stamp 0001_initial`
5. Apply the incremental lease migration:
   `docker compose run --rm --no-deps api alembic upgrade head`
6. Start services:
   `docker compose up -d`
7. Verify:
   `curl http://localhost:8000/ready`

**Do not stamp a fresh database.** The API startup automatically runs `alembic upgrade head` on a fresh database. **Do not stamp a database that might have a different existing schema**; verify it matches Phase 3 before following the upgrade procedure. If you have already run Phase 4 once, never repeat the stamp. In PostgreSQL installations, use versioned operational backups and a controlled change window.

## API and tests

- `GET /health` — liveness: process responds, does not check database.
- `GET /ready` — readiness: database connectivity.
- Existing authenticated `/api/v1/*` routes remain compatible with Phase 3.
- From `backend/`, run `DATABASE_URL=sqlite+pysqlite:// python -m pytest -q`.
- From `backend/`, run `DATABASE_URL=sqlite+pysqlite:///./smoke.db alembic upgrade head` for a local migration smoke test.
- From `frontend/`, run `npm install && npm run build` (internet access may be required for dependencies).

## Remaining blockers before internet-facing production

This release adds release engineering and fault tolerance, but **does not make the app publicly deployable**. Before enabling external access, implement multi-user authentication, secure browser sessions and role-based access controls; TLS termination and a hardened proxy; egress firewall enforcement and connect-time IP validation to mitigate DNS rebinding/SSRF; secret management; PostgreSQL integration and concurrency tests; centralized logs and audit events; rate limits; database backups and restore drills; monitoring/alerts for PulseWatch itself; dependency pinning and vulnerability scans; production-grade deployment manifests; bounded worker concurrency; and explicit alert delivery semantics. The shared API key must not be publicly distributed.

**Lease caveat:** `CHECK_LEASE_SECONDS` must exceed the longest expected probe runtime including scheduling jitter; expired leases may cause a second probe attempt, but stale results are discarded. Notifications remain at-least-once and can duplicate externally after interrupted sends.
