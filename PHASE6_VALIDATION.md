# PulseWatch Phase 6 — Validation and Launch Checklist

## What's new

- Connect-time DNS resolution and IP pinning for HTTP(S) monitors and webhook alerts. Blocks non-public destinations, including cloud instance metadata ranges. Redirects and environment proxy inheritance remain disabled.
- Four new unit tests cover metadata addresses, mixed DNS responses, connect-time pinning, and URL user-info rejection.
- A GitHub Actions PostgreSQL 16 job migrates a disposable database and runs a real incident lifecycle smoke test. The existing SQLite regression and frontend build jobs remain.
- Deployment smoke script checks that the public HTTPS endpoint serves the dashboard, that `/health` is available, and that an unauthenticated API route rejects access.

## Local development

```sh
cp .env.example .env
# Edit .env: choose a long unique PostgreSQL password and matching DATABASE_URL
# Optionally set ADMIN_EMAIL and ADMIN_PASSWORD for initial administrator bootstrap
docker compose up -d --build
docker compose exec api python -m app.bootstrap_admin
```

Visit http://localhost:3000. The authenticated dashboard uses the API at `/api/v1/`.

## Production checklist — manual operator actions

1. Use a dedicated deployment host with Docker and Compose; configure a DNS A/AAAA record for `PULSEWATCH_DOMAIN` and allow inbound TCP 80/443 only. Do not expose PostgreSQL or internal API ports.
2. Create `.env` with `ENVIRONMENT=production`, `ALLOW_PRIVATE_TARGETS=false`, strong `POSTGRES_PASSWORD`, matching `DATABASE_URL`, and an HTTPS-enabled domain. Never commit `.env` or user passwords.
3. Place the worker in a network namespace or egress gateway with **firewall rules blocking RFC1918, loopback, link-local, unique-local IPv6, metadata, and other special-use ranges**. Application-level IP pinning does not replace network policy.
4. Create a backup before upgrading: `docker compose exec -T db pg_dump -U pulsewatch -Fc pulsewatch > pulsewatch-backup.dump`. Store it securely outside the host and rehearse restoration.
5. Deploy using `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`. Verify the Compose plugin supports `!reset`; run `docker compose ... config` before `up`.
6. Bootstrap an administrator using `docker compose exec api python -m app.bootstrap_admin`. Do not log the bootstrap password or leave it in shell history.
7. Execute `./scripts/verify_deployment.sh https://your-domain.example` and inspect `docker compose logs --tail=200 api worker dashboard caddy`.
8. Configure backups, patch cadence, incident ownership, monitoring of PulseWatch itself, and an on-call contact. Independently validate firewall rules, authentication, HTTPS, and restore procedures.
9. Confirm all GitHub Actions jobs pass on your repository, including PostgreSQL and frontend. CI is **configured**, not proven to have executed on GitHub from this environment.

## Limitations and risk register

- No Docker daemon, accessible production domain, or live PostgreSQL service was available during packaging. PostgreSQL CI is configured but not yet run here.
- The frontend npm dependency installation / complete build was not verified locally in this environment; CI is configured to attempt it.
- `PublicOnlyTransport` integrates with internal `httpx.HTTPTransport._pool` implementation. The package narrows compatible versions to httpx 0.28.x and httpcore 1.0.x; rerun security tests before dependency upgrades.
- Single-workspace accounts only; tenant isolation, account-level MFA, organisation provisioning and stronger brute-force controls are future work.
- An authenticated administrator can request connections to public Internet services. Production still needs network-layer egress isolation and sensible rate/resource quotas.
- Outbound SMTP is not covered by URL pinning; the SMTP server is operator-configured. Protect credentials and restrict outbound SMTP as appropriate.
- This release is a **candidate for controlled deployment validation**, not a declaration of production approval.
