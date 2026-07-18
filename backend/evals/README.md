# AI evaluation suite

This suite evaluates whether AI Mode selects appropriate statistical tools and
returns a useful, numerically grounded report. The graders are deterministic
Python code; no second language model judges the answers.

The suite covers ten representative investigations defined in `cases.json`,
including player analysis, measurable and unsupported claims, comparisons,
games, league leaders, statistical similarity, on/off caveats, and filtered
small samples.

## What is checked

Each case defines a tool policy and report policy. The graders check:

- required, acceptable-alternative, and forbidden tool calls;
- the maximum tool-call count and accidental duplicate calls;
- whether the selected explicit mode exposes the tools required by the case;
- structured report fields, verdict use, evidence, counterevidence, data scope,
  confidence, and entity links;
- whether numeric claims in the answer and findings can be matched to values in
  the captured tool results;
- token-usage, elapsed-time, and cache metadata are recorded when a live
  response supplies them.

These checks detect many grounding and orchestration failures, but they are not
a complete measure of basketball correctness or writing quality. A passing live
report still deserves human review.

## Quota-safe default workflow

Run from the repository root:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py
```

This validates all case definitions and verifies their tool routing. It does
**not** call Gemini, fetch NBA data, or consume AI quota.

The equivalent unit-test coverage can be run with the rest of the backend tests:

```powershell
backend\venv\Scripts\python.exe -m unittest discover -s backend\tests
```

## Run a live case deliberately

Live mode calls the configured Gemini model and may also trigger uncached NBA
requests through the tools the model selects. Start with one case:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py --live --limit 1
```

Or select a known case ID:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py --live --case player_recent_trend
```

Successful AI answers normally reuse the application's response cache. Add
`--fresh` only when a newly generated response is the point of the test:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py --live --case player_recent_trend --fresh
```

`--fresh` disables AI response-cache reads and writes for that evaluation
process, so it consumes a new Gemini request without deleting `cache.sqlite`.

Google applies model- and project-specific request and token limits. Check the
limits shown for your project in Google AI Studio before increasing the number
of live cases.

## Saved results and free re-grading

Live runs are saved as JSON under `backend/evals/results/` unless `--output`
specifies another path. The default result files are ignored by git and include
the case, report, tool trace, grade, summary, and run metadata.

Re-run the deterministic graders without another Gemini call:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py --responses backend\evals\results\eval-YYYYMMDD-HHMMSS.json
```

## Command-line reference

| Option | Meaning |
|---|---|
| no option | Validate cases and mode-to-tool routing only; no remote calls |
| `--live` | Generate and grade reports with Gemini |
| `--responses PATH` | Re-grade a previously saved live result |
| `--case ID` | Select one case; repeat the option to select several |
| `--limit N` | Restrict the number of selected cases |
| `--delay SECONDS` | Delay between live cases; default is 15 seconds |
| `--fresh` | Bypass reuse of an existing AI answer for this run |
| `--output PATH` | Choose the JSON output path for a live run |

`--live` and `--responses` are mutually exclusive. The process exits with code
0 when validation or every available grade passes, and 1 when a validation or
grade fails.

## Files

| File | Responsibility |
|---|---|
| `cases.json` | Questions, modes, tool policies, and report policies |
| `graders.py` | Deterministic validation, grounding checks, and summaries |
| `run_evals.py` | CLI, live execution, saving, and re-grading |
| `results/` | Ignored live-run output directory |
| `../tests/test_ai_evals.py` | Unit tests for the grader and committed cases |
| `../tests/test_ai_orchestrator.py` | Unit tests for routing, caching, and response parsing |

When adding an AI tool, update its mode routing where appropriate, add or revise
cases that exercise it, and run both the default suite and backend unit tests.
