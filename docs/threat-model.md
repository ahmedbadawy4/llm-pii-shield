# Threat Model

This project assumes the LLM is untrusted with raw customer data. The shield reduces risk by redacting PII, enforcing minimal policy gates, and emitting audit-safe signals for monitoring.

Attack scenarios and mitigations
--------------------------------
1) Prompt injection via documents or user input
- Scenario: A contract or invoice includes instructions to disclose secrets or bypass rules.
- Mitigation: Only user messages are sent after redaction; keep system prompts immutable outside the user payload; restrict model usage with allowlists; monitor for anomalies in request metadata.

2) PII leakage into prompts, logs, or downstream systems
- Scenario: Emails, phone numbers, or identifiers leak into LLM prompts or audit logs.
- Mitigation: Regex-based redaction before forwarding; metadata-only logging; audit DB stores types and lengths only.

3) Unauthorized model usage
- Scenario: Requests route to unapproved models or endpoints.
- Mitigation: Optional `ALLOWED_MODELS` policy gate; environment-controlled provider configuration.

4) Upstream provider instability or errors
- Scenario: High latency or errors cause retries that leak data or mask failures.
- Mitigation: Prometheus metrics for latency and errors; structured logs with request IDs for tracing; alert on error rate and p99 latency.

5) Abuse of admin endpoints
- Scenario: `GET /admin/stats` is exposed publicly.
- Mitigation: Disabled unless `ADMIN_API_KEY` is set; constant-time key comparison; keep endpoint behind internal networking in production.

Notes and assumptions
---------------------
- Regex-based detection is a baseline; expect false positives/negatives.
- The shield does not yet classify or block content beyond the allowlist policy.
- Responses from the upstream model are returned as-is; downstream services should apply additional safety controls if needed.
