"""
Agent models for Claude Code integration.

Claude Code hooks provide:
- session_id: Unique session identifier (in hook JSON)
- tool_use_id: Unique ID for each tool call
- transcript_path: Path to conversation JSONL for parsing agent hierarchy

We derive agent identity from these. Subagents are spawned via the Task tool,
so we track Task tool_use_ids to identify subagent contexts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AgentType(str, Enum):
    MAIN = "main"
    SUBAGENT = "subagent"


@dataclass
class AgentInfo:
    """
    Represents a Claude agent or subagent in the system.

    Identity is derived from Claude Code hook context:
    - Main agent: session_id is the agent_id
    - Subagent: session_id + task_tool_use_id forms the agent_id
    """

    agent_id: str  # session_id for main, session_id:task_id for subagent
    session_id: str  # Claude session_id from hook input
    agent_type: AgentType = AgentType.MAIN

    # For subagents, the tool_use_id of the Task call that spawned them
    task_tool_use_id: str | None = None

    # Parent agent (for subagents)
    parent_agent_id: str | None = None

    # Timestamps
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)

    # TTL for cleanup (seconds)
    ttl_seconds: int = 600  # 10 minutes default

    def is_subagent(self) -> bool:
        return self.agent_type == AgentType.SUBAGENT

    def update_last_seen(self) -> None:
        self.last_seen = datetime.utcnow()

    def is_expired(self) -> bool:
        elapsed = (datetime.utcnow() - self.last_seen).total_seconds()
        return elapsed > self.ttl_seconds

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "agent_type": self.agent_type.value,
            "task_tool_use_id": self.task_tool_use_id,
            "parent_agent_id": self.parent_agent_id,
            "registered_at": self.registered_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentInfo":
        return cls(
            agent_id=data["agent_id"],
            session_id=data["session_id"],
            agent_type=AgentType(data.get("agent_type", "main")),
            task_tool_use_id=data.get("task_tool_use_id"),
            parent_agent_id=data.get("parent_agent_id"),
            registered_at=datetime.fromisoformat(data["registered_at"])
            if "registered_at" in data
            else datetime.utcnow(),
            last_seen=datetime.fromisoformat(data["last_seen"])
            if "last_seen" in data
            else datetime.utcnow(),
            ttl_seconds=data.get("ttl_seconds", 600),
        )

    @classmethod
    def create_main_agent(cls, session_id: str) -> "AgentInfo":
        """Create a main agent from a Claude session."""
        return cls(
            agent_id=session_id,
            session_id=session_id,
            agent_type=AgentType.MAIN,
        )

    @classmethod
    def create_subagent(
        cls,
        session_id: str,
        task_tool_use_id: str,
        parent_agent_id: str,
    ) -> "AgentInfo":
        """Create a subagent from a Task tool invocation."""
        agent_id = f"{session_id}:{task_tool_use_id}"
        return cls(
            agent_id=agent_id,
            session_id=session_id,
            agent_type=AgentType.SUBAGENT,
            task_tool_use_id=task_tool_use_id,
            parent_agent_id=parent_agent_id,
        )


@dataclass
class HookContext:
    """
    Parsed context from a Claude Code hook invocation.

    This is what hooks receive via stdin JSON.
    """

    session_id: str
    hook_event_name: str  # PreToolUse, PostToolUse, Stop, SubagentStop
    tool_name: str
    tool_input: dict
    tool_use_id: str
    transcript_path: str
    cwd: str
    permission_mode: str  # default, plan, acceptEdits, bypassPermissions

    # Only present in PostToolUse
    tool_response: dict | None = None

    def is_task_tool(self) -> bool:
        """Check if this is a Task (subagent) invocation."""
        return self.tool_name == "Task"

    def is_file_tool(self) -> bool:
        """Check if this is a file modification tool."""
        return self.tool_name in ("Edit", "Write")

    def is_read_tool(self) -> bool:
        """Check if this is a read-only file tool."""
        return self.tool_name == "Read"

    def is_bash_tool(self) -> bool:
        """Check if this is a Bash command."""
        return self.tool_name == "Bash"

    def get_file_path(self) -> str | None:
        """Extract target file path from tool input."""
        if self.tool_name in ("Read", "Edit", "Write"):
            return self.tool_input.get("file_path")
        return None

    def get_bash_command(self) -> str | None:
        """Extract bash command from tool input."""
        if self.tool_name == "Bash":
            return self.tool_input.get("command")
        return None

    def to_dict(self) -> dict:
        result = {
            "session_id": self.session_id,
            "hook_event_name": self.hook_event_name,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_use_id": self.tool_use_id,
            "transcript_path": self.transcript_path,
            "cwd": self.cwd,
            "permission_mode": self.permission_mode,
        }
        if self.tool_response is not None:
            result["tool_response"] = self.tool_response
        return result

    @classmethod
    def from_hook_input(cls, data: dict) -> "HookContext":
        """Parse hook input JSON from stdin."""
        return cls(
            session_id=data["session_id"],
            hook_event_name=data["hook_event_name"],
            tool_name=data["tool_name"],
            tool_input=data.get("tool_input", {}),
            tool_use_id=data["tool_use_id"],
            transcript_path=data.get("transcript_path", ""),
            cwd=data.get("cwd", ""),
            permission_mode=data.get("permission_mode", "default"),
            tool_response=data.get("tool_response"),
        )
