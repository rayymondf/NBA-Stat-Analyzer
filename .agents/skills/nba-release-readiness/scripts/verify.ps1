param(
    [switch]$Container
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$Backend = Join-Path $RepoRoot "backend"
$Frontend = Join-Path $RepoRoot "frontend"
$VenvScripts = Join-Path $Backend ".venv\Scripts"
$OpenApi = Join-Path $Backend "openapi.json"
$GeneratedTypes = Join-Path $Frontend "src\lib\schema.d.ts"
$OpenApiBefore = (Get-FileHash -Algorithm SHA256 $OpenApi).Hash
$GeneratedTypesBefore = (Get-FileHash -Algorithm SHA256 $GeneratedTypes).Hash

Push-Location $Backend
try {
    $UvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($UvCommand) {
        & $UvCommand.Source lock --check
    } else {
        & (Join-Path $VenvScripts "python.exe") -m uv lock --check
    }
    if ($LASTEXITCODE -ne 0) { throw "uv lock check failed." }
    & (Join-Path $VenvScripts "ruff.exe") check app scripts tests load
    if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }
    & (Join-Path $VenvScripts "mypy.exe") app
    if ($LASTEXITCODE -ne 0) { throw "Mypy failed." }
    & (Join-Path $VenvScripts "pytest.exe") --cov=app --cov-report=term-missing
    if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }
    & (Join-Path $VenvScripts "python.exe") scripts/export_openapi.py
    if ($LASTEXITCODE -ne 0) { throw "OpenAPI export failed." }
} finally {
    Pop-Location
}

Push-Location $Frontend
try {
    npm run generate:api
    if ($LASTEXITCODE -ne 0) { throw "OpenAPI TypeScript generation failed." }
    npm audit --audit-level=high
    if ($LASTEXITCODE -ne 0) { throw "npm audit failed." }
    npm run lint -- --deny-warnings
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
    npm test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Pop-Location
}

if ((Get-FileHash -Algorithm SHA256 $OpenApi).Hash -ne $OpenApiBefore) {
    throw "backend/openapi.json was stale; regenerate and commit it."
}
if ((Get-FileHash -Algorithm SHA256 $GeneratedTypes).Hash -ne $GeneratedTypesBefore) {
    throw "frontend/src/lib/schema.d.ts was stale; regenerate and commit it."
}

git -C $RepoRoot diff --check
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed." }
if ($Container) {
    docker build -t nba-stat-analyzer:verify $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw "Container build failed." }
}

Write-Host "All requested release gates passed."
