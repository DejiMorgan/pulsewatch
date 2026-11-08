# PulseWatch — Engineering case study

**Arabome Obadiah Ayodeji**
Backend engineering · Reliability engineering · Operational tooling

## The problem

An API can still return responses while becoming too slow to be useful. Failures can also be intermittent: a single timeout does not always justify an outage notification, while repeated failures should not go unnoticed. I wanted a tool that would record both performance and service health, then preserve enough history to explain when an incident began and how it ended.

## My approach

I separated the API and dashboard from the background worker responsible for scheduled probes. Each check stores its result in PostgreSQL. Incidents are driven by a consecutive-failure threshold, with recovery recorded when a check succeeds. Alert events are saved independently and delivered with retries so a notification outage does not erase incident history.

I introduced worker leases after considering how scheduling behaves when a worker crashes. I also added connect-time destination validation after examining the security risk of a server making outbound requests to user-supplied URLs.

## What the implementation currently demonstrates

- REST API design with FastAPI, typed request/response contracts and SQLAlchemy.
- Background job scheduling, leases and recovery behavior.
- Incident state changes and durable alert event records.
- Relational schema management with Alembic.
- Authentication with administrator/viewer access rules.
- Testable backend components and automated CI configurations.
- A React interface that reads real stored checks rather than hard-coded demo metrics.

## Validation

On 8 November 2026, the local backend suite completed **16 tests successfully** using the configured SQLite test database. The tests include incident behavior, account access, worker lease behavior and destination-address restrictions. The PostgreSQL CI job and browser build have been configured, but successful live execution has not been verified for this release.

I have not published a production uptime figure, throughput benchmark or third-party security assessment. Those measurements require an actual deployed environment and a documented test method.

## Open engineering work

The next steps are to validate Docker Compose and PostgreSQL in a real runtime, complete the frontend production build, enforce network-layer egress restrictions, add request throttling, and rehearse database backup restoration. Larger-scale concerns—retention policies, multiple probe regions and tenant isolation—belong to later versions.

## What I would measure next

- Check scheduling delay: actual start minus expected start.
- Incident detection delay: first failed check to incident creation.
- Alert latency: incident event creation to provider acknowledgement.
- Recovery behavior under forced worker termination.
- Query response times with increasing check-result volume.

All measurements should include the environment, sample size, command used and raw results.
