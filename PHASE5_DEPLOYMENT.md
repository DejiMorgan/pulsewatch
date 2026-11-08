# PulseWatch Phase 5 — Deployment and security guide

## Release classification
This is a **release candidate**, not security-certified production software. Do not monitor untrusted targets until network egress SSRF protections are independently configured and tested. No cloud deployment was performed during packaging.

## New authentication
- Login: POST `/api/v1/auth/login` with JSON `{ "email": "...", "password": "..." }`. Returns an opaque, revocable 12-hour bearer token.
- GET `/api/v1/auth/me`, POST `/api/v1/auth/logout`.
- Bootstrap one admin using `docker compose exec -e ADMIN_EMAIL=admin@example.com -e ADMIN_PASSWORD='your-long-unique-password' api python -m app.bootstrap_admin` (avoid shell history / exposing command line secrets; a secret manager is preferable).
- Admin users can POST `/api/v1/users` with `{email,password,role}` (`admin` or `viewer`).
- Viewers can read monitor metrics/incidents; mutations require admin role. No account UI yet—user creation uses the authenticated REST API.
- Passwords: PBKDF2-SHA256 600,000 iterations with per-user random salts; login lockout at 5 failed attempts for 15 minutes. Tokens stored as SHA-256 digests in PostgreSQL; browser stores the returned token in sessionStorage. Password resets, MFA and auditing are not implemented.
- The earlier shared X-API-Key can authenticate only in `ENVIRONMENT=development`; it is disabled in production.

## Fresh production setup
1. Point an A/AAAA DNS record to a server you control, then set `PULSEWATCH_DOMAIN=monitor.example.com`.
2. Copy `.env.example` to `.env`. Set `ENVIRONMENT=production`, a randomly generated `POSTGRES_PASSWORD`, a matching `DATABASE_URL`, and `ALLOW_PRIVATE_TARGETS=false`. Restrict `.env` permissions (`chmod 600 .env`).
3. Install recent Docker Compose supporting `!reset`, and confirm ports 80/443 are open and no other reverse proxy uses them.
4. Run `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` to verify the merged configuration, then `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
5. Create your admin account using the bootstrap command above (pass secrets via a secure channel). Visit `https://monitor.example.com` and log in.
6. Configure off-host database backups, retention, monitoring, firewalling and a tested restore procedure. See `PHASE4_DEPLOYMENT.md` for upgrading existing databases: back up first; Alembic automatically runs migration `0003_accounts` on API startup.

## Security gaps before Internet exposure
- **Critical**: URL validation alone does not prevent DNS rebinding, redirect-based SSRF or access to cloud metadata/private IPs. Deploy network-level egress ACLs or an isolated egress proxy, re-resolve and pin outgoing connections, disable redirects, and verify both monitoring and alert-delivery paths. Default deny RFC1918, loopback, link-local and metadata services.
- **High**: Add strong rate limits at reverse proxy / gateway for login endpoints; current database account lockout is not IP-based and does not prevent password-spray attacks against many accounts.
- **High**: Keep the server patched; establish secret rotation, TLS validation, log retention and incident response procedures. The browser bearer token is vulnerable to XSS; review the included baseline CSP, perform an XSS assessment, and consider HTTP-only cookie sessions with CSRF protection.
- **High**: Do not use multi-tenant mode: all current users share the same workspace. Roles are application-wide, not per-monitor.
- **Medium**: Frontend build, live Docker Compose deployment and PostgreSQL integration tests require verification in your actual environment. Pin dependencies and image digests before production release.

## Testing
`cd backend && pip install -r requirements-dev.txt && pytest -q`
Fresh migration: `DATABASE_URL=sqlite+pysqlite:///./phase5.db alembic upgrade head`
Frontend build: `cd frontend && npm ci` (after generating a committed lockfile) or `npm install && npm run build`.
