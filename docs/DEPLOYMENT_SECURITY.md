# Deployment security and readiness gate

**Status: preproduction security reference.** These controls are not an audit,
SOC 2 certification, PCI assessment, regulatory approval, or validation on real fraud data.

## Identity

In `RISK_MESH_ENV=production`, API-key access is replaced by verified OIDC
bearer access tokens. Configure `RISK_MESH_OIDC_ISSUER`,
`RISK_MESH_OIDC_AUDIENCE`, and `RISK_MESH_OIDC_JWKS_URL` to trusted
HTTPS values. Tokens require RS256 signatures, issuer, audience, expiration,
issued-at, subject, `tenant_id`, and `riskmesh_role` claims. Allowed roles:
viewer, analyst, admin. API scoring endpoints require analyst or admin;
internal metrics require admin. The tenant claim must match the fixed
`RISK_MESH_TENANT_ID`. API-key fallback is disabled in restricted mode.

The configured OIDC identity provider must issue access tokens with these
claims; this repository does not provision or operate an identity provider.
Use a dedicated issuer and audience, protected JWKS endpoint, short-lived
tokens, MFA, rotation and incident revocation procedures.

## Deployment

- Terminate TLS at a trusted gateway; deny public access to /internal/metrics.
- Use a private container network, restrictive egress and service firewall.
- Supply all credentials through a managed secret store; never commit secrets.
- Mount persistent encrypted storage outside /tmp and arrange tested backups.
- Run a nonroot container with a read-only root filesystem and minimal privileges.
- Configure resource limits, health checks, vulnerability scanning, signed builds,
  dependency pinning, SBOM, logging, alerts and a recovery runbook.
- Current SQLite is a local/single-instance database, not an HA datastore.
  PostgreSQL, schema migrations and disaster recovery are still required.
- The application is not a PCI-scoped payment processor and must not handle
  raw cardholder data.

## Observability

The `/internal/metrics` endpoint exposes bounded request counters grouped
by known route and status class. It does not include tenant IDs, account IDs,
raw paths, IP addresses, or transaction payloads. Integrate the endpoint with
a protected metrics collector and alerting service. Counters are process-local
and reset on restart. Add distributed tracing, structured logs, SLOs, storage
metrics and production alerts before a real deployment.

## Data protection

Security headers and no-store cache behavior are enabled. Signed decisions
and authenticated ML model artifacts detect modification when their HMAC
secrets remain protected. Current storage is plaintext SQLite and lacks
field-level encryption, data retention/deletion policies, backups, and audited
KMS-managed key rotation. These are mandatory blockers for real customer data.

## Fraud-model validation

See [MODEL_VALIDATION.md](MODEL_VALIDATION.md). Independent validation must
be conducted with legally obtained, representative and temporally separated
real-world labeled data, with an evaluator who did not train the model.
No real-world validation has been completed here.
