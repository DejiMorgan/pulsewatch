# Engineering decisions

**Recorded by Arabome Obadiah Ayodeji**

## 001 — Run checks outside the FastAPI request process

**Decision:** A dedicated worker executes scheduled checks and alert delivery.

**Reason:** Monitoring should continue regardless of dashboard traffic. Outbound timeouts should not occupy API request handlers or rely on a request remaining active.

**Tradeoff:** More moving parts and coordination around schedules, worker crashes and retries.

## 002 — Store check results in PostgreSQL

**Decision:** Use ordinary relational tables with indexes and migrations rather than introducing a separate metrics database in the initial version.

**Reason:** It keeps the first release operationally manageable and makes incident records and checks easy to join.

**Tradeoff:** Table growth and retention become important. Partitioning and rollups may be necessary with many monitors.

## 003 — Lease scheduled work

**Decision:** Scheduled probes use expiring claims, and stale work cannot overwrite a newer claim.

**Reason:** A worker may terminate after claiming a task. Leases allow recovery without a permanently stuck monitor.

**Tradeoff:** Leases do not guarantee exactly-once network calls. Idempotency must be considered at the persistence boundary.

## 004 — Treat external notifications as at least once

**Decision:** Persist alert events alongside incident transitions and retry delivery separately.

**Reason:** Notification systems fail independently of the monitoring database.

**Tradeoff:** A crash after delivery but before acknowledging it may produce a duplicate email or webhook request.

## 005 — Limit destination addresses at connection time

**Decision:** Validate public addresses when the connection is made and disable redirects and ambient proxy settings.

**Reason:** Checking a hostname only when a monitor is saved is insufficient because DNS answers can change.

**Tradeoff:** Transport code depends on tested `httpx`/`httpcore` internals. Isolation at the network layer remains mandatory.

## 006 — Shared workspace before multi-tenancy

**Decision:** Implement administrator/viewer authorization but no organization separation.

**Reason:** The early project focuses on monitoring correctness, incident transitions and deployability.

**Tradeoff:** It must not be marketed as multi-tenant SaaS. Tenant boundaries, billing, audit logs and account lifecycle are separate work.
