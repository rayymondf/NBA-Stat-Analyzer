# NBA Stat Analyzer — MCP server setup (Windows / PowerShell)
#
# One-command local setup for the nba_stats MCP server. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File backend\mcp_servers\setup.ps1
#
# It installs the backend + MCP dependencies into backend\.venv, then prints a
# ready-to-paste client config with the correct absolute path for THIS machine.

$ErrorActionPreference = "Stop"

# Resolve the backend directory relative to this script (…\backend\mcp_servers\setup.ps1 -> …\backend)
$BackendDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Write-Host "Backend directory: $BackendDir"

# Require uv.
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. Install it from https://docs.astral.sh/uv/ and re-run."
    exit 1
}

Push-Location $BackendDir
try {
    Write-Host "`nInstalling dependencies (uv sync --extra mcp)…" -ForegroundColor Cyan
    uv sync --extra mcp
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit code $LASTEXITCODE" }

    Write-Host "`nGenerating your MCP client config…`n" -ForegroundColor Cyan
    & "$BackendDir\.venv\Scripts\nba-mcp-config.exe"
}
finally {
    Pop-Location
}

Write-Host "`nDone. Copy the 'mcpServers' entry above into your MCP client config." -ForegroundColor Green
