# ADR 0001: SQLite plus a bounded decoded-object LRU

- Status: accepted
- Date: 2026-08-24

## Decision

Use SQLite WAL as the durable local response cache and a size-bounded in-process
LRU for decoded JSON. Run one API worker in the initial deployment.

## Rationale

The portfolio/local workload benefits from zero service dependencies and
durable completed-season data. SQLite provides transactional writes and easy
inspection; the LRU avoids repeatedly decoding multi-megabyte JSON.

## Consequences

Horizontal replicas do not share cache, single-flight, circuits, or rate limits.
Before scaling out, move these controls to shared infrastructure. Offline
team-season training responses do not belong in the runtime cache after durable
Parquet ingestion and have a narrow cleanup command.
