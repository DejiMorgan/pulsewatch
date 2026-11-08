# Security policy

**Maintainer: Arabome Obadiah Ayodeji**

PulseWatch is currently a portfolio release candidate, not a hosted production service with a published security support commitment.

For private vulnerability reports, contact the project maintainer through the private reporting option on the repository once it is enabled. Avoid posting exploit details or credentials in a public issue. No security email address is listed until a verified contact channel is available.

## Important operating assumptions

The worker makes outbound requests to registered URLs. Even with public-IP validation and redirects disabled, administrators deploying the system must enforce a separate deny policy for internal and metadata networks at the firewall or egress gateway. Do not use this release for arbitrary untrusted users.

The application has a shared workspace, bearer-token sessions and baseline account lockouts. It lacks MFA, tenant isolation, strong distributed login throttling and a completed production security assessment. Never commit `.env` or credentials.

See `PHASE6_VALIDATION.md` for validation instructions and a more detailed risk register.
