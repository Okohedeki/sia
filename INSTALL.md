# Sia Installation Guide

Sia is a Python package that provides observability for Claude Code via hooks. It consists of:
- **Control Plane** - FastAPI daemon that receives hook reports
- **UI** - React frontend for real-time agent observability (bundled in package)
- **Hooks** - Automatic telemetry from Claude Code

---

## Quick Install

### 1. Install Sia Package

```bash
# From the Sia backend directory
cd path/to/sia/backend
pip install -e .

# Verify installation
sia --help
```

### 2. Initialize Hooks in Your Project

```bash
# Navigate to your project directory
cd /path/to/your/project

# Initialize Sia hooks
sia init
```

This will:
- Create `.claude/hooks/sia-hook.sh` (or `.ps1` on Windows)
- Update `.claude/settings.json` with PostToolUse hook configuration

### 3. Start the Control Plane

```bash
# In a dedicated terminal - leave this running
sia start
```

Opens http://localhost:8000 with the UI automatically.

### 4. Use Claude Code

```bash
# In your project directory
claude
```

All tool usage is automatically tracked via hooks and visible in the Sia UI.

---

## Architecture

```
Claude Code (your CLI)
       │
       │ Hooks (PostToolUse)
       ▼
Sia Hook Script
       │
       │ HTTP POST
       ▼
Sia Control Plane (sia start)
       │
       ▼
Web UI (http://localhost:8000)
```

---

## What Gets Tracked

All Claude Code tool usage is automatically captured:
- **Read/Write/Edit** - File operations
- **Bash** - Command execution
- **TodoWrite** - Automatically parsed into execution plans
- **All other tools** - Generic tool call logging

The UI shows:
- Agents (one per Claude Code session)
- Execution plans (from TodoWrite)
- Tool calls with inputs/outputs
- Work units (files being worked on)
- Step progress and logs

---

## Commands

```bash
# Start control plane daemon (serves UI on :8000)
sia start

# Start control plane without opening browser
sia start --no-browser

# Start control plane on different port
sia start --port 9000

# Initialize hooks in current project
sia init

# Initialize hooks globally (in home directory)
sia init --global
```

---

## Troubleshooting

### "sia: command not found"
```bash
# Reinstall the package
pip install -e path/to/sia/backend
```

### No agents appearing in UI
1. Ensure `sia start` is running
2. Verify hooks are configured: check `.claude/settings.json`
3. Restart Claude Code after running `sia init`
4. Check control plane terminal for errors

### Hooks not working
1. Verify `.claude/hooks/sia-hook.sh` (or `.ps1`) exists and is executable
2. Check `.claude/settings.json` has PostToolUse hook configured
3. Test hook manually: `echo '{"tool_name":"test"}' | bash .claude/hooks/sia-hook.sh`

### Control plane not starting
1. Check if port 8000 is already in use
2. Try different port: `sia start --port 9000`
3. Check Python dependencies: `pip install -e .`

---

## Development

### Rebuild Frontend

```bash
cd frontend
npm install
npm run build
```

Output goes to `backend/src/sia/static/`.

### Run Frontend Dev Server

```bash
cd frontend
npm run dev
```

Runs on http://localhost:5173 (for UI development only).

### Reinstall Package After Changes

```bash
cd backend
pip install -e .
```

---

## Package Structure

When installed, Sia provides:
- `sia` CLI command
- FastAPI control plane server
- Bundled React UI (in `sia/static/`)
- Hook scripts (created by `sia init`)

All frontend assets are packaged with the Python package, so no separate frontend build step is needed for end users.
