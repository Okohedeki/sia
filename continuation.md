# Sia Continuation Plan

**Date:** January 4, 2026

---

## Where We Left Off

Sia has a working prototype:
- **Backend:** FastAPI control plane + `SiaAgent` class wrapping Claude SDK
- **Frontend:** React/TypeScript observability UI showing agents and tool calls
- **CLI:** `sia start` launches the control plane
- **Package:** `pip install -e .` installs locally

Current usage requires running `SiaAgent.run()` programmatically:
```python
from sia import SiaAgent
agent = SiaAgent(control_plane="http://localhost:8000")
result = agent.run("Do something")
```

---

## The Problem

The current approach creates a **separate agent runtime**. You're not using Claude Code - you're using a custom agent that happens to use the Claude SDK.

**What you actually want:** Use Claude Code normally, but have Sia provide coordination, observability, and the control plane UI. The agents should BE Claude Code instances, not wrappers.

---

## The Solution: MCP Server Integration

Claude Code natively supports **MCP (Model Context Protocol) servers**. An MCP server can provide tools that Claude Code uses directly.

### How This Works

```
┌─────────────────────────────────────────────────────────┐
│                     Claude Code                          │
│  (Your normal Claude Code CLI - unchanged)              │
│                                                          │
│  Tools available:                                        │
│    - Built-in tools (Read, Write, Bash, etc.)           │
│    - MCP tools from connected servers                   │
└──────────────────────┬──────────────────────────────────┘
                       │ connects via MCP
                       ▼
┌─────────────────────────────────────────────────────────┐
│               Sia MCP Server                             │
│  (Runs alongside control plane)                          │
│                                                          │
│  Provides tools:                                         │
│    - sia_claim      → Lock Service                      │
│    - sia_release    → Lock Service                      │
│    - sia_read       → Logged file read                  │
│    - sia_write      → Logged file write                 │
│    - sia_run        → Logged command execution          │
│    - sia_spawn      → Create child agent                │
│                                                          │
│  Auto-reports:                                           │
│    - Agent registration on first tool call              │
│    - Tool execution telemetry                           │
│    - Resource claims and releases                       │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────┐
│               Sia Control Plane                          │
│  (FastAPI backend - what we already have)               │
│                                                          │
│  - Agent registry                                        │
│  - Lock service                                          │
│  - WebSocket broadcasts                                  │
│  - API for frontend                                      │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│               Control Plane UI                           │
│  (React frontend - what we already have)                │
└─────────────────────────────────────────────────────────┘
```

### Why MCP?

1. **Native integration** - Claude Code already supports MCP servers
2. **No wrapper needed** - You run Claude Code directly, not `SiaAgent.run()`
3. **Tool-level control** - Sia tools can enforce locks before file operations
4. **Transparent** - User just adds Sia to their MCP config and uses Claude Code normally
5. **Multi-instance** - Multiple Claude Code instances connect to same control plane

---

## Distribution Strategy

### Option A: PyPI Package (Recommended)

```bash
pip install sia-agent
sia start              # Starts control plane + MCP server
```

User adds to `~/.claude/claude_code_config.json`:
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

### Option B: npm Package (Alternative)

```bash
npm install -g sia-agent
sia start
```

Same MCP config approach.

### Option C: Docker

```bash
docker run -p 8000:8000 sia-agent
```

MCP config points to Docker container.

---

## Revised Architecture

### What Changes

| Component | Current | New |
|-----------|---------|-----|
| Agent runtime | `SiaAgent` wrapping Claude SDK | Claude Code directly |
| Tool provision | Tools baked into `SiaAgent` | MCP server provides tools |
| Agent registration | On `agent.run()` call | On first MCP tool call |
| Package | Local editable install | PyPI/npm distributable |

### What Stays the Same

- Control plane API (FastAPI)
- Frontend UI (React)
- Lock service design
- Tool semantics (claim, read, write, run, spawn)

---

## Implementation Steps

### Phase 1: MCP Server

1. Create `sia/mcp.py` implementing MCP protocol
2. Implement tool handlers that proxy to control plane
3. Add `sia mcp` CLI command to run MCP server standalone
4. Auto-generate unique agent ID per Claude Code session

### Phase 2: Agent Lifecycle via MCP

1. Register agent on first tool call (lazy registration)
2. Heartbeat mechanism to detect dead agents
3. Clean up agent state when MCP connection closes
4. Handle multiple Claude Code instances connecting

### Phase 3: Coordinated Tools

1. `sia_claim` - Request lock on work unit, block if unavailable
2. `sia_release` - Release lock on work unit
3. `sia_read` - Read file (no lock required, but logged)
4. `sia_write` - Write file (requires lock)
5. `sia_run` - Execute command (optional lock on process resource)

### Phase 4: Packaging

1. Clean up `pyproject.toml` for PyPI publication
2. Add proper versioning
3. Create README with installation/usage instructions
4. Publish to PyPI as `sia-agent`

### Phase 5: Enhanced Coordination

1. `sia_spawn` - Spawn child Claude Code process with own MCP connection
2. Parent-child relationship tracking
3. Resource delegation between agents

---

## Usage After Implementation

### Terminal 1 - Start Sia
```bash
pip install sia-agent
sia start  # Starts control plane on :8000, MCP server ready
```

### Terminal 2 - Configure Claude Code
Add to `~/.claude/claude_code_config.json`:
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

### Terminal 3+ - Run Claude Code Normally
```bash
cd my-project
claude
# Now Claude Code has sia_* tools available
# All activity visible in Sia control plane UI
```

### In Claude Code
Claude can now use:
- `sia_claim path/to/file` - Lock before editing
- `sia_write path/to/file content` - Write with observability
- `sia_run "npm test"` - Run with logging
- `sia_release path/to/file` - Release lock

---

## Alternative: Hooks Approach

Claude Code also supports hooks that run before/after tool execution. This could provide observability without requiring sia_* tools.

**Pros:**
- No new tools to learn - agents use normal Read/Write/Bash
- Purely observational - doesn't change agent behavior

**Cons:**
- Can't enforce locks (only observe, not block)
- Less control over coordination
- Hooks are informational, not blocking

**Verdict:** Hooks are good for pure observability. MCP is required for coordination/locking.

**Hybrid approach:** Use hooks for telemetry on built-in tools, MCP for coordination tools.

---

## Questions to Resolve

1. **Lock enforcement:** Should agents be blocked from using built-in Write/Bash if they haven't claimed the resource via Sia? (Requires hooks + MCP together)

2. **Backwards compatibility:** Should `SiaAgent.run()` still work for programmatic use cases?

3. **Process identification:** How to uniquely identify a Claude Code instance across restarts?

4. **Scope:** Should Sia tools replace built-in tools entirely, or coexist?

---

## Next Session Priorities

1. Implement MCP server skeleton
2. Connect MCP server to existing control plane
3. Test with Claude Code locally
4. Iterate on tool design based on actual usage

---

## Key Insight

The original vision in UNDERSTANDING.md is correct - Sia should be "Docker for AI agents." But Docker doesn't require you to run containers through a special wrapper. You just run `docker run` and the container connects to the Docker daemon.

Similarly, Sia shouldn't require `SiaAgent.run()`. You should just run Claude Code normally, and it connects to the Sia control plane via MCP.

**The MCP server IS the bridge.**