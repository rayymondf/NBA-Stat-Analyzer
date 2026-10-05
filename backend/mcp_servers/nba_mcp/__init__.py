"""MCP server(s) for the NBA Stat Analyzer.

Exposes this project's NBA analytics as Model Context Protocol tools, reusing the
existing (already cached, rate-limited, input-validated) backend logic instead of
reimplementing NBA access:

- ``nba_mcp.nba_stats`` — read-only NBA statistics tools (wraps ``app.ai.tools``).

The server is runnable over stdio (``python -m nba_mcp.nba_stats``) and can be
registered in any MCP client (Claude Desktop, Kiro, Cursor, ...), letting that
client's assistant pull live NBA statistics and analysis on demand.
"""

__all__ = ["nba_stats"]
