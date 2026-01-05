#!/usr/bin/env python3
"""
Sia CLI - Command-line interface for managing Sia coordination daemon.

Commands:
  sia init      Initialize Sia for the current project
  sia start     Start the Sia daemon
  sia stop      Stop the Sia daemon
  sia status    Show daemon and work unit status
  sia ui        Open the web UI in browser
  sia logs      View daemon logs
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# Try importlib.resources (Python 3.9+)
try:
    if sys.version_info >= (3, 9):
        from importlib.resources import files as resource_files
        HAS_RESOURCES = True
    else:
        HAS_RESOURCES = False
except ImportError:
    HAS_RESOURCES = False

# Fallback for older Python
try:
    import pkg_resources
    HAS_PKG_RESOURCES = True
except ImportError:
    HAS_PKG_RESOURCES = False


def get_hooks_source_dir() -> Path:
    """
    Get hooks directory, works for both pip install and source directory.
    
    Tries multiple methods:
    1. importlib.resources (Python 3.9+, pip install)
    2. pkg_resources (older Python, pip install)
    3. Source directory fallback (development)
    """
    # Method 1: importlib.resources (Python 3.9+, pip install)
    if HAS_RESOURCES:
        try:
            hooks_package = resource_files('hooks')
            hooks_path = Path(str(hooks_package))
            # Verify it has the hook files
            if hooks_path.exists() and (hooks_path / "pre_tool_guard.py").exists():
                return hooks_path
        except (ModuleNotFoundError, TypeError, AttributeError):
            pass
    
    # Method 2: pkg_resources (older Python, pip install)
    if HAS_PKG_RESOURCES:
        try:
            hooks_path = Path(pkg_resources.resource_filename('hooks', ''))
            if hooks_path.exists() and (hooks_path / "pre_tool_guard.py").exists():
                return hooks_path
        except Exception:
            pass
    
    # Method 3: Fallback to source directory (development)
    cli_dir = Path(__file__).parent.absolute()
    hooks_dir = cli_dir.parent / "hooks"
    if hooks_dir.exists() and (hooks_dir / "pre_tool_guard.py").exists():
        return hooks_dir
    
    # If all else fails, raise an error
    raise FileNotFoundError(
        "Could not find hooks directory. "
        "Make sure sia-claude is properly installed: pip install sia-claude"
    )


# Paths - now works with both pip install and source directory
HOOKS_SOURCE_DIR = get_hooks_source_dir()

# For cmd_start, we don't need SIA_ROOT anymore since we use -m uvicorn
# which will find the backend module regardless of cwd

# User data directory
if sys.platform == "win32":
    SIA_DATA_DIR = Path(os.environ.get("APPDATA", "~")) / "Sia"
else:
    SIA_DATA_DIR = Path.home() / ".sia"

PID_FILE = SIA_DATA_DIR / "daemon.pid"
LOG_FILE = SIA_DATA_DIR / "daemon.log"

# Default daemon URL
DAEMON_URL = "http://127.0.0.1:7432"


def ensure_data_dir():
    """Ensure Sia data directory exists."""
    SIA_DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_project_claude_dir(project_dir: Path) -> Path:
    """Get the .claude directory for a project."""
    return project_dir / ".claude"


def get_project_hooks_dir(project_dir: Path) -> Path:
    """Get the .claude/hooks directory for a project."""
    return get_project_claude_dir(project_dir) / "hooks"


def is_daemon_running() -> bool:
    """Check if the daemon is running."""
    if not PID_FILE.exists():
        return False

    pid = int(PID_FILE.read_text().strip())

    # Check if process is running
    try:
        if sys.platform == "win32":
            # Windows: use tasklist
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
            )
            return str(pid) in result.stdout
        else:
            # Unix: send signal 0 to check
            os.kill(pid, 0)
            return True
    except (OSError, subprocess.SubprocessError):
        return False


def get_daemon_status() -> dict | None:
    """Get daemon status from health endpoint."""
    try:
        with urlopen(f"{DAEMON_URL}/health", timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


# =============================================================================
# Commands
# =============================================================================


def cmd_init(args):
    """Initialize Sia for the current project."""
    project_dir = Path.cwd()

    print(f"Initializing Sia for: {project_dir}")

    # Create .claude directory
    claude_dir = get_project_claude_dir(project_dir)
    hooks_dir = get_project_hooks_dir(project_dir)
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Copy hook files
    for hook_file in ["pre_tool_guard.py", "post_tool_telemetry.py"]:
        src = HOOKS_SOURCE_DIR / hook_file
        dst = hooks_dir / hook_file

        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied: {hook_file}")
        else:
            print(f"  Warning: Source hook not found: {src}")

    # Create or update settings.json
    settings_file = claude_dir / "settings.json"

    if settings_file.exists():
        # Load existing settings
        with open(settings_file) as f:
            settings = json.load(f)
    else:
        settings = {}

    # Ensure hooks are configured
    hooks_config = {
        "PreToolUse": [
            {
                "matcher": "Edit|Write|Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/pre_tool_guard.py"',
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write|Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/post_tool_telemetry.py"',
                    }
                ],
            }
        ],
    }

    # Merge with existing hooks (Sia hooks take precedence for matched tools)
    existing_hooks = settings.get("hooks", {})

    for event, config in hooks_config.items():
        if event not in existing_hooks:
            existing_hooks[event] = config
        else:
            # Check if Sia hook already exists
            sia_hook_exists = any(
                "sia" in str(h.get("hooks", [{}])[0].get("command", "")).lower()
                for h in existing_hooks[event]
            )
            if not sia_hook_exists:
                existing_hooks[event] = config + existing_hooks[event]

    settings["hooks"] = existing_hooks

    # Write settings
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"  Updated: settings.json")

    print("\nSia initialized successfully!")
    print("\nNext steps:")
    print("  1. Start the daemon: sia start")
    print("  2. Use Claude Code as normal - coordination is automatic")


def cmd_start(args):
    """Start the Sia daemon."""
    ensure_data_dir()

    if is_daemon_running():
        print("Sia daemon is already running.")
        status = get_daemon_status()
        if status:
            print(f"  Agents: {status.get('agents_count', 0)}")
            print(f"  Work units: {status.get('work_units_count', 0)}")
        return

    print("Starting Sia daemon...")

    # Build the command
    if sys.platform == "win32":
        # Windows: use pythonw for background process
        python_cmd = "python"
        cmd = [
            python_cmd, "-m", "uvicorn",
            "backend.main:app",
            "--host", "127.0.0.1",
            "--port", "7432",
        ]
        # Use subprocess.CREATE_NO_WINDOW on Windows
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

        with open(LOG_FILE, "w") as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
    else:
        # Unix: standard background process
        cmd = [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "127.0.0.1",
            "--port", "7432",
        ]

        with open(LOG_FILE, "w") as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    # Save PID
    PID_FILE.write_text(str(process.pid))

    print(f"Daemon started (PID: {process.pid})")
    print(f"Log file: {LOG_FILE}")
    print(f"URL: {DAEMON_URL}")


def cmd_stop(args):
    """Stop the Sia daemon."""
    if not PID_FILE.exists():
        print("Sia daemon is not running (no PID file).")
        return

    pid = int(PID_FILE.read_text().strip())

    try:
        if sys.platform == "win32":
            # Windows: use taskkill
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True)
        else:
            # Unix: send SIGTERM
            os.kill(pid, signal.SIGTERM)

        print(f"Sia daemon stopped (PID: {pid})")
    except Exception as e:
        print(f"Error stopping daemon: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def cmd_status(args):
    """Show daemon and work unit status."""
    print("Sia Status")
    print("=" * 40)

    # Check daemon
    if is_daemon_running():
        print("Daemon: RUNNING")
        status = get_daemon_status()
        if status:
            print(f"  Agents: {status.get('agents_count', 0)}")
            print(f"  Work units: {status.get('work_units_count', 0)}")

            # Get detailed state
            try:
                with urlopen(f"{DAEMON_URL}/work-units/state", timeout=2) as response:
                    state = json.loads(response.read().decode("utf-8"))

                    if state.get("work_units"):
                        print("\nWork Units:")
                        for wu in state["work_units"]:
                            owner = wu.get("owner_agent_id", "available")
                            queue_len = len(wu.get("queue", []))
                            print(f"  {wu['path']}")
                            print(f"    Owner: {owner}")
                            if queue_len > 0:
                                print(f"    Queue: {queue_len} waiting")

                    if state.get("agents"):
                        print("\nAgents:")
                        for agent in state["agents"]:
                            print(f"  {agent['agent_id']} ({agent['agent_type']})")

            except Exception:
                pass
    else:
        print("Daemon: STOPPED")
        print("\nRun 'sia start' to start the daemon.")


def cmd_logs(args):
    """Show daemon logs."""
    if not LOG_FILE.exists():
        print("No log file found.")
        return

    # Show last N lines
    lines = args.lines or 50

    with open(LOG_FILE) as f:
        all_lines = f.readlines()
        for line in all_lines[-lines:]:
            print(line, end="")


def cmd_ui(args):
    """Open the web UI in the default browser."""
    import webbrowser
    
    # Check if daemon is running
    if not is_daemon_running():
        print("Error: Sia daemon is not running.")
        print("Start it with: sia start")
        sys.exit(1)
    
    # Open browser to dashboard
    ui_url = f"{DAEMON_URL}"
    print(f"Opening Sia dashboard: {ui_url}")
    webbrowser.open(ui_url)


# =============================================================================
# Main
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Sia - Work Unit Coordination for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init
    parser_init = subparsers.add_parser("init", help="Initialize Sia for current project")
    parser_init.set_defaults(func=cmd_init)

    # start
    parser_start = subparsers.add_parser("start", help="Start the Sia daemon")
    parser_start.set_defaults(func=cmd_start)

    # stop
    parser_stop = subparsers.add_parser("stop", help="Stop the Sia daemon")
    parser_stop.set_defaults(func=cmd_stop)

    # status
    parser_status = subparsers.add_parser("status", help="Show daemon status")
    parser_status.set_defaults(func=cmd_status)

    # logs
    parser_logs = subparsers.add_parser("logs", help="Show daemon logs")
    parser_logs.add_argument("-n", "--lines", type=int, default=50, help="Number of lines")
    parser_logs.set_defaults(func=cmd_logs)

    # ui
    parser_ui = subparsers.add_parser("ui", help="Open the web UI")
    parser_ui.set_defaults(func=cmd_ui)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
