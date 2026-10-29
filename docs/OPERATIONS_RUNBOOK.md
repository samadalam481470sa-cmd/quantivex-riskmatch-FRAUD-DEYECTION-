# Quantivex RiskMesh restricted-mode operations runbook

**Scope:** single-node **reference** deployment for controlled testing. It is
NOT a production-ready financial-data service. Never use real financial records
without independent security/privacy approval and legal authorization.

## Provisioning

1. Provision a private host, restrict inbound access to a trusted TLS gateway,
   use an encrypted disk, and allow outbound HTTPS only to the trusted OIDC
   JWKS endpoint. Do not publish port 8000 directly.
2. Configure a real OIDC provider issuing RS256 access tokens with
   `tenant_id` and `riskmesh_role` claims; set issuer, audience and JWKS URL.
3. Supply a random 32+ character API key and a fixed tenant identifier through
   your secret manager. The API key is only a startup guard in restricted mode;
   access tokens authenticate API requests.
4. The nonroot container UID is 65532. The persistent data volume must be
   writable by UID 65532 before first startup. **Do not chmod 777**.
   A host bind mount with ownership 65532:65532 is easier to audit than a
   Docker-managed volume; the example named volume may require an explicit
   one-time ownership initialization before it can start.
5. Run `docker compose -f ops/compose.restricted.yml config` to validate
   environment substitution, then `docker compose -f ops/compose.restricted.yml up --build -d`.
   Do not set `RISK_MESH_ENABLE_DEMO=true`.
6. Verify /health through the private gateway and run authenticated smoke
   tests using a short-lived analyst token. Verify an unauthorized tenant
   receives 403 and an unsigned request receives 401.

## Monitoring

Collect the admin-protected /internal/metrics endpoint through a private
scraper with a short-lived admin token. The provided alert rules cover
server-error ratio and missing metrics; wire them into your own Prometheus
and Alertmanager installation. Scrape credentials must never be placed in a
public Prometheus config. These metrics are in-memory and reset on restart.

## Backup and restore

SQLite is not a distributed/HA database. Schedule encrypted snapshots using
the SQLite online backup API or `VACUUM INTO` from a controlled maintenance
process, not a naive copy of a live WAL file. Protect backups and retention
keys, periodically test restoration to an isolated host, verify transaction
counts, then destroy test data securely. No backup job or restore drill has
been executed by this repository.

## Incident response

If a signing key or OIDC issuer is compromised, disable ingress, revoke and
rotate credentials, capture sanitized logs and immutable infrastructure
evidence, then restore only after validation. For model anomalies, disable
ML-based enforcement (the current endpoint is shadow-only), preserve labeled
cases, compare against a frozen baseline and roll back the model artifact.

## Release acceptance

Do not declare production readiness until OIDC integration tests against the
real issuer, penetration testing, load testing, persistent-storage recovery,
secrets rotation, monitoring alerts, independent fraud-model evaluation, and
privacy/regulatory review have all passed and are recorded.
