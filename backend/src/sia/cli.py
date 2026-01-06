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
    init_parser = subparsers.add_parser("init", help="Initialize Sia hooks for Claude Code")
    init_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port where Sia control plane runs (default: 8000)",
    )

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.host, args.port, not args.no_browser)
    elif args.command == "init":
        init_hooks(args.port)
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


def init_hooks(port: int = 8000):
    """Initialize Sia for Claude Code with hook-based tracking."""
    project_dir = Path.cwd()
    hooks_dir = project_dir / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    api_url = f"http://localhost:{port}/api/hooks/tool-use"

    # Bash script (works on Unix, and Windows via Git Bash)
    hook_script = hooks_dir / "sia-hook.sh"
    hook_content = f'''#!/bin/bash
# Sia Hook - Reports tool usage to control plane
input_data=$(cat)
if [ -n "$input_data" ]; then
    # JSON-escape the input using python
    escaped=$(echo "$input_data" | python -c "import sys,json; print(json.dumps(sys.stdin.read()))")
    curl -s -X POST "{api_url}" \\
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

    print(f"\n  Sia Initialized!")
    print(f"  ================")
    print(f"  Hook: {hook_script}")
    print(f"  Config: {settings_path}")
    print(f"")
    print(f"  Usage:")
    print(f"    1. Run 'sia start --port {port}' to launch control plane")
    print(f"    2. Use Claude Code in this project")
    print(f"")
    print(f"  Dashboard: http://localhost:{port}")
    print()


if __name__ == "__main__":
    main()
