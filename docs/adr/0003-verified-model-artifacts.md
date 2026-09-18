# ADR 0003: Immutable, SHA-pinned model artifacts

- Status: accepted
- Date: 2026-08-24

## Decision

Publish model releases under immutable versions with an index containing schema,
filename, size, SHA-256, and metadata. Require a configured digest for remote
bootstrap and support checking it before local promotion deserialization.

## Rationale

Model files are executable serialization boundaries. Atomic filenames alone do
not establish provenance or protect against truncation/substitution.

## Consequences

Operators must update an artifact URL/SHA pair for each release. Integrity does
not make pickle safe from an untrusted producer, so write access to the artifact
prefix remains privileged and rollback uses a prior immutable pair.
