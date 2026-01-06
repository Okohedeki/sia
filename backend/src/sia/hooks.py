"""Sia Hook Script - Reports Claude Code tool usage to control plane.

This script is called by Claude Code hooks after each tool use.
It receives tool information via stdin as JSON and reports to Sia.
"""

import sys
import json
import httpx
import os

CONTROL_PLANE = os.environ.get("SIA_CONTROL_PLANE", "http://localhost:8000")


def report_tool_use(data: dict) -> None:
    """Report a tool use to the control plane."""
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{CONTROL_PLANE}/api/hooks/tool-use", json=data)
    except Exception:
        # Fail silently - don't interrupt Claude Code
        pass


def main():
    """Main entry point for the hook script."""
    # Read JSON from stdin
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return

        data = json.loads(input_data)

        # Extract relevant info from hook payload
        hook_payload = {
            "hook_type": os.environ.get("CLAUDE_HOOK_TYPE", "unknown"),
            "tool_name": data.get("tool_name", ""),
            "tool_input": data.get("tool_input", {}),
            "tool_output": data.get("tool_output", ""),
            "session_id": os.environ.get("CLAUDE_SESSION_ID", ""),
            "working_directory": os.environ.get("CLAUDE_WORKING_DIRECTORY", os.getcwd()),
        }

        report_tool_use(hook_payload)

    except json.JSONDecodeError:
        pass
    except Exception:
        pass


if __name__ == "__main__":
    main()
