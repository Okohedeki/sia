# Sia - Runtime & Control Plane for Multi-Agent AI Execution

Sia is a Python package that provides observability and coordination for Claude Code via hooks. Track agents, execution plans, tool calls, and work units in a real-time web UI.

## Quick Start

```bash
# 1. Install the package
pip install -e .

# 2. Initialize hooks in your project
sia init

# 3. Start the control plane
sia start

# 4. Use Claude Code normally - all activity is tracked!
claude
```

View the UI at http://localhost:8000

## What It Does

Sia automatically tracks:
- **Agents** - Each Claude Code session becomes an agent
- **Tool Calls** - All tool executions (Read, Write, Bash, etc.)
- **Execution Plans** - Automatically extracted from TodoWrite
- **Work Units** - Files being worked on
- **Step Progress** - Plan steps with status and logs

## Architecture

```
Claude Code → Hooks → Sia Control Plane → Web UI
```

1. **Hooks** - Claude Code hooks report all tool usage
2. **Control Plane** - FastAPI daemon receives telemetry
3. **Web UI** - React frontend bundled in package

## Installation

### Local Development

```bash
# Clone the repository
git clone <repo-url>
cd Sia/backend

# Install in editable mode
pip install -e .

# Verify installation
sia --help
```

### In Your Project

```bash
# Navigate to your project
cd /path/to/your/project

# Initialize Sia hooks
sia init

# This creates:
# - .claude/hooks/sia-hook.sh (or .ps1 on Windows)
# - .claude/settings.json with PostToolUse hook
```

## Usage

### Start Control Plane

```bash
# Start the daemon (opens browser automatically)
sia start

# Or without opening browser
sia start --no-browser

# Or on a different port
sia start --port 9000
```

### Use Claude Code

Just use Claude Code normally. All tool usage is automatically tracked via hooks and visible in the web UI.

## Features

- ✅ **Automatic Tracking** - Zero configuration after `sia init`
- ✅ **Real-time UI** - Web interface with live updates
- ✅ **Plan Extraction** - TodoWrite calls create execution plans
- ✅ **Work Unit Tracking** - File operations tracked automatically
- ✅ **Bundled UI** - No separate frontend installation needed

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

## Project Structure

```
Sia/
├── backend/
│   └── src/
│       └── sia/
│           ├── cli.py          # CLI commands (start, init)
│           ├── main.py         # FastAPI control plane
│           ├── registry.py     # Agent registry
│           ├── models.py      # Data models
│           ├── hooks.py        # Hook script helper
│           └── static/         # Bundled React UI
├── frontend/                    # React UI source
└── pyproject.toml              # Package configuration
```

## Troubleshooting

### "sia: command not found"
```bash
pip install -e path/to/sia/backend
```

### No agents appearing
1. Ensure `sia start` is running
2. Verify hooks: check `.claude/settings.json`
3. Restart Claude Code after `sia init`

### Hooks not working
1. Check `.claude/hooks/sia-hook.sh` exists and is executable
2. Verify `.claude/settings.json` has PostToolUse hook
3. Test manually: `echo '{"tool_name":"test"}' | bash .claude/hooks/sia-hook.sh`

## License

[Your License Here]

## Contributing

[Contributing Guidelines]

