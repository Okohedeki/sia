"""Sia CLI - Command line interface for the control plane and MCP server."""

import argparse
import sys
import webbrowser
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

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.host, args.port, not args.no_browser)
    elif args.command == "mcp":
        start_mcp(args.control_plane)
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


if __name__ == "__main__":
    main()
