# Sia - What We Built

## Summary

Sia is now an MCP server that connects Claude Code to a control plane for observability. When you use Claude Code with Sia configured, all `sia_*` tool calls are logged and visible in a real-time UI.

---

## Architecture

```
Claude Code (your normal CLI)
       │
       │ MCP protocol (stdio)
       ▼
Sia MCP Server (`sia mcp`)
       │
       │ HTTP
       ▼
Sia Control Plane (`sia start`)
       │
       ▼
Frontend UI (React)
```

---

## What Changed (This Session)

1. **Removed `SiaAgent` wrapper** - No longer wrapping the Claude SDK
2. **Added MCP server** (`mcp.py`) - Provides tools to Claude Code via MCP protocol
3. **Added `sia mcp` command** - Starts the MCP server
4. **Updated models** - Added `source` field to track agent origin (mcp/sdk)
5. **Updated frontend** - Shows MCP setup instructions, displays agent source

---

## Files

### Backend (`backend/src/sia/`)

| File | Purpose |
|------|---------|
| `mcp.py` | MCP server - provides sia_* tools to Claude Code |
| `main.py` | FastAPI control plane API |
| `registry.py` | In-memory agent store |
| `models.py` | Pydantic models |
| `cli.py` | CLI with `start` and `mcp` commands |
| `__init__.py` | Package exports |

### Frontend (`frontend/src/`)

| File | Purpose |
|------|---------|
| `App.tsx` | Observability UI |
| `App.css` | Dark theme styling |

---

## Installation (New Repo)

### 1. Install Sia

```bash
# Clone or copy the Sia project
cd path/to/sia/backend

# Install in editable mode
pip install -e .
```

### 2. Start Control Plane

```bash
# Terminal 1
sia start
```

Opens browser to http://localhost:8000 with the UI.

### 3. Configure Claude Code

Add to your Claude Code config (`~/.claude.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "sia": {
      "command": "sia",
      "args": ["mcp"]
    }
  }
}
```

### 4. Use Claude Code

```bash
# Terminal 2 - in any repo
claude
```

Claude Code now has these tools available:
- `sia_echo` - Test connection
- `sia_read_file` - Read files (logged)
- `sia_write_file` - Write files (logged)
- `sia_run_command` - Run commands (logged)

All tool calls appear in the Sia UI in real-time.

---

## Testing the MVP

### Quick Test

1. Start control plane: `sia start`
2. In another terminal, test MCP server directly:

```bash
# Send a tools/list request
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | sia mcp
```

Should output JSON with available tools.

### Full Test with Claude Code

1. Start control plane: `sia start`
2. Configure Claude Code (see above)
3. Open Claude Code: `claude`
4. Ask Claude to use a sia tool: "Use sia_echo to say hello"
5. Watch the UI update in real-time

---

## Current Limitations

- No persistence (agents lost on restart)
- No WebSocket (UI polls every 1 second)
- No lock service yet (coordination not enforced)
- Single control plane instance only
