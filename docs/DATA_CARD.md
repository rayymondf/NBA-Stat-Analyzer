# Data card: NBA shot and game statistics

## Source

Statistics are returned by NBA.com endpoints through the community-maintained
`nba_api` client. This repository is not affiliated with the NBA, and the
interface is not a contracted, versioned data service. Availability, fields,
historical corrections, throttling, and terms can change.

Review NBA.com terms before redistributing derived datasets or using them
commercially. The scheduled workflow publishes model evidence by default, not
the full source dataset.

## Scope

The shot pipeline requests one team-season at a time, with `player_id=0`, then
adds the requested season and an ingestion timestamp. A normal three-season run
contains 90 expected team-season calls, including explicit empty partitions.

The checked-in legacy v2 CSV contains 657,387 rows from 2023-24, 2024-25, and
2025-26. It is useful for inspection and the existing v2 artifact, but lacks the
event/player/team identifiers required by the v3 contract. Do not present it as
a v3-reproducible source.

## v3 required fields

- Identity: `GAME_ID`, `GAME_EVENT_ID`, `PLAYER_ID`, `TEAM_ID`
- Time/context: `SEASON`, `GAME_DATE`, `PERIOD`, `MINUTES_REMAINING`,
  `SECONDS_REMAINING`, `HTM`
- Shot: `SHOT_ZONE_BASIC`, `SHOT_ZONE_AREA`, `ACTION_TYPE`, `SHOT_TYPE`,
  `SHOT_DISTANCE`, `LOC_X`, `LOC_Y`, `SHOT_MADE_FLAG`

Validation requires a semantic `YYYY-YY` season, parseable `YYYYMMDD` date,
binary target, valid shot type, nonblank categorical values, bounded numeric
coordinates/time, no critical nulls, and unique game-event identity.

## Storage and lineage

Raw partitions use:

```text
data/raw/shots/season=<season>/team_id=<id>/shots.parquet
data/raw/shots/season=<season>/team_id=<id>/partition.json
```

The sidecar records status, rows, identity, ingestion time, and SHA-256. Reuse
requires all checks to pass. Empty partitions are explicit so retries do not
loop forever.

Processed output is Hive-partitioned Parquet with an embedded `_manifest.json`.
The manifest records source checksum, schema/columns, row count, seasons,
validation report, partition columns, and an inventory/checksum of processed
files. Writes use staging and atomic replacement with rollback.

## Known quality limitations

- NBA.com can omit or revise events and occasionally changes response schemas.
- Recorded shot location/action categories are not optical tracking.
- Older seasons or special competitions may have different coverage.
- Team-season requests can overlap or duplicate if upstream identity fields are
  malformed; the build rejects duplicate game-event pairs.
- Trades and team attribution require event-level interpretation.
- Ingestion time records extraction time, not source event freshness.

## Privacy and sensitivity

The dataset contains public professional basketball records, not application
user data. Logs may contain client IP-derived rate-limit identity and query
parameters; production retention should be minimized. AI Mode separately sends
questions and selected tool results to Google when explicitly used.

## Refresh and deletion

The scheduled workflow runs weekly during October–April. Raw partitions make
the job resumable. Force refresh is explicit. Runtime cache entries used by the
old team-shot training path can be previewed and narrowly removed with
`nba-pipeline cache-prune-pipeline`; they can be re-fetched from NBA.com.
