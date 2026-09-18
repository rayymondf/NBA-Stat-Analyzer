---
name: nba-security-audit
description: Threat-model or security-review the public NBA Stat Analyzer, its FastAPI/React/AI endpoints, dependencies, model artifacts, CI, or deployment. Use for security audits and hardening; not for generic correctness review.
---

# NBA security audit

When delegation is available, use `security_reviewer` for a read-only evidence pass. Keep remediation decisions and verification in the primary thread.

Review these trust boundaries:

- Anonymous browser to FastAPI, including validation, rate/cost limits, error disclosure, CORS, host/proxy handling, and denial of service.
- FastAPI to NBA.com and Gemini, including timeouts, retries, circuit state, fan-out budgets, prompt/tool boundaries, and secret-safe logs.
- CI/object storage to runtime model, including immutable versions, pinned SHA-256, maximum sizes, atomic transport, safe deserialization assumptions, and rollback.
- Source/dependencies/build output, including lockfiles, audits, least-privilege workflow permissions, container user, and secret scanning.

Rank evidence by exploitability and impact. Add regression tests for fixed boundaries. Do not claim protection is distributed across replicas when enforcement is process-local; document the required edge/shared control.
