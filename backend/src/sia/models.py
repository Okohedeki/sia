"""Sia data models."""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class AgentState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentSource(str, Enum):
    MCP = "mcp"           # Claude Code via MCP
    SDK = "sdk"           # Programmatic via SDK
    UNKNOWN = "unknown"


class ToolCall(BaseModel):
    """Represents a single tool execution."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    duration_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Agent(BaseModel):
    """Represents an agent instance."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    task: str
    name: Optional[str] = None
    model: Optional[str] = None
    source: AgentSource = AgentSource.UNKNOWN
    state: AgentState = AgentState.PENDING
    response: Optional[str] = None
    error: Optional[str] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# API Request/Response models

class RegisterAgentRequest(BaseModel):
    task: str
    name: Optional[str] = None
    model: Optional[str] = None
    source: Optional[str] = None  # "mcp", "sdk", etc.


class UpdateStateRequest(BaseModel):
    state: str
    response: Optional[str] = None
    error: Optional[str] = None


class ReportToolCallRequest(BaseModel):
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    duration_ms: int


class ToolCallResponse(BaseModel):
    id: str
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    duration_ms: int
    timestamp: datetime


class AgentResponse(BaseModel):
    id: str
    task: str
    name: Optional[str] = None
    model: Optional[str] = None
    source: AgentSource = AgentSource.UNKNOWN
    state: AgentState
    response: Optional[str] = None
    error: Optional[str] = None
    tool_calls: list[ToolCallResponse] = []
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
