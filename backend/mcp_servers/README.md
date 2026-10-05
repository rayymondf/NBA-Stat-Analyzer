# NBA Stat Analyzer — MCP server

Connect your AI assistant (Claude Desktop, Kiro, Cursor, …) to this project's NBA
analytics. Once connected, you can ask your assistant things like *"compare
Jokić and Embiid's shot quality this season"* and it will pull **live NBA stats**
through this server's tools instead of guessing from memory.

This is a **local** server: it runs on your own machine and your AI client
launches it as a subprocess (MCP "stdio" transport). It is read-only and needs
no API key.

---

## Quick start (download & run locally)

**Prerequisites:** [Git](https://git-scm.com/), Python 3.12, and
[uv](https://docs.astral.sh/uv/). Internet is needed the first time (dependency
install + uncached NBA.com requests).

**1. Get the code**
```bash
git clone <your-repository-url>
cd NBA-Stat-Analyzer
```

**2. Run the one-command setup**

Windows (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File backend\mcp_servers\setup.ps1
```
macOS / Linux:
```bash
bash backend/mcp_servers/setup.sh
```

This installs dependencies into `backend/.venv` and then **prints a ready-to-paste
config with the correct absolute path for your machine** — no hand-editing paths.

**3. Paste the printed config into your AI client** (details per client below),
then restart/reload the client.

> You can re-print the config at any time:
> ```
> backend/.venv/Scripts/nba-mcp-config        # Windows
> backend/.venv/bin/nba-mcp-config            # macOS / Linux
> ```

---

## Connect your client

The setup step prints the exact JSON. Here is where each client expects it.

### Claude Desktop
Edit `claude_desktop_config.json`:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Merge the printed `mcpServers` entry, then **fully quit and reopen** Claude
Desktop. The config looks like:
```json
{
  "mcpServers": {
    "nba_stats": {
      "command": "C:\\path\\to\\NBA-Stat-Analyzer\\backend\\.venv\\Scripts\\nba-mcp-stats.exe",
      "args": []
    }
  }
}
```

### Kiro
Add the entry to `.kiro/settings/mcp.json` (workspace) or
`~/.kiro/settings/mcp.json` (global). Kiro hot-reloads MCP config — no restart
needed.

### Cursor
Open Settings → MCP (or create `.cursor/mcp.json`), merge the entry, then reload
MCP servers.

---

## Verify it works

After connecting, ask your assistant: *"Use nba_stats to search for Nikola
Jokić and show his shot profile this season."* It should call `nba_search_player`
then `nba_get_shot_profile` and return real numbers.

You can also launch the server directly to confirm it starts (Ctrl+C to stop):
```
backend/.venv/Scripts/nba-mcp-stats        # Windows
backend/.venv/bin/nba-mcp-stats            # macOS / Linux
```

---

## What you can ask (the 16 tools)

| Tool | Purpose |
|------|---------|
| `nba_search_player` | Find a player's id by name (call first) |
| `nba_get_player_stats` | Aggregated stats with home/away, W/L, last-N, opponent filters |
| `nba_get_player_percentiles` | Position percentiles + advanced metrics |
| `nba_get_shot_profile` | Shooting by zone / distance vs league average |
| `nba_get_trends` | Recent form vs season baseline |
| `nba_get_career` | Season-by-season career averages |
| `nba_compare_players` | Side-by-side comparison of two players |
| `nba_league_query` | Leaders, improvers, efficient low-minute players, team defense |
| `nba_find_similar_players` | Statistically similar players |
| `nba_list_games` | Recent games (to get a game_id) |
| `nba_investigate_game` | Why a game was won/lost, with evidence |
| `nba_get_game_log` | Recent game-by-game lines |
| `nba_get_on_off_impact` | On/off net-rating estimate |
| `nba_get_elimination_game_stats` | Playoff elimination-game performance |
| `nba_get_shot_quality` | xFG shot-quality model estimate (labelled as a model estimate) |
| `nba_get_previous_season` | Previous season string helper |

Every tool accepts `response_format` = `json` (default) or `markdown`.

---

## Troubleshooting

- **Client shows no tools / server failed to start.** Make sure setup finished
  (`backend/.venv` exists) and the path in your config matches the one
  `nba-mcp-config` printed. Re-run the config generator if you moved the folder.
- **`uv: command not found`.** Install uv (<https://docs.astral.sh/uv/>) and
  re-run setup.
- **First call is slow.** Uncached NBA.com requests populate a local cache on
  first use; repeat calls are fast.
- **Client doesn't support local servers.** Some MCP clients are remote-only;
  use one that supports local/stdio servers (Claude Desktop, Kiro, Cursor do).

---

## How it works (brief)

The server reuses this project's backend: the same cached, rate-limited NBA.com
client and the same computed statistics the web app uses. Your assistant
orchestrates the tools; **every number comes from NBA.com data this project
computed**, never from the model's memory.

This local (stdio) setup is for individual use. Making the server available to
others over a URL would require hosting it with the streamable-HTTP transport
plus authentication and rate limiting — out of scope here.

See the full tool/design notes inline in `nba_mcp/nba_stats.py`.
