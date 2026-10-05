#!/usr/bin/env bash
# NBA Stat Analyzer — MCP server setup (macOS / Linux)
#
# One-command local setup for the nba_stats MCP server. Run from anywhere:
#   bash backend/mcp_servers/setup.sh
#
# It installs the backend + MCP dependencies into backend/.venv, then prints a
# ready-to-paste client config with the correct absolute path for THIS machine.
set -euo pipefail

# Resolve the backend directory relative to this script
# (.../backend/mcp_servers/setup.sh -> .../backend)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
echo "Backend directory: $BACKEND_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is not installed. Install it from https://docs.astral.sh/uv/ and re-run." >&2
  exit 1
fi

cd "$BACKEND_DIR"

echo
echo "Installing dependencies (uv sync --extra mcp)…"
uv sync --extra mcp

echo
echo "Generating your MCP client config…"
echo
"$BACKEND_DIR/.venv/bin/nba-mcp-config"

echo
echo "Done. Copy the 'mcpServers' entry above into your MCP client config."
