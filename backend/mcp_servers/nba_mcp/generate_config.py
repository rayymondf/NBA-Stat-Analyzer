#!/usr/bin/env python3
"""Generate a ready-to-paste MCP client config for *this* machine.

The hardest part of connecting a local (stdio) MCP server is that each client
config needs the absolute path to the server executable on the user's own
machine. This helper detects that path from the running interpreter and prints a
correct config, so a user never hand-edits a path.

Usage (from an activated backend venv, or via the console script):

    python -m nba_mcp.generate_config            # prints config for all clients
    python -m nba_mcp.generate_config --client claude
    python -m nba_mcp.generate_config --client kiro
    python -m nba_mcp.generate_config --client cursor

It prints JSON plus a short note on where each client expects it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def server_command() -> str:
    """Absolute path to the installed ``nba-mcp-stats`` console script.

    Resolved from the current interpreter's Scripts/bin directory so the path is
    always correct for the machine running this helper. Falls back to the module
    invocation if the console script is not found.
    """
    exe_dir = Path(sys.executable).resolve().parent
    candidates = [
        exe_dir / "nba-mcp-stats.exe",   # Windows
        exe_dir / "nba-mcp-stats",       # POSIX
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    # Fallback: run the module with this interpreter (also fully portable).
    return str(Path(sys.executable).resolve())


def _entry() -> tuple[str, dict]:
    """Return (command, server-entry) using the console script when available,
    otherwise the ``python -m`` fallback with explicit args."""
    exe_dir = Path(sys.executable).resolve().parent
    script = exe_dir / ("nba-mcp-stats.exe" if sys.platform == "win32" else "nba-mcp-stats")
    if script.exists():
        return str(script), {"command": str(script), "args": []}
    # Portable fallback: this interpreter + module.
    return str(sys.executable), {
        "command": str(Path(sys.executable).resolve()),
        "args": ["-m", "nba_mcp.nba_stats"],
    }


def build_config() -> dict:
    _, entry = _entry()
    return {"mcpServers": {"nba_stats": entry}}


_CLIENT_NOTES = {
    "claude": (
        "Claude Desktop — add to claude_desktop_config.json\n"
        "  Windows: %APPDATA%\\Claude\\claude_desktop_config.json\n"
        "  macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json\n"
        "Merge the 'mcpServers' entry below, then fully restart Claude Desktop."
    ),
    "kiro": (
        "Kiro — add to .kiro/settings/mcp.json (workspace) or ~/.kiro/settings/mcp.json (global).\n"
        "Merge the 'mcpServers' entry below. Kiro hot-reloads MCP config."
    ),
    "cursor": (
        "Cursor — Settings > MCP (or .cursor/mcp.json).\n"
        "Merge the 'mcpServers' entry below, then reload the MCP servers."
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nba-mcp-config",
        description="Print a ready-to-paste MCP client config for this machine.",
    )
    parser.add_argument(
        "--client",
        choices=["claude", "kiro", "cursor", "all"],
        default="all",
        help="Which client to print setup notes for (default: all).",
    )
    args = parser.parse_args(argv)

    config = build_config()
    config_json = json.dumps(config, indent=2)

    clients = ["claude", "kiro", "cursor"] if args.client == "all" else [args.client]

    print("=" * 72)
    print("NBA Stat Analyzer — MCP client config (generated for THIS machine)")
    print("=" * 72)
    print()
    print("Server executable resolved to:")
    print("  " + server_command())
    print()
    for client in clients:
        print("-" * 72)
        print(_CLIENT_NOTES[client])
        print()
        print(config_json)
        print()
    print("-" * 72)
    print("nba_stats is read-only and needs no API key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
