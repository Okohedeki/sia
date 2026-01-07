"""Sia CLI - Command line interface for the control plane and Claude hooks."""

import argparse
import sys
import webbrowser
import json
import os
from pathlib import Path
from threading import Timer


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="sia",
        description="Sia - Runtime & Control Plane for Multi-Agent AI Execution",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # sia start
    start_parser = subparsers.add_parser("start", help="Start the control plane")
    start_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    start_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    start_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )

    # sia init
    init_parser = subparsers.add_parser("init", help="Initialize Sia for AI code editors")
    init_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port where Sia control plane runs (default: 8000)",
    )
    init_parser.add_argument(
        "--editor",
        choices=["claude", "cursor", "both"],
        default="both",
        help="Which editor to configure (default: both)",
    )

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.host, args.port, not args.no_browser)
    elif args.command == "init":
        init_hooks(args.port, args.editor)
    else:
        parser.print_help()
        sys.exit(1)


def start_server(host: str, port: int, open_browser: bool):
    """Start the control plane server."""
    import uvicorn

    print(f"\n  Sia Control Plane")
    print(f"  =================")
    print(f"  Server:  http://{host}:{port}")
    print(f"  API:     http://{host}:{port}/api/agents")
    print(f"\n  Waiting for agents to connect...\n")

    if open_browser:
        # Open browser after short delay to let server start
        Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    uvicorn.run(
        "sia.main:app",
        host=host,
        port=port,
        log_level="info",
    )


def init_hooks(port: int = 8000, editor: str = "both"):
    """Initialize Sia for AI code editors (Claude Code and/or Cursor)."""
    project_dir = Path.cwd()
    api_url = f"http://localhost:{port}"

    configured = []

    # Configure Claude Code
    if editor in ("claude", "both"):
        configured.append(init_claude_code(project_dir, api_url, port))

    # Configure Cursor
    if editor in ("cursor", "both"):
        configured.append(init_cursor(project_dir, api_url, port))

    # Print summary
    print(f"\n  Sia Initialized!")
    print(f"  ================")
    for config in configured:
        print(f"  {config}")
    print(f"")
    print(f"  Usage:")
    print(f"    1. Run 'sia start --port {port}' to launch control plane")
    if editor in ("claude", "both"):
        print(f"    2. Use Claude Code in this project - activity auto-tracked")
    if editor in ("cursor", "both"):
        print(f"    2. Use Cursor in this project - activity auto-tracked")
    print(f"")
    print(f"  Dashboard: http://localhost:{port}")
    print()


def init_claude_code(project_dir: Path, api_url: str, port: int) -> str:
    """Initialize Claude Code hooks."""
    hooks_dir = project_dir / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    tool_use_url = f"{api_url}/api/hooks/tool-use"

    # Bash script (works on Unix, and Windows via Git Bash)
    hook_script = hooks_dir / "sia-hook.sh"
    hook_content = f'''#!/bin/bash
# Sia Hook - Reports tool usage to control plane
input_data=$(cat)
if [ -n "$input_data" ]; then
    # JSON-escape the input using python
    escaped=$(echo "$input_data" | python -c "import sys,json; print(json.dumps(sys.stdin.read()))")
    curl -s -X POST "{tool_use_url}" \\
        -H "Content-Type: application/json" \\
        -d "{{\\"hook_type\\":\\"$CLAUDE_HOOK_TYPE\\",\\"session_id\\":\\"$CLAUDE_SESSION_ID\\",\\"working_directory\\":\\"$CLAUDE_WORKING_DIRECTORY\\",\\"tool_data\\":$escaped}}" \\
        --max-time 2 2>/dev/null || true
fi
'''

    with open(hook_script, "w", newline='\n') as f:
        f.write(hook_content)

    os.chmod(hook_script, 0o755)

    # On Windows, use Git Bash explicitly
    if sys.platform == "win32":
        hook_command = f'"C:\\Program Files\\Git\\bin\\bash.exe" "{hook_script}"'
    else:
        hook_command = f'bash "{hook_script}"'

    # Create Claude settings with hooks
    settings_path = project_dir / ".claude" / "settings.json"

    existing_settings = {}
    if settings_path.exists():
        try:
            with open(settings_path, "r") as f:
                existing_settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    if "hooks" not in existing_settings:
        existing_settings["hooks"] = {}

    existing_settings["hooks"]["PostToolUse"] = [
        {
            "matcher": "*",
            "hooks": [{"type": "command", "command": hook_command}]
        }
    ]

    with open(settings_path, "w") as f:
        json.dump(existing_settings, f, indent=2)

    return f"Claude Code: {settings_path}"


def init_cursor(project_dir: Path, api_url: str, port: int) -> str:
    """Initialize Cursor with .cursorrules for Sia integration."""
    cursor_dir = project_dir / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)

    # Create .cursorrules file with Sia reporting instructions
    cursorrules_path = project_dir / ".cursorrules"

    existing_rules = ""
    if cursorrules_path.exists():
        try:
            with open(cursorrules_path, "r") as f:
                existing_rules = f.read()
        except IOError:
            pass

    # Only add Sia rules if not already present
    sia_marker = "# SIA INTEGRATION"
    if sia_marker not in existing_rules:
        sia_rules = f'''
{sia_marker}
# The following rules enable Sia activity tracking.
# Sia Control Plane: {api_url}

When starting work on a task, first register with Sia by making a request:
- POST {api_url}/api/agents/register
- Body: {{"task": "<task description>", "name": "cursor-agent", "source": "cursor"}}
- Save the returned agent ID for subsequent calls

When you complete significant work, report it to Sia:
- POST {api_url}/api/agents/{{agent_id}}/tools
- Body: {{"tool_name": "<action>", "tool_input": {{}}, "tool_output": "<result>", "duration_ms": 0}}

When setting up a plan, report it:
- POST {api_url}/api/agents/{{agent_id}}/plan
- Body: {{"steps": ["step 1", "step 2", ...]}}

# END SIA INTEGRATION
'''
        with open(cursorrules_path, "w") as f:
            f.write(existing_rules + sia_rules)

    # Also create MCP config for Cursor (future-proofing)
    mcp_config_path = cursor_dir / "mcp.json"
    mcp_config = {
        "mcpServers": {
            "sia": {
                "url": f"{api_url}/mcp",
                "description": "Sia Control Plane - AI agent observability"
            }
        }
    }

    with open(mcp_config_path, "w") as f:
        json.dump(mcp_config, f, indent=2)

    return f"Cursor: {cursorrules_path}"


if __name__ == "__main__":
    main()
