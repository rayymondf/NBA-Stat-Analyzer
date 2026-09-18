$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js 24 and npm are required."
}

Push-Location (Join-Path $RepoRoot "backend")
try {
    uv sync --locked --extra dev
} finally {
    Pop-Location
}

Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm ci
    npm run build
} finally {
    Pop-Location
}

Write-Host "Setup complete. Run .\start-app.bat and open http://localhost:8000."
