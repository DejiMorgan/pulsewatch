# PulseWatch — Phase 5 release candidate

**Start with [PHASE5_DEPLOYMENT.md](PHASE5_DEPLOYMENT.md).** Phase 5 adds administrator/viewer accounts, revocable bearer sessions, migration 0003, and an optional Caddy HTTPS proxy. Previous dashboard, health checks, incidents and alerts remain available.

# PulseWatch — API Performance & Reliability Monitor

A runnable **Phase 1 backend starter** for API health checks, scheduled probes, latency history, uptime calculations and basic incident detection. This is not yet the complete planned product: React UI, email/webhook alert delivery, incident exports, auth users, and production migrations are not implemented.

## Prerequisites
- Docker Desktop with Docker Compose

## Run
```bash
cp .env.example .env
# Change API_KEY to a strong random value before running (and update DB password in both env vars together if changing it).
docker compose up --build -d
```
Open **http://localhost:8000/docs** for interactive API documentation. The API uses the `X-API-Key` header. `/health` is public.

## Example monitor creation
```bash
curl -X POST 'http://localhost:8000/api/v1/monitors' \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d '{"name":"Example","url":"https://example.com","interval_seconds":60,"expected_status":200,"failure_threshold":3}'
```

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/monitors
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/dashboard/summary
curl -H "X-API-Key: $API_KEY" 'http://localhost:8000/api/v1/monitors/1/metrics?hours=24'
```

Run tests locally from `backend/`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
DATABASE_URL=sqlite+pysqlite:///./test.db pytest -q
```

## Included
- API-key protected FastAPI CRUD (create/list/update/delete) for HTTP monitors.
- PostgreSQL persistence and time-stamped check results.
- Worker with PostgreSQL `SKIP LOCKED` claiming, configurable check intervals.
- Timeout, unexpected-status and connectivity failure detection.
- Incident opens after a configurable consecutive-failure threshold; closes after a successful check.
- Latency history, availability percentage, approximate nearest-rank latency percentiles.
- Docker Compose app, worker and database.
- Tests for incident transitions and target validation.

## Safety / production limitations
- Block private, loopback and reserved target addresses by default; redirects are disabled, proxy env ignored. **This is defense in depth, not full SSRF protection**: DNS can change between lookup and connection. Deploy behind egress controls and implement DNS/IP pinning before supporting untrusted users.
- Change all demonstration passwords/secrets and configure HTTPS/reverse proxy before exposure. API key is a development-only single shared secret; implement identity, permissions, encryption and audit logging for production.
- Database tables are created at startup for convenience. Replace `create_all` with managed Alembic migrations.
- Worker claims a due check by updating its next scheduled time; an unexpected process termination can miss one check. Introduce leases and backfill for stronger delivery guarantees.
- A manual check and a scheduled worker check can race when updating incident counters; serialize per-monitor state changes before production.
- Monitoring represents observed health from this worker's vantage point, not globally measured uptime.
- Checks currently only support GET/HEAD and expected HTTP status; no custom authentication headers.
- No notification delivery yet; incidents are persisted and visible via API.

---

## Phase 2 — Reliability Engine (v0.2)

This release extends Phase 1 without replacing its monitoring endpoints.

**New endpoints** (send `X-API-Key: <API_KEY>`):

- `POST /api/v1/alert-rules` — create a notification policy linked to a monitor.
- `GET /api/v1/alert-rules?monitor_id=1` — list alert rules.
- `DELETE /api/v1/alert-rules/{id}` — disable a policy while retaining its audit trail.
- `GET /api/v1/alert-events?monitor_id=1` — inspect pending, retrying, sent and failed notifications.
- `GET /api/v1/incidents/{id}/report` — get an incident timeline/notification summary in JSON.

Example rule:

```json
{
  "monitor_id": 1,
  "name": "Production outage email",
  "channel": "email",
  "destination": "ops@example.com",
  "notify_on_open": true,
  "notify_on_recovery": true
}
```

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD` and `SMTP_STARTTLS` in `.env` to enable email delivery. Alternatively, choose `channel: "webhook"` and an **HTTPS publicly resolvable** destination. Email and webhook alerts are dispatched by the worker rather than within the API request; a saved rule does not guarantee successful delivery unless the integration is configured and reachable. View delivery outcomes via `/api/v1/alert-events`.

Reliability behavior: after the configured number of consecutive failures, a monitor opens one incident and queues one `opened` event per active eligible alert rule. On successful health check, the incident closes and eligible `resolved` events are queued. A database uniqueness constraint prevents duplicate *outbox event records* per rule/incident/transition. Delivery retries back off exponentially and stop at `ALERT_MAX_ATTEMPTS`. Outbox events and incidents are committed together, so incident state changes are not lost when a notification service is down.

**Upgrade from Phase 1:** Back up PostgreSQL first. `app.init_db` uses `create_all` and will add the new `alert_rules` and `alert_events` tables to an existing Phase 1 database. It does not alter existing tables. Use explicit Alembic migrations for subsequent schema changes and production deployment.

**Run locally:**

```bash
cp .env.example .env # if this is your first run; otherwise merge new variables into existing .env
# Replace sample credentials and API key before network exposure
docker compose up --build -d
curl http://localhost:8000/health
```

**Run tests without a PostgreSQL installation** (inside the backend directory, with dependencies installed):

```bash
DATABASE_URL=sqlite+pysqlite:// python -m pytest -q
```

**Limitations / hardening before production:** The HTTP probe and webhook sender validate destinations and prohibit redirects, but DNS validation alone cannot fully prevent DNS-rebinding attacks; enforce egress network policy and connect-time DNS/IP pinning. Alert delivery is *at least once*, not exactly once: a worker crash or lease timeout can result in a duplicate external notification. `ALERT_LEASE_SECONDS` should exceed the notification timeout. The demo worker executes one outbound operation at a time; split and scale probe/alert workers for production. The JSON incident report is not a full postmortem with root-cause analysis. No frontend dashboard or multi-tenant identity system is included in Phase 2.

---

## Phase 3 — React Monitoring Dashboard (v0.3)

Phase 3 adds an integrated React 18 + TypeScript + Vite dashboard, served via Nginx in Docker Compose.

### Start with Docker Desktop

From the root `pulsewatch/` directory:

```bash
cp .env.example .env  # fresh install only; keep your existing .env when upgrading
# Set a long, unique API_KEY and update the PostgreSQL password where configured.
docker compose up --build -d
```

- **Dashboard:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **Backend health:** http://localhost:8000/health

The dashboard asks for the API key from your `.env`. The key is held in browser `sessionStorage` and transmitted using the existing `X-API-Key` header. This browser-side shared-key approach is for **local development only**. In production, replace it with user sessions, RBAC, TLS, and backend-controlled authentication. Do not expose this interface publicly without those controls.

### Run frontend without the Docker dashboard service

Prerequisite: Node.js 20+ and a running PulseWatch backend on localhost:8000.

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` and `/health` to `localhost:8000` to avoid cross-origin configuration. Run `npm run build` for a type-checked production build. Docker builds the UI and proxies API requests over the internal Compose network, so the browser can use same-origin requests.

### Dashboard features

- **Overview:** active endpoints, sampled availability and latency metrics, open incidents, live endpoint health and a response-time history chart. Graph data is taken from real stored checks (not illustrative data).
- **Monitors:** create monitors, run a check on demand, pause/resume or delete an endpoint, search registered endpoints, and review availability.
- **Incidents:** see open/resolved incidents, reasons and timestamps; download an individual incident's JSON report.
- **Alerting:** configure email/webhook rules, disable alert policies and inspect notification delivery outcomes.
- **Refresh:** 30-second automatic polling and manual refresh, with connection and error states.
- **Design:** responsive dark UI with mobile navigation and accessible form labels.

**Metric interpretation:** Check availability is the percentage of stored checks reporting success, not an uptime SLA. Overview availability is weighted across fetched monitor samples. The displayed average P95 is the arithmetic mean of the selected-window P95 values for individual monitors, not an overall fleet percentile. The graph displays the latest 80 non-null latency samples from the 200 checks returned by the backend. Missing measurements and new monitors remain unpopulated until probes run.

### Verification and limitations

Backend test suite: 8 tests passed with SQLite. TypeScript/TSX syntax transpilation verified. Full frontend dependency installation, TypeScript type-check, Vite production build and Docker runtime smoke test **could not be executed in the current environment** (npm registry unavailable, Docker CLI absent). Run `npm install && npm run build` and `docker compose up --build -d` on your development machine. Existing backend limitations concerning DNS rebinding, worker leases, authentication and migrations still apply.

---

## Phase 4 — Reliability & Release Engineering (v0.4)

Phase 4 introduces Alembic migrations, recoverable monitor leases, atomic scheduled-probe commits, API readiness checks, safer key comparison, startup configuration checks, container restart policies, GitHub Actions CI and additional regression tests. See [PHASE4_DEPLOYMENT.md](PHASE4_DEPLOYMENT.md) for **critical upgrade instructions**, verification steps and the remaining internet-facing production blockers.

**Upgrade warning:** Existing Phase 3 PostgreSQL databases require a one-time Alembic baseline stamp **before** applying revision 0002. Always back up first. Fresh installs must not be stamped. Existing developer auth is still local-only; Phase 4 does not include user accounts, RBAC or deployment-grade SSRF isolation.

## Phase 6 — Network hardening, CI PostgreSQL and validation

Phase 6 adds connect-time IP pinning for outbound monitors/webhooks, DNS-rebinding regression tests, a PostgreSQL-backed CI job, and an HTTPS deployment smoke script. See [PHASE6_VALIDATION.md](PHASE6_VALIDATION.md) for installation, security limitations and the required operator checks. Do not expose this service publicly until production network isolation and deployment validation have been completed.
