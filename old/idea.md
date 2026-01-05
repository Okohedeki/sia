# claude.md — Seamless Claude Code Integration (Hooks + Subagents)

This project is a **Docker-like runtime/control plane for AI agents**. For Claude Code, we integrate via **Hooks** to enforce deterministic coordination over files and processes, while keeping Claude’s `/agent` + subagent workflows intact.

---

## Goal

Make Claude Code multi-agent workflows:
- **Deterministic** (no hidden parallel collisions)
- **Observable** (see what’s running, blocked, queued)
- **Isolated** (agents act on declared work units)
- **Compatible** (works with `/agent`, custom agents, and subagents)

We do this by intercepting tool use and routing it through a local daemon.

---

## How Claude Code Fits In

Claude Code provides:
- `/agent` to select different agent profiles
- Subagents for parallel/focused work
- Tool calls (read/write/edit/bash) as the execution boundary
- Hook events we can intercept

**We do NOT replace Claude Code**. We become the **runtime governor**:
- Locks, queues, scheduling
- Event streaming for UI
- Replay artifacts (diffs + logs)

---

## Integration Architecture

### Components
1. **Claude Code hooks** (project-scoped)
2. **lockd** (local daemon on localhost)
   - lock manager + scheduler
   - event log
   - websocket/SSE stream for UI
3. **UI** (web app)
   - agents, locks, queues, plans, diffs, replay

### Runtime Model
- Files/dirs/processes are **Work Units**
- Edits/writes require **exclusive locks**
- Conflicts are **queued**, not merged ad-hoc
- Everything emits **events** for live visibility

---

## Hook Events We Use

### Required (v1)
- **PreToolUse**: enforce locks + queueing before tools run
- **PostToolUse**: capture diffs + emit telemetry after tools run

### Nice-to-have (v2)
- **UserPromptSubmit**: inject workflow rules (declare work units, plan format)
- **SubagentStop**: treat subagent completion as first-class events

---

## What We Intercept

### File tools
- `Read` → optional (telemetry), usually allowed
- `Edit` / `Write` → must acquire lock on target file
- (Optional) directory-level locks via policy (e.g., lock a folder as a unit)

### Process tools
- `Bash` → classify command into a process resource:
  - `proc:test`, `proc:build`, `proc:migrate`, `proc:deploy`
- Acquire lock before execution (prevents overlapping runs)

---

## Lock + Queue Semantics

### File Locks
- Write lock is **exclusive**
- When denied:
  - caller is placed in a **queue**
  - hook returns deny message with queue position + current holder
- Locks are **time-bound (TTL)** to prevent deadlocks

### Process Locks
- Named resources (e.g., `proc:test`)
- Single-flight execution for shared environments

---

## “Docker-like” Features Implemented via Hooks

1. **Work Units**: agents must declare targets (files/dirs/processes)
2. **Exclusive Locks**: one agent modifies a file at a time
3. **Deterministic Scheduling**: queued requests unblock in order
4. **Live Visibility**: every tool call becomes an event
5. **Plans as Execution Graphs**: plan IDs tie steps → locks → diffs
6. **Diff Artifacts**: every edit/write produces a stored diff
7. **Agent Isolation**: coordination via locks + artifacts, not shared state
8. **Process Coordination**: commands acquire process locks
9. **Lifecycle Control**: pause/terminate by denying further tool use
10. **Replayable Runs**: diffs + command outputs logged per step

---

## Minimal Project Setup (V1)

### 1) Project hooks config
Create `.claude/settings.json` in the repo:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Edit|Write|Bash",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre_tool_guard.py" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post_tool_telemetry.py" }
        ]
      }
    ]
  }
}
