# Threat model

## Assets and trust boundaries

Assets are the Gemini key/quota, model integrity, artifact-store credentials,
service availability, cached NBA/AI payloads, and accuracy/provenance evidence.
Trust boundaries exist at the public browser/API, NBA.com, Google Gemini,
S3-compatible artifact storage, CI secrets, and joblib deserialization.

The app has no accounts or write API. Public deployment should be treated as an
anonymous read service with optional quota-consuming AI.

## Main threats and controls

| Threat | Existing controls | Residual risk / next step |
|---|---|---|
| Resource exhaustion | Route-class sliding-window limits, actual-byte request cap, bounded cache, GZip, upstream/AI concurrency and timeout budgets, circuit, single-flight | Limits are process-local; use Redis/API gateway for replicas |
| Cache stampede | Per-key ref-counted lock and second cache check | One process only |
| Upstream outage/details leak | Bounded stale-if-error, problem details, generic 502, structured logging | NBA.com remains an unofficial dependency |
| Host/CORS abuse | Trusted-host middleware and exact CORS allowlist | Configure exact production domain |
| Injection/path traversal | Typed/semantic query validation, safe SPA path resolution, read-only single-statement DuckDB guard | Reassess if arbitrary SQL becomes public |
| Artifact substitution | Pinned SHA-256, schema/name/size validation, atomic download | A malicious trusted producer can still create unsafe pickle |
| Partial/corrupt data | Partition checksums/status, full validation, processed inventory, atomic swap/rollback | Source correctness is not cryptographically attested by NBA.com |
| AI prompt/tool misuse | Fixed tool registry, semantic tool-argument validation, structured result, bounded calls/tokens/concurrency/global budget, safe error surface | Generated text can still be wrong; protect quota and review claims |
| Secret exposure | `.env` ignored, no secrets in image/workflows, dashboard/GitHub secrets | Add automated secret scanning/rotation policy in hosted repo |
| Dependency compromise | Exact locks, Dependabot, `npm audit`, CodeQL, CI rebuild, GHCR provenance | Add image/SBOM scanning |
| Cross-site embedding/MIME | frame deny, nosniff, referrer/permissions policies | A strict CSP needs UI inline-style refactoring first |

## Abuse cases

- Repeated player/foul/investigation requests can cause fan-out; expensive routes
  use a lower bucket and the client deduplicates identical calls.
- Changing query order cannot create duplicate keys because cache parameters are
  sorted.
- User-supplied request IDs are accepted only from a short safe character set.
- The dataset route can transfer a large file; it is expensive-rate-limited and
  can redirect to object storage.
- Unknown `/api` paths return JSON 404 rather than the SPA shell.

## Deployment checklist

- Set exact trusted hosts/CORS origins and disable API docs if not wanted.
- Put TLS and an external request-size/rate limit at the edge.
- Keep AI disabled without authentication or a strict quota budget.
- Pin the model digest; never load an artifact from an untrusted contributor.
- Restrict object-store credentials to one prefix and separate read/write roles.
- Review logs for secrets/questions and set retention.
- Run dependency, container, and secret scanning on releases.

## Accepted constraints

SQLite, process-local throttles, and no authentication are accepted for the
single-instance portfolio deployment. They are explicitly not sufficient for a
multi-tenant or horizontally scaled production service.
