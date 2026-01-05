# Work Units Implementation Guide

This guide explains what was built for the Work Units feature and how all the pieces work together.

---

## What We Built

```
Sia/
├── backend/                    # The coordination server
│   ├── main.py                 # FastAPI app, runs on port 7432
│   ├── models/
│   │   ├── agent.py            # AgentInfo, HookContext
│   │   ├── work_unit.py        # WorkUnit, QueueEntry
│   │   └── responses.py        # API response types
│   ├── registry/
│   │   └── work_unit_registry.py  # Core logic: claims, queues, releases
│   └── routes/
│       ├── agents.py           # /agents/* endpoints
│       └── work_units.py       # /work-units/* endpoints
├── hooks/                      # Claude Code integration
│   ├── pre_tool_guard.py       # Runs BEFORE tools, claims resources
│   └── post_tool_telemetry.py  # Runs AFTER tools, releases resources
├── cli/
│   └── main.py                 # The `sia` command
├── pyproject.toml              # Package definition
└── README.md
```

---

## Component Deep Dive

### 1. The Daemon (`backend/`)

The daemon is a FastAPI server that maintains the global state of all work units and agents.

**Start it:**
```bash
cd H:/Sia
python -m uvicorn backend.main:app --host 127.0.0.1 --port 7432
```

**Key file: `backend/registry/work_unit_registry.py`**

This is the brain of the system. It:
- Tracks all work units in a dictionary: `{path: WorkUnit}`
- Tracks all agents: `{agent_id: AgentInfo}`
- Handles claiming with automatic queueing
- Handles releasing with automatic promotion

```python
# Core methods:
registry.claim(agent_id, path)    # Claim or queue
registry.release(agent_id, path)  # Release, promote next in queue
registry.get_all_work_units()     # Global visibility
```

**Key file: `backend/models/work_unit.py`**

```python
@dataclass
class WorkUnit:
    path: str                      # "/src/auth.py"
    owner_agent_id: str | None     # Who owns it
    queue: list[QueueEntry]        # Who's waiting
    status: WorkUnitStatus         # available, claimed, completed
    expires_at: datetime | None    # TTL for auto-release
```

**Key file: `backend/models/agent.py`**

```python
@dataclass
class AgentInfo:
    agent_id: str          # "session-abc" or "session-abc:toolu_123"
    session_id: str        # Claude session ID
    agent_type: AgentType  # main or subagent

@dataclass
class HookContext:
    # Parsed from Claude Code hook stdin JSON
    session_id: str
    tool_name: str         # Edit, Write, Bash, etc.
    tool_input: dict       # Tool parameters
    tool_use_id: str       # Unique tool call ID
```

---

### 2. The Hooks (`hooks/`)

Hooks are Python scripts that Claude Code runs before/after tool execution.

**How Claude Code calls hooks:**

1. Claude decides to call a tool (e.g., `Edit`)
2. Claude Code checks `.claude/settings.json` for matching hooks
3. Hook script receives JSON via stdin
4. Hook can allow, block, or modify the tool call

**PreToolUse Hook (`hooks/pre_tool_guard.py`)**

```
┌─────────────────────────────────────────────────────────────┐
│                    pre_tool_guard.py                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Read JSON from stdin                                     │
│     {                                                        │
│       "session_id": "abc123",                                │
│       "tool_name": "Edit",                                   │
│       "tool_input": {"file_path": "/src/auth.py", ...}      │
│     }                                                        │
│                                                              │
│  2. Extract target path: "/src/auth.py"                      │
│                                                              │
│  3. POST to daemon: /work-units/claim                        │
│     {"agent_id": "abc123", "path": "/src/auth.py"}          │
│                                                              │
│  4a. If success=true:                                        │
│      → exit(0)  # Allow tool to proceed                     │
│                                                              │
│  4b. If success=false (queued):                              │
│      → print JSON to stdout:                                 │
│        {"decision": "block", "reason": "..."}               │
│      → exit(0)  # Claude sees the block message             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**PostToolUse Hook (`hooks/post_tool_telemetry.py`)**

```
┌─────────────────────────────────────────────────────────────┐
│                  post_tool_telemetry.py                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Read JSON from stdin (includes tool_response)            │
│                                                              │
│  2. Extract the path that was modified                       │
│                                                              │
│  3. POST to daemon: /work-units/release                      │
│     {"agent_id": "abc123", "path": "/src/auth.py"}          │
│                                                              │
│  4. Next agent in queue automatically gets ownership         │
│                                                              │
│  5. exit(0)  # Always allow (post-hook can't block)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 3. The CLI (`cli/main.py`)

The `sia` command provides user-friendly management.

**Commands:**

| Command | What it does |
|---------|--------------|
| `sia init` | Copies hooks to `.claude/hooks/`, updates `.claude/settings.json` |
| `sia start` | Starts the daemon in background, saves PID |
| `sia stop` | Kills the daemon process |
| `sia status` | Shows running state, agents, work units |
| `sia logs` | Shows daemon log output |

**What `sia init` creates in your project:**

```
your-project/
└── .claude/
    ├── settings.json           # Hook configuration
    └── hooks/
        ├── pre_tool_guard.py   # Copied from Sia
        └── post_tool_telemetry.py
```

**The settings.json it creates:**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/pre_tool_guard.py\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/post_tool_telemetry.py\""
          }
        ]
      }
    ]
  }
}
```

---

## How It All Works Together

### Scenario: Two agents want the same file

```
Timeline:
─────────────────────────────────────────────────────────────────────────

Agent 1                          Daemon                         Agent 2
───────                          ──────                         ───────

Edit /src/auth.py
    │
    ├──► PreToolUse fires
    │    POST /claim
    │         │
    │         ├──► /src/auth.py created
    │         │    owner: agent-1
    │         │    queue: []
    │         │
    │    ◄────┤ {success: true}
    │
    ▼
[Edit proceeds]                                               Edit /src/auth.py
                                                                   │
                                                                   ├──► PreToolUse fires
                                                                   │    POST /claim
                                                                   │         │
                                                                   │         ├──► Already owned!
                                                                   │         │    Add to queue
                                                                   │         │    queue: [agent-2]
                                                                   │         │
                                                                   │    ◄────┤ {success: false,
                                                                   │         │  queue_position: 1}
                                                                   │
                                                                   ▼
                                                              [BLOCKED]
                                                              "Waiting for /src/auth.py
                                                               Queue position: 1"
[Edit completes]
    │
    ├──► PostToolUse fires
    │    POST /release
    │         │
    │         ├──► agent-1 released
    │         │    Promote agent-2!
    │         │    owner: agent-2
    │         │    queue: []
    │         │
    │    ◄────┤ {success: true}
    │
    ▼                                                              │
[Done]                                                             ▼
                                                              [Now owns it!]
                                                              Agent 2 can retry
                                                              and will succeed
```

---

## API Reference

### Claim a Work Unit

```bash
POST /work-units/claim
Content-Type: application/json

{
  "agent_id": "session-001",
  "path": "/src/auth.py",
  "type": "file"
}
```

**Response (claimed):**
```json
{
  "success": true,
  "work_unit": {
    "id": "wu-abc123",
    "path": "/src/auth.py",
    "owner_agent_id": "session-001",
    "queue": []
  },
  "message": "Work unit claimed"
}
```

**Response (queued):**
```json
{
  "success": false,
  "work_unit": {
    "id": "wu-abc123",
    "path": "/src/auth.py",
    "owner_agent_id": "session-001",
    "queue": [{"agent_id": "session-002", "position": 1}]
  },
  "queue_position": 1,
  "owner_agent_id": "session-001",
  "message": "Work unit busy. Added to queue at position 1"
}
```

### Release a Work Unit

```bash
POST /work-units/release
Content-Type: application/json

{
  "agent_id": "session-001",
  "path": "/src/auth.py"
}
```

### Get All Work Units (Global Visibility)

```bash
GET /work-units
```

Returns array of all work units - every agent can see what everyone is working on.

### Get Full State (For UI)

```bash
GET /work-units/state
```

Returns both agents and work units for rendering a dashboard.

---

## Starting and Stopping the Backend

### Using the CLI (Recommended)

The `sia` command manages the daemon as a background process:

```bash
# Start the daemon (runs in background)
sia start

# Check if it's running
sia status

# View logs
sia logs
sia logs -n 100    # Last 100 lines

# Stop the daemon
sia stop
```

### Using Python Directly (Development)

For development, run the daemon in the foreground to see logs:

```bash
cd H:/Sia

# Foreground (see all logs, Ctrl+C to stop)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 7432

# With auto-reload (restarts on code changes)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 7432 --reload
```

### Background Process (Manual)

Run as a background process without the CLI:

**Windows (PowerShell):**
```powershell
# Start in background
Start-Process -NoNewWindow python -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "7432"

# Find and stop
Get-Process python | Where-Object {$_.CommandLine -like "*uvicorn*"} | Stop-Process
```

**Windows (Git Bash / MINGW):**
```bash
# Start in background
cd H:/Sia
python -m uvicorn backend.main:app --host 127.0.0.1 --port 7432 &

# Find the process
ps aux | grep uvicorn

# Stop by PID
kill <PID>
```

**Linux/macOS:**
```bash
# Start in background
cd /path/to/Sia
nohup python -m uvicorn backend.main:app --host 127.0.0.1 --port 7432 > sia.log 2>&1 &
echo $! > sia.pid

# Stop using saved PID
kill $(cat sia.pid)
```

### Verify It's Running

```bash
# Health check
curl http://127.0.0.1:7432/health

# Expected response:
# {"status":"healthy","agents_count":0,"work_units_count":0}
```

### Port Already in Use?

If port 7432 is busy:

```bash
# Find what's using it (Windows)
netstat -ano | findstr :7432

# Find what's using it (Linux/macOS)
lsof -i :7432

# Use a different port
python -m uvicorn backend.main:app --host 127.0.0.1 --port 7433

# Update hooks to use new port
export SIA_DAEMON_URL=http://127.0.0.1:7433
```

---

## Testing Manually

### 1. Start the daemon

```bash
sia start
# Or for development:
cd H:/Sia
python -m uvicorn backend.main:app --host 127.0.0.1 --port 7432
```

### 2. Test claiming

```bash
# Agent 1 claims a file
curl -X POST http://127.0.0.1:7432/work-units/claim \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-1", "path": "/src/auth.py", "type": "file"}'

# Agent 2 tries to claim same file (gets queued)
curl -X POST http://127.0.0.1:7432/work-units/claim \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-2", "path": "/src/auth.py", "type": "file"}'

# Check state
curl http://127.0.0.1:7432/work-units

# Agent 1 releases
curl -X POST http://127.0.0.1:7432/work-units/release \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-1", "path": "/src/auth.py"}'

# Check state again - agent-2 should now own it
curl http://127.0.0.1:7432/work-units
```

### 3. Test hooks directly

```bash
# Simulate PreToolUse hook input
echo '{"session_id": "test-session", "tool_name": "Edit", "tool_input": {"file_path": "/src/test.py"}, "tool_use_id": "toolu_123", "hook_event_name": "PreToolUse", "cwd": "/project", "permission_mode": "default"}' | python hooks/pre_tool_guard.py
```

---

## Key Design Decisions

### 1. Why HTTP instead of file locks?

- Works across processes and machines
- Provides global visibility (agents can see queue state)
- Enables future UI integration via SSE/WebSocket
- Graceful degradation (if daemon is down, hooks allow tools)

### 2. Why FIFO queues?

- Deterministic ordering (no race conditions)
- Fair - first to request, first to receive
- Simple mental model for users

### 3. Why TTL on claims?

- Prevents deadlocks if an agent crashes
- Auto-cleanup keeps the system healthy
- Background task checks every 30 seconds

### 4. Why release after each tool call?

- Fine-grained coordination
- Agents don't hold resources while "thinking"
- Allows interleaving of work

### 5. Why identify agents by session_id?

- It's what Claude Code provides in hooks
- Subagents get composite IDs: `session:task_tool_use_id`
- Simple, deterministic derivation

---

## What's Next

The Work Units feature is complete. Remaining work:

1. **Web UI** - Visual dashboard showing agents, work units, queues
2. **SSE/WebSocket** - Real-time updates instead of polling
3. **Persistence** - SQLite to survive daemon restarts
4. **Process locks** - Coordinate `npm test`, `build`, etc.
5. **Directory locks** - Lock entire folders as units
