# Sia Installation Guide

Sia is an MCP server that provides observability for Claude Code. It consists of:
- **MCP Server** - Connects to Claude Code, provides `sia_*` tools
- **Control Plane** - FastAPI daemon that receives tool call reports
- **UI** - React frontend for real-time agent observability

---

## Quick Install (Test in Any Repo)

### 1. Install Sia

```bash
# From the Sia directory
cd H:/Sia/backend
pip install -e .

# Verify
sia --help
```

### 2. Start the Control Plane (Daemon)

```bash
# In a dedicated terminal - leave this running
sia start
```

Opens http://localhost:8000 with the UI.

### 3. Configure Claude Code

Add to `~/.claude.json` (global) or `.claude/settings.json` (per-project):

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

### 4. Test in Your Repo

```bash
# Go to any repo (e.g., intro-to-C)
cd /path/to/intro-to-C

# Start Claude Code
claude
```

Ask Claude:
```
Use sia_echo to say "hello from intro-to-C"
```

Watch the Sia UI update in real-time.

---

## Architecture

```
Claude Code (your CLI)
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
UI (bundled React app)
```

---

## Available Tools

| Tool | Description |
|------|-------------|
| `sia_echo` | Echo a message (test connection) |
| `sia_read_file` | Read file (logged) |
| `sia_write_file` | Write file (logged) |
| `sia_run_command` | Run shell command (logged) |

All tool calls appear in the UI with:
- Input arguments
- Output/result
- Duration
- Timestamp

---

## Commands

```bash
# Start control plane daemon (serves UI on :8000)
sia start

# Start control plane without opening browser
sia start --no-browser

# Start control plane on different port
sia start --port 9000

# Start MCP server (Claude Code connects to this)
sia mcp

# Start MCP server pointing to different control plane
sia mcp --control-plane http://localhost:9000
```

---

## Troubleshooting

### "sia: command not found"
```bash
pip install -e H:/Sia/backend
```

### MCP not connecting
1. Ensure `sia start` is running
2. Restart Claude Code after config changes
3. Check `curl http://localhost:8000/health`

### No agents in UI
- Use `sia_*` tools explicitly (e.g., "use sia_echo")
- Check control plane terminal for errors

---

## Development

### Rebuild Frontend
```bash
cd H:/Sia/frontend
npm install
npm run build
```

Output goes to `backend/src/sia/static/`.

### Run Frontend Dev Server
```bash
cd H:/Sia/frontend
npm run dev
```

Runs on http://localhost:5173 (for UI development only).
