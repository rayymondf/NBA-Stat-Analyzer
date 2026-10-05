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

The shot pipeline requests one team-season-type at a time, with `player_id=0`,
then tags each shot with its season and season type and adds an ingestion
timestamp. It ingests **both Regular Season and Playoffs** (preseason is
intentionally excluded). A three-season run therefore makes up to 180 team
requests (30 teams x 3 seasons x 2 season types), including explicit empty
partitions for the ~14 teams per season that miss the playoffs.

The current processed dataset is `shots-v1-426fd715aa4e`: 700,077 shots across
2023-24, 2024-25, and 2025-26, with regular season (218,700 / 219,527 / 219,160)
and playoffs (13,840 / 14,377 / 14,473) tagged by `SEASON_TYPE`.

The checked-in legacy v2 CSV contains 657,387 regular-season rows and lacks the
event/player/team identifiers and playoff coverage of the current contract. It
is useful for inspection and the existing v2 artifact; do not present it as a
reproducible source for the current dataset.

## v3 required fields

- Identity: `GAME_ID`, `GAME_EVENT_ID`, `PLAYER_ID`, `TEAM_ID`
- Time/context: `SEASON`, `SEASON_TYPE`, `GAME_DATE`, `PERIOD`,
  `MINUTES_REMAINING`, `SECONDS_REMAINING`, `HTM`
- Shot: `SHOT_ZONE_BASIC`, `SHOT_ZONE_AREA`, `ACTION_TYPE`, `SHOT_TYPE`,
  `SHOT_DISTANCE`, `LOC_X`, `LOC_Y`, `SHOT_MADE_FLAG`

Validation requires a semantic `YYYY-YY` season, parseable `YYYYMMDD` date,
binary target, valid shot type, nonblank categorical values, bounded numeric
coordinates/time, no critical nulls, and unique game-event identity.

## Storage and lineage

Raw partitions use:

```text
data/raw/shots/season=<season>/season_type=<regular-season|playoffs>/team_id=<id>/shots.parquet
data/raw/shots/season=<season>/season_type=<regular-season|playoffs>/team_id=<id>/partition.json
```

The sidecar records status, rows, identity (season, season type, team), ingestion
time, byte size, mtime, and SHA-256. Reuse first trusts a fast size+mtime+rows
fingerprint and falls back to a full checksum + column re-read only on mismatch,
so resuming a run does not re-hash the whole corpus. Empty partitions are
explicit so retries do not loop forever.

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

The 2026–27 regular-season shot partition is deferred until the October 20
opening date. Preseason statistics are available in the app but are never mixed
into the regular-season xFG training dataset. If NBA.com times out during a
pipeline run, the job fails and uploads `ingestion.json` with failed partitions;
the run does not publish a candidate from incomplete data.

Player-facing current-season statistics use a separate 12-hour cache refresh
policy. The weekly pipeline schedule governs the versioned training dataset and
model evidence, not the player-facing statistics cache.
