"""Shared helpers for the NBA MCP servers.

Centralizes the three things both servers need so neither duplicates logic
(mcp-builder DRY guidance):

1. Making this project's ``app`` package importable when the MCP server is
   launched from an arbitrary working directory by an MCP client.
2. A single, consistent response-format option (JSON vs Markdown).
3. One actionable error formatter shared by every tool.

The MCP tools themselves are thin: all NBA access, caching, rate limiting,
circuit breaking, input validation and token trimming already live in
``app.ai.tools`` / ``app.ai.orchestrator`` and are reused verbatim.
"""
from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any


def ensure_app_importable() -> Path:
    """Put the project's ``backend`` directory on ``sys.path``.

    An MCP client may spawn the server with any current working directory, so we
    resolve the backend root relative to this file (``backend/mcp_servers/nba_mcp/_common.py``
    -> ``backend``) and prepend it to ``sys.path`` if ``app`` is not already
    importable. Returns the backend path for callers that need it.
    """
    backend_root = Path(__file__).resolve().parents[2]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    return backend_root


class ResponseFormat(str, Enum):
    """Output format for tool responses.

    ``json`` returns complete structured data for programmatic use; ``markdown``
    returns a compact human-readable rendering. Default is ``json`` because MCP
    clients usually re-render structured data themselves.
    """

    JSON = "json"
    MARKDOWN = "markdown"


def to_json(payload: Any) -> str:
    """Serialize a tool result to indented JSON with stable key order."""
    return json.dumps(payload, indent=2, sort_keys=False, default=str)


def handle_tool_error(exc: Exception) -> str:
    """Map an exception from the wrapped backend into an actionable message.

    The wrapped ``app.ai.tools`` functions raise ``ValueError`` for bad input
    (e.g. a malformed season or out-of-range id) with a message already written
    for a caller, so we surface those directly. Everything else is reported with
    its type so an agent can decide whether to retry or adjust arguments.
    """
    if isinstance(exc, ValueError):
        return f"Error: {exc}"
    if isinstance(exc, (TimeoutError,)):
        return "Error: NBA.com request timed out. The upstream is slow or rate limited; try again shortly."
    name = type(exc).__name__
    message = str(exc).strip()
    if message:
        return f"Error: {name}: {message}"
    return f"Error: {name} occurred while contacting NBA.com. Try again shortly."


def markdown_kv(title: str, data: dict[str, Any]) -> str:
    """Render a flat dict as a small Markdown section (best-effort, shallow)."""
    lines = [f"# {title}", ""]
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            lines.append(f"- **{key}**: `{json.dumps(value, default=str)}`")
        else:
            lines.append(f"- **{key}**: {value}")
    return "\n".join(lines)
