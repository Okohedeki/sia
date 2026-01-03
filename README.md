# Sia - Work Unit Coordination for Claude Code

Sia is a **Docker-like runtime/control plane for AI agents**. It coordinates Claude Code multi-agent workflows by ensuring deterministic access to files and processes.

## The Problem

When Claude Code spawns multiple agents (via `/agent` or subagents), they can conflict:
- Two agents editing the same file simultaneously
- Race conditions in test/build commands
- No visibility into what agents are doing

## The Solution

Sia provides a coordination layer:
- **Work Units**: Files and processes are declared resources
- **Exclusive Claims**: Only one agent modifies a resource at a time
- **FIFO Queues**: Others wait in line, automatically promoted when released
- **Global Visibility**: All agents see what everyone is working on

## Quick Start

### Installation

**Option 1: Pip Install (Recommended)**
```bash
pip install sia-claude
```

**Option 2: Development Install**
```bash
git clone https://github.com/yourorg/sia.git
cd sia
pip install -e .
```

### Setup a Project

```bash
cd /path/to/your-project

# Initialize Sia (creates .claude/hooks and settings)
sia init

# Start the coordination daemon
sia start

# Open the dashboard in your browser
# http://localhost:7432

# Use Claude Code as normal - coordination is automatic!
claude "Refactor the auth module and update tests"
```

### Commands

| Command | Description |
|---------|-------------|
| `sia init` | Initialize Sia for current project |
| `sia start` | Start the coordination daemon |
| `sia stop` | Stop the daemon |
| `sia status` | Show agents and work units |
| `sia logs` | View daemon logs |

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                      CLAUDE CODE                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │  Agent 1  │  │  Agent 2  │  │  Agent 3  │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │              │              │                      │
│        ▼              ▼              ▼                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Claude Code Hooks                        │  │
│  │  (PreToolUse: claim)    (PostToolUse: release)       │  │
│  └────────────────────────┬─────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────┘
                            │ HTTP
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   SIA DAEMON (localhost:7432)                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 Work Unit Registry                     │  │
│  │  /src/auth.py      owner: agent-1     queue: []       │  │
│  │  /src/utils.py     owner: agent-2     queue: [agent-3]│  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

1. Claude decides to edit a file
2. **PreToolUse hook** calls Sia to claim the work unit
3. If available → tool proceeds
4. If busy → agent is queued, waits for release
5. **PostToolUse hook** releases the work unit
6. Next agent in queue automatically gets ownership

## API

The daemon runs on `http://127.0.0.1:7432` and provides:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/work-units/claim` | POST | Claim a work unit or join queue |
| `/work-units/release` | POST | Release a work unit |
| `/work-units` | GET | List all work units |
| `/work-units/state` | GET | Full state (for UI) |
| `/agents` | GET | List all agents |
| `/health` | GET | Health check |

Interactive API docs: http://127.0.0.1:7432/docs

## Project Structure

```
sia/
├── backend/              # FastAPI daemon
│   ├── main.py          # Server entry point
│   ├── models/          # Data models
│   ├── registry/        # Work unit coordination logic
│   └── routes/          # API endpoints
├── cli/                  # CLI tool
│   └── main.py          # 'sia' command implementation
├── hooks/                # Claude Code hooks (copied to projects)
│   ├── pre_tool_guard.py
│   └── post_tool_telemetry.py
└── planning/            # Design documents
```

## Requirements

- Python 3.10+
- Claude Code CLI

## License

MIT
