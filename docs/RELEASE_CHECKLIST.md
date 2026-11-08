# Release checklist

**Owner: Arabome Obadiah Ayodeji**
**Status: Release candidate; public hosting not yet approved**

Use this checklist for the first GitHub publication and any Internet-facing deployment. A checked item means evidence exists, not just that a configuration file was added.

## Confirmed locally

- [x] Python backend regression/security suite: 16 passing tests (8 November 2026; SQLite and mocks).
- [x] Application source and environment template included.
- [x] Migration scripts and deployment smoke-check script included.
- [x] GitHub Actions workflow configured for backend, PostgreSQL and frontend jobs.

## Must be completed before calling the deployment production-ready

- [ ] Run `docker compose config` and build every service on the target machine.
- [ ] Confirm Alembic migrations on a clean PostgreSQL 16 database.
- [ ] Run the PostgreSQL incident-lifecycle integration test against that database.
- [ ] Run `npm install && npm run build` successfully; check the rendered dashboard in a browser.
- [ ] Configure HTTPS with a real owned domain and confirm certificate renewal.
- [ ] Enforce and test firewall/egress restrictions against private, local and metadata addresses.
- [ ] Rate-limit authentication requests at the edge; verify administrator/viewer boundaries.
- [ ] Replace example secrets; configure secure secret distribution and rotation.
- [ ] Rehearse PostgreSQL backup restoration on a separate database.
- [ ] Run `scripts/verify_deployment.sh https://YOUR-DOMAIN` and save the output.
- [ ] Confirm the CI jobs pass on the actual public repository.
- [ ] Run manual monitoring, failure, alert and recovery scenarios end to end.
- [ ] Establish retention, logging, monitoring-of-the-monitor and a rollback plan.

## Evidence to collect

| Check | Expected evidence |
|---|---|
| Backend tests | `pytest -q` output and revision/commit ID |
| PostgreSQL integration | CI job URL and migration output |
| Frontend | Build logs and screenshot of actual dashboard |
| Docker deployment | Compose output with secrets redacted |
| Network policy | Firewall rules plus blocked-destination test |
| Performance | Commands, hardware, dataset, raw results and date |
| Recovery | Forced failure scenario and incident timeline |

## GitHub release notes

Publish the source and documentation as a **portfolio release candidate**. Do not create a release tag named `stable` or make claims of production certification until the gates above have been checked. Do not publish `.env`, passwords, tokens, private monitoring URLs or customer data.
