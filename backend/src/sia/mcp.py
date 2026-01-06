"""Sia MCP Server - Provides tools to Claude Code via Model Context Protocol."""

import json
import sys
import os
import subprocess
import uuid
import time
import atexit
from datetime import datetime
from typing import Any
import httpx

# Global reference to control plane process for cleanup
_control_plane_process = None


def _start_control_plane(host: str = "127.0.0.1", port: int = 8000) -> subprocess.Popen | None:
    """Start the control plane server in the background."""
    global _control_plane_process

    # Check if already running
    try:
        response = httpx.get(f"http://{host}:{port}/health", timeout=2.0)
        if response.status_code == 200:
            return None  # Already running
    except Exception:
        pass  # Not running, start it

    # Start control plane as background process
    _control_plane_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sia.main:app", "--host", host, "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    # Wait for it to be ready
    for _ in range(30):  # 3 seconds max
        try:
            response = httpx.get(f"http://{host}:{port}/health", timeout=1.0)
            if response.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)

    return _control_plane_process


def _cleanup_control_plane():
    """Clean up control plane on exit."""
    global _control_plane_process
    if _control_plane_process:
        _control_plane_process.terminate()
        _control_plane_process = None


atexit.register(_cleanup_control_plane)


class SiaMCPServer:
    """
    MCP Server that provides Sia tools to Claude Code.

    Communicates with the Sia control plane to register agents,
    report tool executions, and enforce resource coordination.
    """

    def __init__(self, control_plane: str = "http://localhost:8000"):
        self.control_plane = control_plane.rstrip("/")
        self.agent_id: str | None = None
        self.session_id = str(uuid.uuid4())[:8]
        self._http = httpx.Client(timeout=30.0)

    def _report(self, endpoint: str, data: dict) -> dict | None:
        """Report to control plane. Fails silently if unavailable."""
        try:
            response = self._http.post(
                f"{self.control_plane}{endpoint}",
                json=data,
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def _ensure_registered(self, context: str = "MCP Session") -> None:
        """Ensure this agent is registered with the control plane."""
        if self.agent_id:
            return

        result = self._report("/api/agents/register", {
            "task": context,
            "name": f"claude-code-{self.session_id}",
            "model": "claude-code",
            "source": "mcp",
        })
        if result:
            self.agent_id = result.get("id")
            self._report(f"/api/agents/{self.agent_id}/state", {"state": "running"})

    def _report_tool_call(
        self,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
        duration_ms: int,
    ) -> None:
        """Report a tool execution to control plane."""
        if not self.agent_id:
            return
        self._report(f"/api/agents/{self.agent_id}/tools", {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "duration_ms": duration_ms,
        })

    def get_tools(self) -> list[dict]:
        """Return MCP tool definitions."""
        return [
            {
                "name": "sia_echo",
                "description": "Echo a message back. Use this to test Sia connection.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message to echo back",
                        }
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "sia_read_file",
                "description": "Read a file through Sia (logged and observable).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to read",
                        }
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "sia_write_file",
                "description": "Write to a file through Sia (logged and observable).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write",
                        }
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "sia_run_command",
                "description": "Run a shell command through Sia (logged and observable).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The command to run",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory (optional)",
                        }
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "sia_set_plan",
                "description": "Set your execution plan with steps. Call this when you have a plan for the task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of step descriptions in order",
                        }
                    },
                    "required": ["steps"],
                },
            },
            {
                "name": "sia_update_step",
                "description": "Update your current step status and the files you're working on.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "step_index": {
                            "type": "integer",
                            "description": "Step number (1-based)",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "skipped"],
                            "description": "New status for the step",
                        },
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files being worked on in this step (optional)",
                        }
                    },
                    "required": ["step_index", "status"],
                },
            },
            {
                "name": "sia_log_step",
                "description": "Add a log entry to a step for tracking progress or notes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "step_index": {
                            "type": "integer",
                            "description": "Step number (1-based)",
                        },
                        "message": {
                            "type": "string",
                            "description": "Log message",
                        },
                        "level": {
                            "type": "string",
                            "enum": ["info", "warning", "error", "debug"],
                            "description": "Log level (default: info)",
                        }
                    },
                    "required": ["step_index", "message"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a Sia tool and return the result."""
        self._ensure_registered(f"Tool: {tool_name}")

        start = datetime.now()
        result = ""

        try:
            if tool_name == "sia_echo":
                result = f"Echo: {arguments.get('message', '')}"

            elif tool_name == "sia_read_file":
                path = arguments.get("path", "")
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        result = f.read()
                else:
                    result = f"Error: File not found: {path}"

            elif tool_name == "sia_write_file":
                path = arguments.get("path", "")
                content = arguments.get("content", "")
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                result = f"Successfully wrote {len(content)} bytes to {path}"

            elif tool_name == "sia_run_command":
                command = arguments.get("command", "")
                cwd = arguments.get("cwd")
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=cwd,
                )
                result = f"Exit code: {proc.returncode}\n"
                if proc.stdout:
                    result += f"Stdout:\n{proc.stdout}\n"
                if proc.stderr:
                    result += f"Stderr:\n{proc.stderr}"

            elif tool_name == "sia_set_plan":
                steps = arguments.get("steps", [])
                if not steps:
                    result = "Error: No steps provided"
                else:
                    plan_result = self._report(f"/api/agents/{self.agent_id}/plan", {
                        "steps": steps,
                    })
                    if plan_result:
                        result = f"Plan set with {len(steps)} steps:\n"
                        for i, step in enumerate(steps, 1):
                            result += f"  {i}. {step}\n"
                    else:
                        result = "Error: Failed to set plan"

            elif tool_name == "sia_update_step":
                step_index = arguments.get("step_index")
                status = arguments.get("status")
                files = arguments.get("files")
                if not step_index or not status:
                    result = "Error: step_index and status are required"
                else:
                    update_data = {"status": status}
                    if files:
                        update_data["files"] = files
                    step_result = self._report(
                        f"/api/agents/{self.agent_id}/steps/{step_index}/status",
                        update_data,
                    )
                    if step_result:
                        result = f"Step {step_index} updated to '{status}'"
                        if files:
                            result += f"\nFiles: {', '.join(files)}"
                    else:
                        result = f"Error: Failed to update step {step_index}"

            elif tool_name == "sia_log_step":
                step_index = arguments.get("step_index")
                message = arguments.get("message", "")
                level = arguments.get("level", "info")
                if not step_index or not message:
                    result = "Error: step_index and message are required"
                else:
                    log_result = self._report(
                        f"/api/agents/{self.agent_id}/steps/{step_index}/logs",
                        {"message": message, "level": level},
                    )
                    if log_result:
                        result = f"Log added to step {step_index}: [{level}] {message}"
                    else:
                        result = f"Error: Failed to add log to step {step_index}"

            else:
                result = f"Error: Unknown tool {tool_name}"

        except Exception as e:
            result = f"Error: {str(e)}"

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        self._report_tool_call(tool_name, arguments, result, duration_ms)

        return result

    def handle_message(self, message: dict) -> dict | None:
        """Handle an incoming MCP message."""
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": "sia",
                        "version": "0.1.0",
                    },
                },
            }

        elif method == "notifications/initialized":
            return None  # No response for notifications

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": self.get_tools(),
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = self.execute_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result,
                        }
                    ],
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    def run(self) -> None:
        """Run the MCP server using stdio transport."""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                message = json.loads(line)
                response = self.handle_message(message)

                if response:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()

            except json.JSONDecodeError:
                continue
            except KeyboardInterrupt:
                break
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": str(e),
                    },
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()


def main(control_plane: str = "http://localhost:8000") -> None:
    """Entry point for MCP server."""
    # Auto-start control plane if not running
    _start_control_plane()

    server = SiaMCPServer(control_plane=control_plane)
    server.run()


if __name__ == "__main__":
    main()
