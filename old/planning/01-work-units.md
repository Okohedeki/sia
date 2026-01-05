# Feature 1: Work Units

## What Are Work Units?

Work Units are **shared resources** that all Claude agents and subagents can see and coordinate around. When an agent wants to work on a file, directory, or process, they must claim the work unit. If another agent already has it, they join a queue and wait.

A Work Unit can be:
- **A file path** (`/src/main.py`)
- **A directory** (`/src/components/`)
- **A process resource** (`proc:test`, `proc:build`)

---

## End-User Experience

### Installation

The user installs Sia once on their system:

```bash
# Clone or download Sia
git clone https://github.com/yourorg/sia.git
cd sia

# Install dependencies
pip install -r backend/requirements.txt

# Install Sia CLI (adds 'sia' command to PATH)
pip install -e .
```

### Setting Up a Project

When a user wants to use Sia with a Claude Code project:

```bash
cd /path/to/my-project

# Initialize Sia for this project
sia init
```

**What `sia init` does:**
1. Creates `.claude/` directory if it doesn't exist
2. Copies hook scripts to `.claude/hooks/`
3. Creates/updates `.claude/settings.json` with hook configuration
4. Optionally starts the Sia daemon

### Starting/Stopping the Daemon

```bash
# Start the coordination daemon (runs in background)
sia start

# Check status
sia status

# Stop the daemon
sia stop
```

### Full Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER WORKFLOW                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. INSTALL (once)           2. INIT PROJECT        3. START DAEMON     │
│  ┌──────────────────┐       ┌──────────────────┐   ┌──────────────────┐ │
│  │ pip install sia  │  ──▶  │ cd my-project    │ ──▶│ sia start        │ │
│  └──────────────────┘       │ sia init         │   └──────────────────┘ │
│                             └──────────────────┘                         │
│                                     │                                    │
│                                     ▼                                    │
│                        ┌──────────────────────────┐                     │
│                        │ .claude/                  │                     │
│                        │ ├── settings.json        │                     │
│                        │ └── hooks/               │                     │
│                        │     ├── pre_tool_guard.py│                     │
│                        │     └── post_tool_telemetry.py                 │
│                        └──────────────────────────┘                     │
│                                                                          │
│  4. USE CLAUDE CODE                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ claude "Refactor the auth module and update tests"               │   │
│  │                                                                   │   │
│  │ Claude spawns subagents ──▶ All coordinate via Sia daemon        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  5. MONITOR (optional)                                                   │
│  ┌──────────────────┐                                                   │
│  │ sia ui           │  ◀── Opens web UI showing agents, queues, etc.   │
│  └──────────────────┘                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## How It All Flows Together

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLAUDE CODE                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │   Main Agent    │  │   Subagent 1    │  │   Subagent 2    │         │
│  │  (session-abc)  │  │ (session-abc:   │  │ (session-abc:   │         │
│  │                 │  │  toolu_123)     │  │  toolu_456)     │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
│           │                    │                    │                   │
│           ▼                    ▼                    ▼                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      CLAUDE CODE HOOKS                            │  │
│  │  ┌────────────────────────┐  ┌────────────────────────────────┐  │  │
│  │  │   PreToolUse Hook      │  │   PostToolUse Hook             │  │  │
│  │  │   pre_tool_guard.py    │  │   post_tool_telemetry.py       │  │  │
│  │  └───────────┬────────────┘  └───────────────┬────────────────┘  │  │
│  └──────────────┼───────────────────────────────┼───────────────────┘  │
└─────────────────┼───────────────────────────────┼───────────────────────┘
                  │ HTTP                          │ HTTP
                  ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SIA DAEMON (localhost:7432)                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Work Unit Registry                             │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │ /src/auth.py          owner: session-abc    queue: []       │ │  │
│  │  │ /src/utils.py         owner: session-abc:toolu_123  queue: []│ │  │
│  │  │ /src/tests/auth.py    owner: null           queue: [abc:456]│ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│                                    │ WebSocket/SSE (future)             │
│                                    ▼                                    │
│                           ┌──────────────┐                              │
│                           │   Web UI     │                              │
│                           └──────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Request Flow: Agent Wants to Edit a File

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Claude decides to edit /src/auth.py                             │
│         Tool call: Edit { file_path: "/src/auth.py", ... }              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: PreToolUse hook fires                                           │
│         pre_tool_guard.py receives JSON via stdin:                      │
│         {                                                                │
│           "session_id": "abc123",                                        │
│           "tool_name": "Edit",                                           │
│           "tool_input": { "file_path": "/src/auth.py", ... },           │
│           "tool_use_id": "toolu_789"                                    │
│         }                                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Hook calls Sia daemon                                           │
│         POST http://localhost:7432/work-units/claim                     │
│         { "agent_id": "abc123", "path": "/src/auth.py", "type": "file" }│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────┐  ┌─────────────────────────────────────────┐
│ CASE A: Path Available      │  │ CASE B: Path Claimed by Another Agent   │
│                             │  │                                          │
│ Response: { success: true } │  │ Response: {                              │
│                             │  │   success: false,                        │
│ Hook exits with code 0      │  │   queue_position: 1,                     │
│ (allow tool to proceed)     │  │   owner_agent_id: "abc123:toolu_123"    │
│                             │  │ }                                        │
│                             │  │                                          │
│                             │  │ Hook outputs JSON to stdout:             │
│                             │  │ { "decision": "block",                   │
│                             │  │   "reason": "Waiting for /src/auth.py.  │
│                             │  │              Queue position: 1" }        │
│                             │  │                                          │
│                             │  │ Claude sees this and waits or works     │
│                             │  │ on something else                        │
└─────────────────────────────┘  └─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Tool executes (if allowed)                                      │
│         Claude's Edit tool modifies /src/auth.py                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 5: PostToolUse hook fires                                          │
│         post_tool_telemetry.py receives result JSON                     │
│         Calls: POST http://localhost:7432/work-units/release            │
│         (Next agent in queue automatically gets ownership)              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Files Created During `sia init`

When a user runs `sia init` in their project, these files are created:

### `.claude/settings.json`

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

### `.claude/hooks/pre_tool_guard.py`

- Reads hook input JSON from stdin
- Extracts agent ID (from session_id) and target path
- Calls `POST /work-units/claim` on Sia daemon
- If claimed: allows tool (exit 0)
- If queued: blocks tool with message (outputs JSON to stdout)

### `.claude/hooks/post_tool_telemetry.py`

- Reads hook result JSON from stdin
- Calls `POST /work-units/release` on Sia daemon
- Emits telemetry events (for future UI)

---

## Agent Identification

Claude Code provides these fields in hook input:

| Field | Description | Example |
|-------|-------------|---------|
| `session_id` | Unique session identifier | `"abc123"` |
| `tool_use_id` | Unique ID for this tool call | `"toolu_01ABC..."` |
| `tool_name` | The tool being called | `"Edit"`, `"Write"`, `"Bash"` |
| `tool_input` | Tool parameters | `{ "file_path": "..." }` |

**Agent ID derivation:**
- **Main agent**: `agent_id = session_id`
- **Subagent**: `agent_id = session_id + ":" + task_tool_use_id`

We detect subagents by tracking when `Task` tool is called, then subsequent tool calls within that context use the combined ID.

---

## Data Structures

### WorkUnit

```python
@dataclass
class WorkUnit:
    id: str                    # Unique identifier (UUID)
    type: str                  # "file", "directory", "process"
    path: str                  # Resource path

    # Ownership
    owner_agent_id: str | None # Current owner (None if unclaimed)
    claimed_at: datetime | None

    # Queue of waiting agents (FIFO)
    queue: list[QueueEntry]

    # Lifecycle
    status: str                # "available", "claimed", "completed"
    ttl_seconds: int           # Auto-release after TTL (default: 300)
    expires_at: datetime | None
```

### QueueEntry

```python
@dataclass
class QueueEntry:
    agent_id: str
    requested_at: datetime
    position: int              # 1-indexed position in queue
```

### ClaimResult

```python
@dataclass
class ClaimResult:
    success: bool              # True if claimed, False if queued
    work_unit: WorkUnit
    queue_position: int | None # Position if queued
    owner_agent_id: str | None # Who owns it (if queued)
    message: str
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/work-units/claim` | POST | Claim a work unit (or join queue) |
| `/work-units/release` | POST | Release a work unit |
| `/work-units` | GET | Get ALL work units (global visibility) |
| `/work-units/state` | GET | Full state for UI |
| `/work-units/by-agent/{id}` | GET | Work units owned by agent |
| `/agents/register` | POST | Register an agent |
| `/agents/{id}/heartbeat` | POST | Keep agent alive |
| `/health` | GET | Daemon health check |

---

## Queue Behavior

1. **FIFO ordering** — first to request, first to receive
2. **Automatic promotion** — when owner releases, next in queue auto-claims
3. **Queue visibility** — agents can see their position and who's ahead
4. **Timeout handling** — if owner TTL expires, auto-release to next in queue
5. **Voluntary leave** — agents can remove themselves from queue

---

## Installation Artifacts

After full installation, the user's system has:

```
~/.sia/                          # Global Sia installation
├── daemon/                       # Daemon process files
│   └── sia.pid                   # PID file when running
└── config.json                   # Global settings

/path/to/user-project/           # User's project
├── .claude/
│   ├── settings.json            # Claude hooks configuration
│   └── hooks/
│       ├── pre_tool_guard.py    # PreToolUse hook
│       └── post_tool_telemetry.py # PostToolUse hook
└── ... (rest of project)
```

---

## Success Criteria

1. ✅ User can install Sia with `pip install`
2. ✅ User can initialize a project with `sia init`
3. ✅ Hooks are automatically configured in `.claude/settings.json`
4. ✅ Daemon starts/stops cleanly with `sia start/stop`
5. ✅ Multiple agents see the same global state
6. ✅ Claiming a busy work unit adds to queue
7. ✅ Releasing promotes next in queue automatically
8. ✅ TTL expiry auto-releases to queue
9. ⬜ Web UI shows real-time state (future)

---

## Implementation Status

- [x] Data models (`backend/models/`)
- [x] Work unit registry (`backend/registry/`)
- [x] API endpoints (`backend/routes/`)
- [x] FastAPI server (`backend/main.py`)
- [x] Pre-tool hook (`hooks/pre_tool_guard.py`)
- [x] Post-tool hook (`hooks/post_tool_telemetry.py`)
- [x] CLI tool (`cli/main.py` → `sia` command)
- [x] Installation script (`pyproject.toml`)
- [ ] Web UI (future)
