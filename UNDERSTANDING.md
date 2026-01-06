# Sia - What We Built

## Summary

Sia is a Python package that provides observability for Claude Code via hooks. When you use Claude Code with Sia hooks configured, all tool usage is automatically logged and visible in a real-time web UI.

---

## Architecture

```
Claude Code (your normal CLI)
       │
       │ Hooks (PostToolUse)
       ▼
Sia Hook Script (reports to control plane)
       │
       │ HTTP
       ▼
Sia Control Plane (`sia start`)
       │
       ▼
Frontend UI (React - bundled in package)
```

---

## What Changed

1. **Hook-based telemetry** - Claude Code hooks automatically report all tool usage
2. **Python package** - Installable via `pip install -e .`
3. **Simple setup** - Run `sia init` to configure hooks, `sia start` to run the daemon
4. **Bundled UI** - React frontend is packaged with the Python package
5. **Automatic tracking** - No manual tool calls needed, all activity is tracked

---

## Files

### Backend (`backend/src/sia/`)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI control plane API |
| `registry.py` | In-memory agent store |
| `models.py` | Pydantic models |
| `cli.py` | CLI with `start` and `init` commands |
| `hooks.py` | Hook script helper (for reference) |
| `static/` | Bundled React frontend |
| `__init__.py` | Package exports |

### Frontend (`frontend/src/`)

| File | Purpose |
|------|---------|
| `App.tsx` | Observability UI |
| `App.css` | Dark theme styling |

---

## Installation

### 1. Install Sia

```bash
# From the Sia directory
cd path/to/sia/backend

# Install in editable mode
pip install -e .
```

### 2. Initialize Hooks in Your Project

```bash
# In your project directory
sia init
```

This creates:
- `.claude/hooks/sia-hook.sh` (or `.ps1` on Windows)
- `.claude/settings.json` with PostToolUse hook configured

### 3. Start Control Plane

```bash
# Terminal 1
sia start
```

Opens browser to http://localhost:8000 with the UI.

### 4. Use Claude Code

```bash
# Terminal 2 - in your project
claude
```

All tool usage is automatically tracked and visible in the Sia UI.

---

## How It Works

1. **Hook Installation**: `sia init` sets up Claude Code hooks that run after each tool use
2. **Automatic Reporting**: Hooks send tool data to the control plane API
3. **Agent Registration**: First tool use from a session auto-registers an agent
4. **Real-time UI**: Web interface shows agents, plans, tool calls, and work units
5. **Plan Tracking**: TodoWrite tool calls are automatically parsed into execution plans

---

## Current Features

- **Automatic agent tracking** - Each Claude Code session becomes an agent
- **Tool call logging** - All tool executions are recorded
- **Plan extraction** - TodoWrite calls create execution plans
- **Work unit tracking** - File operations are tracked as work units
- **Real-time UI** - Web interface with polling updates
- **Step tracking** - Plans broken down into steps with status

---

## Current Limitations

- No persistence (agents lost on restart)
- No WebSocket (UI polls every 1 second)
- No lock service yet (coordination not enforced)
- Single control plane instance only
