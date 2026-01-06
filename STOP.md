# Sia - Current State

**Date:** January 2026

---

## What We Have

Sia is now a **hooks-based Python package** for Claude Code observability.

**How it works:**
```
Claude Code → Hooks → Sia Control Plane → Web UI
```

---

## Current State

**Working:**
- `pip install -e .` in `backend/` installs the `sia` package
- `sia init` sets up Claude Code hooks in your project
- `sia start` runs the control plane daemon with bundled UI
- All Claude Code tool usage is automatically tracked via hooks
- UI available at http://localhost:8000
- Agents, plans, tool calls, and work units visible in real-time

**What gets tracked:**
- All tool calls (Read, Write, Bash, etc.)
- Execution plans (from TodoWrite)
- File operations (as work units)
- Step progress and logs

---

## How to Use

### Setup (one-time per project)

```bash
# 1. Install package
cd H:/Sia/backend
pip install -e .

# 2. Initialize hooks in your project
cd /path/to/your/project
sia init
```

### Run

```bash
# Terminal 1 - Start control plane
sia start

# Terminal 2 - Use Claude Code normally
cd /path/to/your/project
claude
```

All activity is automatically tracked. View at http://localhost:8000

---

## Architecture

### Components

1. **Python Package** (`sia-agent`)
   - CLI commands: `sia start`, `sia init`
   - FastAPI control plane server
   - Bundled React UI in `static/` directory

2. **Hooks** (created by `sia init`)
   - `.claude/hooks/sia-hook.sh` (or `.ps1`)
   - `.claude/settings.json` with PostToolUse configuration
   - Reports all tool usage to control plane

3. **Control Plane** (`sia start`)
   - FastAPI server on :8000
   - Receives hook reports
   - Serves bundled UI
   - In-memory agent registry

4. **Web UI**
   - React frontend bundled in package
   - Real-time polling (1 second intervals)
   - Shows agents, plans, tool calls, work units

---

## Next Steps

### Phase 1: Enhanced Telemetry
1. **Subagent tracking** - Detect and track child agents
2. **Better plan extraction** - More sophisticated plan parsing
3. **WebSocket updates** - Replace polling with real-time push

### Phase 2: Coordination Features
1. **Lock service** - Resource locking and queuing
2. **Agent blocking** - Prevent conflicts
3. **Resource delegation** - Parent-child coordination

### Phase 3: Distribution
1. **PyPI publication** - `pip install sia-agent`
2. **Documentation** - Complete README and guides
3. **Versioning** - Semantic versioning

---

## Key Design Decisions

1. **Hooks over MCP** - Simpler, no protocol complexity
2. **Bundled UI** - Single package, no separate frontend install
3. **Automatic tracking** - Zero configuration after `sia init`
4. **In-memory storage** - Fast, simple, can add persistence later

---

## Testing

### Quick Test

1. Install: `pip install -e .`
2. Initialize: `sia init` (in a test project)
3. Start: `sia start`
4. Use Claude Code: `claude`
5. Check UI: http://localhost:8000

You should see:
- Agent registered automatically
- Tool calls appearing in real-time
- Plans extracted from TodoWrite
- Work units for file operations
