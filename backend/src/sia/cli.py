"""Sia CLI - Command line interface for the control plane and MCP server."""

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

    # sia mcp
    mcp_parser = subparsers.add_parser("mcp", help="Start MCP server for Claude Code")
    mcp_parser.add_argument(
        "--control-plane",
        default="http://localhost:8000",
        help="Control plane URL (default: http://localhost:8000)",
    )

    # sia init
    init_parser = subparsers.add_parser("init", help="Initialize Sia hooks for Claude Code")
    init_parser.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Install hooks globally (default: current project only)",
    )

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.host, args.port, not args.no_browser)
    elif args.command == "mcp":
        start_mcp(args.control_plane)
    elif args.command == "init":
        init_hooks(args.global_install)
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
        log_level="warning",
    )


def start_mcp(control_plane: str):
    """Start the MCP server for Claude Code integration."""
    from .mcp import main as mcp_main
    mcp_main(control_plane=control_plane)


def init_hooks(global_install: bool):
    """Initialize Sia hooks for Claude Code."""
    # Find the sia executable path
    sia_executable = sys.executable.replace("python.exe", "Scripts\\sia.exe")
    if not os.path.exists(sia_executable):
        # Try finding it via which/where
        import shutil
        sia_executable = shutil.which("sia") or "sia"

    # The hook command - runs Python module
    python_exe = sys.executable
    hook_command = f'{python_exe} -m sia.hooks'

    # Hook configuration for Claude Code
    hook_config = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": ".*",  # Match all tools
                    "hooks": [hook_command]
                }
            ]
        }
    }

    if global_install:
        # Install to global Claude Code settings
        settings_paths = [
            Path.home() / ".claude" / "settings.json",
            Path.home() / ".config" / "claude-code" / "settings.json",
        ]
        settings_path = None
        for p in settings_paths:
            if p.parent.exists():
                settings_path = p
                break
        if not settings_path:
            settings_path = settings_paths[0]
            settings_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Install to current project
        settings_path = Path.cwd() / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing settings or create new
    existing_settings = {}
    if settings_path.exists():
        try:
            with open(settings_path, "r") as f:
                existing_settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Merge hook configuration
    if "hooks" not in existing_settings:
        existing_settings["hooks"] = {}

    # Add PostToolUse hook
    if "PostToolUse" not in existing_settings["hooks"]:
        existing_settings["hooks"]["PostToolUse"] = []

    # Check if sia hook already exists
    sia_hook_exists = False
    for hook in existing_settings["hooks"]["PostToolUse"]:
        if isinstance(hook, dict) and "sia.hooks" in str(hook.get("hooks", [])):
            sia_hook_exists = True
            break

    if not sia_hook_exists:
        existing_settings["hooks"]["PostToolUse"].append({
            "matcher": ".*",
            "hooks": [hook_command]
        })

    # Write settings
    with open(settings_path, "w") as f:
        json.dump(existing_settings, f, indent=2)

    print(f"\n  Sia Initialized!")
    print(f"  ================")
    print(f"  Hooks installed to: {settings_path}")
    print(f"")
    print(f"  Next steps:")
    print(f"    1. Run 'sia start' to start the control plane")
    print(f"    2. Open Claude Code in any project")
    print(f"    3. All tool usage will be automatically tracked!")
    print(f"")
    print(f"  View activity at: http://localhost:8000")
    print()


if __name__ == "__main__":
    main()
