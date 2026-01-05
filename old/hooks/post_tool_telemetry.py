#!/usr/bin/env python3
"""
Sia PostToolUse Hook - Releases work units and emits telemetry after tool execution.

This hook is called by Claude Code AFTER a tool executes.
It releases the work unit so the next agent in queue can proceed.

Flow:
1. Receive tool result context from Claude Code (stdin JSON)
2. Extract agent ID and target path
3. Call Sia daemon to release the work unit
4. (Future) Emit telemetry events for UI

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
RELEASE_ENDPOINT = f"{SIA_DAEMON_URL}/work-units/release"

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
        sys.exit(0)  # Don't block on parse errors in post-hook


def get_agent_id(hook_input: dict) -> str:
    """Derive agent ID from hook context."""
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
    """Classify a bash command into a process resource type."""
    command_lower = command.lower()

    if any(kw in command_lower for kw in ["pytest", "npm test", "cargo test", "go test", "jest", "mocha"]):
        return "proc:test"

    if any(kw in command_lower for kw in ["npm run build", "cargo build", "go build", "make", "webpack", "vite build"]):
        return "proc:build"

    if "migrate" in command_lower:
        return "proc:migrate"

    if "deploy" in command_lower:
        return "proc:deploy"

    if any(kw in command_lower for kw in ["npm install", "pip install", "cargo install"]):
        return "proc:install"

    return None


def get_process_resource(hook_input: dict) -> str | None:
    """Get process resource path for Bash commands."""
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        return classify_bash_command(command)

    return None


def release_work_unit(agent_id: str, path: str) -> dict:
    """
    Call Sia daemon to release a work unit.

    Returns the API response or an error dict.
    """
    payload = json.dumps({
        "agent_id": agent_id,
        "path": path,
    }).encode("utf-8")

    request = Request(
        RELEASE_ENDPOINT,
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


def main():
    # Read hook input
    hook_input = read_hook_input()

    tool_name = hook_input.get("tool_name", "")

    # Determine what resource to release
    target_path = get_target_path(hook_input)
    process_resource = get_process_resource(hook_input)

    # If no resource was claimed, nothing to release
    if not target_path and not process_resource:
        sys.exit(0)

    # Get agent identity
    agent_id = get_agent_id(hook_input)

    # Determine resource path
    resource_path = target_path or process_resource

    # Release the work unit
    result = release_work_unit(agent_id, resource_path)

    # Handle result (just log, don't block)
    if "error" in result:
        log(f"Warning: Could not release work unit: {result['error']}")
    elif result.get("success"):
        log(f"Released: {resource_path}")
    else:
        # This can happen if the agent didn't own it (race condition or error)
        log(f"Note: Could not release {resource_path} (may not have been owned)")

    # PostToolUse hooks should not output anything to stdout
    # and should exit 0 to not interfere with Claude's flow
    sys.exit(0)


if __name__ == "__main__":
    main()
