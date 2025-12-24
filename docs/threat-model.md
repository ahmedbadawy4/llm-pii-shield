# Threat Model (Short)

This project is a best-effort PII gateway. It reduces risk but does not eliminate it.

## Assets
- Prompts and model outputs (may contain PII).
- Redacted PII metadata and audit logs.
- Admin endpoint and admin API key.
- Service availability and configuration.

## Threats
- Prompt leakage to upstream LLM if redaction misses patterns.
- Log leakage or unintended retention of sensitive metadata.
- Header spoofing to access `/admin/stats`.
- Injection/bypass attempts via obfuscated PII or non-user roles.
- SSRF/egress abuse by proxying to untrusted endpoints.
- Sensitive data retention in local volumes/backups.

## Mitigations
- Redaction on user content before proxying; keep patterns updated.
- Metadata-only logging by default; secure logs/DB at rest.
- Admin stats protected by `ADMIN_API_KEY` and `X-Admin-Key`.
- Least-privilege runtime, rate limiting (recommended), and TLS.
- Network egress controls on the proxy target (recommended).
- Secret management via Kubernetes Secrets or env injection (not plaintext in charts).

## Non-goals
- Perfect PII detection or compliance guarantees.
- Defending against a fully compromised host or cluster.
- Preventing all misuse of upstream model behavior.
