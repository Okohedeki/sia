#!/usr/bin/env python3
"""
Sia PreToolUse Hook - Coordinates work unit claims before tool execution.

This hook is called by Claude Code BEFORE a tool executes.
It ensures only one agent can modify a file at a time.

Flow:
1. Receive tool call context from Claude Code (stdin JSON)
2. Extract agent ID and target path
3. Call Sia daemon to claim the work unit
4. If claimed: allow tool (exit 0, no output)
5. If queued: block tool (output JSON with decision: "block")

Environment:
- CLAUDE_PROJECT_DIR: Project root (set by Claude Code)
- SIA_DAEMON_URL: Override daemon URL (default: http://127.0.0.1:7432)
"""

import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# Configuration
SIA_DAEMON_URL = os.environ.get("SIA_DAEMON_URL", "http://127.0.0.1:7432")
CLAIM_ENDPOINT = f"{SIA_DAEMON_URL}/work-units/claim"

# Tools that modify files and need coordination
WRITE_TOOLS = {"Edit", "Write"}

# Tools that run commands (may need process locks)
PROCESS_TOOLS = {"Bash"}


def log(message: str) -> None:
    """Log to stderr (doesn't interfere with hook output)."""
    print(f"[sia] {message}", file=sys.stderr)


def read_hook_input() -> dict:
    """Read and parse hook input JSON from stdin."""
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log(f"Failed to parse hook input: {e}")
        sys.exit(1)


def get_agent_id(hook_input: dict) -> str:
    """
    Derive agent ID from hook context.

    Main agent: session_id
    Subagent: session_id:task_tool_use_id (tracked separately)

    For now, we use session_id. Subagent tracking will be enhanced
    by reading the transcript to find parent Task calls.
    """
    session_id = hook_input.get("session_id", "unknown")
    return session_id


def get_target_path(hook_input: dict) -> str | None:
    """Extract the target file path from tool input."""
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name in WRITE_TOOLS:
        return tool_input.get("file_path")

    return None


def classify_bash_command(command: str) -> str | None:
    """
    Classify a bash command into a process resource type.
    Returns a process lock path like "proc:test" or None if no lock needed.
    """
    command_lower = command.lower()

    # Test commands
    if any(kw in command_lower for kw in ["pytest", "npm test", "cargo test", "go test", "jest", "mocha"]):
        return "proc:test"

    # Build commands
    if any(kw in command_lower for kw in ["npm run build", "cargo build", "go build", "make", "webpack", "vite build"]):
        return "proc:build"

    # Migration commands
    if "migrate" in command_lower:
        return "proc:migrate"

    # Deploy commands
    if "deploy" in command_lower:
        return "proc:deploy"

    # Install commands (often conflict)
    if any(kw in command_lower for kw in ["npm install", "pip install", "cargo install"]):
        return "proc:install"

    # No lock needed for other commands
    return None


def get_process_resource(hook_input: dict) -> str | None:
    """Get process resource path for Bash commands."""
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        return classify_bash_command(command)

    return None


def claim_work_unit(agent_id: str, path: str, work_unit_type: str = "file") -> dict:
    """
    Call Sia daemon to claim a work unit.

    Returns the API response or an error dict.
    """
    payload = json.dumps({
        "agent_id": agent_id,
        "path": path,
        "type": work_unit_type,
    }).encode("utf-8")

    request = Request(
        CLAIM_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": body}
    except URLError as e:
        return {"error": "Connection failed", "detail": str(e.reason)}
    except Exception as e:
        return {"error": "Request failed", "detail": str(e)}


def allow() -> None:
    """Allow the tool to proceed (no output, exit 0)."""
    sys.exit(0)


def block(reason: str) -> None:
    """Block the tool with a reason message."""
    output = {
        "decision": "block",
        "reason": reason,
    }
    print(json.dumps(output))
    sys.exit(0)


def main():
    # Read hook input
    hook_input = read_hook_input()

    tool_name = hook_input.get("tool_name", "")

    # Determine what resource we need to claim
    target_path = get_target_path(hook_input)
    process_resource = get_process_resource(hook_input)

    # If no resource needs claiming, allow the tool
    if not target_path and not process_resource:
        allow()

    # Get agent identity
    agent_id = get_agent_id(hook_input)

    # Determine resource path and type
    if target_path:
        resource_path = target_path
        resource_type = "file"
    else:
        resource_path = process_resource
        resource_type = "process"

    # Try to claim the work unit
    result = claim_work_unit(agent_id, resource_path, resource_type)

    # Handle connection errors (daemon not running)
    if "error" in result:
        # If daemon isn't running, log warning but allow the tool
        # This prevents blocking work if Sia isn't started
        log(f"Warning: Could not reach Sia daemon: {result['error']}")
        log("Allowing tool to proceed without coordination.")
        allow()

    # Check claim result
    if result.get("success"):
        # Claimed successfully - allow the tool
        allow()
    else:
        # Queued - block the tool
        queue_position = result.get("queue_position", "?")
        owner = result.get("owner_agent_id", "another agent")

        reason = (
            f"Resource '{resource_path}' is currently owned by {owner}. "
            f"You are in queue at position {queue_position}. "
            f"Please wait or work on something else."
        )
        block(reason)


if __name__ == "__main__":
    main()
