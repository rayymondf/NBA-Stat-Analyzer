# NBA AI Agent Evaluation Suite

The suite checks tool choice, tool-call efficiency, report structure, evidence,
counterevidence, data scope, verdicts, and whether numbers can be traced to tool
results. Its graders are deterministic: no second model is used for judging.

## Free-tier-safe workflow

From the project root, validate all cases and tool routing without calling
Gemini:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py
```

Run one live case when you intentionally want to spend Gemini quota:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py --live --limit 1
```

Successful answers use the app's 12-hour response cache. Add `--fresh` only
when a new API response is required. Live runs are saved under `results/` and
can be graded repeatedly for free:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py --responses backend\evals\results\eval-YYYYMMDD-HHMMSS.json
```

Google applies request-per-minute, input-token-per-minute, and request-per-day
limits per project. The exact active limits vary by model and project, so check
the Rate limits page in Google AI Studio before running multiple live cases.
